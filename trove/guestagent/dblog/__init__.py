#   Mirantis Inc. 2013
#   All Rights Reserved.
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

from trove.guestagent.dblog import dblogagent

AGENT = dblogagent.DBLogRunner()
PossibleException = dblogagent.DBLogError


def save_dbinstance_log(context, log_file):
    """
    Main entry point for starting a log streaming based on the given log_file.
    This will create a log entry for this DB instance and will
    then store the it in a configured repository in specific
    container (e.g. Swift)

    :param context:     the context token which contains the users details
    :param log_file:     fully-qualified file path
    """
    return AGENT.execute_dblog_streaming(context, log_file)
