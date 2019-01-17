# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    has_key,
    calling,
    has_properties,
    has_entry,
)

from xivo_test_helpers.hamcrest.raises import raises
from wazo_provd_client.exceptions import ProvdError

from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestParams(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_get(self):
        result = self._client.params.get('locale')
        assert_that(result, has_key('value'))

    def test_get_errors(self):
        assert_that(
            calling(self._client.params.get).with_args('invalid_param'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )

    def test_get_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        assert_that(
            calling(provd.params.get).with_args('locale'),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_list(self):
        result = self._client.params.list()
        assert_that(result, has_key('params'))

    def test_list_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        assert_that(
            calling(provd.params.list),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_update(self):
        self._client.params.update('locale', 'fr_FR')

    def test_update_errors(self):
        assert_that(
            calling(self._client.params.update).with_args('invalid_param', 'invalid_value'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )

    def test_update_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        self._client.params.update('locale', 'en_US')
        assert_that(
            calling(provd.params.update).with_args('locale', 'fr_FR'),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )
        result = self._client.params.get('locale')
        assert_that(result, has_entry('value', 'en_US'))

    def test_delete(self):
        self._client.params.delete('locale')

    def test_delete_errors(self):
        assert_that(
            calling(self._client.params.delete).with_args('invalid_param'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )

    def test_delete_error_invalid_token(self):
        provd = self.make_provd('invalid-token')
        assert_that(
            calling(provd.params.delete).with_args('locale'),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )
