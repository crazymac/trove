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

from trove.common.context import TroveContext

import trove.extensions.mgmt.instances.models as mgmtmodels
from trove.common import exception
from trove.common import cfg

from trove.taskmanager import models
from trove.openstack.common import log as logging
from trove.openstack.common import importutils
from trove.openstack.common import periodic_task

LOG = logging.getLogger(__name__)
RPC_API_VERSION = "1.0"
CONF = cfg.CONF


class BaseManager(periodic_task.PeriodicTasks):

    def __init__(self):
        super(BaseManager, self).__init__()
        self.admin_context = TroveContext(
            user=CONF.nova_proxy_admin_user,
            auth_token=CONF.nova_proxy_admin_pass,
            tenant=CONF.nova_proxy_admin_tenant_name)
        if CONF.exists_notification_transformer:
            self.exists_transformer = importutils.import_object(
                CONF.exists_notification_transformer,
                context=self.admin_context)

    def resize_volume(self, context, instance_id, new_size):
        raise exception.OperationIsNotSuppotedByTaskmanager(
            operation="resize_volume")

    def resize_flavor(self, context, instance_id, old_flavor, new_flavor):
        raise exception.OperationIsNotSuppotedByTaskmanager(
            operation="resize_flavor")

    def migrate(self, context, instance_id, host):
        raise exception.OperationIsNotSuppotedByTaskmanager(
            operation="migrate")

    def create_instance(self, context, instance_id, name, flavor,
                        image_id, databases, users, datastore_manager,
                        packages, volume_size, backup_id, availability_zone,
                        root_password, nics, overrides):
        raise exception.OperationIsNotSuppotedByTaskmanager(
            operation="create_instance")

    def delete_instance(self, context, instance_id):
        raise exception.OperationIsNotSuppotedByTaskmanager(
            operation="delete_instance")

    def reboot(self, context, instance_id):
        instance_tasks = models.OrchestratorBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.reboot()

    def restart(self, context, instance_id):
        instance_tasks = models.OrchestratorBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.restart()

    def delete_backup(self, context, backup_id):
        models.BackupTasks.delete_backup(context, backup_id)

    def create_backup(self, context, backup_info, instance_id):
        instance_tasks = models.OrchestratorBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.create_backup(backup_info)

    def update_overrides(self, context, instance_id, overrides):
        instance_tasks = models.OrchestratorBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.update_overrides(overrides)

    def unassign_configuration(self, context, instance_id, flavor,
                               configuration_id):
        instance_tasks = models.OrchestratorBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.unassign_configuration(flavor, configuration_id)

    if CONF.exists_notification_transformer:
        @periodic_task.periodic_task(
            ticks_between_runs=CONF.exists_notification_ticks)
        def publish_exists_event(self, context):
            """
            Push this in Instance Tasks to fetch a report/collection
            :param context: currently None as specied in bin script
            """
            mgmtmodels.publish_exist_events(self.exists_transformer,
                                            self.admin_context)
