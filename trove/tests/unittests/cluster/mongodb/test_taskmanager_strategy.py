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
from eventlet import Timeout

from trove.cluster import tasks as cluster_tasks
from trove.common import exception
from trove.common.strategies.mongodb import api as api_strategy
from trove.common.strategies.mongodb import (
    taskmanager as taskmanager_strategy)
from trove.instance import models as instance_models
from trove.taskmanager import api as task_api
from trove.tests.unittests.cluster.mongodb import base
from trove.tests.fakes import guestagent


class TestMongoDBTaskmanagerStrategy(base.MongodbClusteringBase):

    def setUp(self):
        self.safe_taskmanager_api = task_api.load
        super(TestMongoDBTaskmanagerStrategy, self).setUp()

    def tearDown(self):
        task_api.load = self.safe_taskmanager_api
        super(TestMongoDBTaskmanagerStrategy, self).tearDown()

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
                    taskmanager_strategy.MongoDbClusterTasksWorkflow,
                    'get_ip', return_value="1.1.1.1"):
                with mock.patch.object(
                        taskmanager_strategy.MongoDbClusterTasks,
                        'get_guest',
                        return_value=guestagent.FakeGuest(
                        instances[0].id)):
                    with mock.patch.object(
                            taskmanager_strategy.MongoDbClusterTasks,
                            '_all_instances_ready',
                            return_value=self.make_instance_active(cluster)):
                        strategy.create_cluster(
                            self.context, cluster.id)
        final_cluster = api_strategy.MongoDbCluster.load(
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
                    taskmanager_strategy.MongoDbClusterTasksWorkflow,
                    'get_ip', return_value="1.1.1.1"):
                with mock.patch.object(
                        taskmanager_strategy.MongoDbClusterTasks,
                        'get_guest',
                        return_value=guestagent.FakeGuest(
                        instances[0].id)):
                    with mock.patch.object(
                            taskmanager_strategy.
                            MongoDbClusterTasksWorkflow,
                            '_all_instances_ready',
                            side_effect=self._raise(Timeout)):
                        with mock.patch.object(
                                taskmanager_strategy.
                                MongoDbClusterTasksWorkflow,
                                'update_statuses_on_failure') as patched:
                            self.assertRaises(
                                exception.ClusterActionError,
                                strategy.create_cluster,
                                self.context, cluster.id)
                            self.assertTrue(patched.called)
        final_cluster = api_strategy.MongoDbCluster.load(
            self.context, cluster.id)
        self.assertEqual(
            final_cluster.task_id,
            cluster_tasks.ClusterTasks.NONE.code)
