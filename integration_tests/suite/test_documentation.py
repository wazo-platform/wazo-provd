# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests
import pprint

from hamcrest import assert_that, empty

from .helpers.base import BaseIntegrationTest
from .helpers.wait_strategy import NoWaitStrategy

API_VERSION = '0.2'


class TestDocumentation(BaseIntegrationTest):

    asset = 'documentation'
    wait_strategy = NoWaitStrategy()

    def test_documentation_errors(self):
        api_url = 'https://provd:8666/{version}/api/api.yml'.format(version=API_VERSION)
        self.validate_api(api_url)

    def validate_api(self, url):
        validator_port = self.service_port(8080, 'swagger-validator')
        validator_url = 'http://localhost:{port}/debug'.format(port=validator_port)
        response = requests.get(validator_url, params={'url': url})
        assert_that(response.json(), empty(), pprint.pformat(response.json()))
