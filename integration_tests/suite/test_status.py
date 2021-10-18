# Copyright 2020-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
from hamcrest import (
    assert_that,
    has_entries,
)

from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestConfigs(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_list(self):
        results = self._client.status.get()
        assert_that(results, has_entries(rest_api='ok'))
