# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed
from twisted.enterprise import adbapi

logger = logging.getLogger(__name__)

DATABASE_DRIVER = 'psycopg2'


def init_db(db_uri: str, pool_size=16) -> adbapi.ConnectionPool:
    return adbapi.ConnectionPool(
        DATABASE_DRIVER, db_uri, cp_max=pool_size, cp_reconnect=True, cp_noisy=True
    )


@retry(
    stop=stop_after_attempt(60 * 5),
    wait=wait_fixed(1),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
def wait_is_ready(connection):
    try:
        # Try to create session to check if DB is awake
        connection.execute('SELECT 1')
    except Exception as e:
        logger.warning('fail to connect to the database: %s', e)
        raise
