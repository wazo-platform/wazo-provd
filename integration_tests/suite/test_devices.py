# Copyright 2018-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from time import sleep
from typing import Any

from hamcrest import (
    assert_that,
    calling,
    empty,
    equal_to,
    has_entries,
    has_entry,
    has_key,
    has_properties,
    is_,
    is_not,
)
from wazo_provd_client.exceptions import ProvdError
from wazo_test_helpers import until
from wazo_test_helpers.auth import AuthClient as MockAuthClient
from wazo_test_helpers.auth import MockUserToken
from wazo_test_helpers.hamcrest.raises import raises

from .helpers import fixtures
from .helpers.base import (
    INVALID_TOKEN,
    MAIN_TENANT,
    PLUGIN_SERVER,
    SUB_TENANT_1,
    SUB_TENANT_2,
    VALID_TOKEN,
    BaseIntegrationTest,
)
from .helpers.bus import BusClient, setup_bus
from .helpers.filesystem import FileSystemClient
from .helpers.operation import operation_successful
from .helpers.wait_strategy import EverythingOkWaitStrategy

TOKEN = '00000000-0000-4000-9000-000000070435'
TOKEN_SUB_TENANT = '00000000-0000-4000-9000-000000000222'
DELETED_TENANT = '66666666-6666-4666-8666-666666666666'
USER_UUID = 'd1534a6c-3e35-44db-b4df-0e2957cdea77'
DEFAULT_TENANTS = [
    {
        'uuid': MAIN_TENANT,
        'name': 'name1',
        'slug': 'slug1',
        'parent_uuid': MAIN_TENANT,
    },
    {
        'uuid': SUB_TENANT_1,
        'name': 'name2',
        'slug': 'slug2',
        'parent_uuid': MAIN_TENANT,
    },
    {
        'uuid': SUB_TENANT_2,
        'name': 'name4',
        'slug': 'slug4',
        'parent_uuid': MAIN_TENANT,
    },
]
ALL_TENANTS = DEFAULT_TENANTS + [
    {
        'uuid': DELETED_TENANT,
        'name': 'name3',
        'slug': 'slug3',
        'parent_uuid': MAIN_TENANT,
    }
]


class TestDevices(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = EverythingOkWaitStrategy()
    filesystem: FileSystemClient

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.setup_token()
        setup_bus(host='127.0.0.1', port=cls.service_port(5672, 'rabbitmq'))
        cls.filesystem = cls.make_filesystem()
        cls._client.params.update('plugin_server', PLUGIN_SERVER)

    @classmethod
    def setup_token(cls) -> None:
        cls.mock_auth = MockAuthClient('127.0.0.1', cls.service_port(9497, 'auth'))
        token = MockUserToken(
            TOKEN,
            'user_uuid',
            metadata={'uuid': USER_UUID, 'tenant_uuid': MAIN_TENANT},
        )
        cls.mock_auth.set_token(token)
        token = MockUserToken(
            TOKEN_SUB_TENANT,
            'user_uuid',
            metadata={'uuid': 'user_uuid', 'tenant_uuid': SUB_TENANT_1},
        )
        cls.mock_auth.set_token(token)
        cls._reset_auth_tenants()

    @classmethod
    def _delete_auth_tenant(cls) -> None:
        cls.mock_auth.set_tenants(*DEFAULT_TENANTS)

    @classmethod
    def _reset_auth_tenants(cls) -> None:
        cls.mock_auth.set_tenants(*ALL_TENANTS)

    @classmethod
    @contextmanager
    def delete_auth_tenant(
        cls, tenant_uuid: str
    ) -> Generator[None, None, None]:  # tenant_uuid improve readability
        cls._delete_auth_tenant()
        yield
        cls._reset_auth_tenants()

    @classmethod
    @contextmanager
    def create_auth_tenant(
        cls, tenant_uuid: str
    ) -> Generator[None, None, None]:  # tenant_uuid improve readability
        cls._create_auth_tenant()
        yield
        cls._reset_auth_tenants()

    @classmethod
    def make_filesystem(cls) -> FileSystemClient:
        return FileSystemClient(execute=cls.docker_exec)

    def _add_device(
        self, ip, mac, provd=None, plugin='', id_=None, tenant_uuid=None
    ) -> dict[str, Any]:
        device = {'ip': ip, 'mac': mac, 'plugin': plugin}
        if id_:
            device |= {'id': id_}
        provd = provd or self._client
        return provd.devices.create(device, tenant_uuid=tenant_uuid)

    def test_list(self) -> None:
        results = self._client.devices.list()
        assert_that(results, has_key('devices'))

    def test_list_params(self) -> None:
        broken_device = {'mac': 'aa:bb:cc:dd:ee:ff', 'plugin': None}
        self._client.devices.create(broken_device)
        self._client.devices.list(sort='ip', sort_ord='ASC', reverse=True)

    def test_add(self) -> None:
        result_add = self._add_device(
            '10.10.10.10', '00:11:22:33:44:55', id_='1234abcdef1234'
        )
        assert_that(result_add, has_entry('id', '1234abcdef1234'))
        result = self._client.devices.get(result_add['id'])
        assert_that(result, has_entry('is_new', True))

    def test_add_errors(self) -> None:
        assert_that(
            calling(self._add_device).with_args('10.0.1.xx', '00:11:22:33:44:55'),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )
        assert_that(
            calling(self._add_device).with_args(
                '10.0.1.1', '00:11:22:33:44:55', id_='*&!"/invalid _'
            ),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )

    def test_add_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.devices.create).with_args(
                {'id': '*&!"/invalid _', 'ip': '10.0.1.xx', 'mac': '00:11:22:33:44:55'}
            ),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_add_multitenant(self) -> None:
        result_add = self._add_device(
            '10.10.10.200', '01:02:03:04:05:06', tenant_uuid=SUB_TENANT_1
        )
        id_added = result_add['id']
        result = self._client.devices.get(id_added, tenant_uuid=SUB_TENANT_1)
        assert_that(result, has_entry('tenant_uuid', SUB_TENANT_1))
        assert_that(
            result, has_entry('is_new', False)
        )  # Not added in master tenant, so not new

    def test_add_multitenant_wrong_token_errors(self) -> None:
        provd = self.make_provd(VALID_TOKEN)
        assert_that(
            calling(self._add_device).with_args(
                '10.10.10.200',
                '01:02:03:04:05:06',
                provd=provd,
                tenant_uuid=SUB_TENANT_1,
            ),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_update(self) -> None:
        with fixtures.http.Device(self._client) as device:
            device |= {'ip': '5.6.7.8', 'mac': 'aa:bb:cc:dd:ee:ff'}  # type: ignore
            self._client.devices.update(device)

            result = self._client.devices.get(device['id'])
            assert_that(result['ip'], is_(equal_to('5.6.7.8')))
            assert_that(
                result, has_entry('is_new', True)
            )  # Still in master tenant, so still new

    def test_update_errors(self) -> None:
        with fixtures.http.Device(self._client) as device:
            assert_that(
                calling(self._client.devices.update).with_args(
                    {'id': 'invalid_id', 'ip': '1.2.3.4', 'mac': '00:11:22:33:44:55'}
                ),
                raises(ProvdError).matching(has_properties('status_code', 404)),
            )
            assert_that(
                calling(self._client.devices.update).with_args(
                    {'id': device['id'], 'ip': '10.0.1.1', 'mac': '00:11:22:33:44:xx'}
                ),
                raises(ProvdError).matching(
                    has_properties('status_code', 500)
                ),  # FIXME(afournier): should be 400
            )

    def test_update_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.http.Device(self._client):
            assert_that(
                calling(provd.devices.update).with_args(
                    {'ip': '1.2.3.4', 'mac': '00:11:22:33:44:55'}
                ),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )

    def test_update_change_tenant_from_main_to_subtenant(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=MAIN_TENANT) as device:
            self._client.devices.update(device, tenant_uuid=SUB_TENANT_1)
            device_result = self._client.devices.get(device['id'])
            assert_that(device_result, has_entry('tenant_uuid', SUB_TENANT_1))
            assert_that(device_result, has_entry('is_new', False))

    def test_update_change_tenant_to_main_tenant_does_not_change_tenant_but_update_anyway(
        self,
    ) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            device['ip'] = '10.10.10.10'
            self._client.devices.update(device, tenant_uuid=MAIN_TENANT)
            device_result = self._client.devices.get(device['id'])
            assert_that(device_result, has_entries(**device))

    def test_update_change_tenant_to_other_subtenant_error(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            assert_that(
                calling(self._client.devices.update).with_args(
                    device, tenant_uuid=SUB_TENANT_2
                ),
                raises(ProvdError).matching(has_properties('status_code', 404)),
            )

    def test_update_multitenant_wrong_token_errors(self) -> None:
        provd = self.make_provd(VALID_TOKEN)
        with fixtures.http.Device(self._client) as device:
            assert_that(
                calling(provd.devices.update).with_args(
                    device, tenant_uuid=MAIN_TENANT
                ),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )

    def test_synchronize(self) -> None:
        with fixtures.http.Plugin(self._client, bool(fixtures.http.PLUGIN_TO_INSTALL)):
            with fixtures.http.Device(self._client) as device:
                with self._client.devices.synchronize(
                    device['id']
                ) as operation_progress:
                    until.assert_(
                        operation_successful, operation_progress, tries=20, interval=0.5
                    )

    def test_synchronize_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.http.Device(self._client) as device:
            assert_that(
                calling(provd.devices.synchronize).with_args(device['id']),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )
        assert_that(
            calling(provd.devices.synchronize).with_args('invalid_id'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_synchronize_subtenant_from_main(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            with self._client.devices.synchronize(
                device['id'],
                tenant_uuid=MAIN_TENANT,
            ) as operation_progress:
                until.assert_(
                    operation_successful, operation_progress, tries=20, interval=0.5
                )

    def test_synchronize_main_from_subtenant(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=MAIN_TENANT) as device:
            assert_that(
                calling(self._client.devices.synchronize).with_args(
                    device['id'], tenant_uuid=SUB_TENANT_1
                ),
                raises(ProvdError).matching(has_properties('status_code', 404)),
            )

    def test_synchronize_subtenant_from_another_subtenant(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            assert_that(
                calling(self._client.devices.synchronize).with_args(
                    device['id'], tenant_uuid=SUB_TENANT_2
                ),
                raises(ProvdError).matching(has_properties('status_code', 404)),
            )

    def test_synchronize_multitenant_wrong_token_errors(self) -> None:
        provd = self.make_provd(VALID_TOKEN)
        with fixtures.http.Device(self._client) as device:
            assert_that(
                calling(provd.devices.synchronize).with_args(
                    device['id'], tenant_uuid=SUB_TENANT_1
                ),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )

    def test_get(self) -> None:
        with fixtures.http.Device(self._client) as device:
            result = self._client.devices.get(device['id'])
            assert_that(result['id'], is_(equal_to(device['id'])))

    def test_get_errors(self) -> None:
        assert_that(
            calling(self._client.devices.get).with_args('unknown_id'),
            raises(ProvdError).matching(has_properties('status_code', 404)),
        )

    def test_get_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.http.Device(self._client) as device:
            assert_that(
                calling(provd.devices.get).with_args(device['id']),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )
        assert_that(
            calling(provd.devices.get).with_args('unknown_id'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_get_subtenant_from_main_tenant(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            result = self._client.devices.get(device['id'], tenant_uuid=MAIN_TENANT)
            assert_that(result['id'], is_(equal_to(device['id'])))

    def test_get_main_tenant_from_subtenant_errors(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=MAIN_TENANT) as device:
            assert_that(
                calling(self._client.devices.get).with_args(
                    device['id'], tenant_uuid=SUB_TENANT_1
                ),
                raises(ProvdError).matching(has_properties('status_code', 404)),
            )

    def test_delete(self) -> None:
        with fixtures.http.Device(self._client, delete_on_exit=False) as device:
            self._client.devices.delete(device['id'])
            assert_that(
                calling(self._client.devices.get).with_args(device['id']),
                raises(ProvdError).matching(has_properties('status_code', 404)),
            )

    def test_delete_errors(self) -> None:
        assert_that(
            calling(self._client.devices.delete).with_args('unknown_id'),
            raises(ProvdError).matching(has_properties('status_code', 404)),
        )

    def test_delete_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.http.Device(self._client) as device:
            assert_that(
                calling(provd.devices.delete).with_args(device['id']),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )

    def test_delete_subtenant_from_main_tenant(self) -> None:
        with fixtures.http.Device(
            self._client, delete_on_exit=False, tenant_uuid=SUB_TENANT_1
        ) as device:
            self._client.devices.delete(device['id'], tenant_uuid=MAIN_TENANT)
            assert_that(
                calling(self._client.devices.get).with_args(
                    device['id'], tenant_uuid=SUB_TENANT_1
                ),
                raises(ProvdError).matching(has_properties('status_code', 404)),
            )

    def test_delete_main_tenant_from_subtenant(self) -> None:
        with fixtures.http.Device(
            self._client, delete_on_exit=False, tenant_uuid=MAIN_TENANT
        ) as device:
            assert_that(
                calling(self._client.devices.delete).with_args(
                    device['id'], tenant_uuid=SUB_TENANT_1
                ),
                raises(ProvdError).matching(has_properties('status_code', 404)),
            )
            result = self._client.devices.get(device['id'], tenant_uuid=MAIN_TENANT)
            assert_that(result['id'], is_(equal_to(device['id'])))

    def test_reconfigure(self) -> None:
        with fixtures.http.Device(self._client) as device:
            self._client.devices.reconfigure(device['id'])

    def test_reconfigure_errors(self) -> None:
        assert_that(
            calling(self._client.devices.reconfigure).with_args('unknown_id'),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )

    def test_reconfigure_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        with fixtures.http.Device(self._client) as device:
            assert_that(
                calling(provd.devices.reconfigure).with_args(device['id']),
                raises(ProvdError).matching(has_properties('status_code', 401)),
            )
        assert_that(
            calling(provd.devices.reconfigure).with_args('unknown_id'),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_reconfigure_subtenant_from_main_tenant(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=SUB_TENANT_1) as device:
            self._client.devices.reconfigure(device['id'], tenant_uuid=MAIN_TENANT)

    def test_reconfigure_main_tenant_from_subtenant(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=MAIN_TENANT) as device:
            assert_that(
                calling(self._client.devices.reconfigure).with_args(
                    device['id'], tenant_uuid=SUB_TENANT_1
                ),
                raises(ProvdError).matching(has_properties('status_code', 400)),
            )

    def test_dhcp(self) -> None:
        self._client.devices.create_from_dhcp(
            {
                'ip': '10.10.0.1',
                'mac': 'ab:bc:cd:de:ff:01',
                'op': 'commit',
                'options': [],
            }
        )
        find_results = self._client.devices.list(search={'mac': 'ab:bc:cd:de:ff:01'})
        assert_that(find_results, has_key('devices'))
        assert_that(find_results['devices'], is_not(empty()))
        assert_that(find_results['devices'][0], has_entry('ip', '10.10.0.1'))

    def test_dhcp_errors(self) -> None:
        assert_that(
            calling(self._client.devices.create_from_dhcp).with_args(
                {'ip': '10.10.0.1', 'mac': 'ab:bc:cd:de:ff:01', 'op': 'commit'}
            ),
            raises(ProvdError).matching(has_properties('status_code', 400)),
        )

    def test_dhcp_error_invalid_token(self) -> None:
        provd = self.make_provd(INVALID_TOKEN)
        assert_that(
            calling(provd.devices.create_from_dhcp).with_args(
                {'ip': '10.10.0.1', 'mac': 'ab:bc:cd:de:ff:01', 'op': 'commit'}
            ),
            raises(ProvdError).matching(has_properties('status_code', 401)),
        )

    def test_dhcp_adds_in_main_tenant(self) -> None:
        self._client.devices.create_from_dhcp(
            {
                'ip': '10.10.0.1',
                'mac': 'ab:bc:cd:de:ff:01',
                'op': 'commit',
                'options': [],
            }
        )
        find_results = self._client.devices.list(
            search={'mac': 'ab:bc:cd:de:ff:01'}, tenant_uuid=MAIN_TENANT
        )
        assert_that(find_results, has_key('devices'))
        assert_that(find_results['devices'], is_not(empty()))
        assert_that(find_results['devices'][0], has_entry('ip', '10.10.0.1'))

    def test_modify_tenant_in_device_remain_unchanged(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=MAIN_TENANT) as device:
            self._client.devices.update(
                {'id': device['id'], 'tenant_uuid': SUB_TENANT_1}
            )
            result = self._client.devices.get(device['id'])
            assert_that(result, has_entry('tenant_uuid', MAIN_TENANT))

    def test_modify_is_new_in_device_remain_unchanged(self) -> None:
        with fixtures.http.Device(self._client, tenant_uuid=MAIN_TENANT) as device:
            self._client.devices.update({'id': device['id'], 'is_new': False})
            result = self._client.devices.get(device['id'])
            assert_that(result, has_entry('is_new', True))

    def test_delete_when_tenant_deleted_event(self) -> None:
        with (
            fixtures.http.Device(
                self._client, delete_on_exit=False, tenant_uuid=DELETED_TENANT
            ) as device1,
            fixtures.http.Device(
                self._client, delete_on_exit=False, tenant_uuid=DELETED_TENANT
            ) as device2,
            fixtures.http.Device(
                self._client, delete_on_exit=False, tenant_uuid=SUB_TENANT_1
            ) as device3,
        ):
            BusClient.send_tenant_deleted(DELETED_TENANT, 'slug')

            def devices_deleted():
                assert_that(
                    calling(self._client.devices.get).with_args(
                        device1['id'], tenant_uuid=DELETED_TENANT
                    ),
                    raises(ProvdError).matching(has_properties('status_code', 404)),
                )
                assert_that(
                    calling(self._client.devices.get).with_args(
                        device2['id'], tenant_uuid=DELETED_TENANT
                    ),
                    raises(ProvdError).matching(has_properties('status_code', 404)),
                )

            until.assert_(devices_deleted, tries=20, interval=0.5)

            result = self._client.devices.get(device3['id'])
            assert_that(result, has_entry('id', device3['id']))

    def test_delete_when_tenant_deleted_syncdb(self) -> None:
        self.filesystem.create_file(
            '/etc/wazo-provd/conf.d/01-syncdb.yml',
            content='general: {syncdb: {start_sec: 0, interval_sec: 0.1}}',
        )

        with (
            fixtures.http.Device(
                self._client, delete_on_exit=False, tenant_uuid=DELETED_TENANT
            ) as device1,
            fixtures.http.Device(
                self._client, delete_on_exit=False, tenant_uuid=DELETED_TENANT
            ) as device2,
            fixtures.http.Device(
                self._client, delete_on_exit=False, tenant_uuid=SUB_TENANT_1
            ) as device3,
        ):
            self.restart_service('provd')
            self.set_client()
            self.wait_strategy.wait(self)

            def test_devices() -> None:
                with TestDevices.delete_auth_tenant(DELETED_TENANT):
                    assert_that(
                        calling(self._client.devices.get).with_args(device1['id']),
                        raises(ProvdError).matching(has_properties('status_code', 404)),
                    )
                    assert_that(
                        calling(self._client.devices.get).with_args(device2['id']),
                        raises(ProvdError).matching(has_properties('status_code', 404)),
                    )
                    result = self._client.devices.get(device3['id'])
                    assert_that(result, has_entry('id', device3['id']))

            until.assert_(test_devices, tries=20, interval=0.5)
