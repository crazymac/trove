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


from trove.common import exception
from trove.common import utils
from trove.guestagent.datastore.cassandra import service
from trove.guestagent.strategies.restore import base
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _  # noqa


LOG = logging.getLogger(__name__)


class NodetoolSnapshot(base.RestoreRunner):
    """Implementation of Restore Strategy for NodetoolSnapshot."""
    __strategy_name__ = 'nodetoolsnapshot'

    base_restore_cmd = ('cat > backup.tar.gz' + '.enc'
                        if base.RestoreRunner.is_encrypted else '')
    filename = "/tmp/backup.tar.gz"

    app = service.CassandraApp(service.CassandraAppStatus())

    def __init__(self, *args, **kwargs):
        super(NodetoolSnapshot, self).__init__(*args, **kwargs)

    def pre_restore(self):
        LOG.info(_("Stopping db for restore"))
        self.app.stop_db()

    def _unpack(self, location, checksum, command):

        restore_file = ('%s' % self.filename +
                        '.enc' if self.is_encrypted else '')
        stream = self.storage.load(location, checksum)
        content_length = 0
        for chunk in stream:
            with open(restore_file, 'w+') as rst_file:
                rst_file.write(chunk)
            content_length += len(chunk)
        decr_cmd = ('%(decrypt_cmd)s '
                    '-in %(restore_file)s -out %(filename)s'
                    % {'decrypt_cmd': self.decrypt_cmd[:-2],
                       'restore_file': restore_file,
                       'filename': self.filename})
        utils.execute_with_timeout(decr_cmd, shell=True, timeout=100)
        utils.execute_with_timeout('rm -fr %s' % restore_file, shell=True)
        LOG.info(_("Restored %s bytes from stream.") % content_length)

    def post_restore(self):
        conf = self.app.read_conf()
        datadir = conf['data_file_directories'][0]

        # Backup file structure:
        # /var/lib/cassandra/data/{{keyspace}}/{{directory}}/snapshots/

        # This command does next things:
        # 1. Iterates over all keyspaces in given backup
        # 2. Iterates over all directories in each keyspaces directory
        # 3. Finds all *.db files and moves them
        # from ${data_dir}/${keyspace}/${directories}/
        # snapshots/{{snapshot_name}}
        #
        # to ${data_dir}/${keyspace}/${directories}/

        clean_and_move = (
            'data_dir="/tmp/var/lib/cassandra/data" && '
            'for keyspace in `sudo ls -1 ${data_dir}`; '
            'do for directories in `sudo ls -1 ${data_dir}/${keyspace}`; '
            'do i=`sudo find ${data_dir}/${keyspace}/${directories}'
            ' -name *.db`; '
            'sudo mv -f $i ${data_dir}/${keyspace}/${directories}/ '
            '2>/dev/null; '
            'done ; '
            'done;')

        LOG.info(_('Running restore'))
        try:
            # Unzippng pulled tarball
            # ignoring output
            # tar: Removing leading `/' from member names
            unzipping = 'sudo tar xfj %s -C /tmp 2>/dev/null' % self.filename
            out, err = utils.execute_with_timeout(unzipping, shell=True)
            LOG.debug("CMD: %(cmd)s Out: %(out)s Error: %(err)s"
                      % {'out': out, 'err': err, 'cmd': unzipping})

            # Removing tarball
            cleaning = 'sudo rm -f %s' % self.filename
            out, err = utils.execute_with_timeout(cleaning, shell=True)
            LOG.debug("CMD: %(cmd)s Out: %(out)s Error: %(err)s"
                      % {'out': out, 'err': err, 'cmd': cleaning})

            out, err = utils.execute_with_timeout(
                clean_and_move, shell=True)
            LOG.debug("CMD: %(cmd)s Out: %(out)s Error: %(err)s"
                      % {'cmd': clean_and_move, 'out': out, 'err': err})

            # Finding and deleting snapshots directories to be able
            # to copy baked /tmp/var directory to /var
            removing_snapshots_dirs = (
                'sudo rm -rf $(sudo find /tmp/var -type d -name snapshots)')
            out, err = utils.execute_with_timeout(
                removing_snapshots_dirs, shell=True)
            LOG.debug("CMD: %(cmd)s Out: %(out)s Error: %(err)s"
                      % {'out': out, 'err': err,
                         'cmd': removing_snapshots_dirs})

            # Moving data to destination directory
            cp = 'sudo cp -R /tmp/var/lib/cassandra/data/ %s' % datadir
            out, err = utils.execute_with_timeout(cp, shell=True)
            LOG.debug("CMD: %(cmd)s Out: %(out)s Error: %(err)s"
                      % {'out': out, 'err': err, 'cmd': cp})

            # Removing temporary backup storage
            final_cleanup = 'sudo rm -fr /tmp/var'
            out, err = utils.execute_with_timeout(final_cleanup, shell=True)
            LOG.debug("CMD: %(cmd)s Out: %(out)s Error: %(err)s"
                      % {'out': out, 'err': err, 'cmd': final_cleanup})

        except exception.ProcessExecutionError as e:
            LOG.error(_("Error while post-restoring"))
            LOG.error(e)
            raise
        LOG.info(_("Starting db after restore"))
        self.app.restart()
