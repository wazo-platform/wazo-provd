# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import abc
import dataclasses
import uuid
from typing import TYPE_CHECKING, Any

from psycopg2 import sql
from twisted.enterprise import adbapi

from .exceptions import CreationError
from .models import Tenant

if TYPE_CHECKING:
    from .models import Model


class BaseDAO(metaclass=abc.ABCMeta):
    __tablename__: str
    __model__: type[Model]

    def __init__(self, db_connection: adbapi.ConnectionPool) -> None:
        self._db_connection = db_connection

    def _get_model_fields(
        self, exclude: list[str] | None = None
    ) -> list[dataclasses.Field]:
        exclude = exclude or []
        fields = dataclasses.fields(self.__model__)
        return [field for field in fields if field.name not in exclude]

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

    async def create(self, model: Model) -> Model:
        model_pkey = self.__model__._meta['primary_key']
        create_query = self._prepare_create_query()
        model_dict = dataclasses.asdict(model)
        model_dict[model_pkey] = uuid.uuid4()
        query_result = await self._db_connection.runQuery(create_query, {**model_dict})
        for result in query_result:
            res = await self.get(result[model_pkey])
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

    async def get(self, pkey_value: Any) -> Model:
        query = self._prepare_get_query()
        query_results = await self._db_connection.runQuery(query, [pkey_value])
        for result in query_results:
            return self.__model__(*result)
        raise Exception('Could not get item')  # XXX change this exception

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

    async def update(self, model: Model) -> None:
        update_query = self._prepare_update_query()
        pkey = self.__model__._meta['primary_key']
        pkey_value = getattr(model, pkey)
        model_dict = dataclasses.asdict(model)
        del model_dict[pkey]
        await self._db_connection.runQuery(
            update_query, {'pkey': pkey_value, **model_dict}
        )

    def _prepare_delete_query(self) -> sql.SQL:
        model_pkey = self.__model__._meta['primary_key']
        return sql.SQL('DELETE FROM {table} WHERE {pkey_column} = %s;').format(
            table=sql.Identifier(self.__tablename__),
            pkey_column=sql.Identifier(model_pkey),
        )

    async def delete(self, model: Model) -> None:
        delete_query = self._prepare_delete_query()
        pkey = self.__model__._meta['primary_key']
        pkey_value = getattr(model, pkey)
        await self._db_connection.runQuery(delete_query, [pkey_value])


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
