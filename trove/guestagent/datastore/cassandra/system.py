#
#  Copyright 2013 Mirantis Inc.
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
#
import yaml
import socket

from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _

LOG = logging.getLogger(__name__)

CASSANDRA_MOUNT_POINT = "/var/lib/cassandra"
CASSANDRA_CONF = "/etc/cassandra/cassandra.yaml"

UNABLE_CASSANDRA_ON_BOOT = "sudo update-rc.d cassandra enable"
DISABLE_CASSANDRA_ON_BOOT = "sudo update-rc.d cassandra disable"

START_CASSANDRA = "sudo service cassandra start"
STOP_CASSANDRA = "sudo service cassandra stop"
RESTART_CASSANDRA = "sudo service cassandra restart"

CASSANDRA_STATUS = """nodetool statusthrift"""

CASSANDRA_KILL = "sudo pkill -9 cassandra"

TIME_OUT = 10000
CASSANDRA_PACKAGE = 'cassandra=1.2.10'


def update_config_with(key, value):
    LOG.info(_("Opening cassandra.yaml"))
    with open(CASSANDRA_CONF, 'rw') as config:
        LOG.info(_("Preparing YAML object from cassandra.yaml"))
        yamled = yaml.load(config.read())
        LOG.info(_("Updating YAML object from cassandra.yaml with parameter "
                   "%(key)s which value is %(value)s") % {'key': key,
                                                          'value': value})
        yamled.update({key: value})


def get_host():
    return socket.gethostbyname("%s.local" % socket.gethostname())
