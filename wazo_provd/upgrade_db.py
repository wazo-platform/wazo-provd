# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os

import alembic.command
import alembic.config
from sqlalchemy import create_engine

import wazo_provd.config
from wazo_provd.database.helpers import wait_is_ready

logger = logging.getLogger(__name__)


def upgrade(uri: str) -> None:
    current_dir = os.path.dirname(__file__)
    config = alembic.config.Config(f'{current_dir}/database/alembic.ini')
    config.set_main_option('script_location', f'{current_dir}/database/alembic')
    config.set_main_option('sqlalchemy.url', uri)
    config.set_main_option('configure_logging', 'false')

    logger.info('Upgrading database')
    engine = create_engine(uri)
    wait_is_ready(engine)
    alembic.command.upgrade(config, 'head')
    logger.info('Database upgraded')


def upgrade_db() -> None:
    conf = wazo_provd.config.get_config(wazo_provd.config.Options())
    upgrade(conf['database']['uri'])
