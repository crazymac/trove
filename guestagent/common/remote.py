# Copyright 2010-2012 OpenStack Foundation
# Copyright 2013 Mirantis Inc
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

from guestagent.common import cfg
from guestagent.openstack.common.importutils import import_class
from swiftclient.client import Connection

CONF = cfg.CONF

COMPUTE_URL = CONF.nova_compute_url
PROXY_AUTH_URL = CONF.trove_auth_url
VOLUME_URL = CONF.cinder_url
OBJECT_STORE_URL = CONF.swift_url
USE_SNET = CONF.backup_use_snet
HEAT_URL = CONF.heat_url


def guest_client(context, id):
    from guestagent.agent.api import API
    return API(context, id)


def swift_client(context):
    client = Connection(preauthurl=OBJECT_STORE_URL + context.tenant,
                        preauthtoken=context.auth_token,
                        tenant_name=context.tenant,
                        snet=USE_SNET)
    return client


create_guest_client = import_class(CONF.remote_guest_client)
create_swift_client = import_class(CONF.remote_swift_client)
