# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import requests
from functools import wraps
from xivo import auth_verifier

logger = logging.getLogger(__name__)

required_acl = auth_verifier.required_acl
_auth_verifier = None


def get_auth_verifier():
    global _auth_verifier
    if not _auth_verifier:
        _auth_verifier = AuthVerifier()

    return _auth_verifier


class AuthVerifier(auth_verifier.AuthVerifier):

    def verify_token(self, obj, request, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # backward compatibility: when func.acl is not defined, it should
            # probably just raise an AttributeError
            no_auth = getattr(func, 'no_auth', False)
            if no_auth:
                return func(*args, **kwargs)

            acl_check = getattr(func, 'acl', self._fallback_acl_check)
            token_id = request.getHeader('X-Auth-Token')
            kwargs_for_required_acl = dict(kwargs)
            kwargs_for_required_acl.update(obj.__dict__)
            required_acl = self._required_acl(acl_check, args, kwargs_for_required_acl)
            try:
                token_is_valid = self.client().token.is_valid(token_id, required_acl)
            except requests.RequestException as e:
                return self.handle_unreachable(e)

            if token_is_valid:
                return func(*args, **kwargs)

            return self.handle_unauthorized(token_id)
        return wrapper
