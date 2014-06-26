#    Copyright 2014 Mirantis, Inc.
#    All Rights Reserved.
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

from proboscis import before_class
from proboscis import test
from proboscis import asserts

from trove import tests
from trove.tests.api import instances
from trove.tests.api.backups import BACKUP_LIST_GROUP
from trove.tests.util import test_config
from trove.tests.util import create_dbaas_client
from trove.tests.util.users import Requirements

GROUP = "dbaas.api.mgmt.stats"


@test(groups=[tests.INSTANCES, GROUP],
      depends_on_groups=[instances.INSTANCES_LIST_GROUP])
class StatsInstances(object):

    @before_class
    def setUp(self):
        self.user = test_config.users.find_user(Requirements(is_admin=True))
        self.client = create_dbaas_client(self.user)

    @test
    def test_stats_instances_list(self):
        stats = self.client.stats_instances.list()
        # Instances: Here we know we've only two created instance.
        asserts.assert_equal(2, len(stats))

    @test
    def test_stats_instances_by_tenant(self):
        stats = self.client.stats_instances.get(
            instances.instance_info.user.tenant_id)
        # Instances: Here we know we've only one created instance.
        asserts.assert_equal(1, len(stats))
        asserts.assert_equal(stats[0].tenant_id,
                             instances.instance_info.user.tenant_id)
        asserts.assert_equal(stats[0].id, instances.instance_info.id)
        asserts.assert_equal(stats[0].name, instances.instance_info.name)
        asserts.assert_equal(stats[0].status, "ACTIVE")


@test(depends_on_groups=[BACKUP_LIST_GROUP],
      groups=[tests.INSTANCES, GROUP])
class StatsBackups(object):

    @before_class
    def setUp(self):
        self.user = test_config.users.find_user(Requirements(is_admin=True))
        self.client = create_dbaas_client(self.user)

    @test
    def test_stats_backups_list(self):
        stats = self.client.stats_backups.list()
        asserts.assert_equal(1, len(stats))
        asserts.assert_equal(stats[0].name, 'backup_test')
        asserts.assert_equal(stats[0].description, 'test description')
        asserts.assert_not_equal(stats[0].size, 0.0)
        asserts.assert_equal(stats[0].instance_id, instances.instance_info.id)
        asserts.assert_equal(stats[0].state, 'COMPLETED')
