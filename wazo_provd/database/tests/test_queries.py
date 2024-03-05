# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import pytest
from psycopg2 import sql

from ..queries import ServiceConfigurationDAO, TenantDAO


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
