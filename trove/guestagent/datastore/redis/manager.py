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

import os
from trove.common import cfg
from trove.common import instance as rd_instance
from trove.guestagent import dbaas
from trove.guestagent import backup
from trove.guestagent import volume
from trove.guestagent.datastore.redis.service import RedisAppStatus
from trove.guestagent.datastore.redis.service import RedisApp
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _
from trove.openstack.common import periodic_task


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class Manager(periodic_task.PeriodicTasks):
    """
    This is the Redis manager class it is dynamically loaded
    based off of the service_type of the trove instance
    """

    @periodic_task.periodic_task(ticks_between_runs=3)
    def update_status(self, context):
        """
        Updates the redis trove instance it is decorated with
        perodic task so it is automatically called every 3 ticks.
        """
        RedisAppStatus.get().update()

    def change_passwords(self, context, users):
        """
        Changes the redis instance password
        it is currently not not implemented.
        """
        raise NotImplemented()

    def reset_configuration(self, context, configuration):
        """
        Resets to the default configuration
        Currently this does nothing.
        """
        app = RedisApp(RedisAppStatus.get())
        app.reset_configuration(configuration)

    def _perform_restore(self, backup_id, context, restore_location, app):
        """
        Perform a restore on this instance currently it is not implemented.
        """
        raise NotImplemented()

    def prepare(self, context, databases, memory_mb, users, device_path=None,
                mount_point=None, backup_id=None, config_contents=None,
                root_password=None):
        """
        This is called when the trove instance first comes online.
        It is the first rpc message passed from the task manager.
        prepare handles all the base configuration of the redis instance.
        """
        app = RedisApp(RedisAppStatus.get())
        RedisAppStatus.get().begin_install()
        restart_redis = False
        if device_path:
            device = volume.VolumeDevice(device_path)
            device.format()
            if os.path.exists(CONF.mount_point):
                app.stop_db()
                if not backup_id:
                    restart_redis = True
                    device.migrate_data(CONF.mount_point)
            device.mount(CONF.mount_point)
            LOG.debug(_('Mounted the volume.'))
            if restart_redis:

                app.start_redis()
        app.install_if_needed()
        if backup_id:
            self._perform_restore(backup_id, context,
                                  CONF.mount_point, app)
        LOG.info(_('Securing redis now.'))
        app.secure(config_contents)
        app.complete_install_or_restart()
        LOG.info(_('"prepare" redis call has finished.'))

    def restart(self, context):
        """
        Restart this redis instance.
        This method is called when the guest agent
        gets a restart message from the taskmanager.
        """
        app = RedisApp(RedisAppStatus.get())
        app.restart()

    def start_db_with_conf_changes(self, context, config_contents):
        """
        Start this redis instance with new conf changes.
        Right now this does nothing.
        """
        raise NotImplemented()

    def stop_db(self, context, do_not_start_on_reboot=False):
        """
        Stop this redis instance.
        This method is called when the guest agent
        gets a stop message from the taskmanager.
        """
        app = RedisApp(RedisAppStatus.get())
        app.stop_db(do_not_start_on_reboot=do_not_start_on_reboot)

    def get_filesystem_stats(self, context, fs_path):
        """
        Gets file system stats from the provided fs_path.
        """
        return dbaas.get_filesystem_volume_stats(fs_path)

    def create_backup(self, context, backup_id):
        """
        Entry point for initiating a backup for this guest agents db instance.
        The call currently blocks until the backup is complete or errors. If
        device_path is specified, it will be mounted based to a point specified
        in configuration.
        """
        raise NotImplemented()
