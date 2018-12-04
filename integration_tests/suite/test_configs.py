# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
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
    has_properties,
)
from xivo_test_helpers.hamcrest.raises import raises
from wazo_provd_client import Client
from wazo_provd_client.exceptions import ProvdError

from .helpers import fixtures
from .helpers.base import BaseIntegrationTest
from .helpers.base import VALID_TOKEN
from .helpers.wait_strategy import NoWaitStrategy


class TestConfigs(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def setUp(self):
        self._client = self.make_provd(VALID_TOKEN)

    def tearDown(self):
        pass

    def test_list(self):
        results = self._client.configs.list()
        assert_that(results, has_key('configs'))

    def test_list_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        assert_that(
            calling(provd.configs.list),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_get(self):
        with fixtures.Configuration(self._client) as config:
            result = self._client.configs.get(config['id'])
            assert_that(result, has_key('id'))

    def test_get_errors(self):
        assert_that(
            calling(self._client.configs.get).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )

    def test_get_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        with fixtures.Configuration(self._client) as config:
            assert_that(
                calling(provd.configs.get).with_args(config['id']),
                raises(ProvdError).matching(has_properties('status_code', 401))
            )
        assert_that(
            calling(provd.configs.get).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_get_raw(self):
        with fixtures.Configuration(self._client) as config:
            result = self._client.configs.get_raw(config['id'])
            assert_that(result, has_key('ip'))

    def test_get_raw_errors(self):
        assert_that(
            calling(self._client.configs.get_raw).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )

    def test_get_raw_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        with fixtures.Configuration(self._client) as config:
            assert_that(
                calling(provd.configs.get_raw).with_args(config['id']),
                raises(ProvdError).matching(has_properties('status_code', 401))
            )
        assert_that(
            calling(provd.configs.get_raw).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_create(self):
        config = {
            'id': 'test1',
            'parent_ids': ['base'],
            'deletable': True,
            'X_type': 'internal',
            'raw_config': {
                'ntp_ip': '127.0.0.1',
                'X_xivo_phonebook_ip': '127.0.0.1',
                'ntp_enabled': True,
            }
        }
        result = self._client.configs.create(config)
        assert_that(result['id'], is_(equal_to(config['id'])))
        self._client.configs.delete(config['id'])

    def test_create_errors(self):
        invalid_config = {
            'id': 'test1',
            'deletable': True,
            'X_type': 'internal',
            'raw_config': {
                'ntp_ip': '127.0.0.1',
                'X_xivo_phonebook_ip': '127.0.0.1',
                'ntp_enabled': True,
            }
        }
        assert_that(
            calling(self._client.configs.create).with_args(invalid_config),
            raises(ProvdError).matching(has_properties('status_code', 400))
        )

    def test_create_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        config = {
            'id': 'test1',
            'parent_ids': ['base'],
            'deletable': True,
            'X_type': 'internal',
            'raw_config': {
                'ntp_ip': '127.0.0.1',
                'X_xivo_phonebook_ip': '127.0.0.1',
                'ntp_enabled': True,
            }
        }
        assert_that(
            calling(provd.configs.create).with_args(config),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_update(self):
        with fixtures.Configuration(self._client) as config:
            config['raw_config']['ntp_ip'] = '127.0.0.1'
            self._client.configs.update(config)
            result = self._client.configs.get(config['id'])
            assert_that(result['raw_config'], has_entry('ntp_ip', '127.0.0.1'))

    def test_update_errors(self):
        with fixtures.Configuration(self._client):
            invalid_config = {'id': None}
            assert_that(
                calling(self._client.configs.update).with_args(invalid_config),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )

    def test_update_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        with fixtures.Configuration(self._client) as config:
            assert_that(
                calling(provd.configs.update).with_args(config['id'], {}),
                raises(ProvdError).matching(has_properties('status_code', 401))
            )

    def test_delete(self):
        with fixtures.Configuration(self._client, delete_on_exit=False) as config:
            self._client.configs.delete(config['id'])

    def test_delete_errors(self):
        assert_that(
            calling(self._client.configs.delete).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )

    def test_delete_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        with fixtures.Configuration(self._client) as config:
            assert_that(
                calling(provd.configs.delete).with_args(config['id']),
                raises(ProvdError).matching(has_properties('status_code', 401))
            )
        assert_that(
            calling(provd.configs.delete).with_args(config['id']),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_autocreate(self):
        result = self._client.configs.autocreate()
        assert_that(result, has_key('id'))

    def test_autocreate_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        assert_that(
            calling(provd.configs.autocreate),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )
