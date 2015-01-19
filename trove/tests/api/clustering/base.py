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

from proboscis.decorators import before_class

from trove.tests.util import test_config
from trove.tests.util import create_dbaas_client
from trove.tests.util.users import Requirements


class CreateClusterBase(object):

    @before_class
    def setUp(self):
        rd_user = test_config.users.find_user(
            Requirements(is_admin=False, services=["trove"]))
        rd_admin = test_config.users.find_user(
            Requirements(is_admin=True, services=["trove"]))
        self.rd_client = create_dbaas_client(rd_user)
        self.rd_admin = create_dbaas_client(rd_admin)

    def _check_if_datastore_exist(self, datastore_name):
        datastores = self.rd_client.datastores.list()
        datastore_names = [datastore.name for datastore in datastores]
        return datastore_name in datastore_names

    def _get_datastore_and_its_version(self, datastore_name):
        datastore = self.rd_client.datastores.get(datastore_name)
        _version = self.rd_client.datastore_versions.list(
            datastore.id)[0]

        version = self.rd_client.datastore_versions.get(
            datastore.id, _version.id)
        return datastore, version
