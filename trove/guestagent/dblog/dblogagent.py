# Copyright (c) 2011 OpenStack Foundation
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

import os
from trove.common import cfg
from trove.guestagent import dbaas
from trove.guestagent.strategies.dblog.base import DBLogError
from trove.guestagent.strategies.dblog.impl import DBLogStreamer
from trove.guestagent.strategies.storage import get_storage_strategy
from trove.openstack.common import log as logging

LOG = logging.getLogger(__name__)
CONF = cfg.CONF
Runner = DBLogStreamer


class DBLogRunner(object):

    def execute_dblog_streaming(self, context, log_file):

        description = {'dblog': {}}
        name = "".join(log_file.split("/")[-1:])
        storage = get_storage_strategy(
            CONF.storage_strategy,
            CONF.storage_namespace)(context)
        try:
            with Runner(log_file) as dblog:
                try:
                    LOG.info("Starting log streaming %s", name)
                    success, note, checksum, location = storage.save_dblog(
                        dblog.manifest, dblog)
                    LOG.info("DBLog streaming %s completed status: %s", name,
                             success)
                    LOG.info('DBLog %s file swift checksum: %s',
                             name, checksum)
                    LOG.info('DBLog %s location: %s', name,
                             location)
                    log = {
                        'instance_id': CONF.guest_id,
                        'file': name,
                        'size': "%s Mb" % str(dbaas.to_mb(
                            os.stat(log_file).st_size)),
                        'location': location
                    }
                    description.update({'dblog': log})
                    LOG.info("Result: %s" % description['dblog'])
                    if not success:
                        raise DBLogError(note)
                    return description
                except Exception:
                    LOG.exception("Error saving DBLog %s ", name)
                    raise
        except Exception:
            LOG.exception("Error running DBLog streaming")
            raise
