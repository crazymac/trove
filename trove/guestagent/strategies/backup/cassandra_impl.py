#    Copyright 2014 Mirantis Inc.
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

import time
from trove.common import cfg
from trove.common import exception
from trove.common import utils
from trove.guestagent.common import operating_system
from trove.guestagent.datastore.cassandra import service
from trove.guestagent.strategies.backup import base
from trove.openstack.common import log as logging


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class NodetoolSnapshot(base.BackupRunner):

    """NodetoolSnapshot backup."""
    # nodetool snapshot utility http://goo.gl/QtXVsM
    __strategy_name__ = 'nodetoolsnapshot'

    current_cmd = None

    before_backup_cmd_list = [

        # Flushing SST files for consistency
        'nodetool flush',
        # /dev/null used to ignore next message:
        # Requested clearing snapshot for: all keyspaces
        "nodetool clearsnapshot 1>/dev/null",

        # Creating snapshots of each SST
        "nodetool snapshot -t %(backup_name)s 1>/dev/null",

        # Backup file structure:
        # /var/lib/cassandra/data/{{keyspace}}/{{directory}}/snapshots/

        # Looks for all directories related to created snapshots
        # all keyspaces should be included into backup since they contain
        # significant indexes(such as keyspace and
        # column family definition schemes, etc.)
        # related to existing user-defined keyspace,
        # so keeping system keyspaces will give an ability to reduce
        # time on restoring to avoid spending time on rebuilding indexes
        # for user-defined keyspaces.

        "sudo tar cpjfP /tmp/all_ks.tar.gz "
        "$(sudo find %(datadir)s -type d -name %(backup_name)s)",

        # Once all snapshots were collected into common tarball,
        # snapshots should be dropped
        "nodetool clearsnapshot 1>/dev/null",

    ]

    after_backup_cmd_list = [
        "rm -f /tmp/all_ks.tar.gz",
    ]

    def _run_pre_backup(self):

        conf = service.CassandraApp(
            service.CassandraAppStatus()).read_conf()

        backup_name = 'backup_for_%s_%s' % (
            CONF.guest_id, time.strftime("%d-%m-%Y-%H-%M-%S"))
        args = {
            'backup_name': backup_name,
            'datadir': conf['data_file_directories'][0],
        }
        try:
            for cmd in self.before_backup_cmd_list:
                self.current_cmd = cmd
                utils.execute_with_timeout(cmd % args, shell=True)
        except exception.ProcessExecutionError as e:
            LOG.error(e)
            LOG.debug("Failed command: %s" % self.current_cmd)
            raise

    def _run_post_backup(self):
        try:
            for cmd in self.after_backup_cmd_list:
                utils.execute_with_timeout(cmd, shell=True)
        except exception.ProcessExecutionError as e:
            LOG.error(e)
            LOG.debug("Failed command: %s" % self.current_cmd)
            raise

    @property
    def cmd(self):
        cmd = "cat /tmp/all_ks.tar.gz"
        return cmd + self.encrypt_cmd

    @property
    def manifest(self):
        manifest = ("%(ip)s_%(date)s.cassandra.tar.gz" %
                    {
                        'ip': operating_system.get_ip_address(),
                        'date': time.strftime("%d-%m-%Y-%H-%M-%S"),
                    })
        return manifest + self.encrypt_manifest
