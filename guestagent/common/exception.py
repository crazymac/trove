# Copyright 2011 OpenStack Foundation
# Copyright 2013 Mirantis Inc
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
"""I totally stole most of this from melange, thx guys!!!"""


import re

from guestagent.openstack.common import log as logging
from guestagent.openstack.common import exception as openstack_exception
from guestagent.openstack.common import processutils
from guestagent.openstack.common.gettextutils import _

from webob import exc

ClientConnectionError = openstack_exception.ClientConnectionError
ProcessExecutionError = processutils.ProcessExecutionError
DatabaseMigrationError = openstack_exception.DatabaseMigrationError
LOG = logging.getLogger(__name__)
wrap_exception = openstack_exception.wrap_exception


def safe_fmt_string(text):
    return re.sub(r'%([0-9]+)', r'\1', text)


class GuestagentError(openstack_exception.OpenstackException):
    """Base exception that all custom guesagent app exceptions inherit from."""
    internal_message = None

    def __init__(self, message=None, **kwargs):
        if message is not None:
            self.message = message
        if self.internal_message is not None:
            try:
                LOG.error(safe_fmt_string(self.internal_message) % kwargs)
            except Exception:
                LOG.error(self.internal_message)
        self.message = safe_fmt_string(self.message)
        super(GuestagentError, self).__init__(**kwargs)


class DBConstraintError(GuestagentError):

    message = _("Failed to save %(model_name)s because: %(error)s")


class InvalidRPCConnectionReuse(GuestagentError):

    message = _("Invalid RPC Connection Reuse")


class NotFound(GuestagentError):

    message = _("Resource %(uuid)s cannot be found")


class FlavorNotFound(GuestagentError):

    message = _("Resource %(uuid)s cannot be found")


class UserNotFound(NotFound):

    message = _("User %(uuid)s cannot be found on the instance.")


class DatabaseNotFound(NotFound):

    message = _("Database %(uuid)s cannot be found on the instance.")


class ComputeInstanceNotFound(NotFound):

    internal_message = _("Cannot find compute instance %(server_id)s for "
                         "instance %(instance_id)s.")

    message = _("Resource %(instance_id)s can not be retrieved.")


class DnsRecordNotFound(NotFound):

    message = _("DnsRecord with name= %(name)s not found.")


class DatastoreNotFound(NotFound):

    message = _("Datastore '%(datastore)s' cannot be found.")


class DatastoreVersionNotFound(NotFound):

    message = _("Datastore version '%(version)s' cannot be found.")


class DatastoresNotFound(NotFound):

    message = _("Datastores cannot be found.")


class DatastoreNoVersion(GuestagentError):

    message = _("Datastore '%(datastore)s' has no version '%(version)s'.")


class DatastoreVersionInactive(GuestagentError):

    message = _("Datastore version '%(version)s' is not active.")


class DatastoreDefaultDatastoreNotFound(GuestagentError):

    message = _("Please specify datastore.")


class DatastoreDefaultVersionNotFound(GuestagentError):

    message = _("Default version for datastore '%(datastore)s' not found.")


class OverLimit(GuestagentError):

    internal_message = _("The server rejected the request due to its size or "
                         "rate.")


class QuotaExceeded(GuestagentError):

    message = _("Quota exceeded for resources: %(overs)s")


class VolumeQuotaExceeded(QuotaExceeded):

    message = _("Instance volume quota exceeded.")


class GuestError(GuestagentError):

    message = _("An error occurred communicating with the guest: "
                "%(original_message)s.")


class GuestTimeout(GuestagentError):

    message = _("Timeout trying to connect to the Guest Agent.")


class BadRequest(GuestagentError):

    message = _("The server could not comply with the request since it is "
                "either malformed or otherwise incorrect.")


class MissingKey(BadRequest):

    message = _("Required element/key - %(key)s was not specified")


class DatabaseAlreadyExists(BadRequest):

    message = _('A database with the name "%(name)s" already exists.')


class UserAlreadyExists(BadRequest):

    message = _('A user with the name "%(name)s" already exists.')


class UnprocessableEntity(GuestagentError):

    message = _("Unable to process the contained request")


class CannotResizeToSameSize(GuestagentError):

    message = _("When resizing, instances must change size!")


class VolumeAttachmentsNotFound(NotFound):

    message = _("Cannot find the volumes attached to compute "
                "instance %(server_id)")


class VolumeCreationFailure(GuestagentError):

    message = _("Failed to create a volume in Nova.")


class VolumeSizeNotSpecified(BadRequest):

    message = _("Volume size was not specified.")


class LocalStorageNotSpecified(BadRequest):

    message = _("Local storage not specified in flavor ID: %(flavor)s.")


class LocalStorageNotSupported(GuestagentError):

    message = _("Local storage support is not enabled.")


class VolumeNotSupported(GuestagentError):

    message = _("Volume support is not enabled.")


class TaskManagerError(GuestagentError):

    message = _("An error occurred communicating with the task manager: "
                "%(original_message)s.")


class BadValue(GuestagentError):

    message = _("Value could not be converted: %(msg)s")


class PollTimeOut(GuestagentError):

    message = _("Polling request timed out.")


class Forbidden(GuestagentError):

    message = _("User does not have admin privileges.")


class InvalidModelError(GuestagentError):

    message = _("The following values are invalid: %(errors)s")


class ModelNotFoundError(NotFound):

    message = _("Not Found")


class UpdateGuestError(GuestagentError):

    message = _("Failed to update instances")


class ConfigNotFound(NotFound):

    message = _("Config file not found")


class PasteAppNotFound(NotFound):

    message = _("Paste app not found.")


class QuotaNotFound(NotFound):
    message = _("Quota could not be found")


class TenantQuotaNotFound(QuotaNotFound):
    message = _("Quota for tenant %(tenant_id)s could not be found.")


class QuotaResourceUnknown(QuotaNotFound):
    message = _("Unknown quota resources %(unknown)s.")


class BackupUploadError(GuestagentError):
    message = _("Unable to upload Backup onto swift")


class BackupDownloadError(GuestagentError):
    message = _("Unable to download Backup from swift")


class BackupCreationError(GuestagentError):
    message = _("Unable to create Backup")


class BackupUpdateError(GuestagentError):
    message = _("Unable to update Backup table in db")


class SecurityGroupCreationError(GuestagentError):

    message = _("Failed to create Security Group.")


class SecurityGroupDeletionError(GuestagentError):

    message = _("Failed to delete Security Group.")


class SecurityGroupRuleCreationError(GuestagentError):

    message = _("Failed to create Security Group Rule.")


class SecurityGroupRuleDeletionError(GuestagentError):

    message = _("Failed to delete Security Group Rule.")


class BackupNotCompleteError(GuestagentError):

    message = _("Unable to create instance because backup %(backup_id)s is "
                "not completed")


class BackupFileNotFound(NotFound):
    message = _("Backup file in %(location)s was not found in the object "
                "storage.")


class SwiftAuthError(GuestagentError):

    message = _("Swift account not accessible for tenant %(tenant_id)s.")


class DatabaseForUserNotInDatabaseListError(GuestagentError):
    message = _("The request indicates that user %(user)s should have access "
                "to database %(database)s, but database %(database)s is not "
                "included in the initial databases list.")


class DatabaseInitialDatabaseDuplicateError(GuestagentError):
    message = _("Two or more databases share the same name in the initial "
                "databases list. Please correct the names or remove the "
                "duplicate entries.")


class DatabaseInitialUserDuplicateError(GuestagentError):
    message = _("Two or more users share the same name and host in the "
                "initial users list. Please correct the names or remove the "
                "duplicate entries.")


class RestoreBackupIntegrityError(GuestagentError):

    message = _("Current Swift object checksum does not match original "
                "checksum for backup %(backup_id)s.")
