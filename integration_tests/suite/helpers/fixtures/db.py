# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid
from functools import wraps

from wazo_provd.database.models import Tenant


def tenant(**tenant_args):
    def decorator(decorated):
        @wraps(decorated)
        async def wrapper(self, *args, **kwargs):
            tenant_args.setdefault('uuid', uuid.uuid4())
            tenant_args.setdefault('provisioning_key', str(uuid.uuid4()))
            model = Tenant(**tenant_args)

            tenant = await self.tenant_dao.create(model)

            args = tuple(list(args) + [tenant])
            try:
                result = await decorated(self, *args, **kwargs)
            finally:
                await self.tenant_dao.delete(tenant)
            return result

        return wrapper

    return decorator
