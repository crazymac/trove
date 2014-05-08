#    Copyright 2012 OpenStack Foundation
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
import os.path

from heatclient import exc as heat_exceptions
from novaclient import exceptions as nova_exceptions
from trove.backup import models as bkup_models
from trove.common import cfg
from trove.common import template
from trove.common import utils
from trove.common.exception import PollTimeOut
from trove.common.exception import VolumeCreationFailure
from trove.common.exception import TroveError
from trove.common.exception import MalformedSecurityGroupRuleError
from trove.common.remote import create_heat_client
from trove.common.remote import create_cinder_client
from trove.datastore.models import DatastoreVersion
from trove.extensions.security_group.models import SecurityGroup
from trove.extensions.security_group.models import SecurityGroupRule
from swiftclient.client import ClientException
from trove.instance import models as inst_models
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _
from trove.taskmanager import common
import trove.common.remote as remote


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class OrchestratorFreshInstanceTask(common.FreshInstanceTaskMixin):

    def create_instance(self, flavor, image_id, databases, users,
                        datastore_manager, packages, volume_size,
                        backup_id, availability_zone, root_password, nics,
                        overrides):

        volume_info = self._create_server_volume_heat(
            flavor, image_id, datastore_manager,
            volume_size, availability_zone, nics
        )
        self.prepare_guest(datastore_manager, flavor, overrides,
                           backup_id, volume_info, packages, databases,
                           users, root_password)

        self.report_root(root_password)

        self.check_for_errors()

        self.create_dns_entry()

        self.do_guest_check(datastore_manager, flavor)

    def _create_server_volume_heat(self, flavor, image_id,
                                   datastore_manager,
                                   volume_size, availability_zone, nics):
        LOG.debug(_("begin _create_server_volume_heat for id: %s") % self.id)
        try:
            client = create_heat_client(self.context)

            ifaces, ports = self._build_heat_nics(nics)
            template_obj = template.load_heat_template(datastore_manager)
            heat_template_unicode = template_obj.render(
                volume_support=CONF.trove_volume_support,
                ifaces=ifaces, ports=ports)
            try:
                heat_template = heat_template_unicode.encode('utf-8')
            except UnicodeEncodeError:
                LOG.error(_("heat template ascii encode issue"))
                raise TroveError("heat template ascii encode issue")

            parameters = {"Flavor": flavor["name"],
                          "VolumeSize": volume_size,
                          "InstanceId": self.id,
                          "ImageId": image_id,
                          "DatastoreManager": datastore_manager,
                          "AvailabilityZone": availability_zone,
                          "TenantId": self.tenant_id}
            stack_name = 'trove-%s' % self.id
            client.stacks.create(stack_name=stack_name,
                                 template=heat_template,
                                 parameters=parameters,
                                 disable_rollback=False)
            try:
                utils.poll_until(
                    lambda: client.stacks.get(stack_name),
                    lambda stack: stack.stack_status in ['CREATE_COMPLETE',
                                                         'CREATE_FAILED'],
                    sleep_time=common.USAGE_SLEEP_TIME,
                    time_out=common.HEAT_TIME_OUT)
            except common.PollTimeOut:
                LOG.error(_("Timeout during stack status tracing"))
                raise TroveError("Timeout occured in tracking stack status")

            stack = client.stacks.get(stack_name)
            if ((stack.action, stack.stack_status)
                    not in common.HEAT_STACK_SUCCESSFUL_STATUSES):
                raise TroveError("Heat Stack Create Failed.")

            resource = client.resources.get(stack.id, 'BaseInstance')
            if (
                resource.resource_status !=
                    common.HEAT_RESOURCE_SUCCESSFUL_STATE
            ):
                raise TroveError("Heat Resource Provisioning Failed.")
            instance_id = resource.physical_resource_id

            if CONF.trove_volume_support:
                resource = client.resources.get(stack.id, 'DataVolume')
                if (
                    resource.resource_status !=
                        common.HEAT_RESOURCE_SUCCESSFUL_STATE
                ):
                    raise TroveError("Heat Resource Provisioning Failed.")
                volume_id = resource.physical_resource_id
                self.update_db(compute_instance_id=instance_id,
                               volume_id=volume_id)
            else:
                self.update_db(compute_instance_id=instance_id)

        except (TroveError, heat_exceptions.HTTPNotFound) as e:
            msg = _("Error during creating stack for instance %s") % self.id
            LOG.debug(msg)
            err = inst_models.InstanceTasks.BUILDING_ERROR_SERVER
            self._log_and_raise(e, msg, err)

        device_path = CONF.device_path
        mount_point = CONF.get(datastore_manager).mount_point
        volume_info = {'device_path': device_path, 'mount_point': mount_point}

        LOG.debug(_("end _create_server_volume_heat for id: %s") % self.id)
        return volume_info

    def _build_heat_nics(self, nics):
        ifaces = []
        ports = []
        if nics:
            for idx, nic in enumerate(nics):
                iface_id = nic.get('port-id')
                if iface_id:
                    ifaces.append(iface_id)
                    continue
                net_id = nic.get('net-id')
                if net_id:
                    port = {}
                    port['name'] = "Port%s" % idx
                    port['net_id'] = net_id
                    fixed_ip = nic.get('v4-fixed-ip')
                    if fixed_ip:
                        port['fixed_ip'] = fixed_ip
                    ports.append(port)
                    ifaces.append("{Ref: Port%s}" % idx)
        return ifaces, ports


class NativeFreshInstanceTasks(common.FreshInstanceTaskMixin):

    def create_instance(self, flavor, image_id, databases, users,
                        datastore_manager, packages, volume_size,
                        backup_id, availability_zone, root_password, nics,
                        overrides):

        LOG.debug(_("begin create_instance for id: %s") % self.id)
        security_groups = None

        # If security group support is enabled and heat based instance
        # orchestration is disabled, create a security group.
        #
        if CONF.trove_security_groups_support:
            try:
                security_groups = self._create_secgroup(datastore_manager)
            except Exception as e:
                msg = (_("Error creating security group for instance: %s") %
                       self.id)
                err = inst_models.InstanceTasks.BUILDING_ERROR_SEC_GROUP
                self._log_and_raise(e, msg, err)
            else:
                LOG.debug(_("Successfully created security group for "
                            "instance: %s") % self.id)

        if common.USE_NOVA_SERVER_VOLUME:
            volume_info = self._create_server_volume(
                flavor['id'],
                image_id,
                security_groups,
                datastore_manager,
                volume_size,
                availability_zone,
                nics)
        else:
            volume_info = self._create_server_volume_individually(
                flavor['id'],
                image_id,
                security_groups,
                datastore_manager,
                volume_size,
                availability_zone,
                nics)

        self.prepare_guest(datastore_manager, flavor, overrides,
                           backup_id, volume_info, packages, databases,
                           users, root_password)

        self.report_root(root_password)

        self.check_for_errors()

        self.create_dns_entry()

        self.do_guest_check(datastore_manager, flavor)

    def _create_server_volume(self, flavor_id, image_id, security_groups,
                              datastore_manager, volume_size,
                              availability_zone, nics):
        LOG.debug(_("begin _create_server_volume for id: %s") % self.id)
        try:
            files = {"/etc/guest_info": ("[DEFAULT]\n--guest_id="
                                         "%s\n--datastore_manager=%s\n"
                                         "--tenant_id=%s\n" %
                                         (self.id, datastore_manager,
                                          self.tenant_id))}
            name = self.hostname or self.name
            volume_desc = ("datastore volume for %s" % self.id)
            volume_name = ("datastore-%s" % self.id)
            volume_ref = {'size': volume_size, 'name': volume_name,
                          'description': volume_desc}

            server = self.nova_client.servers.create(
                name, image_id, flavor_id,
                files=files, volume=volume_ref,
                security_groups=security_groups,
                availability_zone=availability_zone, nics=nics)
            LOG.debug(_("Created new compute instance %(server_id)s "
                        "for id: %(id)s") %
                      {'server_id': server.id, 'id': self.id})

            server_dict = server._info
            LOG.debug(_("Server response: %s") % server_dict)
            volume_id = None
            for volume in server_dict.get('os:volumes', []):
                volume_id = volume.get('id')

            # Record the server ID and volume ID in case something goes wrong.
            self.update_db(compute_instance_id=server.id, volume_id=volume_id)
        except Exception as e:
            msg = _("Error creating server and volume for "
                    "instance %s") % self.id
            LOG.debug(_("end _create_server_volume for id: %s") % self.id)
            err = inst_models.InstanceTasks.BUILDING_ERROR_SERVER
            self._log_and_raise(e, msg, err)

        device_path = CONF.device_path
        mount_point = CONF.get(datastore_manager).mount_point
        volume_info = {'device_path': device_path, 'mount_point': mount_point}
        LOG.debug(_("end _create_server_volume for id: %s") % self.id)
        return volume_info

    def _create_server_volume_individually(self, flavor_id, image_id,
                                           security_groups, datastore_manager,
                                           volume_size,
                                           availability_zone, nics):
        LOG.debug(_("begin _create_server_volume_individually for id: %s") %
                  self.id)
        server = None
        volume_info = self._build_volume_info(datastore_manager,
                                              volume_size=volume_size)
        block_device_mapping = volume_info['block_device']
        try:
            server = self._create_server(flavor_id, image_id, security_groups,
                                         datastore_manager,
                                         block_device_mapping,
                                         availability_zone, nics)
            server_id = server.id
            # Save server ID.
            self.update_db(compute_instance_id=server_id)
        except Exception as e:
            msg = _("Error creating server for instance %s") % self.id
            err = inst_models.InstanceTasks.BUILDING_ERROR_SERVER
            self._log_and_raise(e, msg, err)
        LOG.debug(_("end _create_server_volume_individually for id: %s") %
                  self.id)
        return volume_info

    def _build_volume_info(self, datastore_manager, volume_size=None):
        volume_info = None
        volume_support = CONF.trove_volume_support
        LOG.debug(_("trove volume support = %s") % volume_support)
        if volume_support:
            try:
                volume_info = self._create_volume(
                    volume_size, datastore_manager)
            except Exception as e:
                msg = _("Error provisioning volume for instance: %s") % self.id
                err = inst_models.InstanceTasks.BUILDING_ERROR_VOLUME
                self._log_and_raise(e, msg, err)
        else:
            LOG.debug(_("device_path = %s") % CONF.device_path)
            LOG.debug(_("mount_point = %s") %
                      CONF.get(datastore_manager).mount_point)
            volume_info = {
                'block_device': None,
                'device_path': CONF.device_path,
                'mount_point': CONF.get(datastore_manager).mount_point,
                'volumes': None,
            }
        return volume_info

    def _create_volume(self, volume_size, datastore_manager):
        LOG.info("Entering create_volume")
        LOG.debug(_("begin _create_volume for id: %s") % self.id)
        volume_client = create_cinder_client(self.context)
        volume_desc = ("datastore volume for %s" % self.id)
        volume_ref = volume_client.volumes.create(
            volume_size, name="datastore-%s" % self.id,
            description=volume_desc)

        # Record the volume ID in case something goes wrong.
        self.update_db(volume_id=volume_ref.id)

        utils.poll_until(
            lambda: volume_client.volumes.get(volume_ref.id),
            lambda v_ref: v_ref.status in ['available', 'error'],
            sleep_time=2,
            time_out=common.VOLUME_TIME_OUT)

        v_ref = volume_client.volumes.get(volume_ref.id)
        if v_ref.status in ['error']:
            raise VolumeCreationFailure()
        LOG.debug(_("end _create_volume for id: %s") % self.id)
        return self._build_volume(v_ref, datastore_manager)

    def _build_volume(self, v_ref, datastore_manager):
        LOG.debug(_("Created volume %s") % v_ref)
        # The mapping is in the format:
        # <id>:[<type>]:[<size(GB)>]:[<delete_on_terminate>]
        # setting the delete_on_terminate instance to true=1
        mapping = "%s:%s:%s:%s" % (v_ref.id, '', v_ref.size, 1)
        bdm = CONF.block_device_mapping
        block_device = {bdm: mapping}
        created_volumes = [{'id': v_ref.id,
                            'size': v_ref.size}]
        LOG.debug("block_device = %s" % block_device)
        LOG.debug("volume = %s" % created_volumes)

        device_path = CONF.device_path
        mount_point = CONF.get(datastore_manager).mount_point
        LOG.debug(_("device_path = %s") % device_path)
        LOG.debug(_("mount_point = %s") % mount_point)

        volume_info = {'block_device': block_device,
                       'device_path': device_path,
                       'mount_point': mount_point,
                       'volumes': created_volumes}
        return volume_info

    def _create_server(self, flavor_id, image_id, security_groups,
                       datastore_manager, block_device_mapping,
                       availability_zone, nics):
        files = {"/etc/guest_info": ("[DEFAULT]\nguest_id=%s\n"
                                     "datastore_manager=%s\n"
                                     "tenant_id=%s\n" %
                                     (self.id, datastore_manager,
                                      self.tenant_id))}
        if os.path.isfile(CONF.get('guest_config')):
            with open(CONF.get('guest_config'), "r") as f:
                files["/etc/trove-guestagent.conf"] = f.read()
        userdata = None
        cloudinit = os.path.join(CONF.get('cloudinit_location'),
                                 "%s.cloudinit" % datastore_manager)
        if os.path.isfile(cloudinit):
            with open(cloudinit, "r") as f:
                userdata = f.read()
        name = self.hostname or self.name
        bdmap = block_device_mapping
        server = self.nova_client.servers.create(
            name, image_id, flavor_id, files=files, userdata=userdata,
            security_groups=security_groups, block_device_mapping=bdmap,
            availability_zone=availability_zone, nics=nics)
        LOG.debug(_("Created new compute instance %(server_id)s "
                    "for id: %(id)s") %
                  {'server_id': server.id, 'id': self.id})
        return server

    def _create_secgroup(self, datastore_manager):
        security_group = SecurityGroup.create_for_instance(
            self.id, self.context)
        tcp_ports = CONF.get(datastore_manager).tcp_ports
        udp_ports = CONF.get(datastore_manager).udp_ports
        self._create_rules(security_group, tcp_ports, 'tcp')
        self._create_rules(security_group, udp_ports, 'udp')
        return [security_group["name"]]

    def _create_rules(self, s_group, ports, protocol):
        err = inst_models.InstanceTasks.BUILDING_ERROR_SEC_GROUP
        err_msg = _("Error creating security group rules."
                    " Invalid port format. "
                    "FromPort = %(from)s, ToPort = %(to)s")

        def set_error_and_raise(port_or_range):
            from_port, to_port = port_or_range
            self.update_db(task_status=err)
            msg = err_msg % {'from': from_port, 'to': to_port}
            raise MalformedSecurityGroupRuleError(message=msg)

        for port_or_range in set(ports):
            try:
                from_, to_ = (None, None)
                from_, to_ = utils.gen_ports(port_or_range)
                cidr = CONF.trove_security_group_rule_cidr
                SecurityGroupRule.create_sec_group_rule(
                    s_group, protocol, int(from_), int(to_),
                    cidr, self.context)
            except (ValueError, TroveError):
                set_error_and_raise([from_, to_])


class OrchestratorBuiltInstanceTasks(common.BuiltInstanceTasksMixin):

    heatclient = None
    UPDATE_COMPLETED = 'UPDATE_COMPLETE'
    UPDATE_FAILED = 'UPDATE_FAILED'
    @property
    def client(self):
        if not self.heatclient:
            self.heatclient = create_heat_client(self.context)
        return self.heatclient

    def _get_stack(self):
        stack_id = self.db_info.stack_id
        stack = self.client.stacks.get(stack_id)
        return stack

    def _update_stack(self, new_parameters, execution_timeout=None):
        try:
            stack = self._get_stack()
            parameters = stack.parameters
            parameters.update(new_parameters)
            self.client.stacks.update(stack_id=self.db_info.stack_id,
                                      parameters=parameters,
                                      template=stack.t)
            try:
                utils.poll_until(
                    lambda: self.client.stacks.get(self.db_info.stack_id),
                    lambda s: s.stack_status in [self.UPDATE_COMPLETED,
                                                 self.UPDATE_FAILED],
                    sleep_time=common.USAGE_SLEEP_TIME,
                    time_out=execution_timeout)
                return stack
            except common.PollTimeOut:
                LOG.error(_("Timeout during stack status tracing"))
                raise TroveError("Timeout occured in tracking stack status")
        except TroveError:
            LOG.error(_("Stack updated failed"))
            raise TroveError("Stack update failed")

    def delete_async(self):
        self._delete_async()

    def _delete_resources(self, deleted_at):
        LOG.debug(_("begin _delete_resources for id: %s") % self.id)
        server_id = self.db_info.compute_instance_id
        old_server = self.nova_client.servers.get(server_id)
        try:
            self.client.stacks.delete(self.db_info.stack_id)
            self._stack_is_deleted()
        except Exception as ex:
            LOG.error(ex)
            LOG.exception(_("Error during delete compute server %s")
                          % old_server.id)

        self._delete_dns_entry()

        self._send_usage_event_on_delete(old_server, deleted_at)

    def _stack_is_deleted(self):
        try:
            utils.poll_until(
                lambda: self.client.stacks.get(self.db_info.stack_id),
                lambda stack: stack.stack_status in ['DELETE_IN_PROGRESS',
                                                     'DELETE_FAILED'],
                sleep_time=common.USAGE_SLEEP_TIME,
                time_out=common.HEAT_TIME_OUT)
        except PollTimeOut:
            LOG.error(_("Timeout during stack status tracing"))
            raise TroveError("Timeout occured in tracking stack status")

    def _load_instance_and_its_datastore_version(self):
        instance = inst_models.DBInstance.find_by(
            self.context, id=self.id)
        dv = DatastoreVersion.load_by_uuid(
            instance.datastore_version_id)

        return instance, dv

    def resize_flavor(self, old_flavor, new_flavor):
        """
        Updates stack base instance with new flavor.
        Rollback enabled by the defaul.
        """
        parameters = {"FlavorRef": new_flavor['name']}
        LOG.info(_("Preparing instance for the restart"))
        self.guest.stop_db()
        LOG.info(_("Updating stack instance resource"))
        stack = self._update_stack(
            parameters, execution_timeout=common.RESIZE_TIME_OUT)
        LOG.info(_("Stack status %s") % stack.stack_status)
        if stack.stack_status == self.UPDATE_FAILED:
            LOG.error(_("Exception occured while resizing instance resource."
                        " Stack was reverted to previous state"))
        instance, dv = self._load_instance_and_its_datastore_version()
        config = self._render_config(
            dv.manager, new_flavor
            if stack.stack_status == self.UPDATE_COMPLETED
            else old_flavor,
            instance.id)
        self.guest.start_db_with_conf_changes(config.config_contents)


class NativeBuiltInstanceTasks(common.BuiltInstanceTasksMixin):
    """
    Performs the various asynchronous instance related tasks.
    """

    def _delete_resources(self, deleted_at):
        LOG.debug(_("begin _delete_resources for id: %s") % self.id)
        server_id = self.db_info.compute_instance_id
        old_server = self.nova_client.servers.get(server_id)
        try:
            self.server.delete()
        except Exception as ex:
            LOG.error(ex)
            LOG.exception(_("Error during delete compute server %s")
                          % self.server.id)

        self._delete_dns_entry()

            # Poll until the server is gone.
        def server_is_finished():
            try:
                server = self.nova_client.servers.get(server_id)
                if not self.server_status_matches(['SHUTDOWN', 'ACTIVE'],
                                                  server=server):
                    LOG.error(_("Server %(server_id)s got into ERROR status "
                                "during delete of instance %(instance_id)s!") %
                              {'server_id': server.id, 'instance_id': self.id})
                return False
            except nova_exceptions.NotFound:
                return True

        try:
            utils.poll_until(server_is_finished, sleep_time=2,
                             time_out=CONF.server_delete_time_out)
        except PollTimeOut:
            LOG.exception(_("Timout during nova server delete of server: %s") %
                          server_id)

        self._send_usage_event_on_delete(old_server, deleted_at)

    def resize_volume(self, new_size):
        LOG.debug(_("begin resize_volume for instance: %s") % self.id)
        action = common.ResizeVolumeAction(self, self.volume_size, new_size)
        action.execute()
        LOG.debug(_("end resize_volume for instance: %s") % self.id)

    def resize_flavor(self, old_flavor, new_flavor):
        action = common.ResizeAction(self, old_flavor, new_flavor)
        action.execute()


class BackupTasks(object):
    @classmethod
    def _parse_manifest(cls, manifest):
        # manifest is in the format 'container/prefix'
        # where prefix can be 'path' or 'lots/of/paths'
        try:
            container_index = manifest.index('/')
            prefix_index = container_index + 1
        except ValueError:
            return None, None
        container = manifest[:container_index]
        prefix = manifest[prefix_index:]
        return container, prefix

    @classmethod
    def delete_files_from_swift(cls, context, filename):
        container = CONF.backup_swift_container
        client = remote.create_swift_client(context)
        obj = client.head_object(container, filename)
        manifest = obj.get('x-object-manifest', '')
        cont, prefix = cls._parse_manifest(manifest)
        if all([cont, prefix]):
            # This is a manifest file, first delete all segments.
            LOG.info(_("Deleting files with prefix: %(cont)s/%(prefix)s") %
                     {'cont': cont, 'prefix': prefix})
            # list files from container/prefix specified by manifest
            headers, segments = client.get_container(cont, prefix=prefix)
            LOG.debug(headers)
            for segment in segments:
                name = segment.get('name')
                if name:
                    LOG.info(_("Deleting file: %(cont)s/%(name)s") %
                             {'cont': cont, 'name': name})
                    client.delete_object(cont, name)
        # Delete the manifest file
        LOG.info(_("Deleting file: %(cont)s/%(filename)s") %
                 {'cont': cont, 'filename': filename})
        client.delete_object(container, filename)

    @classmethod
    def delete_backup(cls, context, backup_id):
        #delete backup from swift
        backup = bkup_models.Backup.get_by_id(context, backup_id)
        try:
            filename = backup.filename
            if filename:
                BackupTasks.delete_files_from_swift(context, filename)
        except ValueError:
            backup.delete()
        except ClientException as e:
            if e.http_status == 404:
                # Backup already deleted in swift
                backup.delete()
            else:
                LOG.exception(_("Exception deleting from swift. "
                                "Details: %s") % e)
                backup.state = bkup_models.BackupState.DELETE_FAILED
                backup.save()
                raise TroveError("Failed to delete swift objects")
        else:
            backup.delete()
