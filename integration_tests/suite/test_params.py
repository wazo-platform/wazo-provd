# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    has_key,
    calling,
    raises,
    has_properties,
)

from xivo_test_helpers import until
from xivo_test_helpers.hamcrest.raises import raises
from wazo_provd_client import Client
from wazo_provd_client.exceptions import ProvdError

from .helpers.base import BaseIntegrationTest
from .helpers.base import VALID_TOKEN
from .helpers.wait_strategy import NoWaitStrategy


class TestParams(BaseIntegrationTest):

    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def setUp(self):
        self._client = self.make_provd(VALID_TOKEN)

    def tearDown(self):
        pass

    def test_get(self):
        result = self._client.params.get('locale')
        assert_that(result, has_key('value'))

    def test_get_errors(self):
        assert_that(
            calling(self._client.params.get).with_args('invalid_param'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )

    def test_list(self):
        result = self._client.params.list()
        assert_that(result, has_key('params'))

    def test_update(self):
        self._client.params.update('locale', 'fr_FR')

    def test_update_errors(self):
        assert_that(
            calling(self._client.params.update).with_args('invalid_param', 'invalid_value'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )

    def test_delete(self):
        self._client.params.delete('locale')

    def test_delete_errors(self):
        assert_that(
            calling(self._client.params.delete).with_args('invalid_param'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )
