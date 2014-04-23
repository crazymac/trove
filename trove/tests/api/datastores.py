# Copyright (c) 2011 OpenStack Foundation
# All Rights Reserved.
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


from nose.tools import assert_equal
from troveclient.compat import exceptions

from proboscis import before_class
from proboscis import test
from proboscis.asserts import assert_raises
from proboscis.asserts import assert_true

from trove import tests
from trove.tests.util import create_dbaas_client
from trove.tests.util import test_config
from trove.tests.util.users import Requirements
from trove.tests.util.check import TypeCheck

GROUP = "dbaas.api.datastores"
NAME = "nonexistent"


@test(groups=[tests.DBAAS_API, GROUP, tests.PRE_INSTANCES],
      depends_on_groups=["services.initialize"])
class Datastores(object):

    @before_class
    def setUp(self):
        rd_user = test_config.users.find_user(
            Requirements(is_admin=False, services=["trove"]))
        rd_admin = test_config.users.find_user(
            Requirements(is_admin=True, services=["trove"]))
        self.rd_client = create_dbaas_client(rd_user)
        self.rd_client_admin = create_dbaas_client(rd_admin)

    @test
    def test_datastore_list_attrs(self):
        datastores = self.rd_client.datastores.list()
        for datastore in datastores:
            with TypeCheck('Datastore', datastore) as check:
                check.has_field("id", basestring)
                check.has_field("name", basestring)
                check.has_field("links", list)
                check.has_field("versions", list)

    @test
    def test_datastore_get(self):
        # Test get by name
        datastore_by_name = self.rd_client.datastores.get(
            test_config.dbaas_datastore)
        with TypeCheck('Datastore', datastore_by_name) as check:
            check.has_field("id", basestring)
            check.has_field("name", basestring)
            check.has_field("links", list)
        assert_equal(datastore_by_name.name, test_config.dbaas_datastore)

        # test get by id
        datastore_by_id = self.rd_client.datastores.get(
            datastore_by_name.id)
        with TypeCheck('Datastore', datastore_by_id) as check:
            check.has_field("id", basestring)
            check.has_field("name", basestring)
            check.has_field("links", list)
            check.has_field("versions", list)
        assert_equal(datastore_by_id.id, datastore_by_name.id)

    @test
    def test_datastore_not_found(self):
        try:
            assert_raises(exceptions.NotFound,
                          self.rd_client.datastores.get, NAME)
        except exceptions.BadRequest as e:
            assert_equal(e.message,
                         "Datastore '%s' cannot be found." % NAME)

    @test
    def test_datastore_with_no_active_versions_is_hidden(self):
        datastores = self.rd_client.datastores.list()
        id_list = [datastore.id for datastore in datastores]
        id_no_versions = test_config.dbaas_datastore_id_no_versions
        assert_true(id_no_versions not in id_list)

    @test
    def test_datastore_with_no_active_versions_is_visible_for_admin(self):
        datastores = self.rd_admin.datastores.list()
        id_list = [datastore.id for datastore in datastores]
        id_no_versions = test_config.dbaas_datastore_id_no_versions
        assert_true(id_no_versions in id_list)

    @test
    def test_create_datastore_as_regular(self):
        assert_raises(exceptions.Unauthorized,
                      self.rd_client.datastores.create,
                      "datastore")


@test(groups=[tests.DBAAS_API, GROUP, tests.PRE_INSTANCES],
      depends_on_groups=["services.initialize"])
class DatastoreVersions(object):

    @before_class
    def setUp(self):
        rd_user = test_config.users.find_user(
            Requirements(is_admin=False, services=["trove"]))
        self.rd_client = create_dbaas_client(rd_user)
        self.datastore_active = self.rd_client.datastores.get(
            test_config.dbaas_datastore)
        self.datastore_version_active = self.rd_client.datastore_versions.list(
            self.datastore_active.id)[0]

    @test
    def test_datastore_version_list_attrs(self):
        versions = self.rd_client.datastore_versions.list(
            self.datastore_active.name)
        for version in versions:
            with TypeCheck('DatastoreVersion', version) as check:
                check.has_field("id", basestring)
                check.has_field("name", basestring)
                check.has_field("links", list)

    @test
    def test_datastore_version_get_attrs(self):
        version = self.rd_client.datastore_versions.get(
            self.datastore_active.name, self.datastore_version_active.name)
        with TypeCheck('DatastoreVersion', version) as check:
            check.has_field("id", basestring)
            check.has_field("name", basestring)
            check.has_field("datastore", basestring)
            check.has_field("links", list)
        assert_equal(version.name, self.datastore_version_active.name)

    @test
    def test_datastore_version_get_by_uuid_attrs(self):
        version = self.rd_client.datastore_versions.get_by_uuid(
            self.datastore_version_active.id)
        with TypeCheck('DatastoreVersion', version) as check:
            check.has_field("id", basestring)
            check.has_field("name", basestring)
            check.has_field("datastore", basestring)
            check.has_field("links", list)
        assert_equal(version.name, self.datastore_version_active.name)

    @test
    def test_datastore_version_not_found(self):
        try:
            assert_raises(exceptions.NotFound,
                          self.rd_client.datastore_versions.get,
                          self.datastore_active.name, NAME)
        except exceptions.BadRequest as e:
            assert_equal(e.message,
                         "Datastore version '%s' cannot be found." % NAME)

    @test
    def test_datastore_version_list_by_uuid(self):
        versions = self.rd_client.datastore_versions.list(
            self.datastore_active.id)
        for version in versions:
            with TypeCheck('DatastoreVersion', version) as check:
                check.has_field("id", basestring)
                check.has_field("name", basestring)
                check.has_field("links", list)

    @test
    def test_datastore_version_get_by_uuid(self):
        version = self.rd_client.datastore_versions.get(
            self.datastore_active.id, self.datastore_version_active.id)
        with TypeCheck('DatastoreVersion', version) as check:
            check.has_field("id", basestring)
            check.has_field("name", basestring)
            check.has_field("datastore", basestring)
            check.has_field("links", list)
        assert_equal(version.name, self.datastore_version_active.name)

    @test
    def test_datastore_version_invalid_uuid(self):
        try:
            self.rd_client.datastore_versions.get_by_uuid(
                self.datastore_version_active.id)
        except exceptions.BadRequest as e:
            assert_equal(e.message,
                         "Datastore version '%s' cannot be found." %
                         test_config.dbaas_datastore_version)

    @test
    def test_datastore_with_no_active_versions_is_hidden(self):
        datastores = self.rd_client.datastores.list()
        id_list = [datastore.id for datastore in datastores]
        id_no_versions = test_config.dbaas_datastore_id_no_versions
        assert_true(id_no_versions not in id_list)

    @test
    def test_datastore_with_no_active_versions_is_visible_for_admin(self):
        datastores = self.rd_admin.datastores.list()
        id_list = [datastore.id for datastore in datastores]
        id_no_versions = test_config.dbaas_datastore_id_no_versions
        assert_true(id_no_versions in id_list)

    @test
    def test_datastore_create(self):
        name = "new_ds"
        datastore = self.rd_client_admin.datastores.create(name)
        with TypeCheck('Datastore', datastore) as check:
            check.has_field("id", basestring)
            check.has_field("name", basestring)
            check.has_field("links", list)
        assert_equal(datastore.name, name)

    @test
    def test_datastore_update(self):
        name = "new_ds"
        new_name = "new_ds_renamed"
        default_version = None
        datastore = self.rd_client_admin.datastores.update(name, new_name,
                                                           default_version)
        with TypeCheck('Datastore', datastore) as check:
            check.has_field("id", basestring)
            check.has_field("name", basestring)
            check.has_field("links", list)
        assert_equal(datastore.name, new_name)

    @test(depends_on=[test_datastore_update])
    def test_try_to_update_datastore_as_regular_user(self):
        name = "new_ds_renamed"
        new_name = "new_ds_renamed_2"
        assert_raises(exceptions.Unauthorized,
                      self.rd_client.datastores.update,
                      name, new_name)

    @test
    def test_datastore_version_create(self):
        datastore = "new_ds_renamed"
        name = "new_ver"
        manager = "mysql"
        image_id = "617ec12e-3849-4469-9e2b-eadf9a076996"
        packages = "packages list"
        active = None
        version = self.rd_client_admin.datastore_versions.create(datastore,
                                                                 name,
                                                                 manager,
                                                                 image_id,
                                                                 packages,
                                                                 active)
        with TypeCheck('DatastoreVersion', version) as check:
            check.has_field("id", basestring)
            check.has_field("datastore", basestring)
            check.has_field("name", basestring)
            check.has_field("image", basestring)
            check.has_field("packages", basestring)
            check.has_field("active", bool)
            check.has_field("links", list)
        assert_equal(version.name, name)
        assert_equal(version.image, image_id)
        assert_equal(version.packages, packages)
        assert_equal(version.active, True)

    @test
    def test_datastore_version_update(self):
        datastore = "new_ds_renamed"
        name = "new_ver"
        new_name = "new_ver2"
        image_id = "617ec12e-3849-4469-9e2b-eadf9a076996"
        packages = "packages list"
        active = False
        version = self.rd_client_admin.datastore_versions.update(name,
                                                                 datastore,
                                                                 new_name,
                                                                 None, None,
                                                                 None, active)
        with TypeCheck('DatastoreVersion', version) as check:
            check.has_field("id", basestring)
            check.has_field("datastore", basestring)
            check.has_field("name", basestring)
            check.has_field("image", basestring)
            check.has_field("packages", basestring)
            check.has_field("active", bool)
            check.has_field("links", list)
        assert_equal(version.name, new_name)
        assert_equal(version.image, image_id)
        assert_equal(version.packages, packages)
        assert_equal(version.active, active)

    @test
    def test_datastore_version_update_by_uuid(self):
        datastore = "new_ds_renamed"
        name = "new_ver2"
        new_name = "new_ver3"
        image_id = "617ec12e-3849-4469-9e2b-eadf9a076996"
        packages = "packages list"
        active = True
        version = self.rd_client_admin.datastore_versions.get(datastore, name)
        version = self.rd_client_admin.datastore_versions.update(version.id,
                                                                 None,
                                                                 new_name,
                                                                 None, None,
                                                                 None, active)
        with TypeCheck('DatastoreVersion', version) as check:
            check.has_field("id", basestring)
            check.has_field("datastore", basestring)
            check.has_field("name", basestring)
            check.has_field("image", basestring)
            check.has_field("packages", basestring)
            check.has_field("active", bool)
            check.has_field("links", list)
        assert_equal(version.name, new_name)
        assert_equal(version.image, image_id)
        assert_equal(version.packages, packages)
        assert_equal(version.active, active)

    @test
    def test_datastore_update_not_found(self):
        name = "not-found"
        try:
            assert_raises(exceptions.NotFound,
                          self.rd_client_admin.datastores.update,
                          name, None, "")
        except exceptions.BadRequest as e:
            assert_equal(e.message,
                         "Datastore '%s' cannot be found." % name)

    @test
    def test_datastore_create_already_exists(self):
        try:
            assert_raises(exceptions.NotFound,
                          self.rd_client_admin.datastores.create,
                          test_config.dbaas_datastore)
        except exceptions.BadRequest as e:
            assert_equal(e.message,
                         "Datastore with name '%s' already exists." %
                         test_config.dbaas_datastore)

    @test
    def test_datastore_version_update_not_found(self):
        datastore = "new_ds_renamed"
        name = "not-found"
        active = True
        try:
            assert_raises(exceptions.NotFound,
                          self.rd_client_admin.datastore_versions.update,
                          name, datastore, None, None, None, None, active)
        except exceptions.BadRequest as e:
            assert_equal(e.message,
                         "Datastore version '%s' cannot be found." % name)

    @test
    def test_datastore_version_create_already_exists(self):
        manager = "mysql"
        image_id = "617ec12e-3849-4469-9e2b-eadf9a076996"
        try:
            assert_raises(exceptions.NotFound,
                          self.rd_client_admin.datastore_versions.create,
                          test_config.dbaas_datastore,
                          test_config.dbaas_datastore_version, manager,
                          image_id, None, None)
        except exceptions.BadRequest as e:
            assert_equal(e.message,
                         "Datastore version with name '%s' already exists." %
                         test_config.dbaas_datastore_version)
