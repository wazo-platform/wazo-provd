# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo import tenant_helpers
from xivo.tenant_helpers import InvalidTenant, InvalidToken, UnauthorizedTenant


class Tenant(tenant_helpers.Tenant):

    @classmethod
    def autodetect(cls, request, tokens, users):
        # Only need to instantiate a Tokens and Users object for the
        # tokens and users parameters, using auth client as their
        # parameter
        token = tokens.from_headers(request)
        try:
            tenant = cls.from_headers(request)
        except InvalidTenant:
            return cls.from_token(token)

        try:
            return tenant.check_against_token(token)
        except InvalidTenant:
            pass  # check against user

        user = users.get(token['metadata'].get('uuid'))
        try:
            return tenant.check_against_user(user)
        except InvalidTenant:
            raise UnauthorizedTenant(tenant.uuid)

    @classmethod
    def from_headers(cls, request):
        return cls.from_headers_one(request)

    @classmethod
    def from_headers_one(cls, request):
        tenant_uuid = request.getHeader('Wazo-Tenant')
        if not tenant_uuid:
            raise InvalidTenant()
        if ',' in tenant_uuid:
            raise InvalidTenant()
        return cls(uuid=tenant_uuid)


class Tokens(tenant_helpers.Tokens):

    def from_headers(self, request):
        token_id = request.getHeader('X-Auth-Token')
        if not token_id:
            raise InvalidToken()
        return self.get(token_id)
