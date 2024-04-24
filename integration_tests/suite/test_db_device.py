# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import Device

from .helpers import fixtures
from .helpers.base import (
    INVALID_RESOURCE_UUID,
    MAIN_TENANT,
    SUB_TENANT_1,
    DBIntegrationTest,
    asyncio_run,
)

MAIN_TENANT_UUID = uuid.UUID(MAIN_TENANT)
SUB_TENANT_1_UUID = uuid.UUID(SUB_TENANT_1)


class TestDevice(DBIntegrationTest):
    asset = 'database'

    @asyncio_run
    @fixtures.db.tenant(uuid=MAIN_TENANT_UUID)
    @fixtures.db.device_config(id='test1')
    @fixtures.db.device_config(id='test2')
    @fixtures.db.device_config(id='test3')
    @fixtures.db.device(tenant_uuid=MAIN_TENANT_UUID, config_id='test1')
    @fixtures.db.device(tenant_uuid=MAIN_TENANT_UUID, config_id='test2')
    @fixtures.db.device(tenant_uuid=MAIN_TENANT_UUID, config_id='test3')
    async def test_find_from_configs(self, _, __, ___, ____, device1, device2, device3):
        device_one_config_id = await self.device_dao.find_from_configs(['test2'])
        assert device_one_config_id == [device2]

        device_two_config_ids = await self.device_dao.find_from_configs(
            ['test1', 'test3']
        )
        assert device_two_config_ids == [device1, device3]

    @asyncio_run
    @fixtures.db.tenant(uuid=MAIN_TENANT_UUID)
    @fixtures.db.device_config(id='test4')
    @fixtures.db.device(tenant_uuid=MAIN_TENANT_UUID, config_id='test4')
    async def test_find_one_from_config(self, _, __, device):
        device_from_db = await self.device_dao.find_one_from_config('test4')
        assert device == device_from_db

    @asyncio_run
    @fixtures.db.tenant(uuid=MAIN_TENANT_UUID)
    @fixtures.db.tenant(uuid=SUB_TENANT_1_UUID)
    @fixtures.db.device_config(id='test5')
    @fixtures.db.device_config(id='test6')
    @fixtures.db.device_config(id='test7')
    @fixtures.db.device(
        mac='00:11:22:33:44:55', tenant_uuid=MAIN_TENANT_UUID, config_id='test5'
    )
    @fixtures.db.device(
        mac='11:22:33:44:55:66', tenant_uuid=MAIN_TENANT_UUID, config_id='test6'
    )
    @fixtures.db.device(
        mac='00:00:00:00:55:66',
        ip='1.2.3.4',
        tenant_uuid=SUB_TENANT_1_UUID,
        config_id='test7',
    )
    async def test_find(self, _, __, ___, ____, _____, device1, device2, device3):
        results = await self.device_dao.find({'mac': '22:33'})
        assert results == [device1, device2]

        results = await self.device_dao.find({'mac': '55:66'})
        assert results == [device2, device3]

        results = await self.device_dao.find({'ip': '1.2.3.4'})
        assert results == [device3]

        results = await self.device_dao.find({'ip': '1.2.3.4', 'mac': '55:66'})
        assert results == [device3]

        results = await self.device_dao.find()
        assert results == [device1, device2, device3]

        results = await self.device_dao.find({})
        assert results == [device1, device2, device3]

        results = await self.device_dao.find({'mac': 'unknown'})
        assert results == []

    @asyncio_run
    @fixtures.db.tenant(uuid=MAIN_TENANT_UUID)
    @fixtures.db.tenant(uuid=SUB_TENANT_1_UUID)
    @fixtures.db.device_config(id='test5')
    @fixtures.db.device_config(id='test6')
    @fixtures.db.device_config(id='test7')
    @fixtures.db.device(
        mac='00:11:22:33:44:55', tenant_uuid=MAIN_TENANT_UUID, config_id='test5'
    )
    @fixtures.db.device(
        mac='11:22:33:44:55:66', tenant_uuid=MAIN_TENANT_UUID, config_id='test6'
    )
    @fixtures.db.device(
        mac='00:00:00:00:55:66',
        ip='1.2.3.4',
        tenant_uuid=SUB_TENANT_1_UUID,
        config_id='test7',
    )
    async def test_find_multitenant(
        self, _, __, ___, ____, _____, device1, device2, device3
    ):
        results = await self.device_dao.find(tenant_uuids=[MAIN_TENANT_UUID])
        assert results == [device1, device2]

        results = await self.device_dao.find(tenant_uuids=[SUB_TENANT_1_UUID])
        assert results == [device3]

        results = await self.device_dao.find(
            tenant_uuids=[MAIN_TENANT_UUID, SUB_TENANT_1_UUID]
        )
        assert results == [device1, device2, device3]

    @asyncio_run
    @fixtures.db.tenant(uuid=MAIN_TENANT_UUID)
    @fixtures.db.tenant(uuid=SUB_TENANT_1_UUID)
    @fixtures.db.device_config(id='test5')
    @fixtures.db.device_config(id='test6')
    @fixtures.db.device_config(id='test7')
    @fixtures.db.device(
        mac='00:11:22:33:44:55', tenant_uuid=MAIN_TENANT_UUID, config_id='test5'
    )
    @fixtures.db.device(
        mac='11:22:33:44:55:66', tenant_uuid=MAIN_TENANT_UUID, config_id='test6'
    )
    @fixtures.db.device(
        mac='00:00:00:00:55:66',
        ip='1.2.3.4',
        tenant_uuid=SUB_TENANT_1_UUID,
        config_id='test7',
    )
    @fixtures.db.device(
        mac='00:00:00:00:55:67', ip='1.2.3.5', tenant_uuid=SUB_TENANT_1_UUID
    )
    async def test_find_pagination_sort(
        self, _, __, ___, ____, _____, device1, device2, device3, device4
    ):
        results = await self.device_dao.find(limit=1, skip=2)
        assert results == [device3]

        results = await self.device_dao.find(limit=2, skip=2)
        assert results == [device3, device4]

        results = await self.device_dao.find(skip=1)
        assert results == [device2, device3, device4]

        results = await self.device_dao.find(limit=3)
        assert results == [device1, device2, device3]

        results = await self.device_dao.find(limit=3, sort=('config_id', 'DESC'))
        assert results == [device4, device3, device2]

        results = await self.device_dao.find(limit=3, sort=('mac', 'ASC'))
        assert results == [device3, device4, device1]

    @asyncio_run
    @fixtures.db.tenant(uuid=MAIN_TENANT_UUID)
    async def test_create(self, _):
        device_id = uuid.uuid4().hex
        device = Device(id=device_id, tenant_uuid=MAIN_TENANT_UUID)
        created_device = await self.device_dao.create(device)
        assert created_device == device

        await self.device_dao.delete(device)

    @asyncio_run
    @fixtures.db.tenant(uuid=MAIN_TENANT_UUID)
    @fixtures.db.tenant(uuid=SUB_TENANT_1_UUID)
    @fixtures.db.device(tenant_uuid=MAIN_TENANT_UUID)
    async def test_get_multitenant(self, _, __, device):
        result = await self.device_dao.get(device.id, tenant_uuids=[MAIN_TENANT_UUID])
        assert result.id == device.id

        result = await self.device_dao.get(
            device.id, tenant_uuids=[SUB_TENANT_1_UUID, MAIN_TENANT_UUID]
        )
        assert result.id == device.id

        with self.assertRaises(EntryNotFoundException):
            await self.device_dao.get(device.id, tenant_uuids=[SUB_TENANT_1_UUID])

    @asyncio_run
    @fixtures.db.tenant(uuid=MAIN_TENANT_UUID)
    @fixtures.db.device(tenant_uuid=MAIN_TENANT_UUID)
    async def test_get(self, _, device):
        result = await self.device_dao.get(device.id)
        assert result.id == device.id

        with self.assertRaises(EntryNotFoundException):
            await self.device_dao.get(INVALID_RESOURCE_UUID)

    @asyncio_run
    @fixtures.db.tenant(uuid=MAIN_TENANT_UUID)
    @fixtures.db.device(tenant_uuid=MAIN_TENANT_UUID)
    async def test_update(self, _, device):
        new_ip = '1.2.3.4'
        device.ip = new_ip
        await self.device_dao.update(device)

        updated_device = await self.device_dao.get(device.id)
        assert updated_device.ip == new_ip

    @asyncio_run
    @fixtures.db.tenant(uuid=MAIN_TENANT_UUID)
    @fixtures.db.device(tenant_uuid=MAIN_TENANT_UUID)
    async def test_delete(self, _, device):
        await self.device_dao.delete(device)

        with self.assertRaises(EntryNotFoundException):
            await self.device_dao.get(device.id)
