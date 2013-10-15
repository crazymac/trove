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
CASSANDRA_MOUNT_POINT = "/var/lib/cassandra"


UPDATE_CONFIG_ON_INSTALL = """echo "rpc_address: 0.0.0.0" |
sudo tee -a /etc/cassandra/cassandra.yaml>/dev/null"""

UNABLE_CASSANDRA_ON_BOOT = "sudo update-rc.d cassandra enable"
DISABLE_CASSANDRA_ON_BOOT = "sudo update-rc.d cassandra disable"

START_CASSANDRA = "sudo service cassandra start"
STOP_CASSANDRA = "sudo service cassandra stop"
RESTART_CASSANDRA = "sudo service cassandra restart"

CASSANDRA_STATUS = """nodetool statusthrift"""

CASSANDRA_KILL = "sudo pkill -9 cassandra"

TIME_OUT = 10000
CASSANDRA_PACKAGE = 'cassandra=1.2.10'
