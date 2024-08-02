# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from xivo import tenant_helpers
from xivo.tenant_helpers import (
    InvalidTenant,
    InvalidTokenAPIException,
    UnauthorizedTenant,
)

from wazo_provd.util import decode_bytes

if TYPE_CHECKING:
    from wazo_auth_client import Client as AuthClient

    from wazo_provd.servers.http_site import Request


class Tenant(tenant_helpers.Tenant):
    @classmethod
    def autodetect(cls, request: Request, auth: AuthClient):
        token = Token.from_headers(request, auth)
        try:
            tenant = cls.from_headers(request)
        except InvalidTenant:
            return cls.from_token(token)

        try:
            return tenant.check_against_token(token)
        except InvalidTenant:
            raise UnauthorizedTenant(tenant.uuid)

    @classmethod
    def from_headers(cls, request: Request):
        tenant_uuid = decode_bytes(request.getHeader(b'Wazo-Tenant'))
        if not tenant_uuid:
            raise InvalidTenant()
        return cls(uuid=tenant_uuid)


class Token(tenant_helpers.Token):
    @classmethod
    def from_headers(cls, request: Request, auth: AuthClient):
        token_id = decode_bytes(request.getHeader(b'X-Auth-Token'))
        if not token_id:
            raise InvalidTokenAPIException('')
        return cls(token_id, auth)
