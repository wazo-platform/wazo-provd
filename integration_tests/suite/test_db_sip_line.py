# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import SIPLine

from .helpers import fixtures
from .helpers.base import INVALID_RESOURCE_UUID, DBIntegrationTest, asyncio_run


class TestSIPLine(DBIntegrationTest):
    asset = 'database'

    @asyncio_run
    @fixtures.db.device_config()
    async def test_create(self, device_config):
        sip_line_uuid = uuid.uuid4()
        sip_line = SIPLine(sip_line_uuid, device_config.id, 1)
        created_sip_line = await self.sip_line_dao.create(sip_line)
        assert created_sip_line == sip_line

        await self.sip_line_dao.delete(sip_line)

    @asyncio_run
    @fixtures.db.device_config(id='test1')
    @fixtures.db.sip_line(config_id='test1')
    async def test_get(self, _, sip_line):
        result = await self.sip_line_dao.get(sip_line.uuid)
        assert result.uuid == sip_line.uuid

        with self.assertRaises(EntryNotFoundException):
            await self.sip_line_dao.get(INVALID_RESOURCE_UUID)

    @asyncio_run
    @fixtures.db.device_config(id='test2')
    @fixtures.db.sip_line(config_id='test2')
    async def test_update(self, _, sip_line):
        new_username = 'user123'
        sip_line.username = new_username
        await self.sip_line_dao.update(sip_line)

        updated_sip_line = await self.sip_line_dao.get(sip_line.uuid)
        assert updated_sip_line.username == new_username

    @asyncio_run
    @fixtures.db.device_config(id='test3')
    @fixtures.db.sip_line(config_id='test3')
    async def test_delete(self, _, sip_line):
        await self.sip_line_dao.delete(sip_line)

        with self.assertRaises(EntryNotFoundException):
            await self.sip_line_dao.get(sip_line.uuid)
