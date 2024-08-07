# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import Tenant

from .helpers import fixtures
from .helpers.base import INVALID_TENANT, DBIntegrationTest, asyncio_run


class TestTenant(DBIntegrationTest):
    asset = 'database'

    @asyncio_run
    @fixtures.db.tenant()
    @fixtures.db.tenant()
    async def test_find_all(self, tenant_1, tenant_2):
        tenants = await self.tenant_dao.find_all()
        assert tenant_1 in tenants
        assert tenant_2 in tenants

    @asyncio_run
    async def test_create(self):
        tenant_uuid = uuid.uuid4()
        tenant = Tenant(uuid=tenant_uuid, provisioning_key='MyCustomKey')
        created_tenant = await self.tenant_dao.create(tenant)
        assert created_tenant == tenant

        await self.tenant_dao.delete(tenant)

    @asyncio_run
    @fixtures.db.tenant()
    async def test_get(self, tenant):
        result = await self.tenant_dao.get(tenant.uuid)
        assert result.uuid == tenant.uuid

        with self.assertRaises(EntryNotFoundException):
            await self.tenant_dao.get(INVALID_TENANT)

    @asyncio_run
    @fixtures.db.tenant(provisioning_key='test123')
    async def test_get_or_create(self, tenant):
        result = await self.tenant_dao.get_or_create(tenant.uuid)
        assert result.provisioning_key == tenant.provisioning_key

        expected_uuid = uuid.uuid4()
        result = await self.tenant_dao.get_or_create(expected_uuid)
        assert result.uuid == expected_uuid

    @asyncio_run
    @fixtures.db.tenant(provisioning_key='MyKey')
    async def test_update(self, tenant):
        provisioning_key = 'UpdatedKey'
        tenant.provisioning_key = provisioning_key
        await self.tenant_dao.update(tenant)

        updated_tenant = await self.tenant_dao.get(tenant.uuid)
        assert updated_tenant.provisioning_key == provisioning_key

    @asyncio_run
    @fixtures.db.tenant()
    async def test_delete(self, tenant):
        await self.tenant_dao.delete(tenant)

        with self.assertRaises(EntryNotFoundException):
            await self.tenant_dao.get(tenant.uuid)
