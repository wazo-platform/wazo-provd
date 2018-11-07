# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from wazo_provd_client import Client
from wazo_provd_client.exceptions import ProvdError
from hamcrest import assert_that, has_key, has_length, is_, equal_to, calling, raises
from .helpers.base import BaseIntegrationTest

from .helpers.wait_strategy import NoWaitStrategy


class TestDevices(BaseIntegrationTest):
    asset = 'base'
    wait_strategy = NoWaitStrategy()

    def setUp(self):
        self._client = Client('localhost', https=False,
                              port=self.service_port(8666, 'provd'), prefix='/provd')

    def tearDown(self):
        pass

    def _add_device(self, ip, mac, plugin='', custom=None):
        custom = custom or {}
        device = {'ip': ip, 'mac': mac, 'plugin': plugin}
        device.update(custom)
        return self._client.devices.add(device)

    def test_device_find(self):
        results = self._client.devices.find()
        assert_that(results, has_key('devices'))

    def test_device_add(self):
        # When it works
        result_add = self._add_device('10.10.10.10', '00:11:22:33:44:55',
                                      custom={'id': '1234abcdef1234'})
        assert_that(result_add, has_key('id'))
        assert_that(result_add['id'], is_(equal_to('1234abcdef1234')))

        # When it fails
        assert_that(calling(self._add_device).with_args(
            '10.0.1.xx', '00:11:22:33:44:55'), raises(ProvdError, pattern='normalized'))
        assert_that(calling(self._add_device).with_args(
            '10.0.1.1', '00:11:22:33:44:55', custom={'id': ''}), raises(ProvdError))

    def test_device_update(self):
        # When it works
        # Need to insert a device first
        result_add = self._add_device('1.2.3.4', 'aa:bb:cc:dd:ee:ff')
        id_added = result_add['id']
        # Update the info
        new_info = {'id': id_added, 'ip': '5.6.7.8',
                    'mac': 'aa:bb:cc:dd:ee:ff'}
        self._client.devices.update(new_info)

        after_res = self._client.devices.get(id_added)
        assert_that(after_res['device']['ip'], is_(equal_to('5.6.7.8')))

        # When it fails
        assert_that(calling(self._client.devices.update).with_args(
            {'ip': '1.2.3.4', 'mac': '00:11:22:33:44:55'}), raises(ProvdError, pattern='resource'))
        assert_that(calling(self._client.devices.update).with_args(
            {'id': id_added, 'ip': '10.0.1.1', 'mac': '00:11:22:33:44:xx'}),
            raises(ProvdError, pattern='normalized'))

    def test_device_synchronize(self):
        result_add = self._add_device('3.3.3.3', '12:bb:34:dd:56:ff')
        id_added = result_add['id']
        self._client.devices.synchronize(id_added)

    def test_device_get(self):
        result_add = self._add_device('9.9.9.9', 'ab:ba:00:12:34:ff')
        id_added = result_add['id']

        # When it works
        after_res = self._client.devices.get(id_added)
        assert_that(after_res['device']['ip'], is_(equal_to('9.9.9.9')))

        # When it fails
        assert_that(calling(self._client.devices.get).with_args(
            'unknown_id'), raises(ProvdError, pattern='resource'))

    def test_device_remove(self):
        result_add = self._add_device('6.6.6.6', '0a:0a:00:12:34:ff')
        id_added = result_add['id']
        # When it works
        self._client.devices.remove(id_added)
        assert_that(calling(self._client.devices.get).with_args(
            id_added), raises(ProvdError, pattern='resource'))

        # when it fails
        assert_that(calling(self._client.devices.remove).with_args(
            'unknown_id'), raises(ProvdError, pattern='resource'))

    def test_device_reconfigure(self):
        result_add = self._add_device('5.5.5.5', '0b:0b:01:12:34:ff')
        id_added = result_add['id']

        # When it works
        self._client.devices.reconfigure(id_added)

        # When it fails
        assert_that(calling(self._client.devices.reconfigure).with_args(
            'unknown_id'), raises(ProvdError, pattern='invalid'))

    def test_device_dhcp(self):
        # When it works
        self._client.devices.insert_from_dhcp(
            {'ip': '10.10.0.1', 'mac': 'ab:bc:cd:de:ff:01', 'op': 'commit', 'options': []})
        find_results = self._client.devices.find({'mac': 'ab:bc:cd:de:ff:01'})
        assert_that(find_results, has_key('devices'))
        assert_that(find_results['devices'], has_length(1))
        assert_that(find_results['devices'][0]['ip'],
                    is_(equal_to('10.10.0.1')))

        # When it fails
        assert_that(calling(self._client.devices.insert_from_dhcp).with_args(
            {'ip': '10.10.0.1', 'mac': 'ab:bc:cd:de:ff:01', 'op': 'commit'}), raises(ProvdError))
