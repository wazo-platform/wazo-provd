# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import requests
from functools import wraps
from xivo_auth_client import Client
from xivo import auth_verifier

logger = logging.getLogger(__name__)

auth_config = None
auth_client = None
enabled = False
required_acl = auth_verifier.required_acl
_auth_verifier = None


def set_auth_enabled(status):
    global enabled
    enabled = status


def set_auth_config(config):
    global auth_config
    auth_config = config


def client():
    global auth_client
    if not auth_client:
        auth_client = Client(**auth_config)
    return auth_client


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

            logger.debug('AuthVerifier.verify_token')
            acl_check = getattr(func, 'acl', self._fallback_acl_check)
            token_id = request.getHeader('X-Auth-Token')
            kwargs_for_required_acl = dict(kwargs)
            kwargs_for_required_acl.update(obj.__dict__)
            logger.debug('kwargs_For_required_acl: %s', kwargs_for_required_acl)
            required_acl = self._required_acl(acl_check, args, kwargs_for_required_acl)
            try:
                token_is_valid = self.client().token.is_valid(token_id, required_acl)
            except requests.RequestException as e:
                return self.handle_unreachable(e)

            if token_is_valid:
                return func(*args, **kwargs)

            return self.handle_unauthorized(token_id)
        return wrapper

    def _required_acl(self, acl_check, args, kwargs):
        result = auth_verifier.AuthVerifier._required_acl(self, acl_check, args, kwargs)
        logger.debug('_required_acl: %s', result)
        return result
