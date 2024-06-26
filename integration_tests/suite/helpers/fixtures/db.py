# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import uuid
from functools import wraps

from wazo_provd.database.models import (
    Device,
    DeviceConfig,
    DeviceRawConfig,
    FunctionKey,
    SCCPLine,
    ServiceConfiguration,
    SIPLine,
    Tenant,
)


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


def service_configuration(**service_configuration_args):
    def decorator(decorated):
        @wraps(decorated)
        async def wrapper(self, *args, **kwargs):
            service_configuration_args.setdefault('uuid', uuid.uuid4())
            service_configuration_args.setdefault(
                'plugin_server', 'http://pluginserver:8000'
            )
            model = ServiceConfiguration(**service_configuration_args)

            service_configuration = await self.service_configuration_dao.create(model)

            args = tuple(list(args) + [service_configuration])
            try:
                result = await decorated(self, *args, **kwargs)
            finally:
                await self.service_configuration_dao.delete(service_configuration)
            return result

        return wrapper

    return decorator


def device(**device_args):
    def decorator(decorated):
        @wraps(decorated)
        async def wrapper(self, *args, **kwargs):
            device_args.setdefault('id', uuid.uuid4().hex)
            device_args.setdefault('tenant_uuid', uuid.uuid4())
            model = Device(**device_args)

            device = await self.device_dao.create(model)

            args = tuple(list(args) + [device])
            try:
                result = await decorated(self, *args, **kwargs)
            finally:
                await self.device_dao.delete(device)
            return result

        return wrapper

    return decorator


def device_config(**device_config_args):
    def decorator(decorated):
        @wraps(decorated)
        async def wrapper(self, *args, **kwargs):
            device_config_args.setdefault('id', uuid.uuid4().hex)
            model = DeviceConfig(**device_config_args)

            device_config = await self.device_config_dao.create(model)

            args = tuple(list(args) + [device_config])
            try:
                result = await decorated(self, *args, **kwargs)
            finally:
                await self.device_config_dao.delete(device_config)
            return result

        return wrapper

    return decorator


def device_raw_config(**device_raw_config_args):
    def decorator(decorated):
        @wraps(decorated)
        async def wrapper(self, *args, **kwargs):
            model = DeviceRawConfig(**device_raw_config_args)

            device_raw_config = await self.device_raw_config_dao.create(model)

            args = tuple(list(args) + [device_raw_config])
            try:
                result = await decorated(self, *args, **kwargs)
            finally:
                await self.device_raw_config_dao.delete(device_raw_config)
            return result

        return wrapper

    return decorator


def sip_line(**sip_line_args):
    def decorator(decorated):
        @wraps(decorated)
        async def wrapper(self, *args, **kwargs):
            sip_line_args.setdefault('uuid', uuid.uuid4())
            model = SIPLine(**sip_line_args)

            sip_line = await self.sip_line_dao.create(model)

            args = tuple(list(args) + [sip_line])
            try:
                result = await decorated(self, *args, **kwargs)
            finally:
                await self.sip_line_dao.delete(sip_line)
            return result

        return wrapper

    return decorator


def sccp_line(**sccp_line_args):
    def decorator(decorated):
        @wraps(decorated)
        async def wrapper(self, *args, **kwargs):
            sccp_line_args.setdefault('uuid', uuid.uuid4())
            model = SCCPLine(**sccp_line_args)

            sccp_line = await self.sccp_line_dao.create(model)

            args = tuple(list(args) + [sccp_line])
            try:
                result = await decorated(self, *args, **kwargs)
            finally:
                await self.sccp_line_dao.delete(sccp_line)
            return result

        return wrapper

    return decorator


def function_key(**function_key_args):
    def decorator(decorated):
        @wraps(decorated)
        async def wrapper(self, *args, **kwargs):
            function_key_args.setdefault('uuid', uuid.uuid4())
            model = FunctionKey(**function_key_args)

            function_key = await self.function_key_dao.create(model)

            args = tuple(list(args) + [function_key])
            try:
                result = await decorated(self, *args, **kwargs)
            finally:
                await self.function_key_dao.delete(function_key)
            return result

        return wrapper

    return decorator
