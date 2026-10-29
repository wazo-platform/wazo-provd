# Copyright 2014-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest
from typing import cast
from unittest.mock import Mock, patch, sentinel

from hamcrest import assert_that, equal_to, has_item, is_

from wazo_provd.app import ApplicationConfigureService, ProvisioningApplication
from wazo_provd.devices.schemas import RawConfigDict
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
        for strategy in ['url_key', None]:
            self.app.http_auth_strategy = strategy

            value = self.service.get('http_auth_strategy', tenant_uuid=sentinel.tenant)

            assert_that(value, equal_to(strategy))

    def test_set_http_auth_strategy_from_master_tenant(self) -> None:
        self.app.tenant_uuid.return_value = 'master'
        self.app.http_auth_strategy = None

        self.service.set('http_auth_strategy', 'url_key', tenant_uuid='master')
        assert_that(self.app.http_auth_strategy, equal_to('url_key'))

        for disabled in [None, '']:
            self.app.http_auth_strategy = 'url_key'
            self.service.set('http_auth_strategy', disabled, tenant_uuid='master')
            assert_that(self.app.http_auth_strategy, equal_to(None))

    def test_set_http_auth_strategy_without_tenant(self) -> None:
        # Persisted values are replayed at startup, before any request.
        self.app.tenant_uuid.return_value = 'master'
        self.app.http_auth_strategy = None

        self.service.set('http_auth_strategy', 'url_key')

        assert_that(self.app.http_auth_strategy, equal_to('url_key'))

    def test_set_http_auth_strategy_from_sub_tenant(self) -> None:
        self.app.tenant_uuid.return_value = 'master'
        self.app.http_auth_strategy = None

        self.assertRaises(
            InvalidParameterError,
            self.service.set,
            'http_auth_strategy',
            'url_key',
            tenant_uuid='sub',
        )
        assert_that(self.app.http_auth_strategy, equal_to(None))

    def test_set_http_auth_strategy_invalid_value(self) -> None:
        self.app.tenant_uuid.return_value = 'master'
        self.app.http_auth_strategy = None

        for value in ['url', 'URL_KEY', 1]:
            self.assertRaises(
                InvalidParameterError,
                self.service.set,
                'http_auth_strategy',
                value,
                tenant_uuid='master',
            )
        assert_that(self.app.http_auth_strategy, equal_to(None))

    def test_set_unknown_param(self) -> None:
        self.assertRaises(KeyError, self.service.set, 'unknown', 'value')

    def test_http_auth_strategy_is_listed(self) -> None:
        for description in [self.service.description, self.service.description_fr]:
            assert_that([key for key, _ in description], has_item('http_auth_strategy'))


@patch('wazo_provd.app.RawConfigSchema', Mock())
class TestDevConfigure(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Mock(use_provisioning_key=False)
        self.app.configure_service.get.return_value = 'tenant-key'
        self.plugin = Mock()
        self.raw_config = cast(
            RawConfigDict, {'http_base_url': 'http://provd:8667', 'ip': '10.0.0.1'}
        )

    def _configure(self, device):
        return ProvisioningApplication._dev_configure(
            self.app, device, self.plugin, self.raw_config
        )

    def _configured_base_url(self) -> str:
        return self.plugin.configure.call_args[0][1]['http_base_url']

    def test_appends_the_tenant_key_when_url_key_is_off(self):
        assert self._configure({'id': 'd1', 'tenant_uuid': 'tenant'})

        assert self._configured_base_url() == 'http://provd:8667/tenant-key'
        self.app.configure_service.get.assert_called_once_with(
            'provisioning_key', 'tenant'
        )
        assert self.raw_config['http_base_url'] == 'http://provd:8667'

    def test_appends_the_tenant_key_when_url_key_is_on(self):
        self.app.use_provisioning_key = True

        assert self._configure({'id': 'd1', 'tenant_uuid': 'tenant'})

        assert self._configured_base_url() == 'http://provd:8667/tenant-key'

    def test_appends_the_tenant_key_without_double_slash(self):
        self.raw_config['http_base_url'] = 'http://provd:8667/'

        assert self._configure({'id': 'd1', 'tenant_uuid': 'tenant'})

        assert self._configured_base_url() == 'http://provd:8667/tenant-key'

    def test_keeps_the_base_url_for_a_tenant_without_key_when_url_key_is_off(self):
        self.app.configure_service.get.return_value = None

        assert self._configure({'id': 'd1', 'tenant_uuid': 'tenant'})

        assert self._configured_base_url() == 'http://provd:8667'

    def test_refuses_a_tenant_without_key_when_url_key_is_on(self):
        self.app.use_provisioning_key = True
        self.app.configure_service.get.return_value = None

        assert not self._configure({'id': 'd1', 'tenant_uuid': 'tenant'})

        self.plugin.configure.assert_not_called()

    def test_refuses_a_device_without_tenant_when_url_key_is_on(self):
        self.app.use_provisioning_key = True

        assert not self._configure({'id': 'd1'})

        self.plugin.configure.assert_not_called()
