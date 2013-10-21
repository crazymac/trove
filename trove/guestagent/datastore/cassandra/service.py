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

from trove.common import cfg
from trove.common import utils
from trove.common import exception
from trove.common import instance as rd_instance
from trove.guestagent.datastore.cassandra import system
from trove.guestagent.datastore import service
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _
from trove.guestagent import pkg


LOG = logging.getLogger(__name__)
CONF = cfg.CONF

packager = pkg.Package()


class CassandraApp(object):
    """Prepares DBaaS on a Guest container."""

    ###########################################################################
    def __init__(self, status):
        """ By default login with root no password for initial setup. """
        self.state_change_wait_time = CONF.state_change_wait_time
        self.status = status

    ###########################################################################

    def install_if_needed(self):
        """Prepare the guest machine with a cassandra server installation"""
        LOG.info(_("Preparing Guest as Cassandra Server"))
        if not self.is_installed():
            self._install_cassandra()
        LOG.info(_("Dbaas install_if_needed complete"))

    ###########################################################################

    def complete_install_or_restart(self):
        self.status.end_install_or_restart()

    ###########################################################################

    def is_installed(self):
        LOG.info(_("Checking cassandra if installed"))
        version = packager.pkg_version(system.CASSANDRA_PACKAGE)
        LOG.info(_("Package: %s") % system.CASSANDRA_PACKAGE)
        LOG.info(_("Version: %s") % "Not installed" if version is None
                                    else version)
        LOG.info(_("Installed ? - %s") % (not version is None))
        return not version is None

    ###########################################################################

    def update_config(self, key, value):
        LOG.info(_("Updating config"))
        system.update_config_with(key, value)

    ###########################################################################

    def _unable_cassandra_on_boot(self):
        utils.execute_with_timeout(system.UNABLE_CASSANDRA_ON_BOOT,
                                   shell=True, run_as_root=True)

    ###########################################################################

    def _disable_on_boot(self):
        utils.execute_with_timeout(system.DISABLE_CASSANDRA_ON_BOOT,
                                   shell=True, run_as_root=True)

    ###########################################################################

    def start_cassandra(self, update_db=False):

        self._unable_cassandra_on_boot()
        try:
            utils.execute_with_timeout(system.START_CASSANDRA,
                                       shell=True, run_as_root=True)
        except exception.ProcessExecutionError:
            pass

        if not (self.status.
                wait_for_real_status_to_change_to(
                rd_instance.ServiceStatuses.RUNNING,
                self.state_change_wait_time,
                update_db)):
            try:
                utils.execute_with_timeout(system.CASSANDRA_KILL,
                                           shell=True, run_as_root=True)
            except exception.ProcessExecutionError as p:
                LOG.error("Error killing stalled Cassandra start command.")
                LOG.error(p)
                self.status.end_install_or_restart()
                raise RuntimeError("Could not start Cassandra")

    ###########################################################################

    def stop_cassandra(self, update_db=False, do_not_start_on_reboot=False):
        if do_not_start_on_reboot:
            self._disable_on_boot()
        utils.execute_with_timeout(system.STOP_CASSANDRA,
                                   shell=True, run_as_root=True)

        if not (self.status.wait_for_real_status_to_change_to(
                rd_instance.ServiceStatuses.SHUTDOWN,
                self.state_change_wait_time, update_db)):
            LOG.error(_("Could not stop Cassandra"))
            self.status.end_install_or_restart()
            raise RuntimeError("Could not stop Cassandra")

    ###########################################################################

    def restart_cassandra(self):
        try:
            self.status.begin_restart()
            utils.execute_with_timeout(system.RESTART_CASSANDRA,
                                       shell=True, run_as_root=True)
        finally:
            self.status.end_install_or_restart()

    ###########################################################################

    def _install_cassandra(self):
        """Install cassandra server. Version 1.1.9-1.2.0"""
        LOG.debug(_("Installing cassandra server"))
        packager.pkg_install(system.CASSANDRA_PACKAGE, system.TIME_OUT)
        LOG.debug(_("Updating config with new listen address"))
        self.update_config('listen_address', system.get_host())
        LOG.debug(_("Updating config with new rpc address"))
        self.update_config('rpc_address', '0.0.0.0')
        self.restart_cassandra()
        LOG.debug(_("Finished installing cassandra server"))
    ###########################################################################


class CassandraAppStatus(service.BaseDbStatus):

    def _get_actual_db_status(self):
        try:
            out, err = utils.execute_with_timeout(system.CASSANDRA_STATUS,
                                                  run_as_root=True, shell=True)
            if "running" in out:
                return rd_instance.ServiceStatuses.RUNNING
            else:
                return rd_instance.ServiceStatuses.SHUTDOWN
        except exception.ProcessExecutionError as e:
            LOG.error("Process execution %s" % e)
            return rd_instance.ServiceStatuses.SHUTDOWN
        except OSError as e:
            LOG.error("OS Error %s" % e)
            return rd_instance.ServiceStatuses.SHUTDOWN
