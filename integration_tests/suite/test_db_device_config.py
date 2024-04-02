# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import DeviceConfig

from .helpers import fixtures
from .helpers.base import (
    INVALID_RESOURCE_UUID,
    MAIN_TENANT,
    DBIntegrationTest,
    asyncio_run,
)


class TestDeviceConfig(DBIntegrationTest):
    asset = 'database'

    @asyncio_run
    @fixtures.db.tenant(uuid=uuid.UUID(MAIN_TENANT))
    @fixtures.db.device_config(id='test1')
    @fixtures.db.device_config(id='test2', parent_id='test1')
    @fixtures.db.device_config(id='test3', parent_id='test2')
    async def test_get_descendants(self, _, __, config2, config3):
        descendants_root_config_id = await self.device_config_dao.get_descendants(
            'test1'
        )
        assert descendants_root_config_id == [config2, config3]

        descendants_child_config_id = await self.device_config_dao.get_descendants(
            'test2'
        )
        assert descendants_child_config_id == [config3]

        descendants_grandchild_config_id = await self.device_config_dao.get_descendants(
            'test3'
        )
        assert descendants_grandchild_config_id == []

    @asyncio_run
    async def test_create(self):
        device_config = DeviceConfig(id=uuid.uuid4().hex)
        created_device_config = await self.device_config_dao.create(device_config)
        assert created_device_config == device_config

        await self.device_config_dao.delete(device_config)

    @asyncio_run
    @fixtures.db.device_config()
    async def test_get(self, device_config):
        result = await self.device_config_dao.get(device_config.id)
        assert result.id == device_config.id

        with self.assertRaises(EntryNotFoundException):
            await self.device_config_dao.get(INVALID_RESOURCE_UUID)

    @asyncio_run
    @fixtures.db.tenant(uuid=uuid.UUID(MAIN_TENANT))
    @fixtures.db.device(tenant_uuid=uuid.UUID(MAIN_TENANT))
    async def test_update(self, _, device):
        new_ip = '1.2.3.4'
        device.ip = new_ip
        await self.device_dao.update(device)

        updated_device = await self.device_dao.get(device.id)
        assert updated_device.ip == new_ip

    @asyncio_run
    @fixtures.db.tenant(uuid=uuid.UUID(MAIN_TENANT))
    @fixtures.db.device(tenant_uuid=uuid.UUID(MAIN_TENANT))
    async def test_delete(self, _, device):
        await self.device_dao.delete(device)

        with self.assertRaises(EntryNotFoundException):
            await self.device_dao.get(device.id)
