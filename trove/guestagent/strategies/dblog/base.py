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

from trove.guestagent.strategy import Strategy
from trove.openstack.common import log as logging
from trove.common import cfg, utils
from eventlet.green import subprocess

import os
import signal

CONF = cfg.CONF

LOG = logging.getLogger(__name__)


class DBLogError(Exception):
    """Error running the Backup Command."""


class DBLogRunner(Strategy):
    """Base class for Backup Strategy implementations """
    __strategy_type__ = 'dblogrunner'
    __strategy_ns__ = 'trove.guestagent.strategies.dblog'

    cmd = None
    is_zipped = CONF.backup_use_gzip_compression

    def __init__(self, path, **kwargs):
        self.filepath = path
        self.process = None
        self.pid = None
        kwargs.update({'path': path})
        self.command = self.cmd % kwargs
        super(DBLogRunner, self).__init__()

    @property
    def dblogstreamer_type(self):
        return type(self).__name__

    def run(self):
        self.process = subprocess.Popen(self.command, shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        preexec_fn=os.setsid)
        self.pid = self.process.pid

    def __enter__(self):
        """Start up the process"""
        self.run()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Clean up everything."""
        if exc_type is not None:
            return False

        if hasattr(self, 'process'):
            try:
                # Send a sigterm to the session leader, so that all
                # child processes are killed and cleaned up on terminate
                # (Ensures zombie processes aren't left around on a FAILURE)
                # https://bugs.launchpad.net/trove/+bug/1253850
                os.killpg(self.process.pid, signal.SIGTERM)
                self.process.terminate()
            except OSError:
                # Already stopped
                pass
            utils.raise_if_process_errored(self.process, DBLogError)
            if not self.check_process():
                raise DBLogError

        return True

    @property
    def filename(self):
        """Subclasses may overwrite this to declare a format (.tar)"""
        return self.filepath

    @property
    def manifest(self):
        return "%s%s" % (self.filename,
                         self.zip_manifest)

    @property
    def zip_cmd(self):
        return ' | gzip' if self.is_zipped else ''

    @property
    def zip_manifest(self):
        return '.gz' if self.is_zipped else ''

    def read(self, chunk_size):
        return self.process.stdout.read(chunk_size)

    def check_process(self):
        """Hook for subclasses to check process for errors."""
        return True
