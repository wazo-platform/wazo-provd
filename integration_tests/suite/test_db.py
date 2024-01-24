# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .helpers.base import DBIntegrationTest
from .helpers.wait_strategy import EverythingOkWaitStrategy


class TestDatabaseIsUp(DBIntegrationTest):
    asset = 'database'
    wait_strategy = EverythingOkWaitStrategy

    def test_that_database_launches(self) -> None:
        self.start_postgres_service()
        self.stop_postgres_service()
