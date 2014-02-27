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
from mockito import when, unstub, any

from trove.guestagent import dbaas
from trove.guestagent.dblog import dblogagent
from trove.guestagent.strategies.dblog.base import DBLogRunner
from trove.guestagent.strategies.dblog.impl import DBLogStreamer
from trove.tests.unittests.backup.test_backupagent import create_fake_data
from trove.tests.unittests.backup.test_backupagent import MockSwift

from tempfile import NamedTemporaryFile


class MockDBLog(DBLogRunner):
    """Create a large temporary file to 'backup' with subprocess."""

    backup_type = 'mock_backup'

    def __init__(self, *args, **kwargs):
        self.data = create_fake_data()
        self.cmd = 'echo %s' % self.data
        super(MockDBLog, self).__init__(*args, **kwargs)


class DBLogAgentTest(testtools.TestCase):

    def setUp(self):
        when(dblogagent).get_storage_strategy(any(), any()).thenReturn(
            MockSwift)
        super(DBLogAgentTest, self).setUp()
        when(dbaas).to_mb(any()).thenReturn('15.15Mb')

    def test_dblogstreamer(self):
        runner = DBLogStreamer("/var/log/mysql/mysql.log")
        self.assertIsNotNone(runner.cmd)
        self.assertIsNotNone(runner.manifest)

    def test_execute_dblog(self):
        with NamedTemporaryFile(delete=False) as f:
            self.file = f.name
        dblogagent.Runner = MockDBLog
        agent = dblogagent.DBLogRunner()
        output = agent.execute_dblog_streaming(
            context=None, log_file=self.file)
        self.assertIsNotNone(output)
        self.assertIsInstance(output, dict)

    def tearDown(self):
        super(DBLogAgentTest, self).tearDown()
        unstub()
