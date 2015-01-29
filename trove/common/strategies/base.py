# Copyright 2014 eBay Software Foundation
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

import functools
from eventlet.timeout import Timeout

from trove.common import exception
from trove.common.i18n import _
from trove.openstack.common import log as logging

LOG = logging.getLogger(__name__)


def decorate_cluster_action(action):

    @functools.wraps(action)
    def wrapper(self, *args, **kwargs):
        timeout = Timeout(kwargs.pop('timeout'))
        LOG.debug("Action: %s. Action timeout: %s" % (
            action.__name__, timeout.seconds))
        try:
            action(self, *args, **kwargs)
        except (Timeout, exception.TroveError, Exception) as e:
            LOG.exception(_("Error during action: %(action)s execution. "
                            "Exception: %(e)s")
                          % {"e": e, "action": action})

            # in common case callback just updates statuses
            # of resources and allows user to terminate cluster/node
            callback = kwargs.pop('callback', None)
            if callback and callable(callback):
                callback(*args)

            # recoverer tries to recover cluster to previous state
            recoverer = kwargs.pop('recoverer', None)
            if recoverer and callable(recoverer):
                recoverer(*args)

            if e is not timeout:
                raise exception.ClusterActionError(
                    action="%s.%s" % (
                        self.__class__.__name__,
                        action.__name__),
                    datastore=self.datastore.name,
                    cluster_id=self.id)
            LOG.exception(_("timeout for cluster action."))
        finally:
            self.reset_task()
            timeout.cancel()

    return wrapper


class BaseAPIStrategy(object):

    @property
    def cluster_class(self):
        raise NotImplementedError()

    @property
    def cluster_controller_actions(self):
        raise NotImplementedError()

    @property
    def cluster_view_class(self):
        raise NotImplementedError()

    @property
    def mgmt_cluster_view_class(self):
        raise NotImplementedError()


class BaseTaskManagerStrategy(object):

    @property
    def task_manager_api_class(self, context):
        raise NotImplementedError()

    @property
    def task_manager_cluster_tasks_class(self, context):
        raise NotImplementedError()


class BaseGuestAgentStrategy(object):

    @property
    def guest_client_class(self):
        raise NotImplementedError()
