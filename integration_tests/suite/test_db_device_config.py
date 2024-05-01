# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import DeviceConfig, DeviceRawConfig

from .helpers import fixtures
from .helpers.base import (
    INVALID_RESOURCE_UUID,
    MAIN_TENANT,
    DBIntegrationTest,
    asyncio_run,
)


class TestDeviceConfig(DBIntegrationTest):
    asset = 'database'
    service = 'postgres'

    @classmethod
    @asyncio_run
    async def setUpClass(cls) -> None:
        super().setUpClass()
        await cls.remove_all_configs()

    @classmethod
    async def remove_all_configs(cls):
        tables_to_flush = (
            'provd_sip_line',
            'provd_sccp_line',
            'provd_device_raw_config',
            'provd_device_config',
        )
        for table in tables_to_flush:
            await cls.db.runOperation(f'DELETE FROM {table};')

    @asyncio_run
    @fixtures.db.tenant(uuid=uuid.UUID(MAIN_TENANT))
    @fixtures.db.device_config(id='test1')
    @fixtures.db.device_config(id='test2', parent_id='test1')
    @fixtures.db.device_config(id='test3', parent_id='test2')
    async def test_get_descendants(
        self,
        _,
        __,
        config2: DeviceConfig,
        config3: DeviceConfig,
    ):
        result = await self.device_config_dao.get_descendants('test1')
        assert result == [config2, config3]

        result = await self.device_config_dao.get_descendants('test2')
        assert result == [config3]

        result = await self.device_config_dao.get_descendants('test3')
        assert result == []

    @asyncio_run
    @fixtures.db.tenant(uuid=uuid.UUID(MAIN_TENANT))
    @fixtures.db.device_config(id='test1')
    @fixtures.db.device_config(id='test2', parent_id='test1')
    @fixtures.db.device_config(id='test3', parent_id='test2')
    async def test_get_parents(
        self,
        _,
        config1: DeviceConfig,
        config2: DeviceConfig,
        __,
    ):
        result = await self.device_config_dao.get_parents('test1')
        assert result == []

        result = await self.device_config_dao.get_parents('test2')
        assert result == [config1]

        result = await self.device_config_dao.get_parents('test3')
        assert result == [config2, config1]

    @asyncio_run
    async def test_create(self):
        device_config = DeviceConfig(id=uuid.uuid4().hex)
        created_device_config = await self.device_config_dao.create(device_config)
        assert created_device_config == device_config

        await self.device_config_dao.delete(device_config)

    @asyncio_run
    async def test_create_with_associations(self):
        device_config = DeviceConfig(id=uuid.uuid4().hex)
        raw_config = DeviceRawConfig(device_config.id)
        device_config.raw_config = raw_config
        created_device_config = await self.device_config_dao.create(device_config)
        assert created_device_config == device_config

        created_device_raw_config = await self.device_raw_config_dao.get(
            created_device_config.id
        )
        assert created_device_raw_config == raw_config

        await self.device_raw_config_dao.delete(raw_config)
        await self.device_config_dao.delete(created_device_config)

    @asyncio_run
    @fixtures.db.device_config()
    async def test_get(self, device_config):
        result = await self.device_config_dao.get(device_config.id)
        assert result.id == device_config.id

        with self.assertRaises(EntryNotFoundException):
            await self.device_config_dao.get(INVALID_RESOURCE_UUID)

    @asyncio_run
    async def test_get_with_associations(self):
        raw_config_model = DeviceRawConfig('test1')
        device_config_model = DeviceConfig('test1', raw_config=raw_config_model)
        await self.device_config_dao.create(device_config_model)
        device_config = await self.device_config_dao.get('test1')
        assert device_config == device_config_model
        await self.device_config_dao.delete(device_config)

    @asyncio_run
    @fixtures.db.device_config(id='test5', role='test')
    @fixtures.db.device_config(id='test6', role='automobile')
    @fixtures.db.device_config(id='test7', role='automobile', deletable=False)
    @fixtures.db.device_config(id='test8', deletable=False)
    async def test_find(
        self,
        config1: DeviceConfig,
        config2: DeviceConfig,
        config3: DeviceConfig,
        config4: DeviceConfig,
    ):
        results = await self.device_config_dao.find({'role': 'test'})
        assert [result.id for result in results] == [config1.id]

        results = await self.device_config_dao.find({'deletable': False})
        assert [result.id for result in results] == [config3.id, config4.id]

        results = await self.device_config_dao.find(
            {'role': 'automobile', 'deletable': False}
        )

        assert [result.id for result in results] == [config3.id]
        results = await self.device_config_dao.find(
            {'role': 'automobile', 'deletable': True}
        )

        assert [result.id for result in results] == [config2.id]

        results = await self.device_config_dao.find()
        assert [result.id for result in results] == [
            config1.id,
            config2.id,
            config3.id,
            config4.id,
        ]

        results = await self.device_config_dao.find({})
        assert [result.id for result in results] == [
            config1.id,
            config2.id,
            config3.id,
            config4.id,
        ]

        results = await self.device_config_dao.find({'role': 'unknown'})
        assert results == []

    @asyncio_run
    @fixtures.db.device_config(id='test5', role='test')
    @fixtures.db.device_config(id='test6', role='automobile')
    @fixtures.db.device_config(id='test7', role='automobile', deletable=False)
    @fixtures.db.device_config(id='test8', deletable=False)
    async def test_find_one(
        self,
        config1: DeviceConfig,
        config2: DeviceConfig,
        config3: DeviceConfig,
        config4: DeviceConfig,
    ):
        result = await self.device_config_dao.find_one({'role': 'test'})
        assert result == config1

        result = await self.device_config_dao.find_one(
            {'role': 'automobile', 'deletable': False}
        )
        assert result == config3

        result = await self.device_config_dao.find_one(
            {'role': 'automobile', 'deletable': True}
        )
        assert result == config2

        result = await self.device_config_dao.find_one()
        assert result == config1

        result = await self.device_config_dao.find_one({})
        assert result == config1

        result = await self.device_config_dao.find_one(
            {'deletable': False, 'role': 'test'}
        )
        assert result is None

    @asyncio_run
    async def test_find_one_with_associations(self):
        config1_model = DeviceConfig(id='test5', role='test')
        await self.device_config_dao.create(config1_model)
        config2_model = DeviceConfig(id='test6', role='automobile')
        await self.device_config_dao.create(config2_model)
        raw_config3_model = DeviceRawConfig('test7')
        config3_model = DeviceConfig(
            id='test7',
            role='automobile',
            deletable=False,
            raw_config=raw_config3_model,
        )
        await self.device_config_dao.create(config3_model)
        config4_model = DeviceConfig(id='test8', deletable=False)
        await self.device_config_dao.create(config4_model)

        result = await self.device_config_dao.find_one({'role': 'test'})
        assert result == config1_model

        result = await self.device_config_dao.find_one(
            {'role': 'automobile', 'deletable': False}
        )
        assert result == config3_model

        result = await self.device_config_dao.find_one(
            {'role': 'automobile', 'deletable': True}
        )
        assert result == config2_model

        result = await self.device_config_dao.find_one()
        assert result == config1_model

        result = await self.device_config_dao.find_one({})
        assert result == config1_model

        result = await self.device_config_dao.find_one(
            {'deletable': False, 'role': 'test'}
        )
        assert result is None

        await self.device_config_dao.delete(config1_model)
        await self.device_config_dao.delete(config2_model)
        await self.device_config_dao.delete(config3_model)
        await self.device_config_dao.delete(config4_model)

    @asyncio_run
    @fixtures.db.device_config(id='test5', role='test')
    @fixtures.db.device_config(id='test6', role='test')
    @fixtures.db.device_config(id='test7', role='test', deletable=False)
    @fixtures.db.device_config(id='test8', role='test1', deletable=False)
    async def test_find_pagination_sort(
        self,
        config1: DeviceConfig,
        config2: DeviceConfig,
        config3: DeviceConfig,
        config4: DeviceConfig,
    ):
        results = await self.device_config_dao.find({'role': 'test'}, limit=1, skip=2)
        assert results == [config3]

        results = await self.device_config_dao.find(
            selectors={'deletable': False, 'role': 'test'}
        )
        assert results == [config3, config4]

        results = await self.device_config_dao.find(selectors={'role': 'test'}, skip=1)
        assert results == [config2, config3, config4]

        results = await self.device_config_dao.find(selectors={'role': 'test'}, limit=3)
        assert results == [config1, config2, config3]

        results = await self.device_config_dao.find(
            selectors={'role': 'test'}, limit=3, sort=('id', 'DESC')
        )
        assert results == [config4, config3, config2]

        results = await self.device_config_dao.find(
            selectors={'role': 'test'}, limit=3, skip=1, sort=('id', 'ASC')
        )
        assert results == [config2, config3, config4]

    @asyncio_run
    @fixtures.db.device_config(id='test1')
    async def test_update(self, device_config: DeviceConfig):
        new_label = 'test123'
        device_config.label = new_label
        await self.device_config_dao.update(device_config)

        updated_device_config = await self.device_config_dao.get(device_config.id)
        assert updated_device_config.label == new_label

    @asyncio_run
    @fixtures.db.device_config(id='test1')
    async def test_update_associations(self, device_config: DeviceConfig):
        new_raw_config = DeviceRawConfig(config_id='test1')
        device_config.raw_config = new_raw_config
        await self.device_config_dao.update(device_config)

        updated_device_config = await self.device_config_dao.get(device_config.id)
        assert updated_device_config.raw_config == new_raw_config

        device_config.raw_config.admin_username = 'test123'
        await self.device_config_dao.update(device_config)

        updated_device_config = await self.device_config_dao.get(device_config.id)
        assert updated_device_config == device_config

    @asyncio_run
    @fixtures.db.device_config(id='test')
    async def test_delete(self, device_config: DeviceConfig):
        await self.device_config_dao.delete(device_config)

        with self.assertRaises(EntryNotFoundException):
            await self.device_config_dao.get(device_config.id)

    @asyncio_run
    async def test_delete_child_replacement(self):
        # Before
        # base ----> test ----> child_test
        # After deletion of `test`
        # base ----> child_test
        base_config_model = DeviceConfig(id='base')
        base_config = await self.device_config_dao.create(base_config_model)
        device_config_model = DeviceConfig(id='test', parent_id='base')
        device_config = await self.device_config_dao.create(device_config_model)
        child_device_model = DeviceConfig(id='child_test', parent_id='test')
        child_device = await self.device_config_dao.create(child_device_model)

        await self.device_config_dao.delete(device_config)

        orphan_child_device = await self.device_config_dao.get(child_device.id)
        assert orphan_child_device.parent_id == base_config.id

        await self.device_config_dao.delete(child_device_model)
        await self.device_config_dao.delete(base_config_model)
