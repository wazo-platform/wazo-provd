# Copyright 2020-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, has_entries
from wazo_test_helpers import until

from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestStatus(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_list(self) -> None:
        def is_ready() -> None:
            status = self._client.status.get()
            assert_that(
                status,
                has_entries(rest_api='ok', bus_consumer=has_entries(status='ok')),
            )

        until.assert_(is_ready, tries=60)
