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
#

from proboscis.asserts import assert_equal
from proboscis.asserts import assert_true
from proboscis.asserts import assert_raises
from proboscis.asserts import assert_is_not_none
from proboscis import test
from trove import tests
from trove.common.utils import poll_until
from trove.tests.api import backups
from trove.tests.api.instances import instance_info
from trove.tests.api.instances import TIMEOUT_INSTANCE_CREATE
from trove.tests.api.instances import TIMEOUT_INSTANCE_DELETE
from trove.tests.config import CONFIG
from troveclient.compat import exceptions

GROUP = "dbaas.api.recovery"


@test(runs_after=[backups.WaitForBackupCreateToFinish],
      groups=[GROUP, tests.INSTANCES])
class RecoverUsingTimestamp(object):

    @test
    def test_recover(self):
        """test recover"""
        result = instance_info.dbaas.backups.list()
        backup = result.pop()
        updated = backup.updated
        res = instance_info.dbaas.instances.recover(
            instance_info.id, updated)
        # result is a dict
        global recover_instance_id
        recover_instance_id = res.get('id')
        assert_equal(200, instance_info.dbaas.last_http_code)
        assert_is_not_none(recover_instance_id)
        assert_equal(instance_info.id, res.get('parent_instance'))
        assert_is_not_none(res.get('recovered_from_closest_timestamp'))
        assert_is_not_none(res.get('closest_backup'))
        assert_equal(backup.id, res.get('closest_backup'))


@test(depends_on_classes=[RecoverUsingTimestamp],
      runs_after=[RecoverUsingTimestamp],
      groups=[GROUP, tests.INSTANCES])
class WaitForRecoverToFinish(object):
    """
        Wait until the instance is finished restoring.
    """

    @test
    def test_instance_recovered(self):
        # This version just checks the REST API status.
        def result_is_active():
            instance = instance_info.dbaas.instances.get(recover_instance_id)
            if instance.status == "ACTIVE":
                return True
            else:
                # If its not ACTIVE, anything but BUILD must be
                # an error.
                assert_equal("BUILD", instance.status)
                if instance_info.volume is not None:
                    assert_equal(instance.volume.get('used', None), None)
                return False

        poll_until(result_is_active, time_out=TIMEOUT_INSTANCE_CREATE,
                   sleep_time=10)


@test(depends_on_classes=[RecoverUsingTimestamp, WaitForRecoverToFinish],
      runs_after=[WaitForRecoverToFinish],
      enabled=(not CONFIG.fake_mode),
      groups=[GROUP, tests.INSTANCES])
class VerifyRecover(object):

    @test
    def test_database_restored(self):
        instances = instance_info.dbaas.instances.list()
        dbs = [d.id for d in instances]
        assert_true(recover_instance_id in dbs,
                    "%s not found among all instances" % recover_instance_id)


@test(runs_after=[VerifyRecover],
      groups=[GROUP, tests.INSTANCES])
class DeleteRecoveredInstance(object):

    @test
    def test_delete_restored_instance(self):
        """test delete restored instance"""
        instance_info.dbaas.instances.delete(recover_instance_id)
        assert_equal(202, instance_info.dbaas.last_http_code)

        def instance_is_gone():
            try:
                instance_info.dbaas.instances.get(recover_instance_id)
                return False
            except exceptions.NotFound:
                return True

        poll_until(instance_is_gone, time_out=TIMEOUT_INSTANCE_DELETE,
                   sleep_time=3)
        assert_raises(exceptions.NotFound, instance_info.dbaas.instances.get,
                      recover_instance_id)
