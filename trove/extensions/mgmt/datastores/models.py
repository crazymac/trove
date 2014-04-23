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

from trove.common import exception
from trove.common import utils
from trove.datastore import models as ds_models


def create_datastore(name):
    if ds_models.DBDatastore.find_all(name=name).count() > 0:
        raise exception.DatastoreAlreadyExists(datastore=name)
    datastore = ds_models.DBDatastore()
    datastore.id = utils.generate_uuid()
    datastore.name = name
    datastore.save()
    datastore = ds_models.Datastore.load(datastore.id)
    return datastore


def update_datastore(id_or_name, new_name, datastore_version):
    version = None
    datastore_id = ds_models.Datastore.load(id_or_name).id
    datastore = ds_models.DBDatastore.find_by(id=datastore_id)
    if new_name:
        if ds_models.DBDatastore.find_all(name=new_name).count() > 0:
            raise exception.DatastoreAlreadyExists(datastore=new_name)
        datastore.name = new_name
    if datastore_version:
        version = ds_models.DatastoreVersion.load(datastore, datastore_version)
        if not version.active:
            raise exception.DatastoreVersionInactive(version=
                                                     version.name)
        datastore.default_version_id = version.id
    elif datastore_version == "":
        datastore.default_version_id = None
    datastore.save()
    datastore = ds_models.Datastore.load(datastore.id)
    return datastore, version


def create_version(datastore_id, name, manager, image_id, packages, active):
    datastore = ds_models.Datastore.load(datastore_id)
    if ds_models.DBDatastoreVersion.find_all(datastore_id=datastore.id,
                                             name=name).count() > 0:
        raise exception.DatastoreVersionAlreadyExists(
            version=name, datastore=datastore.name)
    version = ds_models.DBDatastoreVersion()
    version.id = utils.generate_uuid()
    version.name = name
    version.datastore_id = datastore.id
    version.manager = manager
    version.image_id = image_id
    version.packages = packages
    version.active = active
    version.save()
    version = ds_models.DatastoreVersion.load_by_uuid(version.id)
    return version


def update_version(id_or_name, datastore_id, new_name, manager, image_id,
                   packages, active):
    if datastore_id:
        datastore = ds_models.Datastore.load(datastore_id)
        version_id = ds_models.DatastoreVersion.load(datastore, id_or_name).id
    else:
        version_id = ds_models.DatastoreVersion.load_by_uuid(id_or_name).id
    version = ds_models.DBDatastoreVersion.find_by(id=version_id)
    if new_name:
        version.name = new_name
    if manager:
        version.manager = manager
    if image_id:
        version.image_id = image_id
    if packages is not None:
        version.packages = packages
    if active is not None:
        version.active = active
    version.save()
    version = ds_models.DatastoreVersion.load_by_uuid(version.id)
    return version
