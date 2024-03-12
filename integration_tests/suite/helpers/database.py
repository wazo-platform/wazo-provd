# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor


class DatabaseClient(MagicMock):
    def __init__(self, db_uri: str):
        super().__init__()
        self._db_uri = db_uri

    @contextmanager
    def connection(self):
        with psycopg2.connect(self._db_uri) as connection:
            yield connection

    @contextmanager
    def transaction(self, connection) -> DictCursor:
        try:
            with connection.cursor(cursor_factory=DictCursor) as cursor:
                yield cursor
                connection.commit()
        except psycopg2.DatabaseError:
            print("Database error encountered. Rolling back.")
            connection.rollback()
            raise

    async def runQuery(
        self,
        query: sql.Composed,
        variables: dict | None = None,
    ) -> list[tuple]:
        with self.connection() as conn:
            with self.transaction(conn) as cursor:
                cursor.execute(query, vars=variables)
                return cursor.fetchall()

    async def runOperation(
        self,
        query: sql.Composed,
        variables: dict | None = None,
    ) -> None:
        with self.connection() as conn:
            with self.transaction(conn) as cursor:
                cursor.execute(query, vars=variables)