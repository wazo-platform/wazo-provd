# Copyright 2010-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Device and device collection module.

This module defines 3 kind of objects:
- device info
- device
- device collection

Device info objects and device objects have some similarities. They both
are dictionaries, with the usual restrictions associated with the fact
they may be persisted in a document collection.

They both have the following standardized keys:
  mac -- the normalized MAC address of this device (unicode)
  sn -- the serial number of this device (unicode)
  ip -- the normalized IP address of this device (unicode)
  uuid -- the UUID of this device (unicode)
  vendor -- the vendor name of this device (unicode)
  model -- the model name of this device (unicode)
  version -- the version of the software/firmware of this device (unicode)

Device objects have also the following standardized keys:
  id -- the ID of this device object (unicode) (mandatory)
  plugin -- the ID of the plugin this device is managed by (unicode)
  config -- the ID of the configuration of this device (unicode)
  configured -- a boolean indicating if the device has been successfully
    configured by a plugin. (boolean) (mandatory)
  added -- how the device has been added to the collection (unicode). Right
    now, only 'auto' has been defined.
  options -- dictionary of device options

Non-standard keys MUST begin with 'X_'.

Finally, device collection objects are used as a storage for device objects.

"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, TypeVar

from provd.devices.schemas import DeviceSchema, DeviceDict
from provd.persist.util import ForwardingDocumentCollection
from provd.util import is_normed_ip, is_normed_mac

logger = logging.getLogger(__name__)

_RECONF_KEYS = [
    'plugin',
    'config',
    'mac',
    'uuid',
    'vendor',
    'model',
    'version',
    'options',
]

T = TypeVar('T', bound=Mapping[str, Any])


def copy(device: T) -> T:
    return deepcopy(device)


def needs_reconfiguration(old_device: DeviceDict, new_device: DeviceDict) -> bool:
    for key in _RECONF_KEYS:
        if old_device.get(key) != new_device.get(key):
            logger.debug('%s is now %s', old_device, new_device)
            return True
    return False


# do
def _check_device_validity(device: DeviceDict) -> None:
    if device_mac := device.get('mac'):
        if not is_normed_mac(device_mac):
            raise ValueError(f'Non-normalized MAC address {device_mac}')
    if device_ip := device.get('ip'):
        if not is_normed_ip(device_ip):
            raise ValueError(f'Non-normalized IP address {device_ip}')
    if 'tenant_uuid' not in device:
        raise ValueError('Tenant UUID not specified')
    DeviceSchema.validate(device)


class DeviceCollection(ForwardingDocumentCollection):
    def insert(self, device: DeviceDict):
        _check_device_validity(device)
        return self._collection.insert(device)

    def update(self, device: DeviceDict):
        _check_device_validity(device)
        return self._collection.update(device)
