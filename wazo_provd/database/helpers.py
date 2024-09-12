# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from psycopg2 import errorcodes
from psycopg2.errors import OperationalError
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed
from twisted.enterprise import adbapi

logger = logging.getLogger(__name__)

DATABASE_DRIVER = 'psycopg2'


class ReconnectingConnectionPool(adbapi.ConnectionPool):
    """
    This connection pool will reconnect if the server goes away.  This idea was taken from:
    http://www.gelens.org/2009/09/13/twisted-connectionpool-revisited/
    """

    def _runInteraction(self, interaction, *args, **kw):
        try:
            return adbapi.ConnectionPool._runInteraction(self, interaction, *args, **kw)
        except OperationalError as e:
            if e.pgcode not in (errorcodes.ADMIN_SHUTDOWN, errorcodes.CRASH_SHUTDOWN):
                raise
            logger.error(
                "Lost connection to the database, retrying operation.  If no errors follow, retry was successful."
            )
            conn = self.connections.get(self.threadID())
            self.disconnect(conn)
            return adbapi.ConnectionPool._runInteraction(self, interaction, *args, **kw)


def init_db(db_uri: str, pool_size=16) -> adbapi.ConnectionPool:
    return ReconnectingConnectionPool(
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
