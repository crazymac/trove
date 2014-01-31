#   Copyright (c) 2014 Mirantis, Inc.
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

from trove.common import exception
from trove.common.utils import import_class
from trove.extensions import extension_interface as ext
from trove.datastore.models import DatastoreVersion
from trove.instance.models import DBInstance
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _

LOG = logging.getLogger(__name__)


def _get_controller(controller, req, instance_id):

    context = req.environ[ext.CONTEXT_KEY]
    try:
        db_info = DBInstance.find_by(
            context, instance_id=instance_id)
        manager = DatastoreVersion.load_by_uuid(
            db_info.datastore_version_id).manager
        class_str = ("trove.extensions.%s.service.%s"
                     % (manager, controller))
        controller = import_class(class_str)
        return controller
    except (exception.ModelNotFoundError, ImportError):
        LOG.error(_("Exception while getting controller class"))
        LOG.exception()


class CommonRootController(ext.RootController):

    def index(self, req, tenant_id, instance_id):
        result = (_get_controller(
            self.controller, req, instance_id).
            index(self, req, tenant_id, instance_id))
        return result

    def create(self, req, tenant_id, instance_id):
        result = (_get_controller(
            self.controller, req, instance_id).
            create(self, req, tenant_id, instance_id))
        return result


class CommonUserController(ext.UserController):
    def index(self, req, tenant_id, instance_id):
        result = (_get_controller(
            self.controller, req, instance_id).
            index(self, req, tenant_id, instance_id))
        return result

    def create(self, req, body, tenant_id, instance_id):
        result = (_get_controller(
            self.controller, req, instance_id).
            create(self, req, body, tenant_id, instance_id))
        return result

    def delete(self, req, tenant_id, instance_id, id):
        result = (_get_controller(
            self.controller, req, instance_id).
            delete(self, req, tenant_id, instance_id, id))
        return result

    def update(self, req, body, tenant_id, instance_id, id):
        result = (_get_controller(
            self.controller, req, instance_id).
            update(self, req, body, tenant_id, instance_id, id))
        return result

    def update_all(self, req, body, tenant_id, instance_id):
        result = (_get_controller(
                  self.controller, req, instance_id).update_all(
                  self, req, body, tenant_id, instance_id))
        return result


class CommonUserAccessController(ext.UserAccessController):

    def index(self, req, tenant_id, instance_id, user_id):
        result = (_get_controller(
            self.controller, req, instance_id).
            index(self, req, tenant_id, instance_id, user_id))
        return result

    def update(self, req, body, tenant_id, instance_id, user_id):
        result = (_get_controller(
            self.controller, req, instance_id).
            update(self, req, body, tenant_id, instance_id, user_id))
        return result

    def delete(self, req, tenant_id, instance_id, user_id, id):
        result = (_get_controller(
            self.controller, req, instance_id).
            delete(self, req, tenant_id, instance_id, user_id, id))
        return result


class CommonSchemaController(ext.SchemaController):

    def index(self, req, tenant_id, instance_id):
        result = (_get_controller(
            self.controller, req, instance_id).
            index(self, req, tenant_id, instance_id))
        return result

    def create(self, req, body, tenant_id, instance_id):
        result = (_get_controller(
            self.controller, req, instance_id).
            create(self, req, body, tenant_id, instance_id))
        return result

    def delete(self, req, tenant_id, instance_id, id):
        result = (_get_controller(
            self.controller, req, instance_id).
            delete(self, req, tenant_id, instance_id, id))
        return result

    def show(self, req, tenant_id, instance_id, id):
        result = (_get_controller(
            self.controller, req, instance_id).
            show(self, req, tenant_id, instance_id, id))
        return result
