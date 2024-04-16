# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, equal_to

from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import EverythingOkWaitStrategy


class TestMigration(BaseIntegrationTest):
    asset = 'migration'
    wait_strategy = EverythingOkWaitStrategy()

    def test_migration_workflow(self):
        # Insert old config in jsondb OR mount old config in container
        # Assert old config/values are written on disk

        code = self._exec(['wazo-provd-migrate-db'])
        assert_that(code, equal_to(0))

        # assert database contains migrates values
        # assert jsondb files and app.json are removed

    def test_migration_already_done(self):
        code = self._exec(['wazo-provd-migrate-db'])
        assert_that(code, equal_to(0))

        code = self._exec(['wazo-provd-migrate-db'])
        assert_that(code, equal_to(2))

    def _exec(self, command):
        return self.docker_exec(command, return_attr='returncode')
