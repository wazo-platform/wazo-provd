# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, calling, has_properties
from wazo_provd_client.exceptions import ProvdError
from wazo_test_helpers.hamcrest.raises import raises

from .helpers.base import BaseIntegrationTest


class TestAuthentication(BaseIntegrationTest):
    asset = 'base'

    def test_no_token(self) -> None:
        client = self.make_provd('')

        assert_that(
            calling(client.status.get),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_invalid_token(self) -> None:
        client = self.make_provd('invalid')

        assert_that(
            calling(client.status.get),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )
