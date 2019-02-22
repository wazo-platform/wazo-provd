# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


from xivo_test_helpers import until
from .operation import operation_successful

PLUGIN_TO_INSTALL = 'test-plugin'


class Device(object):

    device_counter = 0

    def __init__(self, client, delete_on_exit=True, tenant_uuid=None):
        self._client = client
        self._device = None
        self._delete_on_exit = delete_on_exit
        self._tenant_uuid = tenant_uuid

    def __enter__(self):
        Device.device_counter += 1
        config = {
            'config': 'defaultconfigdevice',
            'configured': True,
            'description': 'Test device',
            'id': 'testdevice{}'.format(Device.device_counter),
            'ip': '10.0.0.2',
            'mac': '00:11:22:33:44:55',
            'model': 'testdevice',
            'plugin': PLUGIN_TO_INSTALL,
            'vendor': 'test',
            'version': '1.0',
        }
        device = self._client.devices.create(config, tenant_uuid=self._tenant_uuid)
        self._device = self._client.devices.get(device['id'], tenant_uuid=self._tenant_uuid)
        return self._device

    def __exit__(self, type, value, traceback):
        if self._delete_on_exit:
            Device.device_counter -= 1
            self._client.devices.delete(self._device['id'], tenant_uuid=self._tenant_uuid)


class Plugin(object):
    def __init__(self, client, delete_on_exit=True):
        self._client = client
        self._plugin = None
        self._delete_on_exit = delete_on_exit

    def __enter__(self):
        with self._client.plugins.update() as current_operation:
            until.assert_(operation_successful, current_operation, tries=20, interval=0.5)

        with self._client.plugins.install(PLUGIN_TO_INSTALL) as current_operation:
            until.assert_(operation_successful, current_operation, tries=20, interval=0.5)

        self._plugin = self._client.plugins.get(PLUGIN_TO_INSTALL)
        return self._plugin

    def __exit__(self, type, value, traceback):
        if self._delete_on_exit:
            self._client.plugins.uninstall(PLUGIN_TO_INSTALL)


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
        self._config = self._client.configs.get(result['id'])
        return self._config

    def __exit__(self, type, value, traceback):
        if self._delete_on_exit:
            self._client.configs.delete(self._config['id'])
