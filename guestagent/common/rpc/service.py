# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation
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
#

import inspect
import os

from guestagent.openstack.common import importutils
from guestagent.openstack.common import loopingcall
from guestagent.openstack.common.rpc import service as rpc_service
from guestagent.common import cfg

CONF = cfg.CONF


class RpcService(rpc_service.Service):

    def __init__(self, host=None, binary=None, topic=None, manager=None):
        host = host or CONF.host
        binary = binary or os.path.basename(inspect.stack()[-1][1])
        topic = topic or binary.rpartition('trove-')[2]
        self.manager_impl = importutils.import_object(manager)
        self.report_interval = CONF.report_interval
        super(RpcService, self).__init__(host, topic,
                                         manager=self.manager_impl)

    def start(self):
        super(RpcService, self).start()
        # TODO(hub-cap): Currently the context is none... do we _need_ it here?
        pulse = loopingcall.LoopingCall(self.manager_impl.run_periodic_tasks,
                                        context=None)
        pulse.start(interval=self.report_interval,
                    initial_delay=self.report_interval)
        pulse.wait()
