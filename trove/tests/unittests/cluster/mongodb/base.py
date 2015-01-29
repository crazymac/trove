#  Copyright 2015 Mirantis Inc.
#  All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock
import uuid
from testtools import TestCase

from trove.common import context
from trove.common import cfg
from trove.common import remote
from trove.common import instance
from trove.common.strategies.mongodb import api
from trove.common.strategies.mongodb import (
    taskmanager as taskmanager_strategy)
from trove.cluster import service
from trove.datastore import models as datastore_models
from trove.instance import models as instance_models
from trove.instance import tasks
from trove.taskmanager import api as task_api
from trove.tests.fakes import nova
from trove.tests.unittests.util import util


CONF = cfg.CONF


class MongodbClusteringBase(TestCase):

    @classmethod
    def patch_for_instance_create(
            cls, context, name, flavor_id,
            image_id, databases, users,
            datastore, datastore_version,
            volume_size, backup_id,
            availability_zone=None,
            nics=None, configuration_id=None,
            slave_of_id=None, cluster_config=None):
        db_info = instance_models.DBInstance.create(
            name=name, flavor_id=flavor_id,
            tenant_id=context.tenant,
            volume_size=volume_size,
            datastore_version_id=
            datastore_version.id,
            task_status=tasks.InstanceTasks.BUILDING,
            configuration_id=configuration_id,
            slave_of_id=slave_of_id,
            cluster_id=cluster_config.get('id'),
            type=cluster_config.get('instance_type'),
            shard_id=str(cluster_config.get('shard_id'))
        )

        instance_models.InstanceServiceStatus.create(
            instance_id=db_info.id,
            status=instance.ServiceStatuses.NEW)
        return db_info

    class fake_request(object):
        def __init__(self, context):
            self.environ = {"trove.context": context}
            self.host = "localhost"
            self.url_version = "v1.0"

    def setUp(self):
        util.init_db()

        self.orig_quotas = api.check_quotas
        api.check_quotas = mock.MagicMock()

        self.datastore = (
            datastore_models.DBDatastore.create(
                id=str(uuid.uuid4()),
                name="mongodb",
                default_version_id=str(uuid.uuid4())
            ))
        self.version = (
            datastore_models.DBDatastoreVersion.create(
                id=self.datastore.default_version_id,
                datastore_id=self.datastore.id,
                name="2.10",
                manager="mongodb",
                image_id=str(uuid.uuid4()),
                packages="",
                active=1,
            )
        )
        self.valid_instance = [
            {
                "flavor_id": 3,
                "volume_size": 2,
            },
            {
                "flavor_id": 3,
                "volume_size": 2,
            },
            {
                "flavor_id": 3,
                "volume_size": 2,
            },
        ]
        self.invalid_volume_instances = [
            {
                "flavor_id": 3,
                "volume_size": 1
            },
            {
                "flavor_id": 3,
                "volume_size": 2
            },
            {
                "flavor_id": 3,
                "volume_size": 3
            }
        ]
        self.invalid_different_flavors_instances = [
            {
                "flavor_id": 3,
                "volume_size": 1
            },
            {
                "flavor_id": 4,
                "volume_size": 1
            },
            {
                "flavor_id": 5,
                "volume_size": 1
            }
        ]

        self.context = context.TroveContext(
            tenant=str(uuid.uuid4()))
        self.cluster_name = "test_cluster"

        self.request_body = {
            "cluster": {
                "name": "test_cluster",
                "datastore": {
                    "type": self.datastore.id,
                    "version": self.version.id
                },
                "instances": [
                    {
                        "volume": {"size": 5},
                        "flavorRef": 5,
                    },
                    {
                        "volume": {"size": 5},
                        "flavorRef": 5,
                    },
                    {
                        "volume": {"size": 5},
                        "flavorRef": 5,
                    },
                ],
            }
        }

        self.controller = service.ClusterController()
        self.cluster_view_keys = [
            'instances', 'updated', 'task', 'name', 'links',
            'created', 'datastore', 'id'
        ]

        self.safe_remote_nova = remote.create_nova_client
        remote.create_nova_client = nova.fake_create_nova_client
        self.safe_create = instance_models.Instance.create
        instance_models.Instance.create = self.patch_for_instance_create

        super(MongodbClusteringBase, self).setUp()

    def _get_cluster_instances(self, cluster):
        cluster_instances = [
            db_info
            for db_info in
            instance_models.DBInstance.find_all(
                cluster_id=cluster.id)
        ]
        return cluster_instances

    def _get_cluster_instance_service_statuses(self, cluster):
        instances = self._get_cluster_instances(cluster)
        cluster_instance_service_statuses = []
        for cluster_instance in instances:
            cluster_instance_service_statuses.append(
                instance_models.InstanceServiceStatus.get_by(
                    instance_id=cluster_instance.id)
            )
        return cluster_instance_service_statuses

    def _set_cluster_instance_statuses_to_active(self, cluster, statuses=[]):
        statuses = (self._get_cluster_instance_service_statuses(cluster)
                    if not statuses else statuses)
        for status in statuses:
            status.set_status(instance.ServiceStatuses.RUNNING)
            status.save()

    def _get_cluster(self, cluster_id):
        cluster = api.MongoDbCluster.load(
            self.context, cluster_id)
        return cluster

    def _setup_cluster(self):
        instances = self.valid_instance
        cluster = api.MongoDbCluster.create(
            self.context,
            self.cluster_name,
            self.datastore,
            self.version, instances)
        cluster_instances = self._get_cluster_instances(
            cluster)
        cluster_instance_service_statuses = (
            self._get_cluster_instance_service_statuses(
                cluster)
        )
        return (
            cluster,
            cluster_instances,
            cluster_instance_service_statuses
        )

    class fake_server(object):
        def __init__(self):
            self.status = "ACTIVE"
            self.addresses = {"addr": "127.0.0.1"}

    def setup_cluster(self):
        task_api.load = mock.MagicMock()
        instance_models.load_server = mock.MagicMock(
            return_value=None
        )
        instance_models.Instance.get_visible_ip_addresses = (
            mock.MagicMock(return_value=["127.0.0.1"]))
        cluster, instances, statuses = self._setup_cluster()
        self.assertIsNotNone(cluster)
        self.assertIsNotNone(instances)
        self.assertIsNotNone(statuses)
        strategy = (
            taskmanager_strategy.
            MongoDbClusterTasks(
                self.context, cluster.db_info))
        return strategy, cluster, instances, statuses

    def _raise(self, exception_class):

        def do_raise(*args, **kwargs):
            raise exception_class()

        return do_raise

    def tearDown(self):
        api.check_quotas = self.orig_quotas
        self.datastore.delete()
        self.version.delete()
        remote.create_nova_client = self.safe_remote_nova
        instance_models.Instance.create = self.safe_create
        super(MongodbClusteringBase, self).tearDown()
