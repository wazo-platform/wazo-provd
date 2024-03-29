# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import pytest
from psycopg2 import sql

from ..queries import (
    DeviceConfigDAO,
    DeviceDAO,
    DeviceRawConfigDAO,
    ServiceConfigurationDAO,
    TenantDAO,
)


class MockDBConnection:
    def connectionFactory(self, db_connection):
        return self


@pytest.fixture
def db_connection():
    return MockDBConnection()


class TestTenantDAO:
    def test_create_query(self, db_connection):
        tenant_dao = TenantDAO(db_connection)
        expected_composed_query = sql.Composed(
            [
                sql.SQL('INSERT INTO '),
                sql.Identifier('provd_tenant'),
                sql.SQL(' ('),
                sql.Composed(
                    [
                        sql.Identifier('uuid'),
                        sql.SQL(','),
                        sql.Identifier('provisioning_key'),
                    ]
                ),
                sql.SQL(') VALUES ('),
                sql.Composed(
                    [
                        sql.Placeholder('uuid'),
                        sql.SQL(','),
                        sql.Placeholder('provisioning_key'),
                    ]
                ),
                sql.SQL(') RETURNING '),
                sql.Identifier('uuid'),
                sql.SQL(';'),
            ]
        )
        assert tenant_dao._prepare_create_query() == expected_composed_query

    def test_get_query(self, db_connection):
        tenant_dao = TenantDAO(db_connection)
        expected_composed_query = sql.Composed(
            [
                sql.SQL('SELECT '),
                sql.Composed(
                    [
                        sql.Identifier('uuid'),
                        sql.SQL(','),
                        sql.Identifier('provisioning_key'),
                    ]
                ),
                sql.SQL(' FROM '),
                sql.Identifier('provd_tenant'),
                sql.SQL(' WHERE '),
                sql.Identifier('uuid'),
                sql.SQL(' = %s;'),
            ]
        )
        assert tenant_dao._prepare_get_query() == expected_composed_query

    def test_update_query(self):
        tenant_dao = TenantDAO(db_connection)
        expected_composed_query = sql.Composed(
            [
                sql.SQL('UPDATE '),
                sql.Identifier('provd_tenant'),
                sql.SQL(' SET '),
                sql.Composed(
                    [
                        sql.Composed(
                            [
                                sql.Identifier('provisioning_key'),
                                sql.SQL(' = '),
                                sql.Placeholder('provisioning_key'),
                            ]
                        ),
                    ]
                ),
                sql.SQL(' WHERE '),
                sql.Identifier('uuid'),
                sql.SQL(' = %(pkey)s;'),
            ]
        )
        assert tenant_dao._prepare_update_query() == expected_composed_query

    def test_delete_query(self):
        tenant_dao = TenantDAO(db_connection)
        expected_composed_query = sql.Composed(
            [
                sql.SQL('DELETE FROM '),
                sql.Identifier('provd_tenant'),
                sql.SQL(' WHERE '),
                sql.Identifier('uuid'),
                sql.SQL(' = %s;'),
            ]
        )
        assert tenant_dao._prepare_delete_query() == expected_composed_query

    def test_find_all_query(self):
        tenant_dao = TenantDAO(db_connection)
        expected_composed_query = sql.Composed(
            [
                sql.SQL('SELECT '),
                sql.Composed(
                    [
                        sql.Identifier('uuid'),
                        sql.SQL(','),
                        sql.Identifier('provisioning_key'),
                    ]
                ),
                sql.SQL(' FROM '),
                sql.Identifier('provd_tenant'),
                sql.SQL(';'),
            ]
        )
        assert tenant_dao._prepare_find_all_query() == expected_composed_query


class TestServiceConfigurationDAO:
    def test_create_query(self, db_connection):
        configuration_dao = ServiceConfigurationDAO(db_connection)
        expected_composed_query = sql.Composed(
            [
                sql.SQL('INSERT INTO '),
                sql.Identifier('provd_configuration'),
                sql.SQL(' ('),
                sql.Composed(
                    [
                        sql.Identifier('uuid'),
                        sql.SQL(','),
                        sql.Identifier('plugin_server'),
                        sql.SQL(','),
                        sql.Identifier('http_proxy'),
                        sql.SQL(','),
                        sql.Identifier('https_proxy'),
                        sql.SQL(','),
                        sql.Identifier('ftp_proxy'),
                        sql.SQL(','),
                        sql.Identifier('locale'),
                        sql.SQL(','),
                        sql.Identifier('nat_enabled'),
                    ]
                ),
                sql.SQL(') VALUES ('),
                sql.Composed(
                    [
                        sql.Placeholder('uuid'),
                        sql.SQL(','),
                        sql.Placeholder('plugin_server'),
                        sql.SQL(','),
                        sql.Placeholder('http_proxy'),
                        sql.SQL(','),
                        sql.Placeholder('https_proxy'),
                        sql.SQL(','),
                        sql.Placeholder('ftp_proxy'),
                        sql.SQL(','),
                        sql.Placeholder('locale'),
                        sql.SQL(','),
                        sql.Placeholder('nat_enabled'),
                    ]
                ),
                sql.SQL(') RETURNING '),
                sql.Identifier('uuid'),
                sql.SQL(';'),
            ]
        )
        assert configuration_dao._prepare_create_query() == expected_composed_query

    def test_find_one_query(self):
        configuration_dao = ServiceConfigurationDAO(db_connection)
        expected_composed_query = sql.Composed(
            [
                sql.SQL('SELECT '),
                sql.Composed(
                    [
                        sql.Identifier('uuid'),
                        sql.SQL(','),
                        sql.Identifier('plugin_server'),
                        sql.SQL(','),
                        sql.Identifier('http_proxy'),
                        sql.SQL(','),
                        sql.Identifier('https_proxy'),
                        sql.SQL(','),
                        sql.Identifier('ftp_proxy'),
                        sql.SQL(','),
                        sql.Identifier('locale'),
                        sql.SQL(','),
                        sql.Identifier('nat_enabled'),
                    ]
                ),
                sql.SQL(' FROM '),
                sql.Identifier('provd_configuration'),
                sql.SQL(' LIMIT 1;'),
            ]
        )
        assert configuration_dao._prepare_find_one_query() == expected_composed_query

    def test_update_key_query(self):
        configuration_dao = ServiceConfigurationDAO(db_connection)
        expected_composed_query = sql.Composed(
            [
                sql.SQL('UPDATE '),
                sql.Identifier('provd_configuration'),
                sql.SQL(' SET '),
                sql.Identifier('nat_enabled'),
                sql.SQL(' = %s;'),
            ]
        )
        assert (
            configuration_dao._prepare_update_key_query('nat_enabled')
            == expected_composed_query
        )

        with pytest.raises(KeyError, match=r'invalid_key'):
            configuration_dao._prepare_update_key_query('invalid_key')


class TestDeviceDAO:
    def test_find_from_configs(self):
        device_dao = DeviceDAO(db_connection)
        expected_composed_query = sql.Composed(
            [
                sql.SQL('SELECT '),
                sql.Composed(
                    [
                        sql.Identifier('id'),
                        sql.SQL(','),
                        sql.Identifier('tenant_uuid'),
                        sql.SQL(','),
                        sql.Identifier('config_id'),
                        sql.SQL(','),
                        sql.Identifier('mac'),
                        sql.SQL(','),
                        sql.Identifier('ip'),
                        sql.SQL(','),
                        sql.Identifier('vendor'),
                        sql.SQL(','),
                        sql.Identifier('model'),
                        sql.SQL(','),
                        sql.Identifier('version'),
                        sql.SQL(','),
                        sql.Identifier('plugin'),
                        sql.SQL(','),
                        sql.Identifier('configured'),
                        sql.SQL(','),
                        sql.Identifier('auto_added'),
                        sql.SQL(','),
                        sql.Identifier('is_new'),
                    ]
                ),
                sql.SQL(' FROM '),
                sql.Identifier('provd_device'),
                sql.SQL(' WHERE '),
                sql.Identifier('config_id'),
                sql.SQL(' = ANY(%s);'),
            ]
        )
        assert device_dao._prepare_find_from_configs_query() == expected_composed_query


class TestDeviceConfigDAO:
    def test_get_descendants(self):
        device_config_dao = DeviceConfigDAO(db_connection)
        fields = sql.Composed(
            [
                sql.Identifier('id'),
                sql.SQL(','),
                sql.Identifier('parent_id'),
                sql.SQL(','),
                sql.Identifier('deletable'),
                sql.SQL(','),
                sql.Identifier('type'),
                sql.SQL(','),
                sql.Identifier('roles'),
                sql.SQL(','),
                sql.Identifier('configdevice'),
                sql.SQL(','),
                sql.Identifier('transient'),
            ]
        )
        prefixed_fields = sql.Composed(
            [
                sql.Identifier('provd_device_config', 'id'),
                sql.SQL(','),
                sql.Identifier('provd_device_config', 'parent_id'),
                sql.SQL(','),
                sql.Identifier('provd_device_config', 'deletable'),
                sql.SQL(','),
                sql.Identifier('provd_device_config', 'type'),
                sql.SQL(','),
                sql.Identifier('provd_device_config', 'roles'),
                sql.SQL(','),
                sql.Identifier('provd_device_config', 'configdevice'),
                sql.SQL(','),
                sql.Identifier('provd_device_config', 'transient'),
            ]
        )
        expected_composed_query = sql.Composed(
            [
                sql.SQL('WITH RECURSIVE '),
                sql.Identifier('all_children'),
                sql.SQL('('),
                fields,
                sql.SQL(') AS (\nSELECT '),
                fields,
                sql.SQL(' FROM '),
                sql.Identifier('provd_device_config'),
                sql.SQL(' WHERE '),
                sql.Identifier('parent_id'),
                sql.SQL(' = %s\nUNION ALL\nSELECT '),
                prefixed_fields,
                sql.SQL(' FROM '),
                sql.Identifier('all_children'),
                sql.SQL(', '),
                sql.Identifier('provd_device_config'),
                sql.SQL('\nWHERE '),
                sql.Identifier('all_children', 'id'),
                sql.SQL(' = '),
                sql.Identifier('provd_device_config', 'parent_id'),
                sql.SQL('\n)\nSELECT '),
                fields,
                sql.SQL(' FROM '),
                sql.Identifier('all_children'),
                sql.SQL(';'),
            ]
        )
        assert (
            device_config_dao._prepare_get_descendants_query()
            == expected_composed_query
        )


class TestDeviceRawConfigDAO:
    def test_get(self):
        device_raw_config_dao = DeviceRawConfigDAO(db_connection)
        expected_composed_query = sql.Composed(
            [
                sql.SQL('SELECT '),
                sql.Composed(
                    [
                        sql.Identifier('config_id'),
                        sql.SQL(','),
                        sql.Identifier('ip'),
                        sql.SQL(','),
                        sql.Identifier('http_port'),
                        sql.SQL(','),
                        sql.Identifier('http_base_url'),
                        sql.SQL(','),
                        sql.Identifier('tftp_port'),
                        sql.SQL(','),
                        sql.Identifier('dns_enabled'),
                        sql.SQL(','),
                        sql.Identifier('dns_ip'),
                        sql.SQL(','),
                        sql.Identifier('ntp_enabled'),
                        sql.SQL(','),
                        sql.Identifier('ntp_ip'),
                        sql.SQL(','),
                        sql.Identifier('vlan_enabled'),
                        sql.SQL(','),
                        sql.Identifier('vlan_id'),
                        sql.SQL(','),
                        sql.Identifier('vlan_priority'),
                        sql.SQL(','),
                        sql.Identifier('vlan_pc_port_id'),
                        sql.SQL(','),
                        sql.Identifier('syslog_enabled'),
                        sql.SQL(','),
                        sql.Identifier('syslog_ip'),
                        sql.SQL(','),
                        sql.Identifier('syslog_port'),
                        sql.SQL(','),
                        sql.Identifier('syslog_level'),
                        sql.SQL(','),
                        sql.Identifier('admin_username'),
                        sql.SQL(','),
                        sql.Identifier('admin_password'),
                        sql.SQL(','),
                        sql.Identifier('user_username'),
                        sql.SQL(','),
                        sql.Identifier('user_password'),
                        sql.SQL(','),
                        sql.Identifier('timezone'),
                        sql.SQL(','),
                        sql.Identifier('locale'),
                        sql.SQL(','),
                        sql.Identifier('protocol'),
                        sql.SQL(','),
                        sql.Identifier('sip_proxy_ip'),
                        sql.SQL(','),
                        sql.Identifier('sip_proxy_port'),
                        sql.SQL(','),
                        sql.Identifier('sip_backup_proxy_ip'),
                        sql.SQL(','),
                        sql.Identifier('sip_backup_proxy_port'),
                        sql.SQL(','),
                        sql.Identifier('sip_registrar_ip'),
                        sql.SQL(','),
                        sql.Identifier('sip_registrar_port'),
                        sql.SQL(','),
                        sql.Identifier('sip_backup_registrar_ip'),
                        sql.SQL(','),
                        sql.Identifier('sip_backup_registrar_port'),
                        sql.SQL(','),
                        sql.Identifier('sip_outbound_proxy_ip'),
                        sql.SQL(','),
                        sql.Identifier('sip_outbound_proxy_port'),
                        sql.SQL(','),
                        sql.Identifier('sip_dtmf_mode'),
                        sql.SQL(','),
                        sql.Identifier('sip_srtp_mode'),
                        sql.SQL(','),
                        sql.Identifier('sip_transport'),
                        sql.SQL(','),
                        sql.Identifier(
                            'sip_servers_root_and_intermediate_certificates'
                        ),
                        sql.SQL(','),
                        sql.Identifier('sip_local_root_and_intermediate_certificates'),
                        sql.SQL(','),
                        sql.Identifier('sip_local_certificate'),
                        sql.SQL(','),
                        sql.Identifier('sip_local_key'),
                        sql.SQL(','),
                        sql.Identifier('sip_subscribe_mwi'),
                        sql.SQL(','),
                        sql.Identifier('exten_dnd'),
                        sql.SQL(','),
                        sql.Identifier('exten_fwd_unconditional'),
                        sql.SQL(','),
                        sql.Identifier('exten_fwd_no_answer'),
                        sql.SQL(','),
                        sql.Identifier('exten_fwd_busy'),
                        sql.SQL(','),
                        sql.Identifier('exten_fwd_disable_all'),
                        sql.SQL(','),
                        sql.Identifier('exten_park'),
                        sql.SQL(','),
                        sql.Identifier('exten_pickup_group'),
                        sql.SQL(','),
                        sql.Identifier('exten_pickup_call'),
                        sql.SQL(','),
                        sql.Identifier('exten_voicemail'),
                    ]
                ),
                sql.SQL(' FROM '),
                sql.Identifier('provd_device_raw_config'),
                sql.SQL(' WHERE '),
                sql.Identifier('config_id'),
                sql.SQL(' = %s;'),
            ]
        )
        assert device_raw_config_dao._prepare_get_query() == expected_composed_query
