# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import abc
import copy
import dataclasses
import logging
import uuid
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Generic, Literal, Optional, TypeVar

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
        return [
            field
            for field in fields
            if field.name not in exclude and not field.metadata.get('assoc')
        ]

    def _get_model_associations(
        self, exclude: list[str] | None = None
    ) -> list[dataclasses.Field]:
        exclude = exclude or []
        fields = dataclasses.fields(self.__model__)
        return [
            field
            for field in fields
            if field.name not in exclude and field.metadata.get('assoc')
        ]

    def _get_model_fields_by_name(
        self, exclude: list[str] | None = None
    ) -> dict[str, dataclasses.Field]:
        exclude = exclude or []
        fields = dataclasses.fields(self.__model__)
        return {field.name: field for field in fields if field.name not in exclude}

    async def _load_associations(self, model: M) -> M:
        return model

    async def _save_associations(self, model: M) -> M:
        return model

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
        model_dict = model.as_dict(ignore_associations=True)
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
            new_model = self.__model__(*result)
            model = await self._load_associations(new_model)
            return model
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
        await self.get(pkey_value)
        model_dict = model.as_dict(ignore_associations=True)
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

    def __init__(
        self,
        db_connection: adbapi.ConnectionPool,
        raw_config_dao: DeviceRawConfigDAO,
    ):
        super().__init__(db_connection)
        self._raw_config_dao = raw_config_dao

    async def _load_associations(self, model: DeviceConfig) -> DeviceConfig:
        try:
            model.raw_config = await self._raw_config_dao.get(model.id)
        except EntryNotFoundException:
            model.raw_config = None
        return model

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
        return [
            await self._load_associations(self.__model__(*result)) for result in results
        ]

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
        return [
            await self._load_associations(self.__model__(*result)) for result in results
        ]

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

        return [
            await self._load_associations(self.__model__(*result)) for result in results
        ]

    async def find_one(
        self, selectors: dict[str, Any] | None = None
    ) -> Optional[DeviceConfig]:
        query = self._prepare_find_query(selectors, 0, 0, None)
        results = await self._db_connection.runQuery(query)
        for result in results:
            return await self._load_associations(self.__model__(*result))
        return None

    async def _save_associations(self, model: DeviceConfig) -> DeviceConfig:
        if not model.raw_config:
            return model

        model.raw_config.config_id = model.id
        try:
            await self._raw_config_dao.update(model.raw_config)
        except EntryNotFoundException:
            raw_config = await self._raw_config_dao.create(model.raw_config)
            model.raw_config = raw_config
        return model

    async def create(self, model: DeviceConfig) -> DeviceConfig:
        await super().create(model)
        new_model = await self._save_associations(model)
        return new_model

    async def update(self, model: DeviceConfig) -> None:
        await super().update(model)
        await self._save_associations(model)

    async def delete(self, model: DeviceConfig) -> None:
        if model.raw_config:
            await self._raw_config_dao.delete(model.raw_config)
        new_parent = model.parent_id
        children = await self.get_descendants(model.id)
        if children:
            for child in children:
                child.parent_id = new_parent
                await self.update(child)
        await super().delete(model)


class DeviceRawConfigDAO(BaseDAO):
    __tablename__ = 'provd_device_raw_config'
    __model__ = DeviceRawConfig

    def __init__(
        self,
        db_connection: adbapi.ConnectionPool,
        fkey_dao: FunctionKeyDAO,
        sip_line_dao: SIPLineDAO,
        sccp_line_dao: SCCPLineDAO,
    ) -> None:
        super().__init__(db_connection)
        self._fkey_dao = fkey_dao
        self._sip_line_dao = sip_line_dao
        self._sccp_line_dao = sccp_line_dao

    async def _load_associations(self, model: DeviceRawConfig) -> DeviceRawConfig:
        function_keys: list[FunctionKey] = await self._fkey_dao.find_from_config(
            model.config_id
        )
        if function_keys:
            model.function_keys = {str(fkey.position): fkey for fkey in function_keys}

        sip_lines: list[SIPLine] = await self._sip_line_dao.find_from_config(
            model.config_id
        )
        if sip_lines:
            model.sip_lines = {
                str(sip_line.position): sip_line for sip_line in sip_lines
            }

        sccp_lines: list[SCCPLine] = await self._sccp_line_dao.find_from_config(
            model.config_id
        )
        if sccp_lines:
            model.sccp_lines = {
                str(sccp_line.position): sccp_line for sccp_line in sccp_lines
            }
        return model

    async def _save_associations(self, model: DeviceRawConfig) -> DeviceRawConfig:
        original_model = await self._load_associations(copy.copy(model))
        if model.function_keys:
            if original_model.function_keys:
                fkeys_to_delete = set(original_model.function_keys.keys()) - set(
                    model.function_keys.keys()
                )
                for fkey_to_delete in fkeys_to_delete:
                    try:
                        await self._fkey_dao.delete(
                            original_model.function_keys[fkey_to_delete]
                        )
                    except EntryNotFoundException:
                        logger.error(
                            'Could not delete function key: %s', fkey_to_delete
                        )
                        raise

            for position, fkey in model.function_keys.items():
                fkey.config_id = model.config_id
                fkey.position = int(position)
                try:
                    await self._fkey_dao.update(fkey)
                except EntryNotFoundException:
                    fkey.uuid = fkey.uuid or uuid.uuid4()
                    await self._fkey_dao.create(fkey)

        if model.sip_lines:
            if original_model.sip_lines:
                sip_lines_to_delete = set(original_model.sip_lines.keys()) - set(
                    model.sip_lines.keys()
                )
                for sip_line_to_delete in sip_lines_to_delete:
                    try:
                        await self._sip_line_dao.delete(
                            original_model.sip_lines[sip_line_to_delete]
                        )
                    except EntryNotFoundException:
                        logger.error(
                            'Could not delete SIP line: %s', sip_line_to_delete
                        )
                        raise

            for position, sip_line in model.sip_lines.items():
                sip_line.config_id = model.config_id
                sip_line.position = int(position)
                try:
                    await self._sip_line_dao.update(sip_line)
                except EntryNotFoundException:
                    sip_line.uuid = sip_line.uuid or uuid.uuid4()
                    await self._sip_line_dao.create(sip_line)

        if model.sccp_lines:
            if original_model.sccp_lines:
                sccp_lines_to_delete = set(original_model.sccp_lines.keys()) - set(
                    model.sccp_lines.keys()
                )
                for sccp_line_to_delete in sccp_lines_to_delete:
                    try:
                        await self._sccp_line_dao.delete(
                            original_model.sccp_lines[sccp_line_to_delete]
                        )
                    except EntryNotFoundException:
                        logger.error(
                            'Could not delete SCCP line: %s', sccp_line_to_delete
                        )
                        raise

            for position, sccp_line in model.sccp_lines.items():
                sccp_line.config_id = model.config_id
                sccp_line.position = int(position)
                try:
                    await self._sccp_line_dao.update(sccp_line)
                except EntryNotFoundException:
                    sccp_line.uuid = sccp_line.uuid or uuid.uuid4()
                    await self._sccp_line_dao.create(sccp_line)
        return model

    async def get(self, pkey_value: Any) -> DeviceRawConfig:
        model = await super().get(pkey_value)
        model = await self._load_associations(model)
        return model

    async def create(self, model: DeviceRawConfig) -> DeviceRawConfig:
        await super().create(model)
        new_model = await self._save_associations(model)
        return new_model

    async def update(self, model: DeviceRawConfig) -> None:
        await super().update(model)
        await self._save_associations(model)


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
        self, tenant_uuids: list[uuid.UUID | str]
    ) -> sql.SQL:
        clean_tenant_uuids = [
            uuid.UUID(str(tenant_uuid)) for tenant_uuid in tenant_uuids
        ]
        return sql.SQL('{tenant_uuid} = ANY({tenant_uuids}) AND ').format(
            tenant_uuid=sql.Identifier('tenant_uuid'),
            tenant_uuids=sql.Literal(clean_tenant_uuids),
        )

    def _prepare_find_query(
        self,
        selectors: dict[str, Any] | None,
        tenant_uuids: list[uuid.UUID | str] | None,
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
        tenant_uuids: list[uuid.UUID | str] | None = None,
        skip: int = 0,
        limit: int = 0,
        sort: tuple[str, Literal['ASC', 'DESC']] | None = None,
    ) -> list[Device]:
        logger.debug(
            'Devices find with selectors: %s and tenant_uuids: %s',
            selectors,
            tenant_uuids,
        )
        query = self._prepare_find_query(selectors, tenant_uuids, skip, limit, sort)
        results = await self._db_connection.runQuery(query)
        return [self.__model__(*result) for result in results]


class _ConfigRelationDAO(BaseDAO):
    def _prepare_find_from_config_query(self) -> sql.SQL:
        fields = self._get_model_fields()
        field_names = [sql.Identifier(field.name) for field in fields]
        query_fields = sql.SQL(',').join(field_names)

        sql_query = sql.SQL(
            'SELECT {fields} FROM {table} WHERE {config_key} = %s;'
        ).format(
            fields=query_fields,
            table=sql.Identifier(self.__tablename__),
            config_key=sql.Identifier('config_id'),
        )

        return sql_query

    async def find_from_config(self, config_id: str) -> list[M]:
        query = self._prepare_find_from_config_query()
        results = await self._db_connection.runQuery(query, [config_id])
        return [self.__model__(*result) for result in results]


class SIPLineDAO(_ConfigRelationDAO):
    __tablename__ = 'provd_sip_line'
    __model__ = SIPLine


class SCCPLineDAO(_ConfigRelationDAO):
    __tablename__ = 'provd_sccp_line'
    __model__ = SCCPLine


class FunctionKeyDAO(_ConfigRelationDAO):
    __tablename__ = 'provd_function_key'
    __model__ = FunctionKey
