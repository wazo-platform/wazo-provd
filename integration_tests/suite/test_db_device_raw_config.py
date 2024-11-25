# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import DeviceRawConfig

from .helpers import fixtures
from .helpers.base import INVALID_RESOURCE_UUID, DBIntegrationTest, asyncio_run


class TestDeviceRawConfig(DBIntegrationTest):
    asset = 'database'

    @asyncio_run
    @fixtures.db.device_config(id='deviceconf1')
    async def test_create(self, _):
        device_raw_config = DeviceRawConfig(config_id='deviceconf1')
        created_device_raw_config = await self.device_raw_config_dao.create(
            device_raw_config
        )
        assert created_device_raw_config == device_raw_config

        await self.device_raw_config_dao.delete(device_raw_config)

    @asyncio_run
    @fixtures.db.device_config(id='deviceconf2')
    @fixtures.db.device_raw_config(config_id='deviceconf2')
    async def test_get(self, _, device_raw_config):
        result = await self.device_raw_config_dao.get(device_raw_config.config_id)
        assert result.config_id == device_raw_config.config_id

        with self.assertRaises(EntryNotFoundException):
            await self.device_raw_config_dao.get(INVALID_RESOURCE_UUID)

    @asyncio_run
    @fixtures.db.device_config(id='deviceconf3')
    @fixtures.db.device_raw_config(config_id='deviceconf3')
    async def test_update(self, _, device_raw_config):
        new_http_base_url = 'http://localhost:8667'
        device_raw_config.http_base_url = new_http_base_url
        await self.device_raw_config_dao.update(device_raw_config)

        updated_device_raw_config = await self.device_raw_config_dao.get(
            device_raw_config.config_id
        )
        assert updated_device_raw_config.http_base_url == new_http_base_url

    @asyncio_run
    @fixtures.db.device_config(id='deviceconf4')
    @fixtures.db.device_raw_config(config_id='deviceconf4')
    async def test_delete(self, _, device_raw_config):
        await self.device_raw_config_dao.delete(device_raw_config)

        with self.assertRaises(EntryNotFoundException):
            await self.device_raw_config_dao.get(device_raw_config.config_id)
