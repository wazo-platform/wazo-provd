# Copyright 2014-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest
from unittest.mock import Mock, sentinel

from hamcrest import assert_that, equal_to, has_item, is_

from wazo_provd.app import ApplicationConfigureService
from wazo_provd.services import InvalidParameterError


class TestAppConfigureService(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Mock()
        self.service = ApplicationConfigureService(Mock(), {}, self.app)

    def test_get_nat(self) -> None:
        self.app.nat = sentinel.nat

        value = self.service.get('NAT')

        assert_that(value, is_(sentinel.nat))

    def test_set_nat_valid_values(self) -> None:
        for value in [0, 1]:
            self.service.set('NAT', str(value))
            assert_that(self.app.nat, equal_to(value))

    def test_set_nat_invalid_values(self) -> None:
        for value in ['-1', '2', 'foobar']:
            self.assertRaises(InvalidParameterError, self.service.set, 'NAT', value)

    def test_set_nat_to_none(self) -> None:
        self.service.set('NAT', None)
        assert_that(self.app.nat, equal_to(0))

    def test_get_http_auth_strategy(self) -> None:
        for use_provisioning_key, expected in [(True, 'url_key'), (False, None)]:
            self.app.use_provisioning_key = use_provisioning_key

            value = self.service.get('http_auth_strategy', tenant_uuid=sentinel.tenant)

            assert_that(value, equal_to(expected))

    def test_set_http_auth_strategy_is_read_only(self) -> None:
        self.app.http_auth_strategy = None
        self.app.use_provisioning_key = False

        self.assertRaises(
            InvalidParameterError,
            self.service.set,
            'http_auth_strategy',
            'url_key',
            tenant_uuid=sentinel.tenant,
        )
        assert_that(self.app.http_auth_strategy, equal_to(None))
        assert_that(self.app.use_provisioning_key, equal_to(False))

    def test_set_unknown_param(self) -> None:
        self.assertRaises(KeyError, self.service.set, 'unknown', 'value')

    def test_http_auth_strategy_is_listed(self) -> None:
        for description in [self.service.description, self.service.description_fr]:
            assert_that([key for key, _ in description], has_item('http_auth_strategy'))
