# Copyright 2010-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import copy
import logging
import functools
import os.path
from typing import Any, TYPE_CHECKING
from urllib.parse import urlparse

from provd.devices.config import RawConfigError, DefaultConfigFactory, ConfigCollection
from provd.devices.device import needs_reconfiguration, DeviceCollection
from provd.localization import get_localization_service
from provd.operation import OIP_PROGRESS, OIP_FAIL, OIP_SUCCESS
from provd.persist.common import (
    ID_KEY,
    InvalidIdError as PersistInvalidIdError,
    NonDeletableError as PersistNonDeletableError,
)
from provd.plugins import PluginManager, PluginNotLoadedError
from provd.services import (
    InvalidParameterError,
    JsonConfigPersister,
    PersistentConfigurationServiceDecorator,
)
from provd.synchro import DeferredRWLock
from twisted.internet import defer
from provd.rest.server import auth
from provd.rest.server.helpers.tenants import Tenant, Tokens
from provd.util import decode_bytes


if TYPE_CHECKING:
    from .config import ProvdConfigDict


logger = logging.getLogger(__name__)


class InvalidIdError(Exception):
    """Raised when a passed ID is invalid, not necessary because of its type,
    but because of its semantic.

    """

    pass


class DeviceNotInProvdTenantError(Exception):
    def __init__(self, tenant_uuid):
        super().__init__('Device not in provd tenant')
        self.tenant_uuid = tenant_uuid


class TenantInvalidForDeviceError(Exception):
    def __init__(self, tenant_uuid):
        super().__init__('Tenant invalid for device')
        self.tenant_uuid = tenant_uuid


class NonDeletableError(Exception):
    """Raised when a document is non deletable"""

    pass


def _rlock_arg(rw_lock):
    def decorator(fun):
        @functools.wraps(fun)
        def aux(*args, **kwargs):
            d = rw_lock.read_lock.run(fun, *args, **kwargs)
            return d

        return aux

    return decorator


def _wlock_arg(rw_lock):
    def decorator(fun):
        @functools.wraps(fun)
        def aux(*args, **kwargs):
            d = rw_lock.write_lock.run(fun, *args, **kwargs)
            return d

        return aux

    return decorator


def _rlock(fun):
    # Decorator for instance method of ProvisioningApplication that need to
    # acquire the read lock
    @functools.wraps(fun)
    def aux(self, *args, **kwargs):
        d = self._rw_lock.read_lock.run(fun, self, *args, **kwargs)
        return d

    return aux


def _wlock(fun):
    # Decorator for instance method of ProvisioningApplication that need to
    # acquire the write lock
    @functools.wraps(fun)
    def aux(self, *args, **kwargs):
        d = self._rw_lock.write_lock.run(fun, self, *args, **kwargs)
        return d

    return aux


def _check_common_raw_config_validity(raw_config: dict[str, Any]) -> None:
    for param in ['ip', 'http_port', 'tftp_port']:
        if param not in raw_config:
            raise RawConfigError(f'missing {param} parameter')


def _check_raw_config_validity(raw_config: dict[str, Any]) -> None:
    # XXX this is bit repetitive...
    _check_common_raw_config_validity(raw_config)
    if raw_config.get('ntp_enabled'):
        if 'ntp_ip' not in raw_config:
            raise RawConfigError('missing ntp_ip parameter')
    if raw_config.get('vlan_enabled'):
        if 'vlan_id' not in raw_config:
            raise RawConfigError('missing vlan_id parameter')
    if raw_config.get('syslog_enabled'):
        if 'syslog_ip' not in raw_config:
            raise RawConfigError('missing syslog_ip parameter')
    if 'sip_lines' in raw_config:
        for line_no, line in raw_config['sip_lines'].items():
            if 'proxy_ip' not in line and 'sip_proxy_ip' not in raw_config:
                raise RawConfigError(f'missing proxy_ip parameter for line {line_no}')
            if 'protocol' in raw_config and raw_config['protocol'] == 'SIP':
                for param in ['username', 'password', 'display_name']:
                    if param not in line:
                        raise RawConfigError(
                            f'missing {param} parameter for line {line_no}'
                        )
    if 'sccp_call_managers' in raw_config:
        for priority, call_manager in raw_config['sccp_call_managers'].items():
            if 'ip' not in call_manager:
                raise RawConfigError(
                    f'missing ip parameter for call manager {priority}'
                )
    if 'funckeys' in raw_config:
        funckeys = raw_config['funckeys']
        for funckey_no, funckey in funckeys.items():
            try:
                type_ = funckey['type']
            except KeyError:
                raise RawConfigError(f'missing type parameter for funckey {funckey_no}')
            else:
                if (type_ == 'speeddial' or type_ == 'blf') and 'value' not in funckey:
                    raise RawConfigError(
                        f'missing value parameter for funckey {funckey_no}'
                    )


def _set_defaults_raw_config(raw_config: dict[str, Any]) -> None:
    if raw_config.get('syslog_enabled'):
        raw_config.setdefault('syslog_port', 514)
        raw_config.setdefault('level', 'warning')
    if 'sip_proxy_ip' in raw_config:
        raw_config.setdefault('sip_registrar_ip', raw_config['sip_proxy_ip'])
    raw_config.setdefault('sip_srtp_mode', 'disabled')
    raw_config.setdefault('sip_transport', 'udp')
    if 'sip_lines' not in raw_config:
        raw_config['sip_lines'] = {}
    else:
        for line in raw_config['sip_lines'].values():
            if 'proxy_ip' in line:
                line.setdefault('registrar_ip', line['proxy_ip'])
            if 'username' in line:
                line.setdefault('auth_username', line['username'])
    raw_config.setdefault('sccp_call_managers', {})
    raw_config.setdefault('funckeys', {})


class ProvisioningApplication:
    """Main logic used to provision devices.

    Here's the restrictions on the devices/configs/plugins stored by instances
    of this class:
    - device can make references to unknown configs or plugins
    - configs can make references to unknown configs
    - a plugin can be uninstalled even if some devices make references to it
    - a config can be removed even if some devices or other configs make
      reference to it

    This class enforce the plugin contract.

    """

    # Note that, seen from the outside, all method acquiring a lock return a
    # deferred.

    def __init__(
        self,
        cfg_collection: ConfigCollection,
        dev_collection: DeviceCollection,
        config: ProvdConfigDict,
    ):
        self._cfg_collection = cfg_collection
        self._dev_collection = dev_collection
        self._split_config = config
        self._token = None
        self._tenant_uuid = None

        base_storage_dir = config['general']['base_storage_dir']
        plugins_dir = os.path.join(base_storage_dir, 'plugins')

        self.proxies = self._split_config.get('proxy', {})
        self.nat = 0
        self.tenants = self._split_config.get('tenants', {})
        self.http_auth_strategy = self._split_config['general'].get('http_auth_strategy')
        self.use_provisioning_key = self.http_auth_strategy == 'url_key'

        self.pg_mgr = PluginManager(
            self,
            plugins_dir,
            config['general']['cache_dir'],
            config['general']['cache_plugin'],
            config['general']['check_compat_min'],
            config['general']['check_compat_max'],
        )
        if 'plugin_server' in config['general']:
            self.pg_mgr.server = config['general']['plugin_server']

        # Do not move this line up unless you know what you are doing...
        cfg_service = ApplicationConfigureService(self.pg_mgr, self.proxies, self)
        persister = JsonConfigPersister(os.path.join(base_storage_dir, 'app.json'))
        self.configure_service = PersistentConfigurationServiceDecorator(
            cfg_service, persister
        )

        self._base_raw_config = config['general']['base_raw_config']
        logger.info('Using base raw config %s', self._base_raw_config)
        _check_common_raw_config_validity(self._base_raw_config)
        self._rw_lock = DeferredRWLock()
        self._cfg_factory = DefaultConfigFactory()
        self._pg_load_all(True)

    @_wlock
    def close(self):
        logger.info('Closing provisioning application...')
        self.pg_mgr.close()
        logger.info('Provisioning application closed')

    def token(self):
        return self._token

    def set_token(self, token_id):
        logger.debug('Setting token for provd app: %s', token_id)
        self._token = token_id
        auth_client = auth.get_auth_client()
        token = Tokens(auth_client).get(self._token)
        self.set_tenant_uuid(Tenant.from_token(token).uuid)

    def tenant_uuid(self):
        return self._tenant_uuid

    def set_tenant_uuid(self, tenant_uuid):
        self._tenant_uuid = tenant_uuid
        if not self.tenants.get(tenant_uuid):
            self.set_tenant_configuration(tenant_uuid, {})

    def set_tenant_configuration(self, tenant_uuid, config):
        self.tenants[tenant_uuid] = config

    # device methods

    def _dev_get_plugin(self, device):
        if 'plugin' in device:
            return self.pg_mgr.get(device['plugin'])
        return None

    def _dev_get_raw_config(self, device):
        # Return a deferred that will fire with a raw config associated
        # with the device, or fire with None if there's no such raw config
        if 'config' in device:
            cfg_id = device['config']
            return self._cfg_collection.get_raw_config(cfg_id, self._base_raw_config)
        return defer.succeed(None)

    @defer.inlineCallbacks
    def _dev_get_plugin_and_raw_config(self, device):
        # Return a deferred that will fire with a tuple (plugin, raw_config)
        # associated with the device, or fire with the tuple (None, None) if
        # there's at least one without etc etc
        if (plugin := self._dev_get_plugin(device)) is not None:
            raw_config = yield self._dev_get_raw_config(device)
            if raw_config is not None:
                defer.returnValue((plugin, raw_config))
        defer.returnValue((None, None))

    def _dev_configure(self, device, plugin, raw_config):
        # Return true if the device has been successfully configured (i.e.
        # no exception were raised), else false.
        logger.info('Configuring device %s with plugin %s', device[ID_KEY], plugin.id)
        if self.use_provisioning_key:
            tenant_uuid = device.get('tenant_uuid', None)
            if not tenant_uuid:
                logger.warning('Device %s is using provisioning key but has no tenant_uuid', device[ID_KEY])
                return False
            provisioning_key = self.configure_service.get('provisioning_key', tenant_uuid)
            raw_config = copy.deepcopy(raw_config)
            # Inject the provisioning key into the device configuration
            http_base_url = raw_config['http_base_url']
            raw_config['http_base_url'] = f'{http_base_url}/{provisioning_key}'
        try:
            _check_raw_config_validity(raw_config)
        except Exception:
            logger.error(
                'Error while configuring device %s', device[ID_KEY], exc_info=True
            )
        else:
            _set_defaults_raw_config(raw_config)
            try:
                plugin.configure(device, raw_config)
            except Exception:
                logger.error(
                    'Error while configuring device %s', device[ID_KEY], exc_info=True
                )
            else:
                return True
        return False

    @defer.inlineCallbacks
    def _dev_configure_if_possible(self, device):
        # Return a deferred that fire with true if the device has been
        # successfully configured (i.e. no exception were raised), else false.
        plugin, raw_config = yield self._dev_get_plugin_and_raw_config(device)
        if plugin is None:
            defer.returnValue(False)
        else:
            defer.returnValue(self._dev_configure(device, plugin, raw_config))

    def _dev_deconfigure(self, device, plugin):
        # Return true if the device has been successfully deconfigured (i.e.
        # no exception were raised), else false.
        logger.info('Deconfiguring device %s with plugin %s', device[ID_KEY], plugin.id)
        try:
            plugin.deconfigure(device)
        except Exception:
            logger.error(
                'Error while deconfiguring device %s', device[ID_KEY], exc_info=True
            )
            return False
        else:
            return True

    def _dev_deconfigure_if_possible(self, device):
        # Return true if the device has been successfully configured (i.e.
        # no exception were raised), else false.
        if (plugin := self._dev_get_plugin(device)) is None:
            return False
        return self._dev_deconfigure(device, plugin)

    def _dev_synchronize(self, device, plugin, raw_config):
        # Return a deferred that will fire with None once the device
        # synchronization is completed.
        logger.info('Synchronizing device %s with plugin %s', device[ID_KEY], plugin.id)
        _set_defaults_raw_config(raw_config)
        return plugin.synchronize(device, raw_config)

    @defer.inlineCallbacks
    def _dev_synchronize_if_possible(self, device):
        # Return a deferred that will fire with None once the device
        # synchronization is completed.
        plugin, raw_config = yield self._dev_get_plugin_and_raw_config(device)
        if plugin is None:
            # somewhat rare case were the device is marked as configured but
            # the plugin used by the device is not installed/loaded. This
            # is often caused by a manual plugin uninstallation
            raise Exception(f'Plugin {device.get("plugin")} is not installed/loaded')

        yield self._dev_synchronize(device, plugin, raw_config)

    @defer.inlineCallbacks
    def _dev_get_or_raise(self, device_id):
        device = yield self._dev_collection.retrieve(device_id)
        if device is None:
            raise InvalidIdError(f'invalid device ID "{device_id}"')

        defer.returnValue(device)

    @_wlock
    @defer.inlineCallbacks
    def dev_insert(self, device):
        """Insert a new device into the provisioning application.

        Return a deferred that will fire with the ID of the device.

        The deferred will fire it's errback with a ValueError if device
        is not a valid device object, i.e. invalid key value, invalid
        type, etc.

        The deferred will fire it's errback with an Exception if an 'id'
        key is specified but there's already one device with the same ID.

        If device has no 'id' key, one will be added after the device is
        successfully inserted.

        Device will be automatically configured if there's enough information
        to do so.

        Note that:
        - the value of 'configured' is ignored if given.
        - the passed in device object might be modified so that if the device
          has been inserted successfully, the device object has the same value
          as the one which has been inserted.

        """
        logger.info('Inserting new device')
        try:
            # new device are never configured
            device['configured'] = False

            if not device.get('tenant_uuid'):
                device['tenant_uuid'] = self._tenant_uuid

            device['is_new'] = device['tenant_uuid'] == self._tenant_uuid

            try:
                device_id = yield self._dev_collection.insert(device)
            except PersistInvalidIdError as e:
                raise InvalidIdError(e)
            else:
                configured = yield self._dev_configure_if_possible(device)
                if configured:
                    device['configured'] = True
                    yield self._dev_collection.update(device)
                defer.returnValue(device_id)
        except Exception:
            logger.error('Error while inserting device', exc_info=True)
            raise

    @_wlock
    @defer.inlineCallbacks
    def dev_update(self, device, pre_update_hook=None):
        """Update the device.

        The pre_update_hook function is called with the device and
        its config just before the device is persisted.

        Return a deferred that fire with None once the update is completed.

        The deferred will fire its errback with an exception if device has
        no 'id' key.

        The deferred will fire its errback with an InvalidIdError if device
        has unknown id.

        The device is automatically deconfigured/configured if needed.

        Note that the value of 'configured' is ignored if given.

        """
        try:
            try:
                device_id = device[ID_KEY]
            except KeyError:
                raise InvalidIdError(f'No id key for device {device}')
            else:
                logger.info('Updating device %s', device_id)
                old_device = yield self._dev_get_or_raise(device_id)
                if needs_reconfiguration(old_device, device):
                    # Deconfigure old device it was configured
                    if old_device['configured']:
                        self._dev_deconfigure_if_possible(old_device)
                    # Configure new device if possible
                    configured = yield self._dev_configure_if_possible(device)
                    device['configured'] = configured
                else:
                    device['configured'] = old_device['configured']
                if pre_update_hook is not None:
                    config = yield self._cfg_collection.retrieve(device.get('config'))
                    pre_update_hook(device, config)
                # Update device collection if the device is different from
                # the old device
                if device != old_device:
                    device['is_new'] = device['tenant_uuid'] == self._tenant_uuid
                    yield self._dev_collection.update(device)
                    # check if old device was using a transient config that is
                    # no more in use
                    if 'config' in old_device and old_device['config'] != device.get(
                        'config'
                    ):
                        old_device_cfg_id = old_device['config']
                        old_device_cfg = yield self._cfg_collection.retrieve(
                            old_device_cfg_id
                        )
                        if old_device_cfg and old_device_cfg.get('transient'):
                            # if no devices are using this transient config, delete it
                            if not (
                                yield self._dev_collection.find_one(
                                    {'config': old_device_cfg_id}
                                )
                            ):
                                self._cfg_collection.delete(old_device_cfg_id)
                else:
                    logger.info('Not updating device %s: not changed', device_id)
        except Exception:
            logger.error('Error while updating device', exc_info=True)
            raise

    @_wlock
    @defer.inlineCallbacks
    def dev_delete(self, device_id):
        """Delete the device with the given ID.

        Return a deferred that will fire with None once the device is
        deleted.

        The deferred will fire its errback with an InvalidIdError if device
        has unknown id.

        The device is automatically deconfigured if needed.

        """
        logger.info('Deleting device %s', device_id)
        try:
            device = yield self._dev_get_or_raise(device_id)
            # Next line should never raise an exception since we successfully
            # retrieve the device with the same id just before and we are
            # using the write lock
            yield self._dev_collection.delete(device_id)
            # check if device was using a transient config that is no more in use
            if 'config' in device:
                device_cfg_id = device['config']
                device_cfg = yield self._cfg_collection.retrieve(device_cfg_id)
                if device_cfg and device_cfg.get('transient'):
                    # if no devices are using this transient config, delete it
                    if not (
                        yield self._dev_collection.find_one({'config': device_cfg_id})
                    ):
                        self._cfg_collection.delete(device_cfg_id)
            if device['configured']:
                self._dev_deconfigure_if_possible(device)
        except Exception:
            logger.error('Error while deleting device', exc_info=True)
            raise

    def dev_retrieve(self, device_id):
        """Return a deferred that fire with the device with the given ID, or
        fire with None if there's no such document.

        """
        return self._dev_collection.retrieve(device_id)

    def dev_find(self, selector, *args, **kwargs):
        return self._dev_collection.find(selector, *args, **kwargs)

    def dev_find_one(self, selector, *args, **kwargs):
        return self._dev_collection.find_one(selector, *args, **kwargs)

    @_wlock
    @defer.inlineCallbacks
    def dev_reconfigure(self, device_id):
        """Force the reconfiguration of the device. This is usually not
        necessary since configuration is usually done automatically.

        Return a deferred that will fire once the device reconfiguration is
        completed, with either True if the device has been successfully
        reconfigured or else False.

        The deferred will fire its errback with an exception if id is not a
        valid device ID.

        """
        logger.info('Reconfiguring device %s', device_id)
        try:
            device = yield self._dev_get_or_raise(device_id)
            if device['configured']:
                self._dev_deconfigure_if_possible(device)
            configured = yield self._dev_configure_if_possible(device)
            if device['configured'] != configured:
                device['configured'] = configured
                yield self._dev_collection.update(device)
            defer.returnValue(configured)
        except Exception:
            logger.error('Error while reconfiguring device', exc_info=True)
            raise

    @_rlock
    @defer.inlineCallbacks
    def dev_synchronize(self, device_id):
        """Synchronize the physical device with its config.

        Return a deferred that will fire with None once the device is
        synchronized.

        The deferred will fire its errback with an exception if id is not a
        valid device ID.

        The deferred will fire its errback with an exception if the device
        can't be synchronized, either because it has not been configured yet,
        does not support synchronization or if the operation just seem to
        have failed.

        """
        logger.info('Synchronizing device %s', device_id)
        try:
            device = yield self._dev_get_or_raise(device_id)
            if not device['configured']:
                raise Exception(f'Can\'t synchronize not configured device {device_id}')
            else:
                yield self._dev_synchronize_if_possible(device)
        except Exception:
            logger.error('Error while synchronizing device', exc_info=True)
            raise

    # config methods

    @defer.inlineCallbacks
    def _cfg_get_or_raise(self, config_id):
        config = yield self._cfg_collection.retrieve(config_id)
        if config is None:
            raise InvalidIdError(f'Invalid config ID "{config_id}"')
        defer.returnValue(config)

    @_wlock
    @defer.inlineCallbacks
    def cfg_insert(self, config):
        """Insert a new config into the provisioning application.

        Return a Deferred that will fire with the ID of the config.

        The deferred will fire it's errback with a ValueError if config
        is not a valid config object, i.e. invalid key value, invalid
        type, etc.

        The deferred will fire it's errback with an Exception if an 'id'
        key is specified but there's already one config with the same ID.

        If config has no 'id' key, one will be added after the config is
        successfully inserted.

        """
        logger.info('Inserting config %s', config.get(ID_KEY))
        try:
            try:
                config_id = yield self._cfg_collection.insert(config)
            except PersistInvalidIdError as e:
                raise InvalidIdError(e)
            else:
                # configure each device that depend on the newly inserted config
                # 1. get the set of affected configs
                affected_cfg_ids = yield self._cfg_collection.get_descendants(config_id)
                affected_cfg_ids.add(config_id)
                # 2. get the raw_config of every affected config
                raw_configs = {}
                for affected_cfg_id in affected_cfg_ids:
                    raw_configs[
                        affected_cfg_id
                    ] = yield self._cfg_collection.get_raw_config(
                        affected_cfg_id, self._base_raw_config
                    )
                # 3. reconfigure/deconfigure each affected devices
                affected_devices = yield self._dev_collection.find(
                    {'config': {'$in': list(affected_cfg_ids)}}
                )
                for device in affected_devices:
                    plugin = self._dev_get_plugin(device)
                    if plugin is not None:
                        raw_config = raw_configs[device['config']]
                        assert raw_config is not None
                        # deconfigure
                        if device['configured']:
                            self._dev_deconfigure(device, plugin)
                        # configure
                        configured = self._dev_configure(device, plugin, raw_config)
                        # update device if it has changed
                        if device['configured'] != configured:
                            device['configured'] = configured
                            yield self._dev_collection.update(device)
                # 4. return the device id
                defer.returnValue(config_id)
        except Exception:
            logger.error('Error while inserting config', exc_info=True)
            raise

    @_wlock
    @defer.inlineCallbacks
    def cfg_update(self, config):
        """Update the config.

        Return a deferred that fire with None once the update is completed.

        The deferred will fire its errback with an exception if config has
        no 'id' key.

        The deferred will fire its errback with an InvalidIdError if config
        has unknown id.

        Note that device might be reconfigured.

        """
        try:
            try:
                config_id = config[ID_KEY]
            except KeyError:
                raise InvalidIdError(f'No id key for config {config}')

            logger.info('Updating config %s', config_id)
            old_config = yield self._cfg_get_or_raise(config_id)
            if old_config == config:
                logger.info('config has not changed, ignoring update')
            else:
                yield self._cfg_collection.update(config)
                affected_cfg_ids = yield self._cfg_collection.get_descendants(config_id)
                affected_cfg_ids.add(config_id)
                # 2. get the raw_config of every affected config
                raw_configs = {}
                for affected_cfg_id in affected_cfg_ids:
                    raw_configs[
                        affected_cfg_id
                    ] = yield self._cfg_collection.get_raw_config(
                        affected_cfg_id, self._base_raw_config
                    )
                # 3. reconfigure each device having a direct dependency on
                #    one of the affected cfg id
                affected_devices = yield self._dev_collection.find(
                    {'config': {'$in': list(affected_cfg_ids)}}
                )
                for device in affected_devices:
                    plugin = self._dev_get_plugin(device)
                    if plugin is not None:
                        raw_config = raw_configs[device['config']]
                        assert raw_config is not None
                        # deconfigure
                        if device['configured']:
                            self._dev_deconfigure(device, plugin)
                        # configure
                        configured = self._dev_configure(device, plugin, raw_config)
                        # update device if it has changed
                        if device['configured'] != configured:
                            device['configured'] = configured
                            yield self._dev_collection.update(device)
        except Exception:
            logger.error('Error while updating config', exc_info=True)
            raise

    @_wlock
    @defer.inlineCallbacks
    def cfg_delete(self, config_id):
        """Delete the config with the given ID. Does not delete any reference
        to it from other configs.

        Return a deferred that will fire with None once the config is
        deleted.

        The deferred will fire its errback with an InvalidIdError if config
        has unknown id.

        The devices depending directly or indirectly on this config are
        automatically reconfigured if needed.

        """
        config_id = decode_bytes(config_id)
        logger.info('Deleting config %s', config_id)
        try:
            try:
                yield self._cfg_collection.delete(config_id)
            except PersistInvalidIdError as e:
                raise InvalidIdError(e)
            except PersistNonDeletableError as e:
                raise NonDeletableError(e)
            else:
                # 1. get the set of affected configs
                affected_cfg_ids = yield self._cfg_collection.get_descendants(config_id)
                affected_cfg_ids.add(config_id)
                # 2. get the raw_config of every affected config
                raw_configs = {}
                for affected_cfg_id in affected_cfg_ids:
                    raw_configs[
                        affected_cfg_id
                    ] = yield self._cfg_collection.get_raw_config(
                        affected_cfg_id, self._base_raw_config
                    )
                # 3. reconfigure/deconfigure each affected devices
                affected_devices = yield self._dev_collection.find(
                    {'config': {'$in': list(affected_cfg_ids)}}
                )
                for device in affected_devices:
                    plugin = self._dev_get_plugin(device)
                    if plugin is not None:
                        raw_config = raw_configs[device['config']]
                        # deconfigure
                        if device['configured']:
                            self._dev_deconfigure(device, plugin)
                        # configure if device config is not the deleted config
                        if device['config'] == config_id:
                            assert raw_config is None
                            # update device if it has changed
                            if device['configured']:
                                device['configured'] = False
                                yield self._dev_collection.update(device)
                        else:
                            assert raw_config is not None
                            configured = yield self._dev_configure(
                                device, plugin, raw_config
                            )
                            # update device if it has changed
                            if device['configured'] != configured:
                                yield self._dev_collection.update(device)
        except Exception:
            logger.error('Error while deleting config', exc_info=True)
            raise

    def cfg_retrieve(self, config_id):
        """Return a deferred that fire with the config with the given ID, or
        fire with None if there's no such document.

        """
        return self._cfg_collection.retrieve(config_id)

    def cfg_retrieve_raw_config(self, config_id):
        return self._cfg_collection.get_raw_config(config_id, self._base_raw_config)

    def cfg_find(self, selector, *args, **kwargs):
        return self._cfg_collection.find(selector, *args, **kwargs)

    def cfg_find_one(self, selector, *args, **kwargs):
        return self._cfg_collection.find_one(selector, *args, **kwargs)

    @_wlock
    @defer.inlineCallbacks
    def cfg_create_new(self):
        """Create a new config from the config with the autocreate role.

        Return a deferred that will fire with the ID of the newly created
        config, or fire with None if there's no config with the autocreate
        role or if the config factory returned None.

        """
        logger.info('Creating new config')
        try:
            new_config_id = None
            config = yield self._cfg_collection.find_one({'role': 'autocreate'})
            if config:
                # remove the role of the config so we don't create new config
                # with the autocreate role
                del config['role']
                new_config = self._cfg_factory(config)
                if new_config:
                    new_config_id = yield self._cfg_collection.insert(new_config)
                else:
                    logger.debug('Autocreate config factory returned null config')
            else:
                logger.debug('No config with the autocreate role found')

            defer.returnValue(new_config_id)
        except Exception:
            logger.error('Error while autocreating config', exc_info=True)
            raise

    # plugin methods

    def _pg_load_all(self, catch_error=False):
        logger.info('Loading all plugins')
        loaded_plugins = 0
        for pg_id in self.pg_mgr.list_installed():
            try:
                self._pg_load(pg_id)
                loaded_plugins += 1
            except Exception:
                if catch_error:
                    logger.error('Could not load plugin %s', pg_id)
                else:
                    raise
        logger.info('Loaded %d plugins.', loaded_plugins)

    def _pg_configure_pg(self, plugin_id):
        # Raise an exception if configure_common fail
        plugin = self.pg_mgr[plugin_id]
        common_config = copy.deepcopy(self._base_raw_config)
        logger.info('Configuring plugin %s with config %s', plugin_id, common_config)
        try:
            plugin.configure_common(common_config)
        except Exception:
            logger.error('Error while configuring plugin %s', plugin_id, exc_info=True)
            raise

    def _pg_load(self, plugin_id):
        # Raise an exception if plugin loading or common configuration fail
        gen_cfg = dict(self._split_config['general'])
        gen_cfg['proxies'] = self.proxies
        spec_cfg = dict(self._split_config.get('plugin_config', {}).get(plugin_id, {}))
        try:
            self.pg_mgr.load(plugin_id, gen_cfg, spec_cfg)
        except Exception:
            logger.error('Error while loading plugin %s', plugin_id, exc_info=True)
            raise
        else:
            self._pg_configure_pg(plugin_id)

    def _pg_unload(self, plugin_id):
        # This method should never raise an exception
        try:
            self.pg_mgr.unload(plugin_id)
        except PluginNotLoadedError:
            # this is the case were an incompatible/bogus plugin has been
            # installed successfully but the plugin was not loadable
            logger.info('Plugin %s was not loaded ', plugin_id)

    @defer.inlineCallbacks
    def _pg_configure_all_devices(self, plugin_id):
        logger.info('Reconfiguring all devices using plugin %s', plugin_id)
        devices = yield self._dev_collection.find({'plugin': plugin_id})
        for device in devices:
            # deconfigure
            if device['configured']:
                self._dev_deconfigure_if_possible(device)
            # configure
            configured = yield self._dev_configure_if_possible(device)
            if device['configured'] != configured:
                device['configured'] = configured
                yield self._dev_collection.update(device)

    def pg_install(self, plugin_id):
        """Install the plugin with the given id.

        Return a tuple (deferred, operation in progress).

        This method raise the following exception:
          - an Exception if the plugin is already installed.
          - an Exception if there's no installable plugin with the specified
            name.
          - an Exception if there's already an installation/upgrade operation
            in progress for the plugin.
          - an InvalidParameterError if the plugin package is not in cache
            and no 'server' param has been set.

        Affected devices are automatically configured if needed.

        """
        logger.info('Installing and loading plugin %s', plugin_id)
        if self.pg_mgr.is_installed(plugin_id):
            logger.error('Error: plugin %s is already installed', plugin_id)
            raise Exception(f'plugin {plugin_id} is already installed')

        def callback1(_):
            # reset the state to in progress
            oip.state = OIP_PROGRESS

        @_wlock_arg(self._rw_lock)
        def callback2(_):
            # The lock apply only to the deferred return by this function
            # and not on the function itself
            # next line might raise an exception, which is ok
            self._pg_load(plugin_id)
            return self._pg_configure_all_devices(plugin_id)

        def callback3(_):
            oip.state = OIP_SUCCESS

        def errback3(err):
            oip.state = OIP_FAIL
            return err

        deferred, oip = self.pg_mgr.install(plugin_id)
        deferred.addCallback(callback1)
        deferred.addCallback(callback2)
        deferred.addCallbacks(callback3, errback3)
        return deferred, oip

    def pg_upgrade(self, plugin_id):
        """Upgrade the plugin with the given id.

        Same contract as pg_install, except that the plugin must already be
        installed.

        Affected devices are automatically reconfigured if needed.

        """
        logger.info('Upgrading and reloading plugin %s', plugin_id)
        if not self.pg_mgr.is_installed(plugin_id):
            logger.error('Error: plugin %s is not already installed', plugin_id)
            raise Exception(f'plugin {plugin_id} is not already installed')

        def callback1(_):
            # reset the state to in progress
            oip.state = OIP_PROGRESS

        @_wlock_arg(self._rw_lock)
        def callback2(_):
            # The lock apply only to the deferred return by this function
            # and not on the function itself
            if plugin_id in self.pg_mgr:
                self._pg_unload(plugin_id)
            # next line might raise an exception, which is ok
            self._pg_load(plugin_id)
            return self._pg_configure_all_devices(plugin_id)

        def callback3(_):
            oip.state = OIP_SUCCESS

        def errback3(err):
            oip.state = OIP_FAIL
            return err

        # XXX we probably want to check that the plugin is 'really' upgradeable
        deferred, oip = self.pg_mgr.upgrade(plugin_id)
        deferred.addCallback(callback1)
        deferred.addCallback(callback2)
        deferred.addCallbacks(callback3, errback3)
        return deferred, oip

    @_wlock
    @defer.inlineCallbacks
    def pg_uninstall(self, plugin_id):
        """Uninstall the plugin with the given id.

        Return a deferred that will fire with None once the operation is
        completed.

        The deferred will fire its errback with an Exception if the plugin
        is not already installed.

        Affected devices are automatically deconfigured if needed.

        """
        logger.info('Uninstalling and unloading plugin %s', plugin_id)
        self.pg_mgr.uninstall(plugin_id)
        self._pg_unload(plugin_id)
        # soft deconfigure all the device that were configured by this device
        # note that there is no point in calling plugin.deconfigure for every
        # of these devices since the plugin is removed anyway
        affected_devices = yield self._dev_collection.find(
            {'plugin': plugin_id, 'configured': True}
        )
        for device in affected_devices:
            device['configured'] = False
            yield self._dev_collection.update(device)

    @_wlock
    @defer.inlineCallbacks
    def pg_reload(self, plugin_id):
        """Reload the plugin with the given id.

        If the plugin is not loaded yet, load it.

        Return a deferred that will fire with None once the operation is
        completed.

        The deferred will fire its errback with an exception if the plugin
        is not already installed or if there's an error at loading.

        """
        logger.info('Reloading plugin %s', plugin_id)
        if not self.pg_mgr.is_installed(plugin_id):
            logger.error('Can\'t reload plugin %s: not installed', plugin_id)
            raise Exception(f'plugin {plugin_id} is not installed')

        devices = yield self._dev_collection.find({'plugin': plugin_id})
        devices = list(devices)

        # unload plugin
        if plugin_id in self.pg_mgr:
            plugin = self.pg_mgr[plugin_id]
            for device in devices:
                if device['configured']:
                    self._dev_deconfigure(device, plugin)
            self._pg_unload(plugin_id)

        # load plugin
        try:
            self._pg_load(plugin_id)
        except Exception:
            # mark all the devices as not configured and reraise
            # the exception
            for device in devices:
                if device['configured']:
                    device['configured'] = False
                    yield self._dev_collection.update(device)
            raise

        # reconfigure every device
        for device in devices:
            configured = yield self._dev_configure_if_possible(device)
            if device['configured'] != configured:
                device['configured'] = configured
                yield self._dev_collection.update(device)

    def pg_retrieve(self, plugin_id):
        return self.pg_mgr[plugin_id]


def _check_is_server_url(value):
    if value is None:
        return

    try:
        parse_result = urlparse(value)
    except Exception as e:
        raise InvalidParameterError(e)

    if not parse_result.scheme:
        raise InvalidParameterError(f'no scheme: {value}')
    if not parse_result.hostname:
        raise InvalidParameterError(f'no hostname: {value}')


def _check_is_proxy(value):
    if value is None:
        return

    try:
        parse_result = urlparse(value)
    except Exception as e:
        raise InvalidParameterError(e)

    if not parse_result.scheme:
        raise InvalidParameterError(f'No scheme: {value}')
    if not parse_result.hostname:
        raise InvalidParameterError(f'No hostname: {value}')
    if parse_result.path:
        raise InvalidParameterError(f'Path: {value}')


def _check_is_https_proxy(value):
    if value is None:
        return

    if not value:
        raise InvalidParameterError('zero-length value')
    try:
        parse_result = urlparse(value)
    except Exception as e:
        raise InvalidParameterError(e)

    if parse_result.scheme and parse_result.hostname:
        raise InvalidParameterError(f'scheme and hostname: {value}')


class ApplicationConfigureService:
    VIRTUAL_ATTRIBUTES = {'provisioning_key': {'parent': 'tenants'}}

    def __init__(self, pg_mgr: PluginManager, proxies, app: ProvisioningApplication):
        self._pg_mgr = pg_mgr
        self._proxies = proxies
        self._app = app

    def _get_param_locale(self, *args, **kwargs):
        l10n_service = get_localization_service()
        if l10n_service is None:
            logger.info('No localization service registered')
            return None
        return l10n_service.get_locale()

    def _set_param_locale(self, value, *args, **kwargs):
        l10n_service = get_localization_service()
        if l10n_service is None:
            logger.info('No localization service registered')
        else:
            if not value:
                l10n_service.set_locale(None)
            else:
                try:
                    l10n_service.set_locale(value)
                except (UnicodeError, ValueError) as e:
                    raise InvalidParameterError(e)

    def _generic_set_proxy(self, key, value, *args, **kwargs):
        if not value:
            if key in self._proxies:
                del self._proxies[key]
        else:
            self._proxies[key] = value

    def _get_param_http_proxy(self, *args, **kwargs):
        return self._proxies.get('http')

    def _set_param_http_proxy(self, value, *args, **kwargs):
        _check_is_proxy(value)
        self._generic_set_proxy('http', value)

    def _get_param_ftp_proxy(self, *args, **kwargs):
        return self._proxies.get('ftp')

    def _set_param_ftp_proxy(self, value, *args, **kwargs):
        _check_is_proxy(value)
        self._generic_set_proxy('ftp', value)

    def _get_param_https_proxy(self, *args, **kwargs):
        return self._proxies.get('https')

    def _set_param_https_proxy(self, value, *args, **kwargs):
        _check_is_https_proxy(value)
        self._generic_set_proxy('https', value)

    def _get_param_plugin_server(self, *args, **kwargs):
        return self._pg_mgr.server

    def _set_param_plugin_server(self, value, *args, **kwargs):
        _check_is_server_url(value)
        self._pg_mgr.server = value

    def _get_param_NAT(self, *args, **kwargs):
        return self._app.nat

    def _set_param_NAT(self, value, *args, **kwargs):
        if value is None or value == '0':
            value = 0
        elif value == '1':
            value = 1
        else:
            raise InvalidParameterError(value)
        self._app.nat = value

    def _get_tenant_config(self, tenant_uuid):
        return self._app.tenants.get(tenant_uuid)

    def _create_empty_tenant_config(self, tenant_uuid):
        self._app.tenants[tenant_uuid] = {}
        return self._get_tenant_config(tenant_uuid)

    def _get_param_provisioning_key(self, tenant_uuid):
        tenant_config = self._get_tenant_config(tenant_uuid)
        if tenant_config is None:
            tenant_config = self._create_empty_tenant_config(tenant_uuid)
        return tenant_config.get('provisioning_key')

    def _set_param_provisioning_key(self, provisioning_key, tenant_uuid):
        if provisioning_key and (
            len(provisioning_key) < 8 or len(provisioning_key) > 256
        ):
            raise InvalidParameterError(
                '`provisioning_key` should be [8, 256] characters long.'
            )

        tenant_config = self._get_tenant_config(tenant_uuid)
        if tenant_config is None:
            tenant_config = self._create_empty_tenant_config(tenant_uuid)
        tenant_config['provisioning_key'] = provisioning_key

    def get_tenant_from_provisioning_key(self, provisioning_key):
        for tenant, config in self._app.tenants.items():
            if config.get('provisioning_key') == provisioning_key:
                return tenant

    def _set_param_tenants(self, tenants, *args, **kwargs):
        self._app.tenants = tenants

    def _get_param_tenants(self, *args, **kwargs):
        return self._app.tenants

    def get(self, name, *args, **kwargs):
        get_fun_name = f'_get_param_{name}'
        try:
            get_fun = getattr(self, get_fun_name)
        except AttributeError:
            raise KeyError(name)
        else:
            return get_fun(*args, **kwargs)

    def set(self, name, value, *args, **kwargs):
        set_fun_name = f'_set_param_{name}'
        try:
            set_fun = getattr(self, set_fun_name)
        except AttributeError:
            raise KeyError(name)
        else:
            set_fun(value, *args, **kwargs)

    description = [
        ('plugin_server', 'The plugins repository URL'),
        (
            'http_proxy',
            'The proxy for HTTP requests. Format is "http://[user:password@]host:port"',
        ),
        (
            'ftp_proxy',
            'The proxy for FTP requests. Format is "http://[user:password@]host:port"',
        ),
        ('https_proxy', 'The proxy for HTTPS requests. Format is "host:port"'),
        ('locale', 'The current locale. Example: fr_FR'),
        ('NAT', 'Set to 1 if all the devices are behind a NAT.'),
        ('provisioning_key', 'The provisioning key for the tenant. [min: 8, max: 256]'),
    ]

    description_fr = [
        ('plugin_server', "L'addresse (URL) du dépôt de plugins"),
        (
            'http_proxy',
            'Le proxy pour les requêtes HTTP. Le format est "http://[user:password@]host:port"',
        ),
        (
            'ftp_proxy',
            'Le proxy pour les requêtes FTP. Le format est "http://[user:password@]host:port"',
        ),
        ('https_proxy', 'Le proxy pour les requêtes HTTPS. Le format est "host:port"'),
        ('locale', 'La locale courante. Exemple: en_CA'),
        ('NAT', 'Mettre à 1 si toutes les terminaisons sont derrière un NAT.'),
        (
            'provisioning_key',
            'La clé de provisioning pour le tenant. [min: 8, max: 256]',
        ),
    ]
