# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    has_key,
    has_entry,
    is_,
    equal_to,
    calling,
    raises,
    is_not,
    empty,
)
from wazo_provd_client import Client
from wazo_provd_client.exceptions import ProvdError
from .helpers.base import BaseIntegrationTest

from .helpers.wait_strategy import NoWaitStrategy


class TestPlugins(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def setUp(self):
        self._client = Client(
            'localhost', https=False,
            port=self.service_port(8666, 'provd'), prefix='/provd'
        )

    def tearDown(self):
        pass

    def test_install(self):
        self._client.plugins.install('null')

    def test_install_errors(self):
        assert_that(
            calling(self._client.plugins.install).with_args('invalid'),
            raises(ProvdError)
        )

    def test_uninstall(self):
        pass

    def test_list_installed(self):
        pass

    def test_list_installable(self):
        pass

    def test_update(self):
        pass

    def test_get(self):
        pass

    def test_get_errors(self):
        pass

    def test_install(self):
        pass

    def test_get_packages_installed(self):
        pass

    def test_get_packages_installable(self):
        pass

    def test_install_package(self):
        pass
