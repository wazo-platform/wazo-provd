# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    calling,
    empty,
    equal_to,
    has_entry,
    has_key,
    is_,
    is_not,
    has_properties,
)
from xivo_test_helpers import until
from xivo_test_helpers.hamcrest.raises import raises
from wazo_provd_client.exceptions import ProvdError

from .helpers import fixtures
from .helpers.base import (
    BaseIntegrationTest,
    VALID_TOKEN,
    INVALID_TOKEN,
    MAIN_TENANT,
    SUB_TENANT_1,
    SUB_TENANT_2,
)
from .helpers.wait_strategy import NoWaitStrategy
from .helpers.operation import operation_successful


class TestDevices(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def _add_device(self, ip, mac, provd=None, plugin='', id_=None, tenant_uuid=None):
        device = {'ip': ip, 'mac': mac, 'plugin': plugin}
        if id_:
            device.update({'id': id_})
        provd = provd or self._client
        return provd.devices.create(device, tenant_uuid=tenant_uuid)

    def test_list(self):
        results = self._client.devices.list()
        assert_that(results, has_key('devices'))

    def test_add(self):
        result_add = self._add_device('10.10.10.10', '00:11:22:33:44:55', id_='1234abcdef1234')
        assert_that(result_add, has_entry('id', '1234abcdef1234'))

    def test_add_errors(self):
        assert_that(
            calling(self._add_device).with_args('10.0.1.xx', '00:11:22:33:44:55'),
            raises(ProvdError).matching(has_properties('status_code', 400))
        )
        assert_that(
            calling(self._add_device).with_args('10.0.1.1', '00:11:22:33:44:55', id_='*&!"/invalid _'),
            raises(ProvdError).matching(has_properties('status_code', 400))
        )

    def test_add_error_invalid_token(self):
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.devices.create).with_args(
                {'id': '*&!"/invalid _', 'ip': '10.0.1.xx', 'mac': '00:11:22:33:44:55'}
            ),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_add_multitenant(self):
        result_add = self._add_device(
            '10.10.10.200', '01:02:03:04:05:06', tenant_uuid=SUB_TENANT_1
        )
        id_added = result_add['id']
        result = self._client.devices.get(id_added, tenant_uuid=SUB_TENANT_1)
        assert_that(result, has_entry('tenant_uuid', SUB_TENANT_1))

    def test_add_multitenant_wrong_token_errors(self):
        provd = self.make_provd(VALID_TOKEN)
        assert_that(
            calling(self._add_device).with_args(
                '10.10.10.200', '01:02:03:04:05:06', provd=provd, tenant_uuid=SUB_TENANT_1
            ),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_update(self):
        with fixtures.Device(self._client) as device:
            new_info = {'id': device['id'], 'ip': '5.6.7.8', 'mac': 'aa:bb:cc:dd:ee:ff'}
            self._client.devices.update(new_info)

            result = self._client.devices.get(device['id'])
            assert_that(result['ip'], is_(equal_to('5.6.7.8')))

    def test_update_errors(self):
        with fixtures.Device(self._client) as device:
            assert_that(
                calling(self._client.devices.update).with_args(
                    {'ip': '1.2.3.4', 'mac': '00:11:22:33:44:55'}
                ),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )
            assert_that(
                calling(self._client.devices.update).with_args(
                    {'id': device['id'], 'ip': '10.0.1.1', 'mac': '00:11:22:33:44:xx'}
                ),
                raises(ProvdError).matching(has_properties('status_code', 500))
            )

    def test_update_error_invalid_token(self):
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.Device(self._client):
            assert_that(
                calling(provd.devices.update).with_args(
                    {'ip': '1.2.3.4', 'mac': '00:11:22:33:44:55'}
                ),
                raises(ProvdError).matching(has_properties('status_code', 401))
            )

    def test_update_change_tenant_from_main_to_subtenant(self):
        with fixtures.Device(self._client, tenant_uuid=MAIN_TENANT) as device:
            self._client.devices.update(device, tenant_uuid=SUB_TENANT_1)
            device_result = self._client.devices.get(device['id'])
            assert_that(device_result, has_entry('tenant_uuid', SUB_TENANT_1))

    def test_update_change_tenant_to_main_tenant(self):
        with fixtures.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            self._client.devices.update(device, tenant_uuid=MAIN_TENANT)
            device_result = self._client.devices.get(device['id'])
            assert_that(device_result, has_entry('tenant_uuid', MAIN_TENANT))

    def test_update_change_tenant_to_other_subtenant_error(self):
        with fixtures.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            assert_that(
                calling(self._client.devices.update).with_args(device, tenant_uuid=SUB_TENANT_2),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )

    def test_update_multitenant_wrong_token_errors(self):
        provd = self.make_provd(VALID_TOKEN)
        with fixtures.Device(self._client) as device:
            assert_that(
                calling(provd.devices.update).with_args(device, tenant_uuid=MAIN_TENANT),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )

    def test_synchronize(self):
        with fixtures.Plugin(self._client, fixtures.PLUGIN_TO_INSTALL):
            with fixtures.Device(self._client) as device:
                with self._client.devices.synchronize(device['id']) as operation_progress:
                    until.assert_(
                        operation_successful, operation_progress, tries=20, interval=0.5
                    )

    def test_synchronize_error_invalid_token(self):
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.Device(self._client) as device:
            assert_that(
                calling(provd.devices.synchronize).with_args(device['id']),
                raises(ProvdError).matching(has_properties('status_code', 401))
            )
        assert_that(
            calling(provd.devices.synchronize).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_synchronize_subtenant_from_main(self):
        with fixtures.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            self._client.devices.synchronize(device['id'], tenant_uuid=MAIN_TENANT)

    def test_synchronize_main_from_subtenant(self):
        with fixtures.Device(self._client, tenant_uuid=MAIN_TENANT) as device:
            assert_that(
                calling(self._client.devices.synchronize).with_args(
                    device['id'],
                    tenant_uuid=SUB_TENANT_1
                ),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )

    def test_synchronize_subtenant_from_another_subtenant(self):
        with fixtures.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            assert_that(
                calling(self._client.devices.synchronize).with_args(
                    device['id'],
                    tenant_uuid=SUB_TENANT_2
                ),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )

    def test_synchronize_multitenant_wrong_token_errors(self):
        provd = self.make_provd(VALID_TOKEN)
        with fixtures.Device(self._client) as device:
            assert_that(
                calling(provd.devices.synchronize).with_args(device['id'], tenant_uuid=SUB_TENANT_1),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )

    def test_get(self):
        with fixtures.Device(self._client) as device:
            result = self._client.devices.get(device['id'])
            assert_that(result['id'], is_(equal_to(device['id'])))

    def test_get_errors(self):
        assert_that(
            calling(self._client.devices.get).with_args('unknown_id'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )

    def test_get_error_invalid_token(self):
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.Device(self._client) as device:
            assert_that(
                calling(provd.devices.get).with_args(device['id']),
                raises(ProvdError).matching(has_properties('status_code', 401))
            )
        assert_that(
            calling(provd.devices.get).with_args('unknown_id'),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_get_subtenant_from_main_tenant(self):
        with fixtures.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            result = self._client.devices.get(device['id'], tenant_uuid=MAIN_TENANT)
            assert_that(result['id'], is_(equal_to(device['id'])))

    def test_get_main_tenant_from_subtenant_errors(self):
        with fixtures.Device(self._client, tenant_uuid=MAIN_TENANT) as device:
            assert_that(
                calling(self._client.devices.get).with_args(device['id'], tenant_uuid=SUB_TENANT_1),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )

    def test_delete(self):
        with fixtures.Device(self._client, delete_on_exit=False) as device:
            self._client.devices.delete(device['id'])
            assert_that(
                calling(self._client.devices.get).with_args(device['id']),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )

    def test_delete_errors(self):
        assert_that(
            calling(self._client.devices.delete).with_args('unknown_id'),
            raises(ProvdError).matching(has_properties('status_code', 404))
        )

    def test_delete_error_invalid_token(self):
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.Device(self._client) as device:
            assert_that(
                calling(provd.devices.delete).with_args(device['id']),
                raises(ProvdError).matching(has_properties('status_code', 401))
            )

    def test_delete_subtenant_from_main_tenant(self):
        with fixtures.Device(self._client, delete_on_exit=False, tenant_uuid=SUB_TENANT_1) as device:
            self._client.devices.delete(device['id'], tenant_uuid=MAIN_TENANT)
            assert_that(
                calling(self._client.devices.get).with_args(device['id'], tenant_uuid=SUB_TENANT_1),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )

    def test_delete_main_tenant_from_subtenant(self):
        with fixtures.Device(self._client, delete_on_exit=False, tenant_uuid=MAIN_TENANT) as device:
            assert_that(
                calling(self._client.devices.delete).with_args(device['id'], tenant_uuid=SUB_TENANT_1),
                raises(ProvdError).matching(has_properties('status_code', 404))
            )
            result = self._client.devices.get(device['id'], tenant_uuid=MAIN_TENANT)
            assert_that(result['id'], is_(equal_to(device['id'])))

    def test_reconfigure(self):
        with fixtures.Device(self._client) as device:
            self._client.devices.reconfigure(device['id'])

    def test_reconfigure_errors(self):
        assert_that(
            calling(self._client.devices.reconfigure).with_args('unknown_id'),
            raises(ProvdError).matching(has_properties('status_code', 400))
        )

    def test_reconfigure_error_invalid_token(self):
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.Device(self._client) as device:
            assert_that(
                calling(provd.devices.reconfigure).with_args(device['id']),
                raises(ProvdError).matching(has_properties('status_code', 401))
            )
        assert_that(
            calling(provd.devices.reconfigure).with_args('unknown_id'),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_reconfigure_subtenant_from_main_tenant(self):
        with fixtures.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            self._client.devices.reconfigure(device['id'], tenant_uuid=MAIN_TENANT)

    def test_reconfigure_main_tenant_from_subtenant(self):
        with fixtures.Device(self._client, tenant_uuid=MAIN_TENANT) as device:
            assert_that(
                calling(self._client.devices.reconfigure).with_args(device['id'], tenant_uuid=SUB_TENANT_1),
                raises(ProvdError).matching(has_properties('status_code', 400))
            )

    def test_dhcp(self):
        self._client.devices.create_from_dhcp(
            {'ip': '10.10.0.1', 'mac': 'ab:bc:cd:de:ff:01', 'op': 'commit', 'options': []}
        )
        find_results = self._client.devices.list(search={'mac': 'ab:bc:cd:de:ff:01'})
        assert_that(find_results, has_key('devices'))
        assert_that(find_results['devices'], is_not(empty()))
        assert_that(find_results['devices'][0], has_entry('ip', '10.10.0.1'))

    def test_dhcp_errors(self):
        assert_that(
            calling(self._client.devices.create_from_dhcp).with_args(
                {'ip': '10.10.0.1', 'mac': 'ab:bc:cd:de:ff:01', 'op': 'commit'}
            ),
            raises(ProvdError).matching(has_properties('status_code', 400))
        )

    def test_dhcp_error_invalid_token(self):
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.devices.create_from_dhcp).with_args(
                {'ip': '10.10.0.1', 'mac': 'ab:bc:cd:de:ff:01', 'op': 'commit'}
            ),
            raises(ProvdError).matching(has_properties('status_code', 401))
        )

    def test_dhcp_adds_in_main_tenant(self):
        self._client.devices.create_from_dhcp(
            {'ip': '10.10.0.1', 'mac': 'ab:bc:cd:de:ff:01', 'op': 'commit', 'options': []}
        )
        find_results = self._client.devices.list(
            search={'mac': 'ab:bc:cd:de:ff:01'}, tenant_uuid=MAIN_TENANT
        )
        assert_that(find_results, has_key('devices'))
        assert_that(find_results['devices'], is_not(empty()))
        assert_that(find_results['devices'][0], has_entry('ip', '10.10.0.1'))
