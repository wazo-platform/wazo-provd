# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import pytest
from psycopg2 import sql

from ..models import TenantDAO


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
