# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import abc
import dataclasses
import logging
import uuid
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

import psycopg2.extras
from psycopg2 import sql

from .exceptions import CreationError, EntryNotFoundException
from .models import (
    Device,
    DeviceConfig,
    DeviceRawConfig,
    FunctionKey,
    Model,
    SCCPLine,
    ServiceConfiguration,
    SIPLine,
    Tenant,
)

if TYPE_CHECKING:
    from twisted.enterprise import adbapi

logger = logging.getLogger(__name__)

psycopg2.extras.register_uuid()

M = TypeVar('M', bound=Model)


class BaseDAO(Generic[M], metaclass=abc.ABCMeta):
    __tablename__: str
    __model__: type[M]

    def __init__(self, db_connection: adbapi.ConnectionPool) -> None:
        self._db_connection = db_connection

    def _get_model_fields(
        self, exclude: list[str] | None = None
    ) -> list[dataclasses.Field]:
        exclude = exclude or []
        fields = dataclasses.fields(self.__model__)
        return [field for field in fields if field.name not in exclude]

    def _get_model_fields_by_name(
        self, exclude: list[str] | None = None
    ) -> dict[str, dataclasses.Field]:
        exclude = exclude or []
        fields = dataclasses.fields(self.__model__)
        return {field.name: field for field in fields if field.name not in exclude}

    def _prepare_create_query(self) -> sql.SQL:
        model_pkey = self.__model__._meta['primary_key']
        fields = self._get_model_fields()
        field_identifiers = sql.SQL(',').join(
            [sql.Identifier(field.name) for field in fields]
        )
        field_placeholders = sql.SQL(',').join(
            [sql.Placeholder(field.name) for field in fields]
        )
        sql_query = sql.SQL(
            'INSERT INTO {table} ({fields}) VALUES ({placeholders}) RETURNING {pkey};'
        ).format(
            table=sql.Identifier(self.__tablename__),
            fields=field_identifiers,
            placeholders=field_placeholders,
            pkey=sql.Identifier(model_pkey),
        )

        return sql_query

    async def create(self, model: M) -> M:
        create_query = self._prepare_create_query()
        model_dict = model.as_dict()
        query_result = await self._db_connection.runQuery(create_query, {**model_dict})
        for result in query_result:
            res = await self.get(result[0])
            return res
        raise CreationError('Could not create entry')

    def _prepare_get_query(self) -> sql.SQL:
        fields = self._get_model_fields()
        field_names = [sql.Identifier(field.name) for field in fields]
        query_fields = sql.SQL(',').join(field_names)

        sql_query = sql.SQL('SELECT {fields} FROM {table} WHERE {pkey} = %s;').format(
            fields=query_fields,
            table=sql.Identifier(self.__tablename__),
            pkey=sql.Identifier(self.__model__._meta['primary_key']),
        )

        return sql_query

    async def get(self, pkey_value: Any) -> M:
        query = self._prepare_get_query()
        query_results = await self._db_connection.runQuery(query, [pkey_value])
        for result in query_results:
            return self.__model__(*result)
        raise EntryNotFoundException('Could not get entry')

    def _prepare_update_query(self) -> sql.SQL:
        model_pkey = self.__model__._meta['primary_key']
        fields = self._get_model_fields(exclude=[model_pkey])
        field_names = [field.name for field in fields]
        query_column_values = sql.SQL(',').join(
            [
                sql.SQL('{column} = {placeholder}').format(
                    column=sql.Identifier(column), placeholder=sql.Placeholder(column)
                )
                for column in field_names
            ]
        )

        sql_query = sql.SQL(
            'UPDATE {table} SET {columns_values} WHERE {pkey_column} = %(pkey)s;'
        ).format(
            table=sql.Identifier(self.__tablename__),
            columns_values=query_column_values,
            pkey_column=sql.Identifier(model_pkey),
        )

        return sql_query

    async def update(self, model: M) -> None:
        update_query = self._prepare_update_query()
        pkey = self.__model__._meta['primary_key']
        pkey_value = getattr(model, pkey)
        model_dict = model.as_dict()
        del model_dict[pkey]
        await self._db_connection.runOperation(
            update_query, {'pkey': pkey_value, **model_dict}
        )

    def _prepare_delete_query(self) -> sql.SQL:
        model_pkey = self.__model__._meta['primary_key']
        return sql.SQL('DELETE FROM {table} WHERE {pkey_column} = %s;').format(
            table=sql.Identifier(self.__tablename__),
            pkey_column=sql.Identifier(model_pkey),
        )

    async def delete(self, model: M) -> None:
        delete_query = self._prepare_delete_query()
        pkey = self.__model__._meta['primary_key']
        pkey_value = getattr(model, pkey)
        await self._db_connection.runOperation(delete_query, [pkey_value])

    def _prepare_fields_find_query(self) -> sql.SQL:
        fields = self._get_model_fields()
        field_names = [sql.Identifier(field.name) for field in fields]
        query_fields = sql.SQL(',').join(field_names)

        sql_query = sql.SQL('SELECT {fields} FROM {table} WHERE ').format(
            fields=query_fields,
            table=sql.Identifier(self.__tablename__),
        )
        return sql_query

    def _remove_invalid_selectors(self, selectors: dict[str, Any]) -> dict[str, Any]:
        valid_selectors = selectors.copy()
        for selector in selectors:
            if selector not in self._get_model_fields_by_name():
                logger.warning('selector "%s" ignored: not a valid field', selector)
                valid_selectors.pop(selector)
        return valid_selectors

    def _prepare_selector_find_query(self, selectors: dict[str, Any] | None) -> sql.SQL:
        if not selectors:
            return sql.SQL('true')

        valid_selectors = self._remove_invalid_selectors(selectors)
        fields_by_name = self._get_model_fields_by_name()

        all_selectors = []
        for selector, value in valid_selectors.items():
            field = fields_by_name[selector]
            operator = ' = '

            # NOTE(afournier): this is necessary since using __future__ annotations
            # converts all annotations to strings at runtime
            if str(field.type).startswith('str') or field.type is str:
                operator = ' LIKE '
                value = f'%{value}%'

            all_selectors.append(
                sql.Identifier(selector) + sql.SQL(operator) + sql.Literal(value)
            )

        return sql.SQL(' AND ').join(all_selectors)

    def _prepare_sort_find_query(
        self, sort: tuple[str, Literal['ASC', 'DESC']]
    ) -> sql.SQL:
        sort_field, sort_order = sort
        return sql.SQL(' ORDER BY {sort_field} {sort_order}').format(
            sort_field=sql.Identifier(sort_field),
            sort_order=sql.SQL(sort_order),
        )

    def _prepare_pagination_find_query(self, skip: int, limit: int) -> sql.SQL:
        return sql.SQL(' LIMIT {limit} OFFSET {offset}').format(
            limit=sql.Literal(limit) if limit else sql.NULL,
            offset=sql.Literal(skip) if skip else sql.NULL,
        )


class TenantDAO(BaseDAO):
    __tablename__ = 'provd_tenant'
    __model__ = Tenant

    def _prepare_find_all_query(self) -> sql.SQL:
        fields = self._get_model_fields()
        field_names = [sql.Identifier(field.name) for field in fields]
        query_fields = sql.SQL(',').join(field_names)

        sql_query = sql.SQL('SELECT {fields} FROM {table};').format(
            fields=query_fields,
            table=sql.Identifier(self.__tablename__),
        )

        return sql_query

    async def find_all(self) -> list[Tenant]:
        query = self._prepare_find_all_query()
        results = await self._db_connection.runQuery(query)
        return [self.__model__(*result) for result in results]

    async def get_or_create(self, tenant_uuid: uuid.UUID) -> Tenant:
        try:
            return await self.get(tenant_uuid)
        except EntryNotFoundException:
            new_tenant = Tenant(uuid=tenant_uuid)
            return await self.create(new_tenant)


class ServiceConfigurationDAO(BaseDAO):
    __tablename__ = 'provd_configuration'
    __model__ = ServiceConfiguration

    def _prepare_find_one_query(self) -> sql.SQL:
        fields = self._get_model_fields()
        field_names = [sql.Identifier(field.name) for field in fields]
        query_fields = sql.SQL(',').join(field_names)

        sql_query = sql.SQL('SELECT {fields} FROM {table} LIMIT 1;').format(
            fields=query_fields,
            table=sql.Identifier(self.__tablename__),
        )

        return sql_query

    async def find_one(self) -> ServiceConfiguration:
        query = self._prepare_find_one_query()
        results = await self._db_connection.runQuery(query)
        for result in results:
            return self.__model__(*result)
        raise EntryNotFoundException('Could not get entry')

    def _prepare_update_key_query(self, key: str) -> sql.SQL:
        field_names = [field.name for field in self._get_model_fields()]
        if key not in field_names:
            raise KeyError('Invalid key "%s"', key)

        sql_query = sql.SQL('UPDATE {table} SET {key_field} = %s;').format(
            table=sql.Identifier(self.__tablename__),
            key_field=sql.Identifier(key),
        )
        return sql_query

    async def update_key(self, key: str, value: Any) -> None:
        query = self._prepare_update_key_query(key)
        await self._db_connection.runOperation(query, [value])


class DeviceConfigDAO(BaseDAO):
    __tablename__ = 'provd_device_config'
    __model__ = DeviceConfig

    def _prepare_get_descendants_query(self) -> sql.SQL:
        fields = self._get_model_fields()
        field_names = [sql.Identifier(field.name) for field in fields]
        prefixed_field_names = [
            sql.Identifier(self.__tablename__, field.name) for field in fields
        ]
        query_fields = sql.SQL(',').join(field_names)
        prefixed_query_fields = sql.SQL(',').join(prefixed_field_names)

        sql_query = sql.SQL(
            dedent(
                '''\
                WITH RECURSIVE {all_children}({fields}) AS (
                SELECT {fields} FROM {table} WHERE {parent_key} = %s
                UNION ALL
                SELECT {prefixed_query_fields} FROM {all_children}, {table}
                WHERE {all_children_id} = {prefixed_parent_key}
                )
                SELECT {fields} FROM {all_children};'''
            )
        ).format(
            all_children=sql.Identifier('all_children'),
            fields=query_fields,
            table=sql.Identifier(self.__tablename__),
            parent_key=sql.Identifier('parent_id'),
            prefixed_query_fields=prefixed_query_fields,
            all_children_id=sql.Identifier('all_children', 'id'),
            prefixed_parent_key=sql.Identifier(self.__tablename__, 'parent_id'),
        )

        return sql_query

    async def get_descendants(self, config_id: str) -> list[DeviceConfig]:
        query = self._prepare_get_descendants_query()
        results = await self._db_connection.runQuery(query, [config_id])
        return [self.__model__(*result) for result in results]

    def _prepare_get_parents_query(self) -> sql.SQL:
        fields = self._get_model_fields()
        field_names = [sql.Identifier(field.name) for field in fields]
        prefixed_field_names = [
            sql.Identifier(self.__tablename__, field.name) for field in fields
        ]
        query_fields = sql.SQL(',').join(field_names)
        prefixed_query_fields = sql.SQL(',').join(prefixed_field_names)

        sql_query = sql.SQL(
            dedent(
                '''\
                WITH RECURSIVE {all_parents}({fields}) AS (
                SELECT {fields} FROM {table} WHERE {pkey} = %(pkey)s
                UNION ALL
                SELECT {prefixed_query_fields} FROM {all_parents}, {table}
                WHERE {all_parents_parent_id} = {prefixed_pkey}
                )
                SELECT {fields} FROM {all_parents} WHERE {all_parents_id} != %(pkey)s;'''
            )
        ).format(
            all_parents=sql.Identifier('all_parents'),
            fields=query_fields,
            table=sql.Identifier(self.__tablename__),
            pkey=sql.Identifier(self.__model__._meta['primary_key']),
            all_parents_id=sql.Identifier(
                'all_parents', self.__model__._meta['primary_key']
            ),
            prefixed_query_fields=prefixed_query_fields,
            all_parents_parent_id=sql.Identifier('all_parents', 'parent_id'),
            prefixed_pkey=sql.Identifier(
                self.__tablename__, self.__model__._meta['primary_key']
            ),
        )

        return sql_query

    async def get_parents(self, config_id: str) -> list[DeviceConfig]:
        query = self._prepare_get_parents_query()
        results = await self._db_connection.runQuery(query, {'pkey': config_id})
        return [self.__model__(*result) for result in results]

    def _prepare_find_query(
        self,
        selectors: dict[str, Any] | None,
        skip: int,
        limit: int,
        sort: tuple[str, Literal['ASC', 'DESC']] | None,
    ) -> sql.SQL:
        query = self._prepare_fields_find_query()
        query += self._prepare_selector_find_query(selectors)

        if sort is not None:
            query += self._prepare_sort_find_query(sort)

        if skip or limit:
            query += self._prepare_pagination_find_query(skip, limit)

        query += sql.SQL(';')

        return query

    async def find(
        self,
        selectors: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 0,
        sort: tuple[str, Literal['ASC', 'DESC']] | None = None,
    ) -> list[DeviceConfig]:
        query = self._prepare_find_query(selectors, skip, limit, sort)
        results = await self._db_connection.runQuery(query)
        return [self.__model__(*result) for result in results]

    async def find_one(self, selectors: dict[str, Any] | None = None) -> DeviceConfig:
        query = self._prepare_find_query(selectors, 0, 0, None)
        results = await self._db_connection.runQuery(query)
        for result in results:
            return self.__model__(*result)


class DeviceRawConfigDAO(BaseDAO):
    __tablename__ = 'provd_device_raw_config'
    __model__ = DeviceRawConfig


class DeviceDAO(BaseDAO):
    __tablename__ = 'provd_device'
    __model__ = Device

    def _prepare_find_from_configs_query(self) -> sql.SQL:
        fields = self._get_model_fields()
        field_names = [sql.Identifier(field.name) for field in fields]
        query_fields = sql.SQL(',').join(field_names)

        sql_query = sql.SQL(
            'SELECT {fields} FROM {table} WHERE {config_key} = ANY(%s);'
        ).format(
            fields=query_fields,
            table=sql.Identifier(self.__tablename__),
            config_key=sql.Identifier('config_id'),
        )

        return sql_query

    async def find_from_configs(self, config_ids: list[str]) -> list[Device]:
        query = self._prepare_find_from_configs_query()
        results = await self._db_connection.runQuery(query, [config_ids])
        return [self.__model__(*result) for result in results]

    def _prepare_find_one_from_config_query(self) -> sql.SQL:
        fields = self._get_model_fields()
        field_names = [sql.Identifier(field.name) for field in fields]
        query_fields = sql.SQL(',').join(field_names)

        sql_query = sql.SQL(
            'SELECT {fields} FROM {table} WHERE {config_key} = %s LIMIT 1;'
        ).format(
            fields=query_fields,
            table=sql.Identifier(self.__tablename__),
            config_key=sql.Identifier('config_id'),
        )

        return sql_query

    async def find_one_from_config(self, config_id: str) -> Device:
        query = self._prepare_find_one_from_config_query()
        results = await self._db_connection.runQuery(query, [config_id])
        for result in results:
            return self.__model__(*result)
        raise EntryNotFoundException('Could not get entry')

    def _prepare_multitenant_get_query(self) -> sql.SQL:
        fields = self._get_model_fields()
        field_names = [sql.Identifier(field.name) for field in fields]
        query_fields = sql.SQL(',').join(field_names)

        sql_query = sql.SQL(
            'SELECT {fields} FROM {table} WHERE {pkey} = %s AND {tenant_field} = ANY(%s);'
        ).format(
            fields=query_fields,
            table=sql.Identifier(self.__tablename__),
            pkey=sql.Identifier(self.__model__._meta['primary_key']),
            tenant_field=sql.Identifier('tenant_uuid'),
        )

        return sql_query

    async def get(
        self, pkey_value: Any, tenant_uuids: list[uuid.UUID] | None = None
    ) -> Device:
        if tenant_uuids is None:
            query = self._prepare_get_query()
            query_results = await self._db_connection.runQuery(query, [pkey_value])
        else:
            query = self._prepare_multitenant_get_query()
            query_results = await self._db_connection.runQuery(
                query, [pkey_value, tenant_uuids]
            )

        for result in query_results:
            return self.__model__(*result)
        raise EntryNotFoundException('Could not get entry')

    def _prepare_tenant_uuids_find_query(
        self, tenant_uuids: list[uuid.UUID]
    ) -> sql.SQL:
        return sql.SQL('{tenant_uuid} = ANY({tenant_uuids}) AND ').format(
            tenant_uuid=sql.Identifier('tenant_uuid'),
            tenant_uuids=sql.Literal(tenant_uuids),
        )

    def _prepare_find_query(
        self,
        selectors: dict[str, Any] | None,
        tenant_uuids: list[uuid.UUID] | None,
        skip: int,
        limit: int,
        sort: tuple[str, Literal['ASC', 'DESC']] | None,
    ) -> sql.SQL:
        query = self._prepare_fields_find_query()

        if tenant_uuids:
            query += self._prepare_tenant_uuids_find_query(tenant_uuids)

        query += self._prepare_selector_find_query(selectors)

        if sort is not None:
            query += self._prepare_sort_find_query(sort)

        if skip or limit:
            query += self._prepare_pagination_find_query(skip, limit)

        query += sql.SQL(';')

        return query

    async def find(
        self,
        selectors: dict[str, Any] | None = None,
        tenant_uuids: list[uuid.UUID] | None = None,
        skip: int = 0,
        limit: int = 0,
        sort: tuple[str, Literal['ASC', 'DESC']] | None = None,
    ) -> list[Device]:
        query = self._prepare_find_query(selectors, tenant_uuids, skip, limit, sort)
        results = await self._db_connection.runQuery(query)
        return [self.__model__(*result) for result in results]


class SIPLineDAO(BaseDAO):
    __tablename__ = 'provd_sip_line'
    __model__ = SIPLine


class SCCPLineDAO(BaseDAO):
    __tablename__ = 'provd_sccp_line'
    __model__ = SCCPLine


class FunctionKeyDAO(BaseDAO):
    __tablename__ = 'provd_function_key'
    __model__ = FunctionKey
