# Copyright 2018-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, calling, has_key, has_properties, not_
from wazo_provd_client.exceptions import ProvdError
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises

from .helpers import fixtures
from .helpers.base import INVALID_TOKEN, BaseIntegrationTest
from .helpers.fixtures import PLUGIN_TO_INSTALL
from .helpers.operation import operation_successful
from .helpers.wait_strategy import NoWaitStrategy


class TestPlugins(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def test_install(self) -> None:
        with self._client.plugins.update() as operation_progress:
            until.assert_(
                operation_successful, operation_progress, tries=20, interval=0.5
            )

        with self._client.plugins.install(PLUGIN_TO_INSTALL) as operation_progress:
            until.assert_(
                operation_successful, operation_progress, tries=20, interval=0.5
            )

        self._client.plugins.uninstall(PLUGIN_TO_INSTALL)

    def test_install_errors(self) -> None:
        assert_that(
            calling(self._client.plugins.install).with_args('invalid'),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )

    def test_install_error_when_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.plugins.install).with_args('invalid'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_uninstall(self) -> None:
        with fixtures.Plugin(self._client, delete_on_exit=False):
            self._client.plugins.uninstall(PLUGIN_TO_INSTALL)
            assert_that(
                self._client.plugins.list_installed()['pkgs'],
                not_(has_key(PLUGIN_TO_INSTALL)),
            )

    def test_uninstall_errors(self) -> None:
        assert_that(
            calling(self._client.plugins.uninstall).with_args('invalid_plugin'),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )

    def test_uninstall_error_when_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.plugins.uninstall).with_args('invalid_plugin'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_list_installed(self) -> None:
        result = self._client.plugins.list_installed()
        assert_that(result, has_key('pkgs'))

    def test_list_installed_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.plugins.list_installed),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_list_installable(self) -> None:
        result = self._client.plugins.list_installable()
        assert_that(result, has_key('pkgs'))

    def test_list_installable_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.plugins.list_installable),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_update(self) -> None:
        with self._client.plugins.update() as operation_progress:
            until.assert_(
                operation_successful, operation_progress, tries=10, timeout=10
            )

    def test_update_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.plugins.update),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_get(self) -> None:
        with fixtures.Plugin(self._client) as result:
            assert_that(result, has_key('capabilities'))

    def test_get_errors(self) -> None:
        assert_that(
            calling(self._client.plugins.get).with_args('invalid_plugin'),
            raises(ProvdError).matching(has_properties('status_code', 404)),
        )

    def test_get_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.Plugin(self._client):
            assert_that(
                calling(provd.plugins.get).with_args(PLUGIN_TO_INSTALL),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )
        assert_that(
            calling(provd.plugins.get).with_args('unkown_id'),
            raises(ProvdError).matching(
                has_properties('status_code', 404)
            ),  # should be 401
        )

    def test_get_packages_installed(self) -> None:
        with fixtures.Plugin(self._client):
            result = self._client.plugins.get_packages_installed(PLUGIN_TO_INSTALL)
            assert_that(result, has_key('pkgs'))

    def test_get_packages_installed_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.Plugin(self._client):
            assert_that(
                calling(provd.plugins.get_packages_installed).with_args(
                    PLUGIN_TO_INSTALL
                ),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )
        assert_that(
            calling(provd.plugins.get_packages_installed).with_args('unknown_id'),
            raises(ProvdError).matching(
                has_properties('status_code', 404)
            ),  # should be 401
        )

    def test_get_packages_installable(self) -> None:
        with fixtures.Plugin(self._client):
            result = self._client.plugins.get_packages_installable(PLUGIN_TO_INSTALL)
            assert_that(result, has_key('pkgs'))

    def test_get_packages_installable_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.Plugin(self._client):
            assert_that(
                calling(provd.plugins.get_packages_installable).with_args(
                    PLUGIN_TO_INSTALL
                ),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )

    def test_install_package(self) -> None:
        with fixtures.Plugin(self._client):
            results = self._client.plugins.get_packages_installable(PLUGIN_TO_INSTALL)[
                'pkgs'
            ]
            for package in results:
                with self._client.plugins.install_package(
                    PLUGIN_TO_INSTALL, package
                ) as progress:
                    until.assert_(operation_successful, progress, tries=10)

    def test_install_package_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.Plugin(self._client):
            assert_that(
                calling(provd.plugins.install_package).with_args(
                    PLUGIN_TO_INSTALL, 'whatever'
                ),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )
