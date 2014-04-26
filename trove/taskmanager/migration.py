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

from trove.instance import models as i_models
from trove.taskmanager import base
from trove.taskmanager import native
from trove.taskmanager import orchestrator
from trove.openstack.common import log as logging

NATIVE_ENGINE = native.ENGINE
LOG = logging.getLogger(__name__)
RPC_API_VERSION = base.RPC_API_VERSION


class Migration(orchestrator.Orchestrator):

    def __init__(self):
        super(Migration, self).__init__()
        self.native_manager = native.Native()

    def resize_volume(self, context, instance_id, new_size):
        db_info = i_models.get_db_info(context, instance_id)
        if db_info.provisioning_engine in (None, NATIVE_ENGINE):
            self.native_manager.resize_volume(
                context, instance_id, new_size)
        else:
            super(Migration, self).resize_volume(
                context, instance_id, new_size)

    def resize_flavor(self, context, instance_id, old_flavor, new_flavor):
        db_info = i_models.get_db_info(context, instance_id)
        if db_info.provisioning_engine in (None, NATIVE_ENGINE):
            self.native_manager.resize_flavor(
                context, instance_id, old_flavor, new_flavor)
        else:
            super(Migration, self).resize_flavor(
                context, instance_id, old_flavor, new_flavor)

    def delete_instance(self, context, instance_id):
        db_info = i_models.get_db_info(context, instance_id)
        if db_info.provisioning_engine in (None, NATIVE_ENGINE):
            self.native_manager.delete_instance(context, instance_id)
        else:
            super(Migration, self).delete_instance(context, instance_id)
