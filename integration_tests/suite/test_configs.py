# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    calling,
    empty,
    equal_to,
    has_entry,
    has_key,
    is_,
    is_not,
    raises,
)
from wazo_provd_client import Client
from wazo_provd_client.exceptions import ProvdError

from .helpers import fixtures
from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestConfigs(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def setUp(self):
        self._client = Client(
            'localhost', https=False,
            port=self.service_port(8666, 'provd'), prefix='/provd'
        )

    def tearDown(self):
        pass

    def test_list(self):
        results = self._client.configs.list()
        assert_that(results, has_key('configs'))

    def test_get(self):
        with fixtures.Configuration(self._client) as config:
            result = self._client.configs.get(config['id'])
            assert_that(result, has_key('config'))

    def test_get_raw(self):
        with fixtures.Configuration(self._client) as config:
            result = self._client.configs.get_raw(config['id'])
            assert_that(result, has_key('raw_config'))

    def test_create(self):
        pass

    def test_update(self):
        pass

    def test_delete(self):
        pass

    def test_autocreate(self):
        result = self._client.configs.autocreate()
        assert_that(result, has_key('id'))

