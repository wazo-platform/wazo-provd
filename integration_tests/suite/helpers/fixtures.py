# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class DeviceContext:
    context_id = 0

    def __init__(self, client, delete_on_exit=True):
        self._client = client
        self._delete_on_exit = delete_on_exit
        DeviceContext.context_id += 1

    def __enter__(self):
        self._device = {
            'id': 'test123test123{}'.format(DeviceContext.context_id),
            'ip': '10.1.2.3',
            'mac': '00:11:22:33:44:55',
            'plugin': 'null'
        }
        self._client.devices.create(self._device)
        return self._device

    def __exit__(self, type, value, traceback):
        if self._delete_on_exit:
            self._client.devices.delete(self._device['id'])
