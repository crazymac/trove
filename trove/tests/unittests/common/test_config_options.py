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

import os
import testtools
from mock import MagicMock


class TestConfigurations(testtools.TestCase):

    def setUp(self):
        super(TestConfigurations, self).setUp()
        self.orig_os = os.getenv
        os.getenv = MagicMock(return_value=True)

    def tearDown(self):
        os.getenv = self.orig_os
        super(TestConfigurations, self).tearDown()

    def test_updated_heat_configuration_opts(self):
        from trove.common import cfg
        CONF = cfg.CONF
        self.assertTrue(CONF.use_heat)
