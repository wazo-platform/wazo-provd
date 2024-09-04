# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os

from wazo_provd_client import Client
from wazo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase

from .wait_strategy import WaitStrategy

API_VERSION = '0.2'

VALID_TOKEN = 'valid-token'
INVALID_TOKEN = 'invalid-token'
INVALID_TENANT = '00000000-0000-4000-8000-999999999999'
VALID_TOKEN_MULTITENANT = 'valid-token-multitenant'
MAIN_TENANT = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1'
SUB_TENANT_1 = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee2'
SUB_TENANT_2 = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee3'


class BaseIntegrationTest(AssetLaunchingTestCase):
    assets_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
    )
    service = 'provd'
    wait_strategy = WaitStrategy()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.set_client()

    @classmethod
    def set_client(cls):
        cls._client = cls.make_provd(VALID_TOKEN_MULTITENANT)

    @classmethod
    def make_provd(cls, token: str) -> Client:
        return Client(
            '127.0.0.1',
            port=cls.service_port(8666, 'provd'),
            version=API_VERSION,
            prefix=None,
            https=False,
            token=token,
        )
