#    Copyright 2013 OpenStack Foundation
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

import testtools

from trove.common import apischema
from trove.dbinstance_log.service import DBLogController

import jsonschema
import uuid


class DBLogControllerSchemaTest(testtools.TestCase):
    def setUp(self):
        super(DBLogControllerSchemaTest, self).setUp()
        self.instance_id = str(uuid.uuid4())
        self.controller = DBLogController()

    def tearDown(self):
        super(DBLogControllerSchemaTest, self).tearDown()

    def test_validate_creave_success(self):
        body = {
            "dblog": {
                "instance": str(self.instance_id),
                "file": "log-bin"
            }
        }
        schema = self.controller.get_schema('create', body)
        validator = jsonschema.Draft4Validator(schema)
        self.assertTrue(validator.is_valid(body))

    def test_validate_creave_invalid_uuid(self):
        invalid_uuid = "ead-edsa-e23-sdf-23"
        body = {
            "dblog": {
                "instance": invalid_uuid,
                "file": "log-bin"
            }
        }
        schema = self.controller.get_schema('create', body)
        validator = jsonschema.Draft4Validator(schema)
        self.assertFalse(validator.is_valid(body))
        errors = sorted(validator.iter_errors(body), key=lambda e: e.path)
        self.assertEqual("'%s' does not match '%s'" %
                         (invalid_uuid, apischema.uuid['pattern']),
                         errors[0].message)
