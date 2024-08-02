# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import (
    DeviceConfig,
    DeviceRawConfig,
    FunctionKey,
    SCCPLine,
    SIPLine,
)

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
    async def test_create_associations(self):
        device_config = DeviceConfig(id='deviceconf')
        await self.device_config_dao.create(device_config)
        fkey1 = FunctionKey(uuid=uuid.uuid4(), config_id=device_config.id, position=1)
        fkey2 = FunctionKey(uuid=uuid.uuid4(), config_id=device_config.id, position=8)
        sip_line1 = SIPLine(uuid=uuid.uuid4(), config_id=device_config.id, position=1)
        sip_line2 = SIPLine(uuid=uuid.uuid4(), config_id=device_config.id, position=8)
        sccp_line1 = SCCPLine(uuid=uuid.uuid4(), config_id=device_config.id, position=1)
        sccp_line2 = SCCPLine(uuid=uuid.uuid4(), config_id=device_config.id, position=8)
        device_raw_config = DeviceRawConfig(
            config_id=device_config.id,
            function_keys={
                '1': fkey1,
                '8': fkey2,
            },
            sip_lines={
                '1': sip_line1,
                '8': sip_line2,
            },
            sccp_lines={
                '1': sccp_line1,
                '8': sccp_line2,
            },
        )
        await self.device_raw_config_dao.create(device_raw_config)

        created_fkey1 = await self.function_key_dao.get(fkey1.uuid)
        assert created_fkey1 == fkey1

        created_fkey2 = await self.function_key_dao.get(fkey2.uuid)
        assert created_fkey2 == fkey2

        created_sip_line1 = await self.sip_line_dao.get(sip_line1.uuid)
        assert created_sip_line1 == sip_line1

        created_sip_line2 = await self.sip_line_dao.get(sip_line2.uuid)
        assert created_sip_line2 == sip_line2

        created_sccp_line1 = await self.sccp_line_dao.get(sccp_line1.uuid)
        assert created_sccp_line1 == sccp_line1

        created_sccp_line2 = await self.sccp_line_dao.get(sccp_line2.uuid)
        assert created_sccp_line2 == sccp_line2

        await self.device_config_dao.delete(device_config)

    @asyncio_run
    @fixtures.db.device_config(id='deviceconf2')
    @fixtures.db.device_raw_config(config_id='deviceconf2')
    async def test_get(self, _, device_raw_config):
        result = await self.device_raw_config_dao.get(device_raw_config.config_id)
        assert result == device_raw_config

        with self.assertRaises(EntryNotFoundException):
            await self.device_raw_config_dao.get(INVALID_RESOURCE_UUID)

    @asyncio_run
    @fixtures.db.device_config(id='deviceconf')
    @fixtures.db.device_raw_config(config_id='deviceconf')
    @fixtures.db.function_key(config_id='deviceconf', position=1)
    @fixtures.db.function_key(config_id='deviceconf', position=8)
    @fixtures.db.sip_line(config_id='deviceconf', position=1)
    @fixtures.db.sip_line(config_id='deviceconf', position=8)
    @fixtures.db.sccp_line(config_id='deviceconf', position=1)
    @fixtures.db.sccp_line(config_id='deviceconf', position=8)
    async def test_get_with_associations(
        self,
        _,
        device_raw_config: DeviceRawConfig,
        fkey1: FunctionKey,
        fkey2: FunctionKey,
        sip_line1: SIPLine,
        sip_line2: SIPLine,
        sccp_line1: SCCPLine,
        sccp_line2: SCCPLine,
    ):
        result = await self.device_raw_config_dao.get(device_raw_config.config_id)
        assert result.config_id == device_raw_config.config_id

        assert result.function_keys == {'1': fkey1, '8': fkey2}
        assert result.sip_lines == {'1': sip_line1, '8': sip_line2}
        assert result.sccp_lines == {'1': sccp_line1, '8': sccp_line2}

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
    @fixtures.db.device_config(id='deviceconf')
    @fixtures.db.device_raw_config(config_id='deviceconf')
    @fixtures.db.function_key(config_id='deviceconf', position=1)
    @fixtures.db.function_key(config_id='deviceconf', position=8)
    @fixtures.db.sip_line(config_id='deviceconf', position=1)
    @fixtures.db.sip_line(config_id='deviceconf', position=8)
    @fixtures.db.sccp_line(config_id='deviceconf', position=1)
    @fixtures.db.sccp_line(config_id='deviceconf', position=8)
    async def test_update_associations(
        self,
        _,
        __,
        fkey1: FunctionKey,
        fkey2: FunctionKey,
        sip_line1: SIPLine,
        sip_line2: SIPLine,
        sccp_line1: SCCPLine,
        sccp_line2: SCCPLine,
    ):
        device_raw_config = await self.device_raw_config_dao.get('deviceconf')
        new_fkey = FunctionKey(uuid=uuid.uuid4(), config_id='deviceconf', position=3)
        device_raw_config.function_keys = {'3': new_fkey}
        await self.device_raw_config_dao.update(device_raw_config)

        updated_device_raw_config = await self.device_raw_config_dao.get(
            device_raw_config.config_id
        )
        assert updated_device_raw_config == device_raw_config

        fkey2.position = 5
        fkey1.label = '123 testing'
        device_raw_config.function_keys = {'5': fkey2, '1': fkey1}
        await self.device_raw_config_dao.update(device_raw_config)

        updated_device_raw_config = await self.device_raw_config_dao.get(
            device_raw_config.config_id
        )
        assert updated_device_raw_config == device_raw_config

        sip_line2.position = 5
        sip_line1.display_name = 'Uncle Bob'
        device_raw_config.sip_lines = {'5': sip_line2, '1': sip_line1}
        await self.device_raw_config_dao.update(device_raw_config)

        updated_device_raw_config = await self.device_raw_config_dao.get(
            device_raw_config.config_id
        )
        assert updated_device_raw_config == device_raw_config

        sccp_line2.position = 5
        sccp_line1.ip = '1.2.3.4'
        device_raw_config.sccp_lines = {'5': sccp_line2, '1': sccp_line1}
        await self.device_raw_config_dao.update(device_raw_config)

        updated_device_raw_config = await self.device_raw_config_dao.get(
            device_raw_config.config_id
        )
        assert updated_device_raw_config == device_raw_config

    @asyncio_run
    @fixtures.db.device_config(id='deviceconf4')
    @fixtures.db.device_raw_config(config_id='deviceconf4')
    async def test_delete(self, _, device_raw_config: DeviceRawConfig):
        await self.device_raw_config_dao.delete(device_raw_config)

        with self.assertRaises(EntryNotFoundException):
            await self.device_raw_config_dao.get(device_raw_config.config_id)

    @asyncio_run
    async def test_delete_cascade(self):
        device_config = DeviceConfig(id='deviceconf')
        await self.device_config_dao.create(device_config)
        device_raw_config = DeviceRawConfig(config_id=device_config.id)
        await self.device_raw_config_dao.create(device_raw_config)
        fkey1 = FunctionKey(uuid=uuid.uuid4(), config_id=device_config.id, position=1)
        await self.function_key_dao.create(fkey1)
        fkey2 = FunctionKey(uuid=uuid.uuid4(), config_id=device_config.id, position=8)
        await self.function_key_dao.create(fkey2)
        sip_line1 = SIPLine(uuid=uuid.uuid4(), config_id=device_config.id, position=1)
        await self.sip_line_dao.create(sip_line1)
        sip_line2 = SIPLine(uuid=uuid.uuid4(), config_id=device_config.id, position=8)
        await self.sip_line_dao.create(sip_line2)
        sccp_line1 = SCCPLine(uuid=uuid.uuid4(), config_id=device_config.id, position=1)
        await self.sccp_line_dao.create(sccp_line1)
        sccp_line2 = SCCPLine(uuid=uuid.uuid4(), config_id=device_config.id, position=8)
        await self.sccp_line_dao.create(sccp_line2)

        # NOTE(afournier): the function key, sip lines and sccp lines depend on
        # device config, not on raw_config
        await self.device_config_dao.delete(device_config)

        with self.assertRaises(EntryNotFoundException):
            await self.device_raw_config_dao.get(device_raw_config.config_id)

        with self.assertRaises(EntryNotFoundException):
            await self.function_key_dao.get(fkey1.uuid)

        with self.assertRaises(EntryNotFoundException):
            await self.function_key_dao.get(fkey2.uuid)

        with self.assertRaises(EntryNotFoundException):
            await self.sip_line_dao.get(sip_line1.uuid)

        with self.assertRaises(EntryNotFoundException):
            await self.sip_line_dao.get(sip_line2.uuid)

        with self.assertRaises(EntryNotFoundException):
            await self.sccp_line_dao.get(sccp_line1.uuid)

        with self.assertRaises(EntryNotFoundException):
            await self.sccp_line_dao.get(sccp_line2.uuid)
