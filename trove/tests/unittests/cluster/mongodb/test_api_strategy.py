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

from trove.common import exception
from trove.common.strategies.mongodb import api
from trove.instance import models as instance_models
from trove.taskmanager import api as task_api
from trove.tests.unittests.cluster.mongodb import base


class TestMongoDBAPIStrategy(base.MongodbClusteringBase):

    def setUp(self):
        self.safe_taskamager_api = task_api.load
        task_api.load = mock.MagicMock()
        super(TestMongoDBAPIStrategy, self).setUp()

    def tearDown(self):
        task_api.load = self.safe_taskamager_api
        super(TestMongoDBAPIStrategy, self).tearDown()

    def test_create_cluster_controller_with_view(self):
        view = self.controller.create(
            self.fake_request(self.context),
            self.request_body,
            self.context.tenant)
        cluster_response = view._data['cluster']
        cluster_instances = cluster_response['instances']
        for instance in cluster_instances:
            self.assertIn("shard_id", instance)
        self.assertIsNotNone(view._data)
        self.assertIsInstance(cluster_response, dict)
        self.assertIsNotNone(cluster_response)
        self.assertEqual(sorted(self.cluster_view_keys),
                         sorted([key for key, value
                                 in cluster_response.iteritems()]))

    def test_successful_cluster_create(self):
        cluster = api.MongoDbCluster.create(
            self.context,
            self.cluster_name,
            self.datastore,
            self.version, self.valid_instance)
        cluster_instances = [
            db_info
            for db_info in
            instance_models.DBInstance.find_all(
                cluster_id=cluster.db_info.id)
        ]
        cluster_instances_ids = [
            db_info.id for db_info in cluster_instances
        ]
        for instance in cluster_instances:
            self.assertTrue(hasattr(instance, "shard_id"))
        self.assertEqual(7, len(cluster_instances_ids))
        self.assertIsNotNone(cluster)
        self.assertEqual(cluster.db_info.name, self.cluster_name)
        for db_info in cluster_instances:
            db_info.delete()
        cluster.db_info.delete()

    def test_failed_cluster_create_due_to_volume_size(self):
        self.assertRaises(exception.ClusterVolumeSizesNotEqual,
                          api.MongoDbCluster.create,
                          self.context,
                          self.cluster_name,
                          self.datastore,
                          self.version, self.invalid_volume_instances)

    def test_failed_cluster_create_due_to_required_volume_size(self):
        instances = [{"flavor_id": 3}] * 3
        self.assertRaises(exception.ClusterVolumeSizeRequired,
                          api.MongoDbCluster.create,
                          self.context,
                          self.cluster_name,
                          self.datastore,
                          self.version, instances)

    def test_failed_cluster_create_due_to_not_enough_instances(self):
        instances = []
        self.assertRaises(exception.ClusterNumInstancesNotSupported,
                          api.MongoDbCluster.create,
                          self.context,
                          self.cluster_name,
                          self.datastore,
                          self.version, instances)

    def test_failed_cluster_create_due_to_different_flavors(self):
        self.assertRaises(exception.ClusterFlavorsNotEqual,
                          api.MongoDbCluster.create,
                          self.context,
                          self.cluster_name,
                          self.datastore,
                          self.version,
                          self.invalid_different_flavors_instances)
