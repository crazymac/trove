#   Copyright 2014 Mirantis, Inc.
#   All Rights Reserved.
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

from trove.db import get_db_api
from trove.backup.models import DBBackup
from trove.instance import models as instance_models
from trove.openstack.common import log as logging

LOG = logging.getLogger(__name__)
db_api = get_db_api()


class StatsModels(object):

    @classmethod
    def stats_instances(cls, tenant_id=None):
        condition_1 = (instance_models.InstanceServiceStatus.instance_id
                       == instance_models.DBInstance.id)
        condition_2 = instance_models.DBInstance.deleted == 0
        condition_3 = instance_models.DBInstance.tenant_id == tenant_id

        instances = instance_models.DBInstance.find_all().join(
            instance_models.InstanceServiceStatus, condition_1)

        if tenant_id:
            db_info = (instances.filter(condition_2, condition_3).
                       add_entity(instance_models.InstanceServiceStatus))
        else:
            db_info = (instances.filter(condition_2).add_entity(
                       instance_models.InstanceServiceStatus))

        instances = []
        attrs_list = ["id", "tenant_id", "name", "flavor_id", "hostname",
                      "volume_size", "compute_instance_id", "created",
                      "server_status", "task_start_time"]

        for instance, status in db_info:
            instance_data = {}
            for attr in attrs_list:
                instance_data.update({attr: getattr(instance, attr)})

            instance_data["task"] = instance.task_status.action
            instance_data["task_description"] = instance.task_status.db_text
            instance_data["status"] = status.status.api_status
            instance_data["status_description"] = status.status.description
            instance_data["status_updated_at"] = status.updated_at

            instances.append(instance_data)

        return instances

    @classmethod
    def stats_backups(cls, tenant_id=None):
        conditions = {"deleted": False}
        if tenant_id:
            conditions.update({"tenant_id": tenant_id})
        db_info = DBBackup.find_all(**conditions)
        backups = []
        attr_list = ["id", "tenant_id", "name", "description",
                     "backup_type", "size", "state", "instance_id",
                     "backup_timestamp", "created", "updated"]
        for backup in db_info:
            backup_data = {}
            for attr in attr_list:
                backup_data.update({attr: getattr(backup, attr)})
            backups.append(backup_data)
        return backups
