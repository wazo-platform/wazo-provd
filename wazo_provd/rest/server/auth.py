# Copyright 2018-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
from functools import wraps

from wazo_auth_client import Client as AuthClient
from xivo import auth_verifier, http_exceptions

from wazo_provd.util import decode_bytes

__all__ = ['http_exceptions']

logger = logging.getLogger(__name__)

required_acl = auth_verifier.required_acl
_auth_verifier = None
_auth_client = None


def get_auth_verifier():
    global _auth_verifier
    if not _auth_verifier:
        _auth_verifier = AuthVerifierProvd()
    return _auth_verifier


def get_auth_client(**config):
    global _auth_client
    if not _auth_client:
        _auth_client = AuthClient(**config)
    return _auth_client


class AuthVerifierProvd:
    def __init__(self):
        self.auth_client = None
        self.helpers = auth_verifier.AuthVerifierHelpers()

    def set_client(self, auth_client):
        self.auth_client = auth_client

    def verify_token(self, obj, request, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.helpers.extract_no_auth(func):
                return func(*args, **kwargs)

            token_uuid = decode_bytes(request.getHeader(b'X-Auth-Token'))
            tenant_uuid = decode_bytes(request.getHeader(b'Wazo-Tenant'))
            required_acl = self.helpers.extract_required_acl(
                func,
                kwargs | obj.__dict__,
            )

            self.helpers.validate_token(
                self.auth_client,
                token_uuid,
                required_acl,
                tenant_uuid,
            )
            return func(*args, **kwargs)

        return wrapper
