#    Copyright (c) 2014 Mirantis, Inc.
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

from trove.common import cfg
from trove.common import exception
from trove.common.remote import create_guest_client
from trove.instance.models import set_task_status
from trove.instance.tasks import InstanceTasks
from trove.openstack.common import log as logging
from trove.openstack.common.gettextutils import _

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class BaseDatastoreLogMapping(object):
    mapping = {}

    ALLOW_AUDIT = False

    @classmethod
    def get_logging_mapping(cls):
        return cls.mapping


class MySQLDatastoreLogMapping(BaseDatastoreLogMapping):

    ALLOW_AUDIT = (CONF.get('mysql').
                   allow_database_log_files_audit)
    mapping = {
        'general_log': '/var/log/mysql/mysql.log',
        'log_slow_queries': '/var/log/mysql/mysql-slow.log',
        'log-error': '/var/log/mysql/mysql-error.log'
    }


class RedisDatastoreLogMapping(BaseDatastoreLogMapping):

    ALLOW_AUDIT = (CONF.get('redis').
                   allow_database_log_files_audit)
    mapping = {
        'server_log': '/var/log/redis/server.log',
    }


class CassandraDatastoreLogMapping(BaseDatastoreLogMapping):

    ALLOW_AUDIT = (CONF.get('cassandra').
                   allow_database_log_files_audit)
    mapping = {
        'system_log': '/var/log/cassandra/system.log',
    }


class LogFilesMapping(object):

    logs_per_class = {
        'mysql': MySQLDatastoreLogMapping,
        'redis': RedisDatastoreLogMapping,
        'cassandra': CassandraDatastoreLogMapping,
    }

    @classmethod
    def load(cls, manager=None):
        mapper_cls = cls.logs_per_class.get(manager)
        return ((mapper_cls.get_logging_mapping()
                if mapper_cls.ALLOW_AUDIT else {}) if mapper_cls
                and hasattr(mapper_cls, 'get_logging_mapping')
                else {})


class DBLog(object):

    @classmethod
    def save_log_entry(cls, log_file, instance_id, context):
        try:
            set_task_status(context, instance_id,
                            InstanceTasks.IN_PROGRESS)
            guest = create_guest_client(context, instance_id)
            db_log = guest.save_db_log(context, log_file)
            return db_log
        except Exception as e:
            LOG.error(e)
            raise exception.TroveError(
                _("Seems that there is no log file"))
        finally:
            set_task_status(context, instance_id,
                            InstanceTasks.NONE)
