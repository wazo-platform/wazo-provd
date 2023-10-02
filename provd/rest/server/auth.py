# Copyright 2018-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import requests

from functools import wraps
from twisted.internet import defer, threads
from wazo_auth_client import Client as AuthClient
from wazo_auth_client.exceptions import InvalidTokenException, MissingPermissionsTokenException
from xivo import auth_verifier

from provd.util import decode_bytes

logger = logging.getLogger(__name__)

required_acl = auth_verifier.required_acl
_auth_verifier = None
_auth_client = None


def get_auth_verifier():
    global _auth_verifier
    if not _auth_verifier:
        _auth_verifier = AuthVerifier()
    return _auth_verifier


def get_auth_client(**config):
    global _auth_client
    if not _auth_client:
        _auth_client = AuthClient(**config)
    return _auth_client


class AuthVerifier(auth_verifier.AuthVerifier):

    def verify_token(self, obj, request, func):
        @defer.inlineCallbacks
        @wraps(func)
        def wrapper(*args, **kwargs):
            # backward compatibility: when func.acl is not defined, it should
            # probably just raise an AttributeError
            no_auth = getattr(func, 'no_auth', False)
            if no_auth:
                defer.returnValue(func(*args, **kwargs))

            acl_check = getattr(func, 'acl', self._fallback_acl_check)
            token_id = decode_bytes(request.getHeader(b'X-Auth-Token'))
            tenant_uuid = decode_bytes(request.getHeader(b'Wazo-Tenant'))
            kwargs_for_required_acl = dict(kwargs)
            kwargs_for_required_acl.update(obj.__dict__)
            required_acl = self._required_acl(acl_check, args, kwargs_for_required_acl)
            try:
                token_is_valid = yield threads.deferToThread(self.client().token.check, token_id, required_acl, tenant=tenant_uuid)
            except InvalidTokenException:
                defer.returnValue(self._handle_invalid_token_exception(token_id, required_access=required_acl))
            except MissingPermissionsTokenException:
                defer.returnValue(self._handle_missing_permissions_token_exception(token_id, required_access=required_acl))
            except requests.RequestException as e:
                defer.returnValue(self.handle_unreachable(e))

            if token_is_valid:
                defer.returnValue(func(*args, **kwargs))

            defer.returnValue(self.handle_unauthorized(token_id, required_access=required_acl))

        return wrapper
