#  Copyright 2014 Mirantis Inc.
#  All Rights Reserved.
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

from trove.common import cfg
from trove.common.strategies import base
from trove.guestagent import api as guest_api
from trove.openstack.common import log as logging

CONF = cfg.CONF
CASSANDRA_CONF = CONF.get('cassandra')
LOG = logging.getLogger(__name__)

# RPC workflow variables
VERIFICATION_TIMEOUT = (
    CASSANDRA_CONF.cluster_status_verification_timeout)
TOKEN_MODIFICATION_TIMEOUT = (
    CASSANDRA_CONF.token_modification_timeout)
CLUSTER_CONFIG_RETRIEVER_TIMEOUT = (
    CASSANDRA_CONF.cluster_config_retriever_timeout)
LOCAL_SCHEMA_RESETTER_TIMEOUT = (
    CASSANDRA_CONF.node_local_schema_resetter_timeout
)


class CassandraGuestAgentStrategy(base.BaseGuestAgentStrategy):

    @property
    def guest_client_class(self):
        return CassandraDbGuestAgentAPI


class CassandraDbGuestAgentAPI(guest_api.API):

    def cluster_complete(self):
        LOG.debug("Calling cluster_complete for cluster %s." % self.id)
        return self._cast("cluster_complete",
                          self.version_cap)

    def verify_cluster_is_running(self, cluster_ips):
        LOG.debug("Calling verify_cluster_is_running for cluster %s."
                  % self.id)
        return self._call("verify_cluster_is_running",
                          VERIFICATION_TIMEOUT,
                          self.version_cap,
                          cluster_ips=cluster_ips)

    def update_seed_provider(self, seed_ips):
        LOG.debug("Calling update_seed_provider for cluster %s."
                  % self.id)
        self._cast("update_seed_provider", self.version_cap,
                   seed_ips=seed_ips)

    def setup_tokens(self):
        LOG.debug("Calling setup_tokens for cluster %s." % self.id)
        return self._call("setup_tokens", TOKEN_MODIFICATION_TIMEOUT,
                          self.version_cap,)

    def get_cluster_config(self):
        LOG.debug("Calling get_cluster_config for cluster %s." % self.id)
        return self._call("get_cluster_config",
                          CLUSTER_CONFIG_RETRIEVER_TIMEOUT,
                          self.version_cap,)

    def drop_system_keyspace(self):
        LOG.debug("Calling drop_system_keyspace for cluster %s." % self.id)
        return self._call("drop_system_keyspace", guest_api.AGENT_HIGH_TIMEOUT,
                          self.version_cap,)

    def reset_local_schema(self):
        LOG.debug("Calling reset_local_schema for cluster %s." % self.id)
        return self._call("reset_local_schema", LOCAL_SCHEMA_RESETTER_TIMEOUT,
                          self.version_cap,)
