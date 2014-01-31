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


from trove.common import wsgi

CONTEXT_KEY = wsgi.CONTEXT_KEY
Result = wsgi.Result


class RootController(wsgi.Controller):
    """
    This controller class responsible
    for root user operation. Each new datastore which will
    support rootenabling should inherit
    controller from this controller class
    """
    controller = "RootController"

    def index(self, req, tenant_id, instance_id):
        pass

    def create(self, req, tenant_id, instance_id):
        pass


class UserController(wsgi.Controller):
    """
    This controller class responsible
    for users operation. Each new datastore which will support users
    should inherit controller from this controller class
    """
    controller = "UserController"

    def index(self, req, tenant_id, instance_id):
        pass

    def delete(self, req, tenant_id, instance_id, id):
        pass

    def create(self, req, body, tenant_id, instance_id):
        pass

    def show(self, req, tenant_id, instance_id, id):
        pass

    def update(self, req, body, tenant_id, instance_id, id):
        pass

    def update_all(self, req, body, tenant_id, instance_id):
        pass


class UserAccessController(wsgi.Controller):
    """
    This controller class responsible
    for users operation. Each new datastore which will support root
    enabling should inherit controller from this controller class
    """

    controller = "UserAccessController"

    def index(self, req, tenant_id, instance_id, user_id):
        pass

    def update(self, req, body, tenant_id, instance_id, user_id):
        pass

    def delete(self, req, tenant_id, instance_id, user_id, id):
        pass


class SchemaController(wsgi.Controller):
    """
    This controller class responsible
    for databases operation. Each new datastore which will support databases
    should inherit controller from this controller class
    """
    controller = "SchemaController"

    def index(self, req, tenant_id, instance_id):
        pass

    def create(self, req, body, tenant_id, instance_id):
        pass

    def delete(self, req, tenant_id, instance_id, id):
        pass

    def show(self, req, tenant_id, instance_id, id):
        pass
