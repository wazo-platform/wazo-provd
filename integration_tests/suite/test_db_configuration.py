# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import ServiceConfiguration

from .helpers import fixtures
from .helpers.base import INVALID_RESOURCE_UUID, DBIntegrationTest, asyncio_run


class TestServiceConfiguration(DBIntegrationTest):
    asset = 'database'

    @asyncio_run
    @fixtures.db.service_configuration()
    async def test_find_one(self, service_conf):
        service_conf_from_db = await self.service_configuration_dao.find_one()
        assert service_conf == service_conf_from_db

    @asyncio_run
    async def test_create(self):
        service_conf_uuid = uuid.uuid4()
        service_conf = ServiceConfiguration(
            uuid=service_conf_uuid, plugin_server='http://test-plugin-server'
        )
        created_service_conf = await self.service_configuration_dao.create(service_conf)
        assert created_service_conf == service_conf

        await self.service_configuration_dao.delete(service_conf)

    @asyncio_run
    @fixtures.db.service_configuration()
    async def test_get(self, service_configuration):
        result = await self.service_configuration_dao.get(service_configuration.uuid)
        assert result.uuid == service_configuration.uuid

        with self.assertRaises(EntryNotFoundException):
            await self.service_configuration_dao.get(INVALID_RESOURCE_UUID)

    @asyncio_run
    @fixtures.db.service_configuration()
    async def test_update(self, service_conf):
        new_plugin_server = 'http://new-plugin-server'
        service_conf.plugin_server = new_plugin_server
        await self.service_configuration_dao.update(service_conf)

        updated_service_conf = await self.service_configuration_dao.get(
            service_conf.uuid
        )
        assert updated_service_conf.plugin_server == new_plugin_server

    @asyncio_run
    @fixtures.db.service_configuration()
    async def test_update_key(self, service_conf):
        new_plugin_server = 'http://new-plugin-server'
        await self.service_configuration_dao.update_key(
            'plugin_server', new_plugin_server
        )

        updated_service_conf = await self.service_configuration_dao.get(
            service_conf.uuid
        )
        assert updated_service_conf.plugin_server == new_plugin_server

    @asyncio_run
    @fixtures.db.service_configuration()
    async def test_delete(self, service_configuration):
        await self.service_configuration_dao.delete(service_configuration)

        with self.assertRaises(EntryNotFoundException):
            await self.service_configuration_dao.get(service_configuration.uuid)
