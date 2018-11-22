# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


from xivo_test_helpers import until
from wazo_provd_client.operation import OperationInProgress
from hamcrest import assert_that, is_

from .operation import operation_successful


class Device(object):

    def __init__(self, client, delete_on_exit=True):
        self._client = client
        self._device = None
        self._delete_on_exit = delete_on_exit

    def __enter__(self):
        device = self._client.devices.create({})
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
        location = self._client.plugins.update()
        with OperationResource(self._client.plugins, location) as current_operation:
            until.assert_(operation_successful, current_operation, tries=20, interval=0.5)

        location = self._client.plugins.install(self._plugin_name)

        with OperationResource(self._client.plugins, location) as current_operation:
            until.assert_(operation_successful, current_operation, tries=20, interval=0.5)

        self._plugin = self._client.plugins.get(self._plugin_name)['plugin_info']
        return self._plugin

    def __exit__(self, type, value, traceback):
        if self._delete_on_exit:
            self._client.plugins.uninstall(self._plugin_name)


class OperationResource(object):
    def __init__(self, client, location, delete_on_exit=True):
        self._client = client
        self._location = location
        self._operation = None
        self._delete_on_exit = delete_on_exit

    def __enter__(self):
        self._operation = OperationInProgress(self._client, self._location)
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
        config = self._client.configs.autocreate()
        self._config = self._client.configs.get(config['id'])['config']
        return self._config

    def __exit__(self, type, value, traceback):
        if self._delete_on_exit:
            self._client.configs.delete(self._config['id'])
