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


from trove.taskmanager import models

from trove.taskmanager.resources import base

RPC_API_VERSION = base.RPC_API_VERSION
ENGINE = "orchestrator"


class Orchestrator(base.BaseManager):

    def __init__(self):
        super(Orchestrator, self).__init__()

    def delete_instance(self, context, instance_id):
        instance_tasks = models.OrchestratorBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.delete_async()

    def create_instance(self, context, instance_id, name, flavor,
                        image_id, databases, users, datastore_manager,
                        packages, volume_size, backup_id, availability_zone,
                        root_password, nics, overrides):

        instance_tasks = models.OrchestratorFreshInstanceTask.load(
            context, instance_id)
        instance_tasks.update_db(provisioning_engine=ENGINE)
        instance_tasks.create_instance(
            flavor, image_id, databases, users,
            datastore_manager, packages,
            volume_size, backup_id,
            availability_zone, root_password, nics,
            overrides
        )

    def resize_flavor(self, context, instance_id, old_flavor, new_flavor):
        instance_tasks = models.OrchestratorBuiltInstanceTasks.load(
            context, instance_id)
        instance_tasks.resize_flavor(old_flavor, new_flavor)
