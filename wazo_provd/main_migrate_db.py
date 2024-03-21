# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import logging

from xivo.chain_map import ChainMap
from xivo.config_helper import read_config_file_hierarchy
from xivo.user_rights import change_user
from xivo.xivo_logging import setup_logging

from wazo_provd.config import _DEFAULT_CONFIG

logger = logging.getLogger(__name__)
USER = 'wazo-provd'
LOGFILE = '/var/log/wazo-provd.log'


def parse_args(parser):
    parser.add_argument(
        '-d',
        '--debug',
        action='store_true',
        help="Log debug messages. Overrides log_level. Default: %(default)s",
    )
    return parser.parse_args()


def main():
    parser = argparse.ArgumentParser(description='wazo-provd database migrator')
    options = parse_args(parser)

    file_config = {
        key: value
        for key, value in read_config_file_hierarchy(_DEFAULT_CONFIG).items()
        if key in ('database')
    }
    config = ChainMap(file_config, _DEFAULT_CONFIG)

    change_user(USER)

    debug = config['general']['verbose'] or options.debug
    setup_logging(LOGFILE, debug=debug)

    migrate_data(config)


def migrate_data(config):
    logger.info('Migrate wazo-provd data from jsondb to pg...')
    # migration
    logger.info('wazo-provd data migrated!')
