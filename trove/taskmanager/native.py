# Copyright 2011 OpenStack Foundation
# All Rights Reserved.
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

import trove.common.cfg as cfg
from trove.common import exception
from trove.openstack.common import log as logging
from trove.taskmanager import common
from trove.taskmanager import models

from trove.taskmanager import base

LOG = logging.getLogger(__name__)
RPC_API_VERSION = base.RPC_API_VERSION
CONF = cfg.CONF
ENGINE = "native"


class Native(base.BaseManager):

    def __init__(self):
        super(Native, self).__init__()

    def resize_volume(self, context, instance_id, new_size):
        instance_tasks = models.NativeBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.resize_volume(new_size)

    def resize_flavor(self, context, instance_id, old_flavor, new_flavor):
        instance_tasks = models.NativeBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.resize_flavor(old_flavor, new_flavor)

    def reboot(self, context, instance_id):
        instance_tasks = models.NativeBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.reboot()

    def restart(self, context, instance_id):
        instance_tasks = models.NativeBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.restart()

    def migrate(self, context, instance_id, host):
        instance_tasks = models.NativeBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.migrate(host)

    def delete_instance(self, context, instance_id):
        try:
            instance_tasks = models.NativeBuiltInstanceTasks.load(
                context, instance_id)
            instance_tasks.delete_async()
        except exception.UnprocessableEntity:
            instance_tasks = common.FreshInstanceTaskMixin.load(
                context, instance_id)
            instance_tasks.delete_async()

    def delete_backup(self, context, backup_id):
        models.BackupTasks.delete_backup(context, backup_id)

    def create_backup(self, context, backup_info, instance_id):
        instance_tasks = models.NativeBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.create_backup(backup_info)

    def create_instance(self, context, instance_id, name, flavor,
                        image_id, databases, users, datastore_manager,
                        packages, volume_size, backup_id, availability_zone,
                        root_password, nics, overrides):
        instance_tasks = models.NativeFreshInstanceTasks.load(
            context, instance_id)
        instance_tasks.update_db(provisioning_engine=ENGINE)
        instance_tasks.create_instance(
            flavor, image_id, databases, users,
            datastore_manager, packages,
            volume_size, backup_id,
            availability_zone, root_password, nics,
            overrides
        )

    def update_overrides(self, context, instance_id, overrides):
        instance_tasks = models.NativeBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.update_overrides(overrides)

    def unassign_configuration(self, context, instance_id, flavor,
                               configuration_id):
        instance_tasks = models.NativeBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.unassign_configuration(flavor, configuration_id)
