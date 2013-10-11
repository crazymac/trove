#
#  Copyright 2013 Mirantis Inc.
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
#

import os
from trove.common import cfg

from trove.guestagent import volume
from trove.guestagent.manager.cassandra import service
from trove.guestagent.manager.cassandra import system
from trove.openstack.common import periodic_task
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _
from trove.guestagent import dbaas

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class Manager(periodic_task.PeriodicTasks):

    def __init__(self):
        self.appStatus = service.CassandraAppStatus()
        self.app = service.CassandraApp(self.appStatus)

    @periodic_task.periodic_task(ticks_between_runs=3)
    def update_status(self, context):
        """Update the status of the MySQL service"""
        self.appStatus.update()

    def restart(self):
        self.app.restart_cassandra()

    def get_filesystem_stats(self, context, fs_path):
        """ Gets the filesystem stats for the path given """
        return dbaas.get_filesystem_volume_stats(fs_path)

    def prepare(self, context, databases, memory_mb, users, device_path=None,
                mount_point=None, backup_id=None, config_contents=None,
                root_password=None):

        service.CassandraAppStatus.get().begin_install()
        app = service.CassandraApp(service.CassandraAppStatus.get())
        restart_cass = False
        if device_path:
            device = volume.VolumeDevice(device_path)
            device.format()
            if os.path.exists(system.CASSANDRA_MOUNT_POINT):
                #stop and do not update database
                app.stop_cassandra()
                #rsync exiting data
                if not backup_id:
                    restart_cass = True
                    device.migrate_data(system.CASSANDRA_MOUNT_POINT)
            #mount the volume
            device.mount(mount_point)
            LOG.debug(_("Mounted the volume."))
        app.install_if_needed()
        #if backup_id:
        #   self._perform_restore(backup_id, context, system.CASSANDRA_MOUNT_POINT, app)
        app.complete_install_or_restart()
        LOG.info('"prepare" call has finished.')