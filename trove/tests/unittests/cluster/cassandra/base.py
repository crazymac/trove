#  Copyright 2014 Mirantis Inc.
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
from trove.common import exception
from trove.common import remote
from trove.common import instance
from trove.common.strategies import cassandra
from trove.common.strategies.cassandra import api
from trove.cluster import service
from trove.cluster import models
from trove.cluster import tasks as cluster_tasks
from trove.datastore import models as datastore_models
from trove.instance import models as instance_models
from trove.instance import tasks
from trove.tests.unittests.util import util
from trove.tests.fakes import nova


class CassandraClusteringBase(TestCase):

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

        self.datastore = (
            datastore_models.DBDatastore.create(
                id=str(uuid.uuid4()),
                name="cassandra",
                default_version_id=str(uuid.uuid4())
            ))
        self.version = (
            datastore_models.DBDatastoreVersion.create(
                id=self.datastore.default_version_id,
                datastore_id=self.datastore.id,
                name="2.10",
                manager="cassandra",
                image_id=str(uuid.uuid4()),
                packages="",
                active=1,
            )
        )
        self.valid_instance = [
            {
                "flavor_id": 3,
                "volume_size": 2,
                "type": cassandra.SEED_NODE
            },
            {
                "flavor_id": 3,
                "volume_size": 2,
                "type": cassandra.DATA_NODE
            },
            {
                "flavor_id": 3,
                "volume_size": 2,
                "type": cassandra.DATA_NODE
            },
        ]
        self.invalid_instance_roles = [
            {
                "flavor_id": 3,
                "volume_size": 2,
                "type": cassandra.DATA_NODE
            },
            {
                "flavor_id": 3,
                "volume_size": 2,
                "type": cassandra.SEED_NODE
            },
            {
                "flavor_id": 3,
                "volume_size": 2,
                "type": cassandra.SEED_NODE
            },
        ]
        self.invalid_instance_no_seeds = [
            {
                "flavor_id": 3,
                "volume_size": 2,
                "type": cassandra.DATA_NODE
            },
            {
                "flavor_id": 3,
                "volume_size": 2,
                "type": cassandra.DATA_NODE
            },
            {
                "flavor_id": 3,
                "volume_size": 2,
                "type": cassandra.DATA_NODE
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
                        "type": cassandra.SEED_NODE
                    },
                    {
                        "volume": {"size": 5},
                        "flavorRef": 5,
                        "type": cassandra.DATA_NODE
                    },
                    {
                        "volume": {"size": 5},
                        "flavorRef": 5,
                        "type": cassandra.DATA_NODE
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
        self.safe_instance_models = instance_models.Instance.create
        instance_models.Instance.create = self.patch_for_instance_create

        super(CassandraClusteringBase, self).setUp()

    def execute_cluster_action_test(self, performer, assertion, **kwargs):
        cluster = api.CassandraCluster.create(
            self.context,
            self.cluster_name,
            self.datastore,
            self.version, self.valid_instance)

        cluster_id = cluster.db_info.id
        cluster.update_db(task_status=cluster_tasks.ClusterTasks.NONE)
        db_infos = instance_models.DBInstance.find_all(
            cluster_id=cluster_id, deleted=False).all()
        datastore_status = instance_models.InstanceServiceStatus.get_by(
            instance_id=db_infos[0].id)
        with mock.patch.object(instance_models, 'load_any_instance',
                               return_value=
                               instance_models.SimpleInstance(
                               self.context,
                               db_infos[0],
                               datastore_status)):
            kwargs.update({'cluster_id': cluster_id})
            assertion(performer, check_unprocessible=kwargs.get(
                'check_unprocessible', False), **kwargs)

    def assertion(self, performer, check_unprocessible=False, **kwargs):
        data = performer(**kwargs)
        self.assertIsNone(data._data)
        self.assertEqual(202, data.status)
        cluster = models.DBCluster.get_by(
            id=kwargs.get('cluster_id'))
        cluster_task_id = cluster.task_id
        cluster_task = cluster_tasks.ClusterTask.from_code(
            cluster_task_id)
        self.assertEqual(cluster_task, kwargs.get('status_for_assertion'))
        if check_unprocessible:
            self.assertRaises(exception.UnprocessableEntity,
                              performer,
                              **kwargs)

    def performer(self, **kwargs):
        extended_datanode = self.controller.action(
            self.fake_request(self.context),
            kwargs.get('action'),
            self.context.tenant,
            kwargs.get('cluster_id'))
        return extended_datanode

    def tearDown(self):
        self.datastore.delete()
        self.version.delete()
        remote.create_nova_client = self.safe_remote_nova
        instance_models.Instance.create = self.safe_instance_models
        super(CassandraClusteringBase, self).tearDown()
