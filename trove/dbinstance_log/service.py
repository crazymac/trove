#    Mirantis Inc. 2014
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

import trove.common.apischema as apischema
from trove.common import cfg
from trove.common import exception
from trove.common import wsgi
from trove.datastore import models as dstore_models
from trove.datastore.models import DatastoreVersion
from trove.dbinstance_log import models as dblob_models
from trove.dbinstance_log import views
from trove.instance import models as i_models
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class DBLogController(wsgi.Controller):

    schemas = apischema.dbinstance_log.copy()

    def index(self, req, tenant_id):
        LOG.info(_("Listing a log files "
                   "entry per datastore/version"
                   "for tenant '%s'") % tenant_id)
        LOG.info(_("req : '%s'\n\n") % req)
        datastores = dstore_models.Datastores.load()
        datastores_v = []
        for dstore in datastores:
            for v in dstore_models.DatastoreVersions.load(dstore.id):
                datastores_v.append(v)
        view = views.DatastoreVersionsDBLogView(datastores_v, req)
        return wsgi.Result(view.data(), 200)

    def show(self, req, tenant_id, id):
        LOG.info(_("req : '%s'\n\n") % req)
        dstore_v = dstore_models.DatastoreVersion.load_by_uuid(id)
        LOG.info(_("Listing a log files "
                   "entry for datastore_version %(dstore_v)s"
                   "for tenant %(tenant_id)s")
                 % {'tenant_id': tenant_id, 'dstore_v': dstore_v.name})
        view = views.DatastoreVersionDBLogView(dstore_v, req)
        return wsgi.Result(view.data(), 200)

    def create(self, req, tenant_id, body):
        LOG.info(_("Creating a log file "
                   "entry for tenant '%s'") % tenant_id)
        LOG.info(_("req : '%s'\n\n") % req)
        LOG.info(_("body : '%s'\n\n") % body)
        context = req.environ[wsgi.CONTEXT_KEY]
        try:
            instance_id = body['dblog']['instance']
            log_name = body['dblog']['file']
        except KeyError as ve:
            raise exception.BadRequest(message=ve)
        db_info = i_models.get_db_info(context, id=instance_id)
        instance_status = i_models.InstanceServiceStatus.find_by(
            context, instance_id=instance_id).get_status()
        if not instance_status.action_is_allowed:
            raise exception.BadRequest(
                message=_("Instance is not ready. Current status: %s")
                % instance_status)
        manager = (DatastoreVersion.load_by_uuid(
            db_info.datastore_version_id).manager)
        mapping = dblob_models.LogFilesMapping.load(manager=manager)
        if mapping:
            if log_name not in mapping.keys():
                msg = _("Wrong file mentioned")
                raise exception.BadRequest(message=msg)
        else:
            raise exception.BadRequest(message=_("Audit not supported "
                                                 "for given datastore"))
        try:
            description = dblob_models.DBLog.save_log_entry(
                mapping.get(log_name), instance_id, context)
            view = views.InstanceDBLogView(description, req)
            return wsgi.Result(view.data(), 200)
        except Exception as e:
            raise exception.BadRequest(msg=str(e))
