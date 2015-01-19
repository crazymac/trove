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

import os
import tempfile
import functools
import yaml

from trove.common import cfg
from trove.common import utils
from trove.common import exception
from trove.common import instance as rd_instance
from trove.guestagent.common import operating_system
from trove.guestagent.datastore.cassandra import system
from trove.guestagent.datastore import service
from trove.guestagent import pkg
from trove.openstack.common import log as logging
from trove.common.i18n import _


LOG = logging.getLogger(__name__)
CONF = cfg.CONF

packager = pkg.Package()


def decorate_exec_action(action):

    @functools.wraps(action)
    def wrapper(self, *args, **kwargs):
        LOG.debug("Action: %s" % action.__name__)
        try:
            return action(self, *args, **kwargs)
        except (exception.ProcessExecutionError, Exception) as e:
            LOG.exception(_("Error during running action %(action)s. "
                            "Exception: %(e)s.") %
                          {"action": action, "e": e})

    return wrapper


class CassandraApp(object):
    """Prepares DBaaS on a Guest container."""

    def __init__(self, status):
        """By default login with root no password for initial setup."""
        self.state_change_wait_time = CONF.state_change_wait_time
        self.status = status

    def install_if_needed(self, packages):
        """Prepare the guest machine with a cassandra server installation."""
        LOG.info(_("Preparing Guest as a Cassandra Server"))
        if not packager.pkg_is_installed(packages):
            self._install_db(packages)
        LOG.debug("Cassandra install_if_needed complete")

    def complete_install_or_restart(self):
        self.status.end_install_or_restart()

    def _enable_db_on_boot(self):
        utils.execute_with_timeout(system.ENABLE_CASSANDRA_ON_BOOT,
                                   shell=True)

    def _disable_db_on_boot(self):
        utils.execute_with_timeout(system.DISABLE_CASSANDRA_ON_BOOT,
                                   shell=True)

    def init_storage_structure(self, mount_point):
        try:
            cmd = system.INIT_FS % mount_point
            utils.execute_with_timeout(cmd, shell=True)
        except exception.ProcessExecutionError:
            LOG.exception(_("Error while initiating storage structure."))

    def start_db(self, update_db=False):
        self._enable_db_on_boot()
        try:
            utils.execute_with_timeout(system.START_CASSANDRA,
                                       shell=True)
        except exception.ProcessExecutionError:
            LOG.exception(_("Error starting Cassandra"))
            pass

        if not (self.status.
                wait_for_real_status_to_change_to(
                rd_instance.ServiceStatuses.RUNNING,
                self.state_change_wait_time,
                update_db)):
            try:
                utils.execute_with_timeout(system.CASSANDRA_KILL,
                                           shell=True)
            except exception.ProcessExecutionError:
                LOG.exception(_("Error killing Cassandra start command."))
            self.status.end_install_or_restart()
            raise RuntimeError(_("Could not start Cassandra"))

    def stop_db(self, update_db=False, do_not_start_on_reboot=False):
        if do_not_start_on_reboot:
            self._disable_db_on_boot()
        utils.execute_with_timeout(system.STOP_CASSANDRA,
                                   shell=True,
                                   timeout=system.SERVICE_STOP_TIMEOUT)

        if not (self.status.wait_for_real_status_to_change_to(
                rd_instance.ServiceStatuses.SHUTDOWN,
                self.state_change_wait_time, update_db)):
            LOG.error(_("Could not stop Cassandra."))
            self.status.end_install_or_restart()
            raise RuntimeError(_("Could not stop Cassandra."))

    def restart(self):
        try:
            self.status.begin_restart()
            LOG.info(_("Restarting Cassandra server."))
            self.stop_db()
            self.start_db()
        finally:
            self.status.end_install_or_restart()

    def _install_db(self, packages):
        """Install cassandra server"""
        LOG.debug("Installing cassandra server.")
        packager.pkg_install(packages, None, system.INSTALL_TIMEOUT)
        LOG.debug("Finished installing Cassandra server")

    def _write_file(self, config_contents,
                    source_path=system.CASSANDRA_CONF,
                    execute_function=utils.execute_with_timeout,
                    mkstemp_function=tempfile.mkstemp,
                    unlink_function=os.unlink,
                    access_mode="644"):

        # first securely create a temp file. mkstemp() will set
        # os.O_EXCL on the open() call, and we get a file with
        # permissions of 600 by default.
        (conf_fd, conf_path) = mkstemp_function()

        LOG.debug('Storing temporary configuration at %s.' % conf_path)

        # write config and close the file, delete it if there is an
        # error. only unlink if there is a problem. In normal course,
        # we move the file.
        try:
            os.write(conf_fd, config_contents)
            execute_function("sudo", "mv", conf_path, source_path)
            execute_function("sudo", "chmod", access_mode, source_path)
        except Exception:
            LOG.exception(
                _("Exception generating Cassandra configuration %s.") %
                conf_path)
            unlink_function(conf_path)
            raise
        finally:
            os.close(conf_fd)

        LOG.info(_('Wrote new Cassandra configuration.'))

    def write_config(self, config_contents):
        self._write_file(
            config_contents,
            source_path=system.CASSANDRA_CONF)

    def read_conf(self, raw=False):
        """Returns cassandra.yaml in dict structure."""

        LOG.debug("Opening cassandra.yaml.")
        with open(system.CASSANDRA_CONF, 'r') as config:
            LOG.debug("Preparing YAML object from cassandra.yaml.")
            data = config.read()
        return data if raw else yaml.load(data)

    def update_config_with_single(self, key, value):
        """Updates single key:value in 'cassandra.yaml'."""

        yamled = self.read_conf()
        yamled.update({key: value})
        LOG.debug("Updating cassandra.yaml with %(key)s: %(value)s."
                  % {'key': key, 'value': value})
        dump = yaml.safe_dump(yamled, default_flow_style=False)
        LOG.debug("Dumping YAML to stream. Dump: %s." % dump)
        self.write_config(dump)

    def update_conf_with_group(self, group):
        """Updates group of key:value in 'cassandra.yaml'."""

        yamled = self.read_conf()
        for key, value in group.iteritems():
            if key == 'seed':
                (yamled.get('seed_provider')[0].
                 get('parameters')[0].
                 update({'seeds': value}))
            else:
                yamled.update({key: value})
            LOG.debug("Updating cassandra.yaml with %(key)s: %(value)s."
                      % {'key': key, 'value': value})
        dump = yaml.safe_dump(yamled, default_flow_style=False)
        LOG.debug("Dumping YAML to stream")
        self.write_config(dump)

    def make_host_reachable(self, include_seed=False):
        updates = {
            'rpc_address': "0.0.0.0",
            'broadcast_rpc_address': operating_system.get_ip_address(),
            'listen_address': operating_system.get_ip_address(),
        }
        if include_seed:
            updates.update(
                {'seed': operating_system.get_ip_address()}
            )
        self.update_conf_with_group(updates)

    def start_db_with_conf_changes(self, config_contents):
        LOG.info(_("Starting Cassandra with configuration changes."))
        LOG.debug("Inside the guest - Cassandra is running %s."
                  % self.status.is_running)
        if self.status.is_running:
            LOG.error(_("Cannot execute start_db_with_conf_changes because "
                        "Cassandra state == %s.") % self.status)
            raise RuntimeError("Cassandra not stopped.")
        LOG.debug("Initiating config.")
        self.write_config(config_contents)
        self.start_db(True)

    def reset_configuration(self, configuration):
        config_contents = configuration['config_contents']
        LOG.debug("Resetting configuration")
        self.write_config(config_contents)

    def inject_files(self, path_and_content_dict_list):
        if path_and_content_dict_list:
            for item in path_and_content_dict_list:
                LOG.debug("Injection item: %s." % item)
                for dest_location, content in item.iteritems():
                    LOG.debug("Location: %s. Content: %s" % (
                        dest_location, content))
                    self._write_file(
                        content,
                        source_path=dest_location)

    def update_overrides(self, overrides_file, remove=False):
        """
        This function will either updates Cassandra,yaml file

        :param overrides:
        :param remove:
        :return:
        """

        if overrides_file:
            LOG.debug("Updating config file.")

            self.write_config(overrides_file)
            self.make_host_reachable()

    @decorate_exec_action
    def setup_tokens(self, *args, **kwargs):
        tokens, stderr = utils.execute_with_timeout(
            system.GET_TOKENS_CMD, shell=True,
            timeout=100)
        parsed_tokens = ",".join(tokens.split("\n"))
        LOG.debug("Instance tokens: %s." % parsed_tokens)
        self.update_config_with_single('initial_token', parsed_tokens)
        return "OK"

    @decorate_exec_action
    def verify_cluster_is_running(self, cluster_ips, **kwargs):
        LOG.debug("IPs that should be visible to this node: %s."
                  % cluster_ips)
        local_cluster_ips, stderr = utils.execute_with_timeout(
            system.CLUSTER_STATUS, shell=True,
            timeout=1000)
        local_cluster_ips = local_cluster_ips.split("\n")[:-1]
        LOG.debug("Visible IPs from this node: %s." % local_cluster_ips)
        LOG.debug("Comparator %s - %s" % (
            cluster_ips, local_cluster_ips))
        LOG.debug("Lists are equal - %s" % set(
            sorted(local_cluster_ips)) == set(sorted(cluster_ips)))
        return ("OK" if set(
            sorted(local_cluster_ips)) == set(sorted(cluster_ips)) else None)

    @decorate_exec_action
    def save_system_traces(self, *args, **kwargs):
        utils.execute_with_timeout(
            "sudo cp -r /var/lib/cassandra/data/system_traces "
            "/tmp/system_traces", shell=True, timeout=100)
        return "OK"

    @decorate_exec_action
    def restore_system_traces(self, *args, **kwargs):
        utils.execute_with_timeout(
            "sudo mv /tmp/system_traces "
            "/var/lib/cassandra/data/system_traces", shell=True, timeout=100)
        return "OK"

    @decorate_exec_action
    def drop_system_keyspace(self, *args, **kwargs):
        utils.execute_with_timeout(
            "sudo rm -fr /var/lib/cassandra/data/*", timeout=100, shell=True)
        return "OK"

    @decorate_exec_action
    def reset_local_schema(self, *args, **kwargs):
        utils.execute_with_timeout("nodetool resetlocalschema",
                                   timeout=100, shell=True)
        return "OK"


class CassandraAppStatus(service.BaseDbStatus):

    def _get_actual_db_status(self, *args, **kwargs):
        try:
            # If status check would be successful,
            # bot stdin and stdout would contain nothing
            out, err = utils.execute_with_timeout(system.CASSANDRA_STATUS,
                                                  shell=True)
            if "Connection error. Could not connect to" not in err:
                return rd_instance.ServiceStatuses.RUNNING
            else:
                return rd_instance.ServiceStatuses.SHUTDOWN
        except (exception.ProcessExecutionError, OSError) as e:
            LOG.exception(_("Error getting Cassandra status. "
                            "Exception: %(e)s.") % {"e": e})
            return rd_instance.ServiceStatuses.SHUTDOWN
