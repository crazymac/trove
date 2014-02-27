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

from trove.dbinstance_log.models import LogFilesMapping
from trove.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class DatastoreVersionDBLogView(object):
    def __init__(self, datastore_v, req=None):
        self.datastore_v = datastore_v
        self.req = req

    def data(self):
        mapping = LogFilesMapping.load(
            manager=self.datastore_v.manager)
        dbinstance_log = {
            "datastore_version_manager": self.datastore_v.manager,
            "datastore_log_files": " | ".join(mapping.keys()) + ""
        }
        return {'dblog': dbinstance_log}


class DatastoreVersionsDBLogView(object):
    def __init__(self, datastore_vs, req=None):
        self.datastore_vs = datastore_vs
        self.req = req

    def data(self):
        data = []
        for dstore_v in self.datastore_vs:
            data.append(self.data_for_datastore(dstore_v))
        return {'dblogs': data}

    def data_for_datastore(self, datastore_v):
        view = DatastoreVersionDBLogView(datastore_v, req=self.req)
        return view.data()['dblog']


class InstanceDBLogView(object):
    def __init__(self, description, req=None):
        self.db_log = description
        self.req = req

    def data(self):
        return {"dblog": self.db_log['dblog']}
