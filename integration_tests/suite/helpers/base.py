#!/usr/bin/env python3
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import os

from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase

from .wait_strategy import WaitStrategy


class BaseIntegrationTest(AssetLaunchingTestCase):

    assets_root = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', 'assets'))
    service = 'provd'
    wait_strategy = WaitStrategy()

    def url(self, *parts):
        return 'http://localhost:{port}/provd/{path}'.format(port=self.service_port(8666, 'provd'),
                                                             path='/'.join(parts))

    @classmethod
    def _docker_compose_options(cls):
        return [
            '--file', os.path.join(cls.assets_root, 'docker-compose.yml'),
            '--file', os.path.join(cls.assets_root,
                                   'docker-compose.{}.override.yml'.format(cls.asset)),
            '--project-name', cls.service,
        ]
