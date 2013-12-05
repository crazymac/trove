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

import contextlib
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy.orm import sessionmaker

from guestagent.common import cfg
from guestagent.openstack.common import log as logging
from guestagent.openstack.common.gettextutils import _

_ENGINE = None
_MAKER = None


LOG = logging.getLogger(__name__)

CONF = cfg.CONF


def configure_db(options, models_mapper=None):
    global _ENGINE
    if not _ENGINE:
        _ENGINE = _create_engine(options)
    if models_mapper:
        models_mapper.map(_ENGINE)


def _create_engine(options):
    engine_args = {
        "pool_recycle": CONF.sql_idle_timeout,
        "echo": CONF.sql_query_log
    }
    LOG.info(_("Creating SQLAlchemy engine with args: %s") % engine_args)
    return create_engine(options['sql_connection'], **engine_args)


def get_session(autocommit=True, expire_on_commit=False):
    """Helper method to grab session."""
    global _MAKER, _ENGINE
    if not _MAKER:
        if not _ENGINE:
            msg = "***The Database has not been setup!!!***"
            LOG.exception(msg)
            raise RuntimeError(msg)
        _MAKER = sessionmaker(bind=_ENGINE,
                              autocommit=autocommit,
                              expire_on_commit=expire_on_commit)
    return _MAKER()


def raw_query(model, autocommit=True, expire_on_commit=False):
    return get_session(autocommit, expire_on_commit).query(model)


def clean_db():
    global _ENGINE
    meta = MetaData()
    meta.reflect(bind=_ENGINE)
    with contextlib.closing(_ENGINE.connect()) as con:
        trans = con.begin()
        for table in reversed(meta.sorted_tables):
            if table.name != "migrate_version":
                con.execute(table.delete())
        trans.commit()


def drop_db(options):
    meta = MetaData()
    engine = _create_engine(options)
    meta.bind = engine
    meta.reflect()
    meta.drop_all()
