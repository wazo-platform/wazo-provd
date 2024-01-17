# Copyright 2018-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests
from hamcrest import assert_that, has_entries
from wazo_test_helpers import until
from wazo_test_helpers.wait_strategy import WaitStrategy


class NoWaitStrategy(WaitStrategy):
    def wait(self, provd):
        pass


class EverythingOkWaitStrategy(WaitStrategy):
    def wait(self, integration_test):
        def is_ready():
            try:
                status = integration_test._client.status.get()
            except requests.RequestException:
                status = {}
            assert_that(
                status,
                has_entries(
                    {
                        'rest_api': 'ok',
                        'bus_consumer': has_entries(status='ok'),
                    }
                ),
            )

        until.assert_(is_ready, tries=60)
