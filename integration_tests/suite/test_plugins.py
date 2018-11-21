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
    not_,
    empty,
)
from xivo_test_helpers import until
from wazo_provd_client import Client, operation
from wazo_provd_client.exceptions import ProvdError

from .helpers import fixtures
from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy

PLUGIN_TO_INSTALL = 'test-plugin'


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
        location = self._client.plugins.update()

        until.assert_(fixtures.operation_successful, self._client.plugins, location, tries=20, interval=0.5)

        location = self._client.plugins.install(PLUGIN_TO_INSTALL)

        until.assert_(fixtures.operation_successful, self._client.plugins, location, tries=20, interval=0.5)

        self._client.plugins.uninstall(PLUGIN_TO_INSTALL)

    def test_install_errors(self):
        assert_that(
            calling(self._client.plugins.install).with_args('invalid'),
            raises(ProvdError)
        )

    def test_uninstall(self):
        with fixtures.Plugin(self._client, PLUGIN_TO_INSTALL, False):
            self._client.plugins.uninstall(PLUGIN_TO_INSTALL)
            assert_that(self._client.plugins.list_installed()['pkgs'], not_(has_key(PLUGIN_TO_INSTALL)))

    def test_list_installed(self):
        result = self._client.plugins.list_installed()
        assert_that(result, has_key('pkgs'))

    def test_list_installable(self):
        result = self._client.plugins.list_installable()
        assert_that(result, has_key('pkgs'))

    def test_update(self):
        location = self._client.plugins.update()

        until.assert_(fixtures.operation_successful, self._client.plugins, location, tries=10, timeout=10)

    def test_get(self):
        with fixtures.Plugin(self._client, PLUGIN_TO_INSTALL):
            result = self._client.plugins.get(PLUGIN_TO_INSTALL)
            assert_that(result, has_key('plugin_info'))
            assert_that(result['plugin_info'], has_key('version'))

    def test_get_errors(self):
        assert_that(
            calling(self._client.plugins.get).with_args('invalid_plugin'),
            raises(ProvdError)
        )

    def test_get_packages_installed(self):
        with fixtures.Plugin(self._client, PLUGIN_TO_INSTALL):
            result = self._client.plugins.get_packages_installed(PLUGIN_TO_INSTALL)
            assert_that(result, has_key('pkgs'))

    def test_get_packages_installable(self):
        with fixtures.Plugin(self._client, PLUGIN_TO_INSTALL):
            result = self._client.plugins.get_packages_installed(PLUGIN_TO_INSTALL)
            assert_that(result, has_key('pkgs'))

    def test_install_package(self):
        with fixtures.Plugin(self._client, PLUGIN_TO_INSTALL):
            results = self._client.plugins.get_packages_installable(PLUGIN_TO_INSTALL)['pkgs']
            for package in results:
                location = self._client.plugins.install_package(PLUGIN_TO_INSTALL, package)
                until.assert_(fixtures.operation_successful, self._client.plugins, location, tries=10)
