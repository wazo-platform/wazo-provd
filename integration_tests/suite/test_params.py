# Copyright 2018-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, calling, has_entry, has_key, has_properties
from wazo_provd_client.exceptions import ProvdError
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises

from .helpers.base import (
    INVALID_TENANT,
    INVALID_TOKEN,
    SUB_TENANT_1,
    SUB_TENANT_2,
    VALID_TOKEN_MULTITENANT,
    BaseIntegrationTest,
)
from .helpers.bus import BusClient, setup_bus
from .helpers.operation import operation_fail, operation_successful
from .helpers.wait_strategy import EverythingOkWaitStrategy


class TestParams(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.wait_strategy.wait(cls)
        setup_bus(host='127.0.0.1', port=cls.service_port(5672, 'rabbitmq'))

    def test_get(self) -> None:
        result = self._client.params.get('locale')
        assert_that(result, has_key('value'))

    def test_get_errors(self) -> None:
        assert_that(
            calling(self._client.params.get).with_args('invalid_param'),
            raises(ProvdError).matching(has_properties('status_code', 404)),
        )

    def test_get_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.params.get).with_args('locale'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_list(self) -> None:
        result = self._client.params.list()
        assert_that(result, has_key('params'))

    def test_list_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.params.list),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_update(self) -> None:
        self._client.params.update('locale', 'fr_FR')

    def test_update_errors(self) -> None:
        assert_that(
            calling(self._client.params.update).with_args(
                'invalid_param', 'invalid_value'
            ),
            raises(ProvdError).matching(has_properties('status_code', 404)),
        )

    def test_update_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        self._client.params.update('locale', 'en_US')
        assert_that(
            calling(provd.params.update).with_args('locale', 'fr_FR'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )
        result = self._client.params.get('locale')
        assert_that(result, has_entry('value', 'en_US'))

    def test_delete(self) -> None:
        self._client.params.delete('locale')

    def test_delete_errors(self) -> None:
        assert_that(
            calling(self._client.params.delete).with_args('invalid_param'),
            raises(ProvdError).matching(has_properties('status_code', 404)),
        )

    def test_delete_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.params.delete).with_args('locale'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_stable_plugin_server(self) -> None:
        stable_url = 'https://provd.wazo.community/plugins/2/stable/'
        self._client.params.update('plugin_server', stable_url)

        with self._client.plugins.update() as op_progress:
            until.assert_(operation_successful, op_progress, tries=10, interval=0.5)

    def test_wrong_plugin_server(self) -> None:
        wrong_url = 'https://provd.wazo.community/plugins/2/wrong/'
        self._client.params.update('plugin_server', wrong_url)

        with self._client.plugins.update() as op_progress:
            until.assert_(operation_fail, op_progress, tries=10, interval=0.5)

    def test_provisioning_key_for_tenant(self) -> None:
        self._client.params.update('provisioning_key', 'this-is-a-key')
        assert_that(
            self._client.params.get('provisioning_key'),
            has_entry('value', 'this-is-a-key'),
        )

    def test_provisioning_key_for_invalid_tenant(self) -> None:
        provd = self.make_provd(VALID_TOKEN_MULTITENANT)
        provd.set_tenant(INVALID_TENANT)
        assert_that(
            calling(provd.params.update).with_args('provisioning_key', 'not-working'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_provisioning_key_can_be_nulled(self) -> None:
        self._client.params.update('provisioning_key', None)
        assert_that(
            self._client.params.get('provisioning_key'),
            has_entry('value', None),
        )

    def test_provisioning_key_min_max_limit(self) -> None:
        min_length = 8
        too_short_key = 'a' * (min_length - 1)
        assert_that(
            calling(self._client.params.update).with_args(
                'provisioning_key', too_short_key
            ),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )

        max_length = 256
        too_long_key = 'a' * (max_length + 1)
        assert_that(
            calling(self._client.params.update).with_args(
                'provisioning_key', too_long_key
            ),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )

    def test_provisioning_key_invalid_characters(self) -> None:
        assert_that(
            calling(self._client.params.update).with_args(
                'provisioning_key', 'asdf1234%$'
            ),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )

    def test_provisioning_key_for_unconfigured_tenant(self) -> None:
        # Do not use SUB_TENANT_1 in another provisioning key test
        provd = self.make_provd(VALID_TOKEN_MULTITENANT)
        provd.set_tenant(SUB_TENANT_1)
        assert_that(
            provd.params.get('provisioning_key'),
            has_entry('value', None),
        )

    def test_provisioning_key_already_exists(self) -> None:
        self._client.params.update('provisioning_key', 'secure-key')
        # Should not raise an error since it's the same tenant
        self._client.params.update('provisioning_key', 'secure-key')

        provd = self.make_provd(VALID_TOKEN_MULTITENANT)
        provd.set_tenant(SUB_TENANT_2)
        assert_that(
            calling(provd.params.update).with_args('provisioning_key', 'secure-key'),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )

    def test_provisioning_key_multiple_null_values_can_exist(self) -> None:
        self._client.params.update('provisioning_key', None)
        # Should not raise an error since it's the same tenant
        self._client.params.update('provisioning_key', None)

        provd = self.make_provd(VALID_TOKEN_MULTITENANT)
        provd.set_tenant(SUB_TENANT_2)
        # Should not raise an error since multiple tenants can have a null provisioning key
        provd.params.update('provisioning_key', None)

    def test_provisioning_key_deleted_tenant(self) -> None:
        provd = self.make_provd(VALID_TOKEN_MULTITENANT)
        provd.set_tenant(SUB_TENANT_2)
        provd.params.update('provisioning_key', '123testingkey')
        BusClient.send_tenant_deleted(SUB_TENANT_2, 'slug')

        def _empty_provisioning_key():
            assert_that(
                provd.params.get('provisioning_key'),
                has_entry('value', None),
            )

        until.assert_(_empty_provisioning_key, tries=10, interval=5)
