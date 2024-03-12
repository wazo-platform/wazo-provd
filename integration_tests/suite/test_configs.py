# Copyright 2018-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    calling,
    equal_to,
    has_entry,
    has_key,
    has_properties,
    is_,
)
from wazo_provd_client.exceptions import ProvdError
from wazo_test_helpers.hamcrest.raises import raises

from .helpers import fixtures
from .helpers.base import INVALID_TOKEN, BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestConfigs(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_list(self) -> None:
        results = self._client.configs.list()
        assert_that(results, has_key('configs'))

    def test_list_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.configs.list),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_get(self) -> None:
        with fixtures.http.Configuration(self._client) as config:
            result = self._client.configs.get(config['id'])
            assert_that(result, has_key('id'))

    def test_get_errors(self) -> None:
        assert_that(
            calling(self._client.configs.get).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 404)),
        )

    def test_get_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.http.Configuration(self._client) as config:
            assert_that(
                calling(provd.configs.get).with_args(config['id']),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )
        assert_that(
            calling(provd.configs.get).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_get_raw(self) -> None:
        with fixtures.http.Configuration(self._client) as config:
            result = self._client.configs.get_raw(config['id'])
            assert_that(result, has_key('ip'))

    def test_get_raw_errors(self) -> None:
        assert_that(
            calling(self._client.configs.get_raw).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 404)),
        )

    def test_get_raw_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.http.Configuration(self._client) as config:
            assert_that(
                calling(provd.configs.get_raw).with_args(config['id']),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )
        assert_that(
            calling(provd.configs.get_raw).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_create(self) -> None:
        config = {
            'id': 'test1',
            'parent_ids': ['base'],
            'deletable': True,
            'X_type': 'internal',
            'raw_config': {
                'ip': '127.0.0.1',
                'http_port': 8667,
                'ntp_ip': '127.0.0.1',
                'X_xivo_phonebook_ip': '127.0.0.1',
                'ntp_enabled': True,
            },
        }
        result = self._client.configs.create(config)
        assert_that(result['id'], is_(equal_to(config['id'])))
        self._client.configs.delete(config['id'])

    def test_create_errors(self) -> None:
        invalid_config = {
            'id': 'test1',
            'deletable': True,
            'X_type': 'internal',
            'raw_config': {
                'ip': '127.0.0.1',
                'http_port': 8667,
                'ntp_ip': '127.0.0.1',
                'X_xivo_phonebook_ip': '127.0.0.1',
                'ntp_enabled': True,
            },
        }
        assert_that(
            calling(self._client.configs.create).with_args(invalid_config),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )

    def test_create_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        config = {
            'id': 'test1',
            'parent_ids': ['base'],
            'deletable': True,
            'X_type': 'internal',
            'raw_config': {
                'ip': '127.0.0.1',
                'http_port': 8667,
                'ntp_ip': '127.0.0.1',
                'X_xivo_phonebook_ip': '127.0.0.1',
                'ntp_enabled': True,
            },
        }
        assert_that(
            calling(provd.configs.create).with_args(config),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_update(self) -> None:
        with fixtures.http.Configuration(self._client) as config:
            config['raw_config']['ntp_ip'] = '127.0.0.1'
            self._client.configs.update(config)
            result = self._client.configs.get(config['id'])
            assert_that(result['raw_config'], has_entry('ntp_ip', '127.0.0.1'))

    def test_update_errors(self) -> None:
        with fixtures.http.Configuration(self._client):
            invalid_config = {'id': None}
            assert_that(
                calling(self._client.configs.update).with_args(invalid_config),
                raises(ProvdError).matching(has_properties('status_code', 404)),
            )

    def test_update_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.http.Configuration(self._client) as config:
            assert_that(
                calling(provd.configs.update).with_args({'id': config['id']}),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )

    def test_delete(self) -> None:
        with fixtures.http.Configuration(self._client, delete_on_exit=False) as config:
            self._client.configs.delete(config['id'])

    def test_delete_nonexistant_error(self) -> None:
        assert_that(
            calling(self._client.configs.delete).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 404)),
        )

    def test_delete_undeletable_error(self) -> None:
        config = {
            'id': 'test1',
            'parent_ids': ['base'],
            'deletable': False,
            'X_type': 'internal',
            'raw_config': {
                'ip': '127.0.0.1',
                'http_port': 8667,
                'ntp_ip': '127.0.0.1',
                'X_xivo_phonebook_ip': '127.0.0.1',
                'ntp_enabled': True,
            },
        }
        self._client.configs.create(config)
        assert_that(
            calling(self._client.configs.delete).with_args(config['id']),
            raises(ProvdError).matching(has_properties('status_code', 403)),
        )

        # To actually delete the config we need to update it
        config['deletable'] = True
        self._client.configs.update(config)
        self._client.configs.delete(config['id'])

    def test_delete_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.http.Configuration(self._client) as config:
            assert_that(
                calling(provd.configs.delete).with_args(config['id']),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )
        assert_that(
            calling(provd.configs.delete).with_args(config['id']),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_autocreate(self) -> None:
        result = self._client.configs.autocreate()
        assert_that(result, has_key('id'))

    def test_autocreate_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.configs.autocreate),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )
