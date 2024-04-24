# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import SCCPLine

from .helpers import fixtures
from .helpers.base import INVALID_RESOURCE_UUID, DBIntegrationTest, asyncio_run


class TestSCCPLine(DBIntegrationTest):
    asset = 'database'

    @asyncio_run
    @fixtures.db.device_config()
    async def test_create(self, device_config):
        sccp_line_uuid = uuid.uuid4()
        sccp_line = SCCPLine(sccp_line_uuid, device_config.id, 1)
        created_sccp_line = await self.sccp_line_dao.create(sccp_line)
        assert created_sccp_line == sccp_line

        await self.sccp_line_dao.delete(sccp_line)

    @asyncio_run
    @fixtures.db.device_config(id='test1')
    @fixtures.db.sccp_line(config_id='test1')
    async def test_get(self, _, sccp_line):
        result = await self.sccp_line_dao.get(sccp_line.uuid)
        assert result.uuid == sccp_line.uuid

        with self.assertRaises(EntryNotFoundException):
            await self.sccp_line_dao.get(INVALID_RESOURCE_UUID)

    @asyncio_run
    @fixtures.db.device_config(id='test2')
    @fixtures.db.sccp_line(config_id='test2')
    async def test_update(self, _, sccp_line):
        new_ip = '1.2.3.4'
        sccp_line.ip = new_ip
        await self.sccp_line_dao.update(sccp_line)

        updated_sccp_line = await self.sccp_line_dao.get(sccp_line.uuid)
        assert updated_sccp_line.ip == new_ip

    @asyncio_run
    @fixtures.db.device_config(id='test3')
    @fixtures.db.sccp_line(config_id='test3')
    async def test_delete(self, _, sccp_line):
        await self.sccp_line_dao.delete(sccp_line)

        with self.assertRaises(EntryNotFoundException):
            await self.sccp_line_dao.get(sccp_line.uuid)
