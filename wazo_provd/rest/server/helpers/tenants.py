# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from xivo import tenant_helpers
from xivo.tenant_helpers import InvalidTenant, InvalidToken, UnauthorizedTenant

from wazo_provd.util import decode_bytes

if TYPE_CHECKING:
    from wazo_provd.servers.http_site import Request


class Tenant(tenant_helpers.Tenant):
    @classmethod
    def autodetect(cls, request: Request, tokens: Tokens):
        token = tokens.from_headers(request)
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


class Tokens(tenant_helpers.Tokens):
    def from_headers(self, request: Request):
        token_id = decode_bytes(request.getHeader(b'X-Auth-Token'))
        if not token_id:
            raise InvalidToken()
        return self.get(token_id)
