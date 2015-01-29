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
import time
import yaml

from trove.common import cfg
from trove.common import exception
from trove.common.instance import ServiceStatuses
from trove.common.strategies import base
from trove.common import utils
from trove.common import template
from trove.common.strategies import cassandra
from trove.instance.models import DBInstance
from trove.instance.models import Instance
from trove.instance.models import InstanceServiceStatus
from trove.instance.tasks import InstanceTasks
from trove.openstack.common.gettextutils import _
from trove.openstack.common import log as logging
from trove.taskmanager import api as task_api
from trove.taskmanager import models as task_models


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
USAGE_SLEEP_TIME = CONF.usage_sleep_time  # seconds.


class CassandraTaskManagerStrategy(base.BaseTaskManagerStrategy):

    @property
    def task_manager_api_class(self):
        return CassandraTaskManagerAPI

    @property
    def task_manager_cluster_tasks_class(self):
        return CassandraClusterTasks

    @property
    def task_manager_manager_actions(self):
        return {
            'add_data_node_to_cluster': self._manager_add_data_node,
            'add_seed_node_to_cluster': self._manager_add_seed_node
        }

    def _manager_add_data_node(self, context, cluster_id, node_id):
        cluster_tasks = task_models.ClusterTasks.load(
            context,
            cluster_id,
            CassandraClusterTasks)
        cluster_tasks.add_data_node_to_cluster(
            context, cluster_id, node_id)

    def _manager_add_seed_node(self, context, cluster_id, node_id):
        cluster_tasks = task_models.ClusterTasks.load(
            context,
            cluster_id,
            CassandraClusterTasks)
        cluster_tasks.add_seed_node_to_cluster(
            context, cluster_id, node_id)


class CassandraClusteringWorkflow(task_models.ClusterTasks):

    def verify_cluster_is_running(self, cluster_guests, ips_to_verify=None):
        cluster_ips = (
            set(sorted([self.get_ip(instance) for instance in self.instances]))
            if not ips_to_verify else ips_to_verify)
        LOG.debug("Cluster IPs: %s." % cluster_ips)
        statuse_by_node_id = {}
        statuses = []
        for guest in cluster_guests:
            status = guest.verify_cluster_is_running(set(cluster_ips))
            LOG.debug("Cluster status is %s for instance %s" %
                      (status, guest.id))
            statuse_by_node_id.update({guest.id: status})
            statuses.append(status)
            guest.cluster_complete()

        if len(set(statuses)) != 1 or 'OK' not in set(statuses):
            raise exception.TroveError(
                _("Unable to configure cluster: %(id)s. "
                  "One or more instance is not visible to other "
                  "cluster nodes. Node statuses: %(statuse_by_node_id)s."
                  ) % {'id': self.id,
                       'statuse_by_node_id': statuse_by_node_id})

    def update_status_on_fail(self, context, cluster_id, node_id):
        if CONF.update_status_on_fail:
            db_instance = DBInstance.find_by(context, id=node_id)
            db_instance.set_task_status(
                InstanceTasks.BUILDING_ERROR_SERVER)
            db_instance.save()
            self.update_db()

    def update_statuses_on_failure(self, context, cluster_id):
        if CONF.update_status_on_fail:
            db_instances = DBInstance.find_all(
                cluster_id=cluster_id).all()
            for db_instance in db_instances:
                db_instance.set_task_status(
                    InstanceTasks.BUILDING_ERROR_SERVER)
                db_instance.save()
            self.update_db()

    def _check_cluster_nodes_are_active(self, cluster_id):
        # fetch instances by cluster_id against instances table
        db_instances = DBInstance.find_all(cluster_id=cluster_id).all()
        instance_ids = [db_instance.id for db_instance in db_instances]
        LOG.debug("instances in cluster %s: %s" % (cluster_id,
                                                   instance_ids))

        # checks if all instances are in ACTIVE state
        if not self._all_instances_ready(instance_ids, cluster_id):
            raise exception.TroveError(
                message=_("Instances for cluster %(id)s are "
                          "not ready.") % {"id": self.id})

    def _all_instances_ready(self, instance_ids, cluster_id):

        def _all_status_ready(ids):
            LOG.debug("Checking service status of instance ids: %s" % ids)
            for instance_id in ids:
                status = InstanceServiceStatus.find_by(
                    instance_id=instance_id).get_status()
                if (status == ServiceStatuses.FAILED or
                   status == ServiceStatuses.FAILED_TIMEOUT_GUESTAGENT):
                        # if one has failed, no need to continue polling
                        LOG.debug("Instance %s in %s, exiting polling." % (
                            instance_id, status))
                        return True
                if (status != ServiceStatuses.RUNNING and
                   status != ServiceStatuses.BUILD_PENDING):
                        # if one is not in a ready state, continue polling
                        LOG.debug("Instance %s in %s, continue polling." % (
                            instance_id, status))
                        return False
            LOG.debug("Instances are ready, exiting polling for: %s" % ids)
            return True

        def _instance_ids_with_failures(ids):
            LOG.debug("Checking for service status failures for "
                      "instance ids: %s" % ids)
            failed_instance_ids = []
            for instance_id in ids:
                status = InstanceServiceStatus.find_by(
                    instance_id=instance_id).get_status()
                if (status == ServiceStatuses.FAILED or
                   status == ServiceStatuses.FAILED_TIMEOUT_GUESTAGENT):
                        failed_instance_ids.append(instance_id)
            return failed_instance_ids

        def all_instances_are_ready():
            return _all_status_ready(instance_ids)

        LOG.debug("Polling until service status is ready for "
                  "instance ids: %s" % instance_ids)
        try:
            utils.poll_until(all_instances_are_ready,
                             sleep_time=USAGE_SLEEP_TIME,
                             time_out=CONF.usage_timeout * len(instance_ids))
        except exception.PollTimeOut:
            LOG.exception(_("Timeout for all instance service statuses "
                            "to become ready."))
            self.update_statuses_on_failure(self.context, cluster_id)
            return False

        failed_ids = _instance_ids_with_failures(instance_ids)
        if failed_ids:
            LOG.error(_("Some instances failed to become ready: %s") %
                      failed_ids)
            self.update_statuses_on_failure(self.context, cluster_id)
            return False

        return True

    def reboot(self, node, node_guestagent):
        node.update_db(
            task_status=InstanceTasks.BUILDING)
        node.set_servicestatus_new()
        node_guestagent.restart(wait_until_active=False)
        # required to wait until guest will restart
        # datastore and update its status
        time.sleep(10)

    def apply_config(self, nodes, config, reboot=True):
        for node in nodes:
            guest = self.get_guest(node)
            guest.update_overrides(config)
            guest.drop_system_keyspace()
            if reboot:
                self.reboot(node, guest)

    @base.decorate_cluster_action
    def _create_cluster(self, context, cluster_id, **kwargs):

        cassandra_conf = CONF.cassandra
        num_tokens = cassandra_conf.num_tokens_per_instance
        partitioner = cassandra_conf.cluster_partitioner
        endpoint_snith = cassandra_conf.endpoint_snitch_strategy

        # fetch instances by cluster_id against instances table
        instances, instance_ids = self._get_instance_objectest_and_ids()
        LOG.debug("Instances in cluster %s: %s" % (cluster_id,
                                                   instance_ids))

        # check if server is ACTIVE
        LOG.debug("Running server status check.")
        self._all_servers_ready()

        # checks if all instances are in ACTIVE state
        LOG.debug("Running datastore status check.")
        if not self._all_instances_ready(instance_ids, self.id):
            raise exception.TroveError(
                message=_("Instances for cluster %(id)s are "
                          "not ready.") % {"id": self.id})

        instances, instance_ids = self._get_instance_objectest_and_ids(
            require_server=True)
        seed_nodes = [instance for instance in instances
                      if instance.type == cassandra.SEED_NODE]
        seed_node_ids = [data_node.id for data_node in seed_nodes]
        data_nodes = [instance for instance in instances
                      if instance.type == cassandra.DATA_NODE]

        cluster_ips = [self.get_ip(instance) for instance in instances]

        # collects seed nodes IPs
        seed_node_ips = str(", ".join([self.get_ip(seed_node)
                                       for seed_node in seed_nodes]))

        # sets up cassandra.yaml for all datanodes
        config_template = template.SingleInstanceConfigTemplate(
            instances[0].datastore_version,
            None, instances[0].id).render()

        cassandra_conf_file = yaml.load(config_template)

        cassandra_conf_file['cluster_name'] = str(self.name)

        cassandra_conf_file['num_tokens'] = num_tokens
        cassandra_conf_file['partitioner'] = partitioner
        cassandra_conf_file['endpoint_snitch'] = endpoint_snith

        LOG.debug("Preparing seed nodes.")
        #for seed nodes
        for seed_node in seed_nodes:
            (cassandra_conf_file.
             get('seed_provider')[0].
             get('parameters')[0].
             update({'seeds': self.get_ip(seed_node)}))
            self.apply_config(
                [seed_node],
                yaml.safe_dump(cassandra_conf_file,
                               default_flow_style=False),
                reboot=True)
        # seed node should be ACTIVE before datanodes to
        # prevent communication problems
        LOG.debug("Polling seed node datastore statuses.")
        if not self._all_instances_ready(seed_node_ids, cluster_id):
            raise exception.TroveError(
                message=_("Instances for cluster %(id)s are "
                          "not ready.") % {"id": self.id})

        # for data nodes
        (cassandra_conf_file.
         get('seed_provider')[0].
         get('parameters')[0].
         update({'seeds': seed_node_ips}))

        LOG.debug("Preparing data nodes.")
        for data_node in data_nodes:
            guest = self.get_guest(data_node)
            self.apply_config(
                [data_node],
                yaml.safe_dump(cassandra_conf_file,
                               default_flow_style=False),
                reboot=True)
            # checks if datanode are in ACTIVE state
            if not self._all_instances_ready(
                    [data_node.id], cluster_id):
                raise exception.TroveError(
                    message=_("Instances for cluster %(id)s are "
                              "not ready.") % {"id": self.id})
            guest.reset_local_schema()

        # sets up tokens on all cluster nodes
        LOG.debug("Seting up cluster tokens for each cluster node.")
        for instance in instances:
            guest = self.get_guest(instance)
            guest.setup_tokens()
            self.reboot(instance, guest)
            # checks if all nodes (both seeds and datanodes)
            # are in ACTIVE state
            if not self._all_instances_ready([instance.id],
                                             cluster_id):
                raise exception.TroveError(
                    message=_("Instances for cluster %(id)s are "
                              "not ready.") % {"id": self.id})

        # it may appear that Cassand would take some
        # time to terminate MessagingService, so it's required
        # to wait and check if instances are ACTIVE before
        # checking cluster discoverability
        LOG.debug("Polling cluster node datastore statuses.")
        if not self._all_instances_ready(instance_ids, self.id):
            raise exception.TroveError(
                message=_("Instances for cluster %(id)s are "
                          "not ready.") % {"id": self.id})

        # checks if each cluster node can discover others
        self.verify_cluster_is_running([self.get_guest(instance)
                                        for instance in instances],
                                       ips_to_verify=cluster_ips)

        for instance in instances:
            instance.reset_task_status()

    def _get_instance_objectest_and_ids(self, require_server=False):
        instances = [instance for instance
                     in (self.instances_without_server
                     if not require_server else self.instances)]
        instance_ids = [instance.id for instance in instances]
        return instances, instance_ids

    def _get_any_node_by_its_type(self, cluster_nodes, instance_type,
                                  instance_exception_ids=[]):
        """
        Retrieves {data_|seed_} node instance object by given
        type and instance exception ids

        @param cluster_nodes List of cluster instances
        @type cluster_nodes list

        @param instance_type cluster node type
        @type instance_type basestring

        @param instance_exception_ids instances that would be excluded
                                      from iteration check
        @type instance_exception_ids list
        """

        for node in cluster_nodes:
            if (node.type == instance_type
               and node.id not in instance_exception_ids):

                return node

    @base.decorate_cluster_action
    def _add_data_node(self, context, cluster_id, node_id, **kwargs):

        LOG.debug("Running server status check.")
        self._all_servers_ready()

        LOG.debug("Running service status checks for all instances.")
        self._check_cluster_nodes_are_active(cluster_id)

        instances, ids = self._get_instance_objectest_and_ids()
        cluster_guests = [self.get_guest(instance) for instance in instances]
        cluster_ips = [self.get_ip(instance) for instance in instances]
        LOG.debug("Getting data node templete for provisioning needs.")
        datanode = self._get_any_node_by_its_type(
            instances, cassandra.DATA_NODE, instance_exception_ids=[node_id])
        LOG.debug("Data node template info: %s." % datanode.__dict__)

        LOG.debug("Running service status checks for all instances.")
        if not self._all_instances_ready([node_id], cluster_id):
            raise exception.TroveError(
                message=_("Instances for cluster %(id)s are "
                          "not ready.") % {"id": self.id})

        new_datanode = Instance.load(context, node_id)
        LOG.debug("New data node info: %s." % new_datanode.__dict__)
        new_datanode_guest = self.get_guest(new_datanode)
        datanode_config = yaml.load(
            self.get_guest(datanode).get_cluster_config())
        datanode_config.update(
            {
                'rpc_address': "0.0.0.0",
                'broadcast_rpc_address': self.get_ip(new_datanode),
                'listen_address': self.get_ip(new_datanode)
            }
        )
        del datanode_config['initial_token']
        LOG.debug("New data node config template: %s." % datanode_config)
        dump = yaml.safe_dump(datanode_config, default_flow_style=False)

        LOG.debug("Updating new data node configuration "
                  "file and rebooting.")
        self.apply_config([new_datanode], dump, reboot=True)
        LOG.debug("Waiting until new data node will become ACTIVE.")
        if not self._all_instances_ready([node_id], self.id):
            raise exception.TroveError(
                message=_("Instances for cluster %(id)s are "
                          "not ready.") % {"id": self.id})

        LOG.debug("Setting up tokens on new data node.")
        new_datanode_guest.setup_tokens()
        LOG.debug("Rebooting datastore to apply new/updated "
                  "configuration options.")
        self.reboot(new_datanode, new_datanode_guest)
        LOG.debug("Waiting until new data node will become ACTIVE.")
        if not self._all_instances_ready([node_id], self.id):
            raise exception.TroveError(
                message=_("Instances for cluster %(id)s are "
                          "not ready.") % {"id": self.id})

        LOG.debug("Verifying that cluster is running.")
        self.verify_cluster_is_running(cluster_guests,
                                       ips_to_verify=cluster_ips)

        LOG.debug("Reseting new data node's local schema to force "
                  "it to re-sync data.")
        new_datanode_guest.reset_local_schema()
        new_datanode.reset_task_status()

    @base.decorate_cluster_action
    def _add_seed_node(self, context, cluster_id, node_id, **kwargs):

        LOG.debug("Running server status check.")
        self._all_servers_ready()

        LOG.debug("Running service status checks for all instances.")
        self._check_cluster_nodes_are_active(cluster_id)

        new_seed_node = Instance.load(context, node_id)
        new_seed_guest = self.get_guest(new_seed_node)

        instances, ids = self._get_instance_objectest_and_ids(
            require_server=True)
        cluster_guests = [self.get_guest(instance) for instance in instances]
        cluster_ips = [self.get_ip(instance) for instance in instances]
        datanodes = [instance for instance in instances
                     if instance.type == cassandra.DATA_NODE]
        LOG.debug("Cluster data nodes IDs: %s" % ", ".join([
            datanode.id for datanode in datanodes]))
        seed_nodes_ips = str(", ".join(
            [self.get_ip(instance) for instance in instances
             if instance.type == cassandra.SEED_NODE]))
        LOG.debug("Cluster seed IPs: %s." % seed_nodes_ips)
        new_seed_node_ip = self.get_ip(new_seed_node)
        LOG.debug("New seed IP: %s." % new_seed_node_ip)
        seed_node_template = self._get_any_node_by_its_type(
            instances, cassandra.SEED_NODE,
            instance_exception_ids=[node_id])
        LOG.debug("Seed node template ID: %s." % seed_node_template.id)
        seed_node_template_guest = self.get_guest(seed_node_template)

        new_seed_node_conf = yaml.load(
            seed_node_template_guest.get_cluster_config())
        new_seed_node_conf.update(
            {
                'rpc_address': "0.0.0.0",
                'broadcast_rpc_address': new_seed_node_ip,
                'listen_address': new_seed_node_ip
            }
        )
        del new_seed_node_conf['initial_token']
        LOG.debug("New data node config template: %s." % new_seed_node_conf)
        dump = yaml.safe_dump(new_seed_node_conf, default_flow_style=False)
        LOG.debug("Updating new data node configuration "
                  "file and rebooting.")
        self.apply_config([new_seed_node], dump, reboot=True)
        if not self._all_instances_ready([node_id], self.id):
            raise exception.TroveError(
                message=_("Instances for cluster %(id)s are "
                          "not ready.") % {"id": self.id})

        LOG.debug("Setting up tokens on new data node.")
        new_seed_guest.setup_tokens()
        LOG.debug("Rebooting datastore to apply new/updated "
                  "configuration options.")
        self.reboot(new_seed_node, new_seed_guest)
        LOG.debug("Waiting until new data node will become ACTIVE.")
        if not self._all_instances_ready([node_id], self.id):
            raise exception.TroveError(
                message=_("Instances for cluster %(id)s are "
                          "not ready.") % {"id": self.id})

        for datanode in datanodes:
            guest = self.get_guest(datanode)

            # Question: there are two ways to apply new seed
            # node provider to each data node:
            #
            # 1. Get data node config ->
            #    set seed provider ->
            #    apply config -> reboot.
            #
            # 2. Get seed node IPs ->
            #    send seed node IPs to guest (using specific RPC API) ->
            #    let guest update only seed provider -> reboot.

            guest.update_seed_provider(seed_nodes_ips)
            self.reboot(datanode, guest)
        LOG.debug("Running service status checks for all instances.")
        self._check_cluster_nodes_are_active(cluster_id)

        self.verify_cluster_is_running(cluster_guests,
                                       ips_to_verify=cluster_ips)

        LOG.debug("Reseting new data node's local schema to force "
                  "it to re-sync data.")
        new_seed_guest.reset_local_schema()

        new_seed_node.reset_task_status()

    def recover_cluster_from_failed_seed_node(
            self, context, cluster_id, node_id):
        #TODO(denis_makogon): implement recoverer for different cluster action
        pass


class CassandraClusterTasks(CassandraClusteringWorkflow):

    def create_cluster(self, context, cluster_id):
        LOG.debug("begin create_cluster for id: %s" % cluster_id)
        self._create_cluster(context, cluster_id,
                             callback=self.update_statuses_on_failure,
                             timeout=
                             len(self.instances_without_server)
                             * CONF.usage_timeout)
        LOG.debug("end create_cluster for id: %s" % cluster_id)

    def add_data_node_to_cluster(self, context, cluster_id, node_id):
        LOG.debug("begin add_data_node_to_cluster for id: %s" % cluster_id)
        self._add_data_node(context, cluster_id, node_id,
                            callback=self.update_status_on_fail,
                            timeout=CONF.usage_timeout)
        LOG.debug("end add_data_node_to_cluster for id: %s" % cluster_id)

    def add_seed_node_to_cluster(self, context, cluster_id, node_id):
        LOG.debug("start add_seed_node_to_cluster for id: %s" % cluster_id)
        self._add_seed_node(context, cluster_id, node_id,
                            callback=self.update_status_on_fail,
                            timeout=
                            (len(self.instances_without_server) - 1)
                            * CONF.usage_timeout,
                            recoverer=
                            self.recover_cluster_from_failed_seed_node)
        LOG.debug("end add_seed_node_to_cluster for id: %s" % cluster_id)


class CassandraTaskManagerAPI(task_api.API):

    def cassandra_add_data_node_to_cluster(
            self, cluster_id, node_id):
        LOG.debug("Making async call to add node to"
                  " cluster %s " % cluster_id)
        cctxt = self.client.prepare(version=self.version_cap)
        cctxt.cast(self.context,
                   "cassandra_add_data_node_to_cluster",
                   cluster_id=cluster_id, node_id=node_id)

    def cassandra_add_seed_node_to_cluster(
            self, cluster_id, node_id):
        LOG.debug("Making async call to add seed node to"
                  " cluster %s " % cluster_id)
        cctxt = self.client.prepare(version=self.version_cap)
        cctxt.cast(self.context, "cassandra_add_seed_node_to_cluster",
                   cluster_id=cluster_id, node_id=node_id)
