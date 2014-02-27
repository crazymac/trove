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

from trove.dbinstance_log import models


class LoaderTest(testtools.TestCase):
    def setUp(self):
        super(LoaderTest, self).setUp()

    def tearDown(self):
        super(LoaderTest, self).tearDown()

    def test_loader_success(self):
        rst = models.LogFilesMapping.load('mysql')
        self.assertIsNotNone(rst)

    def test_load_audit_false(self):
        models.MySQLDatastoreLogMapping.mapping = {}
        rst = models.LogFilesMapping.load('mysql')
        self.assertEqual(0, len(rst))

    def test_content_on_load_mysql_empty(self):
        rst = models.LogFilesMapping.load('mysql')
        mapping = (models.MySQLDatastoreLogMapping.
                   get_logging_mapping()
                   if models.MySQLDatastoreLogMapping
                   .ALLOW_AUDIT else {})
        self.assertEqual(mapping, rst)

    def test_content_on_load_mysql_not_empty(self):
        models.MySQLDatastoreLogMapping.ALLOW_AUDIT = True
        rst = models.LogFilesMapping.load('mysql')
        mapping = (models.MySQLDatastoreLogMapping.
                   get_logging_mapping())
        self.assertEqual(mapping, rst)

    def test_content_on_load_redis_empty(self):
        rst = models.LogFilesMapping.load('redis')
        mapping = (models.RedisDatastoreLogMapping.
                   get_logging_mapping()
                   if models.RedisDatastoreLogMapping.
                   ALLOW_AUDIT else {})
        self.assertEqual(mapping, rst)

    def test_content_on_load_redis_not_empty(self):
        models.RedisDatastoreLogMapping.ALLOW_AUDIT = True
        rst = models.LogFilesMapping.load('redis')
        mapping = (models.RedisDatastoreLogMapping.
                   get_logging_mapping())
        self.assertEqual(mapping, rst)

    def test_content_on_load_cassandra_not_empty(self):
        models.CassandraDatastoreLogMapping.ALLOW_AUDIT = True
        rst = models.LogFilesMapping.load('cassandra')
        mapping = (models.CassandraDatastoreLogMapping.
                   get_logging_mapping())
        self.assertEqual(mapping, rst)

    def test_content_on_load_cassandra_empty(self):
        rst = models.LogFilesMapping.load('cassandra')
        mapping = (models.CassandraDatastoreLogMapping.
                   get_logging_mapping()
                   if models.CassandraDatastoreLogMapping
                   .ALLOW_AUDIT else {})
        self.assertEqual(mapping, rst)
