# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import FunctionKey

from .helpers import fixtures
from .helpers.base import INVALID_RESOURCE_UUID, DBIntegrationTest, asyncio_run


class TestFunctionKey(DBIntegrationTest):
    asset = 'database'

    @asyncio_run
    @fixtures.db.device_config()
    async def test_create(self, device_config):
        function_key_uuid = uuid.uuid4()
        function_key = FunctionKey(function_key_uuid, device_config.id)
        created_function_key = await self.function_key_dao.create(function_key)
        assert created_function_key == function_key

        await self.function_key_dao.delete(function_key)

    @asyncio_run
    @fixtures.db.device_config(id='test1')
    @fixtures.db.function_key(config_id='test1')
    async def test_get(self, _, function_key):
        result = await self.function_key_dao.get(function_key.uuid)
        assert result.uuid == function_key.uuid

        with self.assertRaises(EntryNotFoundException):
            await self.function_key_dao.get(INVALID_RESOURCE_UUID)

    @asyncio_run
    @fixtures.db.device_config(id='test2')
    @fixtures.db.function_key(config_id='test2')
    async def test_update(self, _, function_key):
        new_value = '12345'
        function_key.value = new_value
        await self.function_key_dao.update(function_key)

        updated_function_key = await self.function_key_dao.get(function_key.uuid)
        assert updated_function_key.value == new_value

    @asyncio_run
    @fixtures.db.device_config(id='test3')
    @fixtures.db.function_key(config_id='test3')
    async def test_delete(self, _, function_key):
        await self.function_key_dao.delete(function_key)

        with self.assertRaises(EntryNotFoundException):
            await self.function_key_dao.get(function_key.uuid)
