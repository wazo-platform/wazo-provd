# Copyright 2017-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from wazo_provd_client import Client
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase

from .wait_strategy import WaitStrategy

API_VERSION = '0.2'

VALID_TOKEN = 'valid-token'
INVALID_TOKEN = 'invalid-token'
VALID_TOKEN_MULTITENANT = 'valid-token-multitenant'
MAIN_TENANT = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1'
SUB_TENANT_1 = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee2'
SUB_TENANT_2 = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee3'


class BaseIntegrationTest(AssetLaunchingTestCase):

    assets_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets'))
    service = 'provd'
    wait_strategy = WaitStrategy()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._client = cls.make_provd(VALID_TOKEN_MULTITENANT)

    @classmethod
    def make_provd(cls, token):
        return Client(
            'localhost',
            port=cls.service_port(8666, 'provd'),
            version=API_VERSION,
            prefix=None,
            https=False,
            token=token,
        )
