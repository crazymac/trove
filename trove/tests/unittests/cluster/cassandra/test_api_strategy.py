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

from trove.cluster import tasks
from trove.common import exception
from trove.common.strategies import cassandra
from trove.common.strategies.cassandra import api
from trove.instance import models as instance_models
from trove.taskmanager import api as task_api
from trove.tests.unittests.cluster.cassandra import base


class TestCassandraAPIStrategy(base.CassandraClusteringBase):

    def setUp(self):
        self.safe_taskamager_api = task_api.load
        task_api.load = mock.MagicMock()
        super(TestCassandraAPIStrategy, self).setUp()

    def tearDown(self):
        task_api.load = self.safe_taskamager_api
        super(TestCassandraAPIStrategy, self).tearDown()

    def test_create_cluster_controller_with_view(self):
        view = self.controller.create(
            self.fake_request(self.context),
            self.request_body,
            self.context.tenant)
        cluster_response = view._data['cluster']
        cluster_instances = cluster_response['instances']
        for instance in cluster_instances:
            self.assertIn("type", instance)
        instance_types = [instance['type'] for instance in cluster_instances]
        self.assertIn(cassandra.SEED_NODE, instance_types)
        self.assertIn(cassandra.DATA_NODE, instance_types)
        self.assertIsNotNone(view._data)
        self.assertIsInstance(cluster_response, dict)
        self.assertIsNotNone(cluster_response)
        self.assertEqual(sorted(self.cluster_view_keys),
                         sorted([key for key, value
                                 in cluster_response.iteritems()]))

    def test_successful_cluster_create(self):
        cluster = api.CassandraCluster.create(
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
        roles = [instance.type for instance in cluster_instances]
        seed_node_roles = [seed_node for seed_node in roles
                           if seed_node == cassandra.SEED_NODE]
        data_node_roles = [data_node for data_node in roles
                           if data_node == cassandra.DATA_NODE]
        cluster_instances_ids = [
            db_info.id for db_info in cluster_instances
        ]
        self.assertEqual(3, len(cluster_instances_ids))
        self.assertEqual(1, len(seed_node_roles))
        self.assertEqual(2, len(data_node_roles))
        self.assertIsNotNone(cluster)
        self.assertEqual(cluster.db_info.name, self.cluster_name)

        for db_info in cluster_instances:
            db_info.delete()
        cluster.db_info.delete()

    def test_failed_cluster_create_due_to_volume_size(self):
        self.assertRaises(exception.ClusterVolumeSizesNotEqual,
                          api.CassandraCluster.create,
                          self.context,
                          self.cluster_name,
                          self.datastore,
                          self.version, self.invalid_volume_instances)

    def test_failed_cluster_create_due_missing_seed_nodes(self):
        self.assertRaises(
            exception.CassandraSeedNodeTypeRequired,
            api.CassandraCluster.create,
            self.context,
            self.cluster_name,
            self.datastore,
            self.version, self.invalid_instance_no_seeds)

    def test_failed_cluster_create_due_invalid_role_ration(self):
        self.assertRaises(
            exception.CassandraClusterInvalidClusterInstanceRolesRatio,
            api.CassandraCluster.create,
            self.context,
            self.cluster_name,
            self.datastore,
            self.version, self.invalid_instance_roles)

    def test_failed_cluster_create_due_to_required_volume_size(self):
        instances = [{"flavor_id": 3}] * 3
        self.assertRaises(exception.ClusterVolumeSizeRequired,
                          api.CassandraCluster.create,
                          self.context,
                          self.cluster_name,
                          self.datastore,
                          self.version, instances)

    def test_failed_cluster_create_due_to_not_enough_instances(self):
        instances = []
        self.assertRaises(exception.ClusterNumInstancesNotSupported,
                          api.CassandraCluster.create,
                          self.context,
                          self.cluster_name,
                          self.datastore,
                          self.version, instances)

    def test_failed_cluster_create_due_to_different_flavors(self):
        self.assertRaises(exception.ClusterFlavorsNotEqual,
                          api.CassandraCluster.create,
                          self.context,
                          self.cluster_name,
                          self.datastore,
                          self.version,
                          self.invalid_different_flavors_instances)

    def test_successful_cluster_add_datanode(self):
        action = {"add_data_node": {}}
        self.execute_cluster_action_test(
            self.performer, self.assertion, action=action,
            status_for_assertion=tasks.ClusterTasks.ADDING_DATA_NODE)

    def test_successful_cluster_add_seed_node(self):
        action = {"add_seed_node": {}}
        self.execute_cluster_action_test(
            self.performer, self.assertion, action=action,
            status_for_assertion=tasks.ClusterTasks.ADDING_SEED_NODE)
