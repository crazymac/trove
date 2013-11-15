#    Copyright 2013 Rackspace
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
import re
import uuid
import time
from datetime import date

from trove.common import cfg
from trove.common import utils as utils
from trove.common import exception
from trove.common import instance as rd_instance
from trove.guestagent import pkg
from trove.guestagent.datastore import service
from trove.guestagent.datastore.redis import system
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _

LOG = logging.getLogger(__name__)
TMP_REDIS_CONF = '/tmp/redis.conf.tmp'
CONF = cfg.CONF
packager = pkg.Package()


def _load_redis_options():
    """
    Reads the redis config file for all redis options.
    Right now this does not do any smart parsing and returns only key
    value pairs as a str, str.
    So: 'foo bar baz' becomes {'foo' : 'bar baz'}
    """
    options = {}
    with open(system.REDIS_CONFIG, 'r') as fd:
        for opt in fd.readline().split(' '):
            options.update({opt[0]: ' '.join(opt[1:])})
    return options


class RedisAppStatus(service.BaseDbStatus):
    """
    Handles all of the status updating for the redis guest agent.
    """
    @classmethod
    def get(cls):
        """
        Gets an instance of the RedisAppStatus class.
        """
        if not cls._instance:
            cls._instance = RedisAppStatus()
        return cls._instance

    def _get_actual_db_status(self):
        """
        Gets the actual status of the Redis instance
        First it attempts to make a connection to the redis instance
        by making a PING request.
        If PING does not return PONG we do a ps
        to see if the process is blocked or hung.
        This implementation stinks but redis-cli only returns 0
        at this time.
        http://redis.googlecode.com/svn/trunk/redis-cli.c
        If we raise another exception.ProcessExecutionError while
        running ps.
        We attempt to locate the PID file and see if the process
        is crashed or shutdown.
        Remeber by default execute_with_timeout raises this exception
        if a non 0 status code is returned from the cmd called.
        """
        options = _load_redis_options()
        try:
            if 'requirepass' in options:
                LOG.info(_('Password is set running ping with password'))
                out, err = utils.execute_with_timeout(
                    system.REDIS_CLI,
                    '-a',
                    options['requirepass'],
                    'PING',
                    run_as_root=True,
                    root_helper='sudo')
            else:
                LOG.info(_('Password not set running ping without password'))
                out, err = utils.execute_with_timeout(
                    system.REDIS_CLI,
                    'PING',
                    run_as_root=True,
                    root_helper='sudo')
            LOG.info(_('Redis is RUNNING.'))
            return rd_instance.ServiceStatuses.RUNNING
        except exception.ProcessExecutionError:
            LOG.error(_('Process execution error on redis-cli'))
        if out.strip() != 'PONG':
            try:
                out, err = utils.execute_with_timeout('/bin/ps', '-C',
                                                      'redis-server', 'h')
                pid = out.split()[0]
                LOG.info(_('Redis pid: %(pid)s' % {'pid': pid}))
                LOG.info(_('Service Status is BLOCKED.'))
                return rd_instance.ServiceStatuses.BLOCKED
            except exception.ProcessExecutionError:
                pid_file = options.get('pidfile',
                                       '/var/run/redis/redis-server.pid')
                if os.path.exists(pid_file):
                    LOG.info(_('Service Status is CRASHED.'))
                    return rd_instance.ServiceStatuses.CRASHED
                else:
                    LOG.info(_('Service Status is SHUTDOWN.'))
                    return rd_instance.ServiceStatuses.SHUTDOWN


class RedisApp(object):
    """
    Handles installation and configuration of redis
    on a trove instance.
    """

    def __init__(self, status):
        """
        Sets default status and state_change_wait_time
        """
        self.state_change_wait_time = CONF.state_change_wait_time
        self.status = status

    def install_if_needed(self):
        """
        Install redis if needed do nothing if it is already installed.
        """
        LOG.info(_('Preparing Guest as Redis Server'))
        if not self.is_installed():
            self._install_redis()
        LOG.info(_('Dbaas install_if_needed complete'))

    def complete_install_or_restart(self):
        """
        finalize status updates for install or restart.
        """
        self.status.end_install_or_restart()

    def _install_redis(self):
        """
        Install the redis server.
        """
        LOG.debug(_('Installing redis server'))
        self._create_redis_conf_dir()
        packager.pkg_install(system.REDIS_PACKAGE, self.TIME_OUT)
        self.start_redis()
        LOG.debug(_('Finished installing redis server'))
        #TODO(rnirmal): Add checks to make sure the package got installed

    def _create_redis_conf_dir(self):
        LOG.debug(_("Creating %s" % system.REDIS_CONF_DIR))
        command = "mkdir -p %s" % system.REDIS_CONF_DIR
        utils.execute_with_timeout(command,
                                   run_as_root=True,
                                   root_helper='sudo')

    def _enable_redis_on_boot(self):
        """
        Enables redis on boot.
        """
        LOG.info(_('Enabling redis on boot.'))
        conf = system.REDIS_CONF_DIR
        if os.path.isfile(conf):
            command = "sed -i '/^manual$/d' %(conf)s" % {'conf': conf}
        else:
            command = system.REDIS_CMD_ENABLE
        utils.execute_with_timeout(command,
                                   run_as_root=True,
                                   root_helper='sudo')

    def _disable_redis_on_boot(self):
        """
        Disables redis on boot.
        """
        LOG.info(_('Disabling redis on boot.'))
        conf = system.REDIS_CONF_DIR
        if os.path.isfile(conf):
            command = "sudo sh -c 'echo manual >> %(conf)s'" % {'conf': conf}
        else:
            command = system.REDIS_CMD_DISABLE
        utils.execute_with_timeout(command,
                                   run_as_root=True,
                                   root_helper='sudo')

    def stop_db(self, update_db=False, do_not_start_on_reboot=False):
        """
        Stops the redis application on the trove instance.
        """
        LOG.info(_('Stopping redis...'))
        if do_not_start_on_reboot:
            self._disable_redis_on_boot()
        utils.execute_with_timeout(system.REDIS_CMD_STOP,
                                   run_as_root=True,
                                   root_helper='sudo')
        if not self.status.wait_for_real_status_to_change_to(
                rd_instance.ServiceStatuses.SHUTDOWN,
                self.state_change_wait_time, update_db):
            LOG.error(_('Could not stop Redis!'))
            self.status.end_install_or_restart()
            raise RuntimeError('Could not stop Redis!')

    def restart(self):
        """
        Restarts the redis daemon.
        """
        try:
            self.status.begin_restart()
            self.stop_db()
            self.start_redis()
        finally:
            self.status.end_install_or_restart()

    def secure(self, config_contents):
        """
        Secure this redis instance.
        """
        with open(TMP_REDIS_CONF, 'w') as fd:
            fd.write(config_contents)
        utils.execute_with_timeout('mv',
                                   TMP_REDIS_CONF,
                                   system.REDIS_CONFIG,
                                   run_as_root=True,
                                   root_helper='sudo')

    def start_redis(self, update_db=False):
        """
        Start the redis daemon.
        """
        LOG.info(_("Starting redis..."))
        self._enable_redis_on_boot()
        try:
            utils.execute_with_timeout(system.REDIS_CMD_START,
                                       run_as_root=True,
                                       root_helper='sudo')
        except exception.ProcessExecutionError:
            pass
        if not self.status.wait_for_real_status_to_change_to(
                rd_instance.ServiceStatuses.RUNNING,
                self.state_change_wait_time, update_db):
            LOG.error(_("Start up of redis failed!"))
            # If it won't start, but won't die either, kill it by hand so we
            # don't let a rouge process wander around.
            try:
                utils.execute_with_timeout('pkill', '-9',
                                           'redis-server',
                                           run_as_root=True,
                                           root_helper='sudo')
            except exception.ProcessExecutionError as p:
                LOG.error('Error killing stalled redis start command.')
                LOG.error(p)
                # There's nothing more we can do...
            self.status.end_install_or_restart()
            raise RuntimeError('Could not start redis!')

    def is_installed(self):
        """
        Determine if redis is installed or not.
        """
        #(cp16net) could raise an exception, does it need to be handled here?
        version = packager.pkg_version(system.REDIS_PACKAGE)
        return not version is None
