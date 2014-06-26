#    Copyright 2014 Mirantis, Inc.
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

from trove.common import wsgi
from trove.common.auth import admin_context
from trove.extensions.mgmt.stats import models
from trove.extensions.mgmt.stats import views
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _

LOG = logging.getLogger(__name__)


class StatsInstancesController(wsgi.Controller):
    """Controller for instances stats functionality."""

    @admin_context
    def index(self, req, tenant_id, body=None):
        """Return all instances for all/per tenant(s)."""
        LOG.info(_("req : '%s'\n\n") % req)
        instances = []
        if body:
            if body['tenant_id']:
                instances = models.StatsModels.stats_instances(
                    tenant_id=body['tenant_id'])
        else:
            instances = models.StatsModels.stats_instances()
        data = views.InstancesStatsView(instances).data()
        return wsgi.Result(data, 200)


class StatsBackupsController(wsgi.Controller):
    """Controller for backups stats functionality."""

    @admin_context
    def index(self, req, tenant_id, body=None):
        """Returns all backups for all/per tenant(s)."""
        LOG.info(_("req : '%s'\n\n") % req)
        backups = []
        if body:
            if body['tenant_id']:
                backups = models.StatsModels.stats_backups(
                    tenant_id=body['tenant_id'])
        else:
            backups = models.StatsModels.stats_backups()
        data = views.BackupsStatsView(backups).data()
        return wsgi.Result(data, 200)
