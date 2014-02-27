#   Copyright 2013 OpenStack Foundation
#   All Rights Reserved.
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

import uuid

from proboscis import test
from proboscis import SkipTest
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_not_equal
from proboscis.asserts import assert_raises
from proboscis.decorators import time_out

from trove.tests.api.instances import WaitForGuestInstallationToFinish
from trove.tests.api.instances import instance_info
from trove.tests.util import test_config
from trove.tests.util.check import TypeCheck

import troveclient.compat
from troveclient.compat import exceptions


GROUP = "dbaas.api.dblogs"
VALID_LOGNAME = "general_log"
INVALID_LOGNAME = "some_kind_of_log"


@test(depends_on_classes=[WaitForGuestInstallationToFinish],
      groups=[GROUP])
class CreateDBLogs(object):

    @test
    def test_create_dblog_invalid(self):
        if test_config.auth_strategy == "fake":
            raise SkipTest("Skipping create_dblog_invalid test for fake mode.")
        invalid_inst_id = uuid.uuid4()
        try:
            instance_info.dbaas.dblogs.create(INVALID_LOGNAME, invalid_inst_id)
        except exceptions.BadRequest as e:
            resp, body = instance_info.dbaas.client.last_response
            assert_equal(resp.status, 400)
            if not isinstance(instance_info.dbaas.client,
                              troveclient.compat.xml.TroveXmlClient):
                assert_equal(e.message,
                             "Validation error: "
                             "backup['instance'] u'%s' does not match "
                             "'^([0-9a-fA-F]){8}-([0-9a-fA-F]){4}-"
                             "([0-9a-fA-F]){4}-([0-9a-fA-F]){4}-"
                             "([0-9a-fA-F]){12}$'" %
                             invalid_inst_id)

    @test
    def test_dblog_create_instance_not_found(self):
        """test create dblog with unknown instance"""
        if test_config.auth_strategy == "fake":
            raise SkipTest("Skipping create_dblog "
                           "instance_not_foundtest for fake mode.")

        assert_raises(exceptions.NotFound, instance_info.dbaas.dblogs.create,
                      VALID_LOGNAME, str(uuid.uuid4()))

    @test
    @time_out(40)
    def test_dblog_create_valid(self):
        """test create dblog for a given instance"""
        if test_config.auth_strategy == "fake":
            raise SkipTest("Skipping create_dblog valid for fake mode.")
        instances = instance_info.dbaas.instances.list()
        result = instance_info.dbaas.dblogs.create(VALID_LOGNAME,
                                                   instances[0].id)
        with TypeCheck("DBLog", result) as check:
            check.has_field("file", basestring)
            check.has_field("instance_id", basestring)
            check.has_field("location", basestring)
            check.has_field("size", basestring)
        assert_equal(instance_info.id, result.instance_id)
        assert_equal("mysql.log", result.file)

    @test
    def test_dblog_list(self):
        """test list dblogs for datastores"""
        result = instance_info.dbaas.dblogs.list()
        assert_not_equal(0, len(result))
        for first in result:
            with TypeCheck("DBLog", first) as check:
                check.has_field("datastore_version_manager", basestring)
                check.has_field("datastore_log_files", basestring)
            assert_not_equal(None, first.datastore_version_manager)
            assert_not_equal(None, first.datastore_log_files)

    @test
    def test_dblog_show(self):
        """test list dblogs for given datastore"""
        version = instance_info.dbaas_datastore_version.list(
            test_config.dbaas_datastore)
        result = instance_info.dbaas.dblogs.show(version.id)
        with TypeCheck("DBLog", result) as check:
            check.has_field("datastore_version_manager", basestring)
            check.has_field("datastore_log_files", basestring)
        assert_not_equal(None, result.datastore_version_manager)
        assert_not_equal(None, result.datastore_log_files)
