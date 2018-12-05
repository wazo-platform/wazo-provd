# Copyright 2017-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import os

from wazo_provd_client import Client
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase

from .wait_strategy import WaitStrategy

VALID_TOKEN = 'valid-token'


class BaseIntegrationTest(AssetLaunchingTestCase):

    assets_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets'))
    service = 'provd'
    wait_strategy = WaitStrategy()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._client = cls.make_provd(VALID_TOKEN)

    def url(self, *parts):
        return 'http://localhost:{port}/provd/{path}'.format(
            port=self.service_port(8666, 'provd'),
            path='/'.join(parts)
        )

    @classmethod
    def make_provd(cls, token):
        return Client(
            'localhost',
            https=False,
            token=token,
            port=cls.service_port(8666, 'provd'),
            prefix='/provd',
        )
