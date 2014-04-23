# vim: tabstop=4 shiftwidth=4 softtabstop=4

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


from trove.common import apischema
from trove.common import exception
from trove.common import wsgi
from trove.common.auth import admin_context
from trove.datastore import views
from trove.extensions.mgmt.datastores import models
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _


LOG = logging.getLogger(__name__)


class MgmtDatastoreController(wsgi.Controller):
    """Controller for datastores functionality"""
    schemas = apischema.datastore

    @admin_context
    def create(self, req, body, tenant_id):
        LOG.debug("req : '%s'.\n\n" % req)

        name = body['datastore']['name']
        LOG.info(_("Creating datastore '%s'") % name)
        datastore = models.create_datastore(name)
        view = views.DatastoreView(datastore, [], req)
        return wsgi.Result(view.data(), 200)

    @admin_context
    def update(self, req, body, tenant_id, id):
        LOG.debug("req : '%s'\n\n" % req)
        LOG.info(_("Updating datastore '%s'") % id)

        name = body['datastore'].get('name')
        datastore_version = body['datastore'].get('datastore_version')
        if not (name or datastore_version is not None):
            raise exception.BadRequest(_("Nothing to update."))
        datastore, version = models.update_datastore(
            id, name, datastore_version)
        view = views.DatastoreView(datastore, [version], req)

        return wsgi.Result(view.data(), 200)


class MgmtDatastoreVersionController(wsgi.Controller):
    """Controller for datastore versions functionality"""
    schemas = apischema.version

    @admin_context
    def create(self, req, body, tenant_id, datastore_id):
        LOG.debug("req : '%s'\n\n" % req)

        name = body['version']['name']
        manager = body['version']['manager']
        image_id = body['version']['image_id']
        packages = body['version'].get('packages', "")
        active = body['version'].get('active', True)

        LOG.info(_("Creating datastore version '%s'.") % name)
        version = models.create_version(datastore_id, name, manager, image_id,
                                        packages, active)
        view = views.DatastoreVersionView(version, req)

        return wsgi.Result(view.data(), 200)

    @admin_context
    def update(self, req, body, tenant_id, id, datastore_id=None):
        LOG.debug("req : '%s'\n\n" % req)

        name = body['version'].get('name')
        manager = body['version'].get('manager')
        image_id = body['version'].get('image_id')
        packages = body['version'].get('packages')
        active = body['version'].get('active')

        if not (name or manager or image_id or packages is not None or
                active is not None):
            raise exception.BadRequest(_("Nothing to update."))

        LOG.info(_("Updating datastore version '%s'") % id)
        version = models.update_version(id, datastore_id, name, manager,
                                        image_id, packages, active)
        view = views.DatastoreVersionView(version, req)

        return wsgi.Result(view.data(), 200)
