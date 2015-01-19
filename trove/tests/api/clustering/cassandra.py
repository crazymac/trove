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

from proboscis import asserts
from proboscis import test
from proboscis import SkipTest
from proboscis.decorators import time_out

from trove.common.utils import poll_until

from trove.tests.api.clustering import base

from trove.tests.config import CONFIG
from trove.tests.util.check import TypeCheck

from troveclient.compat import exceptions

GROUP = "dbaas.api.clustering.cassandra"
DATASTORE_NAME = "cassandra"
CLUSTER_PROVISIONING_TIMEOUT = 2700


@test(groups=[GROUP])
class CreateCassandraCluster(base.CreateClusterBase):

    invalid_valid_request_body_with_different_flavors = [
        {
            "flavorRef": 2,
            "volume": {"size": 1},
            "type": "data_node"
        },
        {
            "flavorRef": 3,
            "volume": {"size": 1},
            "type": "data_node"
        },
        {
            "flavorRef": 4,
            "volume": {"size": 1},
            "type": "data_node"
        }
    ]

    invalid_valid_request_body_with_different_volumes = [
        {
            "flavorRef": 2,
            "volume": {"size": 1},
            "type": "seed_node"
        },
        {
            "flavorRef": 2,
            "volume": {"size": 2},
            "type": "data_node"
        },
        {
            "flavorRef": 2,
            "volume": {"size": 3},
            "type": "data_node"
        }
    ]

    invalid_valid_request_body_without_seeds = [
        {
            "flavorRef": 2,
            "volume": {"size": 1},
            "type": "data_node"
        },
        {
            "flavorRef": 2,
            "volume": {"size": 1},
            "type": "data_node"
        },
        {
            "flavorRef": 2,
            "volume": {"size": 1},
            "type": "data_node"
        }
    ]

    # to decrease testing time and resources it was decided
    # to start cluster with one seed_node
    # then using cluster actions -
    # extend it with seed_node or data_node
    valid_valid_request_body = [
        {
            "flavorRef": 2,
            "volume": {"size": 1},
            "type": "seed_node"
        },
        {
            "flavorRef": 2,
            "volume": {"size": 1},
            "type": "data_node"
        },
    ]

    fake_mode_valid_valid_request_body = [
        {
            "flavorRef": 2,
            "volume": {"size": 1},
            "type": "seed_node"
        },
        {
            "flavorRef": 2,
            "volume": {"size": 1},
            "type": "data_node"
        },
        {
            "flavorRef": 2,
            "volume": {"size": 1},
            "type": "data_node"
        },
    ]

    def get_datastore_or_skip_test(self):
        if not self._check_if_datastore_exist(DATASTORE_NAME):
            raise SkipTest("Please run kick-start for Cassandra datastore.")
        return self._get_datastore_and_its_version(DATASTORE_NAME)

    @test
    def test_cassandra_datastore_and_its_version_for_existance(self):
        datastore, version = self.get_datastore_or_skip_test()
        asserts.assert_is_not_none(datastore)
        asserts.assert_is_not_none(version)
        asserts.assert_equal(200, self.rd_client.last_http_code)

    @test(depends_on=[
        test_cassandra_datastore_and_its_version_for_existance])
    def test_create_cluster_with_different_flavors(self):
        datastore, version = self.get_datastore_or_skip_test()
        asserts.assert_raises(
            exceptions.Forbidden,
            self.rd_client.clusters.create,
            "test_cluster",
            datastore.id,
            version.id,
            instances=
            self.invalid_valid_request_body_with_different_flavors)
        asserts.assert_equal(403, self.rd_client.last_http_code)

    @test(depends_on=[test_create_cluster_with_different_flavors],
          runs_after=[test_create_cluster_with_different_flavors])
    def test_create_cluster_with_different_volumes(self):
        datastore, version = self.get_datastore_or_skip_test()
        asserts.assert_raises(
            exceptions.Forbidden,
            self.rd_client.clusters.create,
            "test_cluster",
            datastore.id,
            version.id,
            instances=
            self.invalid_valid_request_body_with_different_volumes)
        asserts.assert_equal(403, self.rd_client.last_http_code)

    @test(depends_on=[test_create_cluster_with_different_volumes],
          runs_after=[test_create_cluster_with_different_volumes])
    def test_create_cluster_without_seed_nodes(self):
        datastore, version = self.get_datastore_or_skip_test()
        asserts.assert_raises(
            exceptions.Forbidden,
            self.rd_client.clusters.create,
            "test_cluster",
            datastore.id,
            version.id,
            instances=
            self.invalid_valid_request_body_without_seeds)
        asserts.assert_equal(403, self.rd_client.last_http_code)

    @test(depends_on=[test_create_cluster_without_seed_nodes],
          runs_after=[test_create_cluster_without_seed_nodes])
    def test_create_cluster_successfuly(self):
        instances = (self.fake_mode_valid_valid_request_body
                     if CONFIG.fake_mode
                     else self.valid_valid_request_body)
        datastore, version = self.get_datastore_or_skip_test()
        self.cluster = self.rd_client.clusters.create(
            "test_cluster", datastore.id,
            version.id, instances=instances)
        with TypeCheck('Cluster', self.cluster) as check:
            check.has_field("id", basestring)
            check.has_field("name", basestring)
            check.has_field("datastore", dict)
            check.has_field("instances", list)
            check.has_field("links", list)
            check.has_field("created", unicode)
            check.has_field("updated", unicode)
            for instance in self.cluster.instances:
                isinstance(instance, dict)
                asserts.assert_is_not_none(instance['id'])
                asserts.assert_is_not_none(instance['links'])
                asserts.assert_is_not_none(instance['name'])
                asserts.assert_is_not_none(instance['type'])

        asserts.assert_equal(200, self.rd_client.last_http_code)

    @test(depends_on=[test_create_cluster_successfuly])
    @time_out(CLUSTER_PROVISIONING_TIMEOUT)
    def test_wait_until_cluster_is_active(self):
        # This version just checks the REST API status.
        report = CONFIG.get_report()

        if not getattr(self, 'cluster', None):
            raise SkipTest(
                "Skipping this tests due to failure of previous.")

        def result_is_active():
            cluster = self.rd_client.clusters.get(self.cluster.id)
            cluster_instances = [
                self.rd_client.instances.get(instance['id'])
                for instance in cluster.instances]

            report.log("Cluster info %s." % cluster._info)
            report.log("Cluster instances info %s." % cluster_instances)

            if cluster.task['name'] == "NONE":

                if ["ERROR"] * len(cluster_instances) == [
                   str(instance.status) for instance in cluster_instances]:
                    report.log("Cluster provisioning failed due to certain "
                               "problems. Please check API, Taskmanager, "
                               "Guestagent log files.")
                    raise Exception

                if ["ACTIVE"] * len(cluster_instances) == [
                   str(instance.status) for instance in cluster_instances]:
                    report.log("Cluster is ready.")
                    return True
            else:
                # If its not ACTIVE, anything but BUILD must be
                # an error.
                asserts.assert_not_equal(
                    ["ERROR"] * len(cluster_instances),
                    [instance.status
                     for instance in cluster_instances])

            report.log("Continue polling, cluster is not ready yet.")

        poll_until(result_is_active)

        report.log("Created cluster, ID = %s." % self.cluster.id)

    @test(depends_on=[test_wait_until_cluster_is_active])
    def test_cluster_delete(self):
        report = CONFIG.get_report()

        if not getattr(self, 'cluster', None):
            raise SkipTest(
                "Skipping this tests due to failure of previous.")

        self.rd_client.clusters.delete(self.cluster.id)
        asserts.assert_equal(202, self.rd_client.last_http_code)

        def _poll():
            try:
                cluster = self.rd_client.clusters.get(
                    self.cluster.id)
                report.log("Cluster info %s" % cluster._info)
                report.log("last HTTP code: %s"
                           % self.rd_client.last_http_code)
                asserts.assert_equal(
                    200, self.rd_client.last_http_code)
                asserts.assert_equal("DELETING", cluster.task['name'])
                return False
            except exceptions.NotFound:
                report.log("Cluster has gone.")
                asserts.assert_equal(404, self.rd_client.last_http_code)
                return True

        poll_until(_poll)

    @test(depends_on=[test_wait_until_cluster_is_active])
    def test_add_data_node_to_building_cluster(self):
        raise SkipTest("To be added.")

    @test(depends_on=[test_add_data_node_to_building_cluster])
    def test_add_seed_node_to_building_cluster(self):
        raise SkipTest("To be added.")
