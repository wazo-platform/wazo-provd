# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class Device:

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
