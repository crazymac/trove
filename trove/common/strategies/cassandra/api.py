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

import six

from novaclient import exceptions as nova_exceptions

from trove.cluster import models
from trove.cluster.tasks import ClusterTasks
from trove.cluster.views import ClusterView
from trove.common import cfg
from trove.common import exception
from trove.common import template
from trove.common import remote
from trove.common.strategies import base
from trove.common.strategies import cassandra
from trove.common.views import create_links
from trove.common import wsgi
from trove.datastore import models as datastore_models
from trove.extensions.mgmt.clusters.views import MgmtClusterView
from trove.instance import models as inst_models
from trove.openstack.common.gettextutils import _
from trove.openstack.common import log as logging
from trove.quota.quota import check_quotas
from trove.taskmanager import api as task_api


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class CassandraRackDatacenter(template.SingleInstanceConfigTemplate):
    template_name = "cassandra-rackdc.properties"


class CassandraAPIStrategy(base.BaseAPIStrategy):

    @property
    def cluster_class(self):
        return CassandraCluster

    @property
    def cluster_controller_actions(self):
        return {
            'add_data_node': self._action_add_data_node,
            'add_seed_node': self._action_add_seed_node,
        }

    def _action_add_data_node(self, cluster, body):
        cluster.add_data_node()
        return wsgi.Result(None, 202)

    def _action_add_seed_node(self, cluster, body):
        cluster.add_seed_node()
        return wsgi.Result(None, 202)

    @property
    def cluster_view_class(self):
        return CassandraClusterView

    @property
    def mgmt_cluster_view_class(self):
        return CassandraMgmtClusterView


class CassandraCluster(models.Cluster):

    @classmethod
    def create(cls, context, name, datastore, datastore_version, instances):

        cassandra_conf = CONF.get(datastore_version.manager)

        num_instances = len(instances)
        if num_instances < cassandra_conf.cluster_size:
            raise exception.ClusterNumInstancesNotSupported(
                num_instances="at least %s" % cassandra_conf.cluster_size)
        deltas = {'instances': len(instances)}

        flavor_ids = [instance['flavor_id'] for instance in instances]
        if len(set(flavor_ids)) != 1:
            raise exception.ClusterFlavorsNotEqual()
        flavor_id = flavor_ids[0]
        nova_client = remote.create_nova_client(context)
        try:
            flavor = nova_client.flavors.get(flavor_id)
        except nova_exceptions.NotFound:
            raise exception.FlavorNotFound(uuid=flavor_id)

        volume_size = None
        volume_sizes = [instance['volume_size'] for instance in instances
                        if instance.get('volume_size', None)]

        if cassandra_conf.volume_support:
            if len(volume_sizes) != num_instances:
                raise exception.ClusterVolumeSizeRequired()
            if len(set(volume_sizes)) != 1:
                raise exception.ClusterVolumeSizesNotEqual()
            volume_size = volume_sizes[0]
            models.validate_volume_size(volume_size)
            deltas['volumes'] = volume_size * len(instances)
        else:
            if len(volume_sizes) > 0:
                raise exception.VolumeNotSupported()
            ephemeral_support = cassandra_conf.device_path
            if ephemeral_support and flavor.ephemeral == 0:
                raise exception.LocalStorageNotSpecified(flavor=flavor_id)

        seed_nodes = [instance for instance in instances
                      if instance.get("type") == cassandra.SEED_NODE]
        data_nodes = [instance for instance in instances
                      if instance.get("type") == cassandra.DATA_NODE]
        if len(seed_nodes) == 0:
            raise exception.CassandraSeedNodeTypeRequired()
        if (len(data_nodes) / len(seed_nodes)
                < cassandra_conf.initial_cluster_data_to_seed_nodes_ratio):
            raise exception.CassandraClusterInvalidClusterInstanceRolesRatio(
                ratio=cassandra_conf.initial_cluster_data_to_seed_nodes_ratio)

        check_quotas(context.tenant, deltas)
        db_info = models.DBCluster.create(
            name=name, tenant_id=context.tenant,
            datastore_version_id=datastore_version.id,
            task_status=ClusterTasks.BUILDING_INITIAL)

        cluster_config = {
            "id": db_info.id,
            "instance_type": cassandra.DATA_NODE
        }
        cluster_config = cls.prepare_snitch_strategy(
            cassandra_conf, datastore_version, cluster_config)

        for i in range(1, len(instances) + 1):
            instance_name = "%s-node-%s" % (name, str(i))
            if i == len(instances):
                cluster_config.update({"instance_type": cassandra.SEED_NODE})
            inst_models.Instance.create(context, instance_name,
                                        flavor_id,
                                        datastore_version.image_id,
                                        [], [], datastore,
                                        datastore_version,
                                        volume_size, None,
                                        availability_zone=None,
                                        nics=None,
                                        configuration_id=None,
                                        cluster_config=cluster_config)
        task_api.load(context, datastore_version.manager).create_cluster(
            db_info.id)

        return CassandraCluster(context, db_info, datastore, datastore_version)

    @classmethod
    def prepare_snitch_strategy(cls, cassandra_conf,
                                datastore_version, cluster_config):
        if (cassandra_conf.endpoint_snitch_strategy
                == cassandra.GOSSIP_FILE_SNITCH_STRATEGY):
            rackdc_config = CassandraRackDatacenter(
                datastore_models.DatastoreVersion(
                    datastore_version), None, None)
            rackdc_config.render()
            inject_files = [
                {
                    "path": "/etc/cassandra/cassandra-rackdc.properties",
                    "content": rackdc_config.config_contents
                }]
            cluster_config.update({"inject_files": inject_files})

        return cluster_config

    def _add_node(self, cluster_config, task_status):
        if self.db_info.task_status != ClusterTasks.NONE:
            current_task = self.db_info.task_status.name
            msg = _("This action cannot be performed on the cluster while "
                    "the current cluster task is '%s'.") % current_task
            LOG.error(msg)
            raise exception.UnprocessableEntity(msg)

        nodes = inst_models.DBInstance.find_all(cluster_id=self.id).all()
        node_template = inst_models.load_any_instance(
            self.context, nodes[0].id)
        deltas = {'instances': 1}
        volume_size = node_template.volume_size
        if volume_size:
            deltas['volumes'] = volume_size
        check_quotas(self.context.tenant, deltas)
        cassandra_conf = CONF.get(node_template.datastore_version.manager)
        cluster_config = self.prepare_snitch_strategy(
            cassandra_conf, node_template.datastore_version, cluster_config)
        node = inst_models.Instance.create(
            self.context,
            "%s-node-%s" % (self.name, str(len(nodes) + 1)),
            node_template.flavor_id,
            node_template.datastore_version.image_id,
            [], [], node_template.datastore,
            node_template.datastore_version,
            volume_size, None,
            availability_zone=None,
            nics=None,
            configuration_id=None,
            cluster_config=cluster_config)

        self.update_db(task_status=task_status)
        manager = (datastore_models.DatastoreVersion.
                   load_by_uuid(node_template.datastore_version.id).manager)
        return node, manager

    def add_data_node(self):
        node, manager = self._add_node(
            {'id': self.id,
             'instance_type': cassandra.DATA_NODE},
            ClusterTasks.ADDING_DATA_NODE)
        task_api.load(
            self.context, manager
        ).cassandra_add_data_node_to_cluster(self.id, node.id)

    def add_seed_node(self):
        node, manager = self._add_node(
            {'id': self.id,
             'instance_type': cassandra.SEED_NODE},
            ClusterTasks.ADDING_SEED_NODE)
        task_api.load(
            self.context, manager
        ).cassandra_add_seed_node_to_cluster(self.id, node.id)


class CassandraClusterView(ClusterView):

    def build_instances(self):
        instances = []
        ip_list = []
        if self.load_servers:
            cluster_instances = self.cluster.instances
        else:
            cluster_instances = self.cluster.instances_without_server
        for instance in cluster_instances:
            instance_dict = {
                "id": instance.id,
                "type": instance.type,
                "name": instance.name,
                "links": create_links("instances", self.req, instance.id)
            }
            if self.load_servers:
                ips = instance.get_visible_ip_addresses()
                if ips and (isinstance(ips, list) and len(ips) > 0):
                    ip_list.append(ips[0])
                instance_dict["status"] = instance.status
                if CONF.get(instance.datastore_version.manager).volume_support:
                    instance_dict["volume"] = {"size": instance.volume_size}
                instance_dict["flavor"] = self._build_flavor_info(
                    instance.flavor_id)
            instances.append(instance_dict)
        return instances, ip_list


class MetaMRO(type):
    def mro(cls):
        return cls, CassandraClusterView, MgmtClusterView, object


@six.add_metaclass(MetaMRO)
class CassandraMgmtClusterView(CassandraClusterView, MgmtClusterView):
    pass
