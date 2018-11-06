#!/usr/bin/env python3
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from wazo_provd_client import Client
from wazo_provd_client.exceptions import ProvdError, ProvdServiceUnavailable, InvalidProvdError
from hamcrest import assert_that, has_key, has_length, is_, equal_to, calling, raises
from .helpers.base import BaseIntegrationTest

from .helpers.wait_strategy import NoWaitStrategy


class TestDevices(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def setUp(self):
        self._client = Client('localhost', https=False, port=self.service_port(8666, 'provd'), prefix='/provd', verify_certificate=False)

    def tearDown(self):
        pass

    def _add_device(self, ip, mac, plugin=''):
        device = {'ip': ip, 'mac': mac, 'plugin': plugin}
        return self._client.devices.add(device)

    def test_device_list(self):
        results = self._client.devices.find()
        assert_that(results, has_key('devices'))

    def test_device_creation(self):
        # When it works
        result_before = self._client.devices.find()
        assert_that(result_before, has_key('devices'))
        assert_that(result_before['devices'], has_length(0))

        result_add = self._add_device('10.10.10.10', '00:11:22:33:44:55')
        assert_that(result_add, has_key('id'))

        result_after_add = self._client.devices.find()
        assert_that(result_after_add, has_key('devices'))

        # When it fails
        assert_that(calling(self._add_device).with_args('asdf', '00:11:22:33:44:55'), raises(ProvdError))
