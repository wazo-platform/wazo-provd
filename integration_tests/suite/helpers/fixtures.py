# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


from xivo_test_helpers import until
from wazo_provd_client.operation import OperationInProgress
from hamcrest import assert_that, is_

from .operation import operation_successful

PLUGIN_TO_INSTALL = 'test-plugin'


class Device(object):

    def __init__(self, client, delete_on_exit=True):
        self._client = client
        self._device = None
        self._delete_on_exit = delete_on_exit

    def __enter__(self):
        config = {
            'config': 'defaultconfigdevice',
            'configured': True,
            'description': 'Test device',
            'id': 'testdevice1',
            'ip': '10.0.0.2',
            'mac': '00:11:22:33:44:55',
            'model': 'testdevice',
            'plugin': PLUGIN_TO_INSTALL,
            'vendor': 'test',
            'version': '1.0',
        }
        device = self._client.devices.create(config)
        self._device = self._client.devices.get(device['id'])['device']
        return self._device

    def __exit__(self, type, value, traceback):
        if self._delete_on_exit:
            self._client.devices.delete(self._device['id'])


class Plugin(object):
    def __init__(self, client, plugin_name, delete_on_exit=True):
        self._client = client
        self._plugin_name = plugin_name
        self._plugin = None
        self._delete_on_exit = delete_on_exit

    def __enter__(self):
        progress = self._client.plugins.update()
        with OperationResource(progress) as current_operation:
            until.assert_(operation_successful, current_operation, tries=20, interval=0.5)

        progress = self._client.plugins.install(self._plugin_name)

        with OperationResource(progress) as current_operation:
            until.assert_(operation_successful, current_operation, tries=20, interval=0.5)

        self._plugin = self._client.plugins.get(self._plugin_name)['plugin_info']
        return self._plugin

    def __exit__(self, type, value, traceback):
        if self._delete_on_exit:
            self._client.plugins.uninstall(self._plugin_name)


class OperationResource(object):
    def __init__(self, progress, delete_on_exit=True):
        self._operation = progress
        self._delete_on_exit = delete_on_exit

    def __enter__(self):
        return self._operation

    def __exit__(self, type, value, traceback):
        if self._delete_on_exit:
            self._operation.delete()


class Configuration(object):

    def __init__(self, client, delete_on_exit=True):
        self._client = client
        self._config = None
        self._delete_on_exit = delete_on_exit

    def __enter__(self):
        config = {
            'id': 'test1',
            'parent_ids': ['base'],
            'deletable': True,
            'X_type': 'internal',
            'raw_config': {
                'ntp_ip': '127.0.0.1',
                'X_xivo_phonebook_ip': '127.0.0.1',
                'ntp_enabled': True,
            }
        }
        result = self._client.configs.create(config)
        self._config = self._client.configs.get(result['id'])['config']
        return self._config

    def __exit__(self, type, value, traceback):
        if self._delete_on_exit:
            self._client.configs.delete(self._config['id'])
