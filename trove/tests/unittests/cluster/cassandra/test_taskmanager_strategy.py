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
from eventlet import Timeout

from trove.cluster import tasks as cluster_tasks
from trove.common import exception
from trove.common.strategies import cassandra
from trove.common.strategies.cassandra import api as api_strategy
from trove.common.strategies.cassandra import (
    taskmanager as taskmanager_strategy)
from trove.instance import models as instance_models
from trove.instance import tasks
from trove.taskmanager import api as task_api
from trove.tests.unittests.cluster.cassandra import base
from trove.tests.fakes import guestagent


class TestCassandraTaskmanagerStrategy(base.CassandraClusteringBase):

    def setUp(self):
        self.safe_taskmanager_api = task_api.load
        super(TestCassandraTaskmanagerStrategy, self).setUp()

    def tearDown(self):
        task_api.load = self.safe_taskmanager_api
        super(TestCassandraTaskmanagerStrategy, self).tearDown()

    def make_instance_active(self, cluster):

        def make_active(object_instances, ids, cluster_id):
            self._set_cluster_instance_statuses_to_active(cluster)
        return make_active

    def test_create_cluster_complete(self):
        (strategy, cluster,
         instances, statuses) = self.setup_cluster()

        self._set_cluster_instance_statuses_to_active(
            cluster, statuses=statuses)
        with mock.patch.object(instance_models, 'load_server',
                               return_value=self.fake_server()):
            with mock.patch.object(
                    taskmanager_strategy.CassandraClusteringWorkflow,
                    'get_ip', return_value="1.1.1.1"):
                with mock.patch.object(
                        taskmanager_strategy.CassandraClusterTasks,
                        'get_guest',
                        return_value=guestagent.FakeGuest(
                        instances[0].id)):
                    with mock.patch.object(
                            taskmanager_strategy.CassandraClusterTasks,
                            '_all_instances_ready',
                            return_value=self.make_instance_active(cluster)):
                        strategy.create_cluster(
                            self.context, cluster.id)
        final_cluster = api_strategy.CassandraCluster.load(
            self.context, cluster.id)
        self.assertEqual(
            final_cluster.task_id,
            cluster_tasks.ClusterTasks.NONE.code)

    def test_create_cluster_with_timeout_and_callback(self):
        (strategy, cluster,
         instances, statuses) = self.setup_cluster()
        with mock.patch.object(instance_models, 'load_server',
                               return_value=self.fake_server()):
            with mock.patch.object(
                    taskmanager_strategy.CassandraClusterTasks,
                    '_all_servers_ready'):
                with mock.patch.object(
                        taskmanager_strategy.CassandraClusteringWorkflow,
                        'get_ip', return_value="1.1.1.1"):
                    with mock.patch.object(
                            taskmanager_strategy.CassandraClusterTasks,
                            'get_guest',
                            return_value=guestagent.FakeGuest(
                            instances[0].id)):
                        with mock.patch.object(
                                taskmanager_strategy.
                                CassandraClusteringWorkflow,
                                '_all_instances_ready',
                                side_effect=self._raise(Timeout)):
                            self.assertRaises(
                                exception.ClusterActionError,
                                strategy.create_cluster,
                                self.context, cluster.id)
            final_cluster = api_strategy.CassandraCluster.load(
                self.context, cluster.id)
            self.assertEqual(
                final_cluster.task_id,
                cluster_tasks.ClusterTasks.NONE.code)

    def test_create_failed_cluster_due_to_failed_verification(self):
        (strategy, cluster,
         instances, statuses) = self.setup_cluster()
        self._set_cluster_instance_statuses_to_active(
            cluster, statuses=statuses)
        with mock.patch.object(instance_models, 'load_server',
                               return_value=self.fake_server()):
            with mock.patch.object(
                    taskmanager_strategy.CassandraClusteringWorkflow,
                    'verify_cluster_is_running',
                    side_effect=self._raise(exception.TroveError)):
                with mock.patch.object(
                        taskmanager_strategy.CassandraClusterTasks,
                        'get_guest',
                        return_value=guestagent.FakeGuest(
                        instances[0].id)):
                    self.assertRaises(exception.ClusterActionError,
                                      strategy.create_cluster,
                                      self.context, cluster.id)
                final_cluster = api_strategy.CassandraCluster.load(
                    self.context, cluster.id)
                self.assertEqual(
                    final_cluster.task_id,
                    cluster_tasks.ClusterTasks.NONE.code)
                for instance in cluster.instances:
                    self.assertEqual(
                        instance.db_info.get_task_status(),
                        tasks.InstanceTasks.BUILDING_ERROR_SERVER)

    def test_successful_extend_cluster_add_data_node(self):
        action = "add_data_node"
        node_type = cassandra.DATA_NODE
        self._extend_cluster_with_node(action, node_type)

    def test_failed_extend_cluster_add_data_node(self):
        action = "add_data_node"
        node_type = cassandra.DATA_NODE
        self._extend_cluster_with_node(action, node_type, wrapper=self.wrapper,
                                       exception_to_raise=Timeout,
                                       exception_to_handle=
                                       exception.ClusterActionError)

    def test_successful_extend_cluster_add_seed_node(self):
        action = "add_seed_node"
        node_type = cassandra.SEED_NODE
        self._extend_cluster_with_node(action, node_type)

    def test_failed_extend_cluster_add_seed_node(self):
        action = "add_seed_node"
        node_type = cassandra.SEED_NODE
        self._extend_cluster_with_node(action, node_type, wrapper=self.wrapper,
                                       exception_to_raise=Timeout,
                                       exception_to_handle=
                                       exception.ClusterActionError)
