#   Mirantis Inc. 2013
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

import time
from trove.common import cfg
from trove.guestagent.strategies.dblog import base
from trove.openstack.common import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class DBLogStreamer(base.DBLogRunner):

    is_encrypted = False
    __strategy_ns__ = "trove.guestagent.strategies.dblog.DBLogStreamer"
    __strategy_name__ = "dblogstreamer"
    __strategy_type__ = "dblogstreamer"

    @property
    def cmd(self):
        cmd = "cat %(path)s"
        LOG.info("Executing %s" % cmd)
        return cmd + self.zip_cmd

    @property
    def filename(self):
        log_name = "_".join("".join(
            self.filepath.split("/")[-1:]).split("."))
        return ('%(guest)s_%(log)s_%(timestamp)s'
                % {
                    'guest': CONF.guest_id,
                    'log': log_name,
                    'timestamp': time.strftime("%H-%M-%S")
                })
