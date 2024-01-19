# Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from twisted.enterprise import adbapi
from wazo_test_helpers import until


class SynchronousDatabaseAdapter:
    def __init__(self, connection_pool: adbapi.ConnectionPool):
        self._pool = connection_pool
        self._pool.start()

    def stop(self) -> None:
        self._pool.close()

    def execute(self, query: str) -> Any:
        result = None

        def query_ok(query_result):
            nonlocal result
            result = query_result

        def query_error(err):
            err.raiseException()

        def query_has_result():
            nonlocal result
            return result is not None

        res = self._pool.runQuery(query)
        res.addCallbacks(query_ok, query_error)

        until.true(query_has_result, tries=10)
        return result
