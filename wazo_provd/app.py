# Copyright 2010-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import functools
import logging
import os.path
import re
import traceback
from collections import deque
from collections.abc import Callable, Generator
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Literal, Union, cast
from urllib.parse import urlparse
from uuid import UUID, uuid4

from pydantic import ValidationError
from twisted.internet import defer
from twisted.internet.defer import Deferred
from xivo.chain_map import ChainMap

from wazo_provd.database.exceptions import EntryNotFoundException
from wazo_provd.database.models import (
    Device,
    DeviceConfig,
    DeviceRawConfig,
    ServiceConfiguration,
)
from wazo_provd.database.models import Tenant as TenantModel
from wazo_provd.devices.config import (
    RawConfigError,
    build_autocreate_config,
    check_config_validity,
    config_types_fixes,
)
from wazo_provd.devices.device import check_device_validity, needs_reconfiguration
from wazo_provd.localization import get_localization_service
from wazo_provd.operation import (
    OIP_FAIL,
    OIP_PROGRESS,
    OIP_SUCCESS,
    OperationInProgress,
)
from wazo_provd.persist.common import ID_KEY
from wazo_provd.persist.common import InvalidIdError as PersistInvalidIdError
from wazo_provd.persist.id import get_id_generator_factory
from wazo_provd.plugins import PluginManager, PluginNotLoadedError
from wazo_provd.rest.server import auth
from wazo_provd.rest.server.helpers.tenants import Tenant, tenant_helpers
from wazo_provd.services import InvalidParameterError
from wazo_provd.synchro import DeferredRWLock
from wazo_provd.util import decode_bytes

from .devices.schemas import (
    BaseDeviceDict,
    ConfigDict,
    ConfigSchema,
    DeviceDict,
    DeviceSchema,
    RawConfigDict,
    RawConfigSchema,
)

if TYPE_CHECKING:
    from typing import Concatenate, ParamSpec, TypeVar

    from twisted.python import failure

    from wazo_provd.database.queries import (
        DeviceConfigDAO,
        DeviceDAO,
        DeviceRawConfigDAO,
        FunctionKeyDAO,
        SCCPLineDAO,
        ServiceConfigurationDAO,
        SIPLineDAO,
        TenantDAO,
    )

    from .config import ProvdConfigDict
    from .plugins import Plugin

    P = ParamSpec('P')
    R = TypeVar('R')


logger = logging.getLogger(__name__)


class InvalidIdError(Exception):
    """Raised when a passed ID is invalid, not necessary because of its type,
    but because of its semantic.

    """

    pass


class DeviceNotInProvdTenantError(Exception):
    def __init__(self, tenant_uuid: str) -> None:
        super().__init__('Device not in provd tenant')
        self.tenant_uuid = tenant_uuid


class TenantInvalidForDeviceError(Exception):
    def __init__(self, tenant_uuid: str) -> None:
        super().__init__('Tenant invalid for device')
        self.tenant_uuid = tenant_uuid


class NonDeletableError(Exception):
    """Raised when a document is non deletable"""

    pass


def _rlock_arg(
    rw_lock: DeferredRWLock,
) -> Callable[[Callable[P, R]], Callable[P, Deferred]]:
    def decorator(fun: Callable[P, R]) -> Callable[P, Deferred]:
        @functools.wraps(fun)
        def aux(*args: P.args, **kwargs: P.kwargs) -> Deferred:
            d = rw_lock.read_lock.run(fun, *args, **kwargs)
            return d

        return aux

    return decorator


def _wlock_arg(
    rw_lock: DeferredRWLock,
) -> Callable[[Callable[P, R]], Callable[P, Deferred]]:
    def decorator(fun: Callable[P, R]) -> Callable[P, Deferred]:
        @functools.wraps(fun)
        def aux(*args: P.args, **kwargs: P.kwargs) -> Deferred:
            d = rw_lock.write_lock.run(fun, *args, **kwargs)
            return d

        return aux

    return decorator


def _rlock(
    fun: Callable[Concatenate[ProvisioningApplication, P], R]
) -> Callable[Concatenate[ProvisioningApplication, P], Deferred]:
    # Decorator for instance method of ProvisioningApplication that need to
    # acquire the read lock
    @functools.wraps(fun)
    def aux(
        self: ProvisioningApplication, *args: P.args, **kwargs: P.kwargs
    ) -> Deferred:
        d = self._rw_lock.read_lock.run(fun, self, *args, **kwargs)
        return d

    return aux


def _wlock(
    fun: Callable[Concatenate[ProvisioningApplication, P], R]
) -> Callable[Concatenate[ProvisioningApplication, P], Deferred]:
    # Decorator for instance method of ProvisioningApplication that need to
    # acquire the write lock
    @functools.wraps(fun)
    def aux(
        self: ProvisioningApplication, *args: P.args, **kwargs: P.kwargs
    ) -> Deferred:
        d = self._rw_lock.write_lock.run(fun, self, *args, **kwargs)
        return d

    return aux


def _check_common_raw_config_validity(raw_config: dict[str, Any]) -> None:
    for param in ['ip', 'http_port', 'tftp_port']:
        if param not in raw_config:
            raise RawConfigError(f'missing {param} parameter')


def _check_raw_config_validity(raw_config: RawConfigDict) -> RawConfigDict:
    try:
        return RawConfigSchema.validate(raw_config)
    except ValidationError as e:
        # Try to resemble as close as possible to the old method. Do we really want this?
        error = e.errors()[0]
        field = '.'.join(error['loc'])
        raise RawConfigError(f'{field}: {error["msg"]}')


def _set_defaults_raw_config(raw_config: RawConfigDict) -> None:
    if raw_config.get('syslog_enabled'):
        raw_config.setdefault('syslog_port', 514)
        raw_config.setdefault('syslog_level', 'warning')  # type: ignore[typeddict-item]
    if 'sip_proxy_ip' in raw_config:
        raw_config.setdefault('sip_registrar_ip', raw_config['sip_proxy_ip'])
    raw_config.setdefault('sip_srtp_mode', 'disabled')  # type: ignore[typeddict-item]
    raw_config.setdefault('sip_transport', 'udp')  # type: ignore[typeddict-item]
    if 'sip_lines' not in raw_config or raw_config['sip_lines'] is None:
        raw_config['sip_lines'] = {}
    else:
        for line in raw_config['sip_lines'].values():
            if 'proxy_ip' in line:
                line.setdefault('registrar_ip', line['proxy_ip'])
            if 'username' in line:
                line.setdefault('auth_username', line['username'])
    raw_config.setdefault('sccp_call_managers', {})
    raw_config.setdefault('funckeys', {})  # type: ignore[typeddict-item]


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
        device_dao: DeviceDAO,
        device_config_dao: DeviceConfigDAO,
        device_raw_config_dao: DeviceRawConfigDAO,
        function_key_dao: FunctionKeyDAO,
        sccp_line_dao: SCCPLineDAO,
        sip_line_dao: SIPLineDAO,
        tenant_dao: TenantDAO,
        configuration_dao: ServiceConfigurationDAO,
        config: ProvdConfigDict,
    ) -> None:
        self._split_config: ProvdConfigDict = config
        self._token: str | None = None
        self._tenant_uuid: str | None = None

        self.device_dao = device_dao
        self.device_config_dao = device_config_dao
        self.device_raw_config_dao = device_raw_config_dao
        self.function_key_dao = function_key_dao
        self.sccp_line_dao = sccp_line_dao
        self.sip_line_dao = sip_line_dao
        self.tenant_dao = tenant_dao
        self.configuration_dao = configuration_dao

        base_storage_dir = config['general']['base_storage_dir']
        plugins_dir = os.path.join(base_storage_dir, 'plugins')

        self.proxies: dict[str, str] = {}
        self.nat: int = 0
        self.tenants: dict[str, dict] = {}
        self.reload_tenants()

        self.http_auth_strategy: Union[Literal['url_key'], None] = self._split_config[
            'general'
        ].get('http_auth_strategy')
        self.use_provisioning_key: bool = self.http_auth_strategy == 'url_key'

        self.pg_mgr = PluginManager(
            self,
            plugins_dir,
            config['general']['cache_dir'],
            config['general']['cache_plugin'],
            config['general']['check_compat_min'],
            config['general']['check_compat_max'],
        )

        self.create_or_load_service_configuration()

        # Do not move this line up unless you know what you are doing...
        self.configure_service = ApplicationConfigureService(
            self.pg_mgr, self.proxies, self
        )

        self._base_raw_config = config['general']['base_raw_config']
        logger.info('Using base raw config %s', self._base_raw_config)
        _check_common_raw_config_validity(self._base_raw_config)
        self._rw_lock = DeferredRWLock()
        self._pg_load_all(True)

    @_wlock
    def close(self) -> None:
        logger.info('Closing provisioning application...')
        self.pg_mgr.close()
        logger.info('Provisioning application closed')

    def token(self) -> str | None:
        return self._token

    def set_token(self, token_id: str) -> None:
        logger.debug('Setting token for provd app: %s', token_id)
        self._token = token_id
        auth_client = auth.get_auth_client()
        token = tenant_helpers.Token(self._token, auth_client)
        self.set_tenant_uuid(Tenant.from_token(token).uuid)

    def tenant_uuid(self) -> str | None:
        return self._tenant_uuid

    def set_tenant_uuid(self, tenant_uuid: str) -> None:
        self._tenant_uuid = tenant_uuid
        if not self.tenants.get(tenant_uuid):
            self.set_tenant_configuration(tenant_uuid, {})

    def set_tenant_configuration(
        self, tenant_uuid: str, config: dict[str, Any]
    ) -> None:
        self.tenants[tenant_uuid] = config

    def reload_tenants(self) -> None:
        load_tenant_d = defer.ensureDeferred(self.tenant_dao.find_all())
        load_tenant_d.addCallback(self._load_tenants)
        load_tenant_d.addErrback(self._handle_error)

    def _load_tenants(self, tenants: list[TenantModel]) -> None:
        logger.debug('Loading tenants: %s', tenants)
        for tenant in tenants:
            tenant_conf = tenant.as_dict()
            del tenant_conf[tenant._meta['primary_key']]
            self.set_tenant_configuration(str(tenant.uuid), tenant_conf)

    def _handle_error(self, fail: failure.Failure) -> failure.Failure:
        tb = fail.getTracebackObject()
        exc_formatted = ''.join(traceback.format_exception(None, fail.value, tb))
        logger.error('Error in Deferred:\n%s', exc_formatted)
        return fail

    def create_or_load_service_configuration(self) -> None:
        reload_conf_d = defer.ensureDeferred(self.configuration_dao.find_one())
        reload_conf_d.addErrback(self._add_service_configuration_if_missing)
        reload_conf_d.addCallbacks(self._load_service_configuration, self._handle_error)
        reload_conf_d.addErrback(self._handle_error)

    def _add_service_configuration_if_missing(self, fail: failure.Failure) -> Deferred:
        fail.trap(EntryNotFoundException)
        service_configuration = ServiceConfiguration(
            uuid=uuid4(),
            plugin_server='http://provd.wazo.community/plugins/2/stable/',
            http_proxy=None,
            https_proxy=None,
            ftp_proxy=None,
            locale=None,
            nat_enabled=False,
        )
        return defer.ensureDeferred(
            self.configuration_dao.create(service_configuration)
        )

    def _load_service_configuration(self, service_config: ServiceConfiguration) -> None:
        logger.debug('Loading service configuration from database: %s', service_config)
        self.nat = 1 if service_config.nat_enabled else 0
        if service_config.plugin_server:
            self.pg_mgr.server = service_config.plugin_server
        if service_config.http_proxy:
            self.proxies['http'] = service_config.http_proxy
        if service_config.https_proxy:
            self.proxies['https'] = service_config.https_proxy
        if service_config.ftp_proxy:
            self.proxies['ftp'] = service_config.ftp_proxy

    # device methods

    def _dev_get_plugin(self, device: BaseDeviceDict | DeviceDict) -> dict | None:
        logger.debug('AFDEBUG: in _dev_get_plugin')
        if 'plugin' in device:
            logger.debug(
                'AFDEBUG Trying to get plugin from device: %s', device['plugin']
            )
            return self.pg_mgr.get(device['plugin'])
        logger.debug('AFDEBUG no plugin in device, exiting _dev_get_plugin')
        return None

    def _cfg_raw_create_dict_from_model(
        self, raw_conf_model: DeviceRawConfig
    ) -> RawConfigDict:
        raw_conf_dict = raw_conf_model.as_dict(ignore_foreign_keys=True)
        return cast(RawConfigDict, raw_conf_dict)

    @defer.inlineCallbacks
    def _get_flat_raw_config(self, config_id: str):
        config_deferreds = []
        parent_configs = yield defer.ensureDeferred(
            self.device_config_dao.get_parents(config_id)
        )
        for parent_config in parent_configs:
            config_deferreds.append(self.cfg_retrieve_raw_config(parent_config.id))

        raw_configs = yield defer.gatherResults(config_deferreds, consumeErrors=True)
        raw_config_parents: deque[RawConfigDict] = deque()
        for raw_config in raw_configs:
            raw_config_parents.appendleft(raw_config)

        flat_raw_config: RawConfigDict = cast(
            RawConfigDict, ChainMap(*raw_config_parents)
        )
        return flat_raw_config

    def _dev_create_model_from_dict(self, device: DeviceDict) -> Device:
        auto_added = device.get('added') == "auto"
        return Device(
            id=device['id'],  # type: ignore[arg-type]
            tenant_uuid=UUID(device['tenant_uuid']),
            config_id=device.get('config', None),
            mac=device.get('mac', None),
            ip=str(device.get('ip', '')),
            vendor=device.get('vendor', None),
            model=device.get('model', None),
            version=device.get('version', None),
            plugin=device.get('plugin', None),
            configured=device.get('configured', None),
            auto_added=auto_added,
            is_new=device.get('is_new', None),
        )

    def _dev_create_dict_from_model(self, device_model: Device) -> DeviceDict:
        try:
            device_schema = DeviceSchema(**device_model.as_dict())
            return device_schema.dict()
        except Exception as e:
            logger.error(
                'Could not load device %s: %s',
                device_model.id,
                e,
                exc_info=e,
                stack_info=True,
            )
            raise

    @defer.inlineCallbacks
    def _dev_get_raw_config(self, device: BaseDeviceDict | DeviceDict) -> Deferred:
        # Return a deferred that will fire with a raw config associated
        # with the device, or fire with None if there's no such raw config
        if device.get('config'):
            cfg_id = device['config']
            flat_config = yield self._get_flat_raw_config(cfg_id)
            logger.debug('Got flat raw config: %s', flat_config)
            defer.returnValue(flat_config)
        logger.debug('config key not in device, device = %s', device)
        defer.returnValue(None)

    @defer.inlineCallbacks
    def _dev_get_plugin_and_raw_config(self, device):
        # Return a deferred that will fire with a tuple (plugin, raw_config)
        # associated with the device, or fire with the tuple (None, None) if
        # there's at least one without etc. etc
        logger.debug('AFDEBUG in dev_get_plugin_and_raw_config')
        plugin = self._dev_get_plugin(device)
        logger.debug(
            'AFDEBUG _dev_get_plugin_and_raw_config: device = %s, plugin = %s',
            device,
            plugin,
        )
        if plugin:
            logger.debug('AFDEBUG if 1 start')
            raw_config = yield self._dev_get_raw_config(device)
            logger.debug('AFDEBUG if 1 end')
            if raw_config is not None:
                logger.debug('AFDEBUG if 2 start')
                defer.returnValue((plugin, raw_config))
                logger.debug('AFDEBUG if 2 end')
        logger.debug('AFDEBUG no if')
        defer.returnValue((None, None))

    @defer.inlineCallbacks
    def _dev_configure(
        self,
        device: BaseDeviceDict | DeviceDict,
        plugin: Plugin,
        raw_config: RawConfigDict,
    ):
        # Return true if the device has been successfully configured (i.e.
        # no exception were raised), else false.
        device_id = device[ID_KEY]
        logger.info('Configuring device %s with plugin %s', device_id, plugin.id)
        if self.use_provisioning_key:
            tenant_uuid = device.get('tenant_uuid', None)
            if not tenant_uuid:
                logger.warning(
                    'Device %s is using provisioning key but has no tenant_uuid',
                    device_id,
                )
                defer.returnValue(False)
            provisioning_key = yield self.configure_service.get(
                'provisioning_key', tenant_uuid
            )

            raw_config = deepcopy(raw_config)
            http_base_url = raw_config['http_base_url']
            raw_config['http_base_url'] = f'{http_base_url}/{provisioning_key}'

        _set_defaults_raw_config(raw_config)
        try:
            RawConfigSchema.validate(raw_config)
        except ValidationError as e:
            logger.error(
                'Error while configuring device %s. '
                'There were errors with some values: %s',
                device_id,
                e.errors(),
            )
        except Exception:
            # Do we really want to catch **any** exception?
            logger.error('Error while configuring device %s', device_id, exc_info=True)
        else:
            try:
                plugin.configure(device, raw_config)
            except Exception:
                logger.error(
                    'Error while configuring device %s', device_id, exc_info=True
                )
            else:
                defer.returnValue(True)
        defer.returnValue(False)

    @defer.inlineCallbacks
    def _dev_configure_if_possible(self, device: BaseDeviceDict | DeviceDict):
        # Return a deferred that fire with true if the device has been
        # successfully configured (i.e. no exception were raised), else false.
        logger.debug('AFDEBUG entering _dev_configure_if_possible')
        plugin, raw_config = yield self._dev_get_plugin_and_raw_config(device)
        if plugin is None:
            logger.debug('AFDEBUG _dev_configure_if_possible: `plugin` is None')
            defer.returnValue(False)
        else:
            logger.debug('AFDEBUG _dev_configure_if_possible before dev_configure')
            configured = yield self._dev_configure(device, plugin, raw_config)
            logger.debug(
                'AFDEBUG _dev_configure_if_possible Newly configured device has configured value of %s',
                configured,
            )
            defer.returnValue(configured)
        logger.debug('AFDEBUG exiting _dev_configure_if_possible')

    def _dev_deconfigure(self, device: BaseDeviceDict | DeviceDict, plugin):
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

    def _dev_deconfigure_if_possible(self, device: BaseDeviceDict | DeviceDict):
        # Return true if the device has been successfully configured (i.e.
        # no exception were raised), else false.
        if (plugin := self._dev_get_plugin(device)) is None:
            return False
        return self._dev_deconfigure(device, plugin)

    def _dev_synchronize(
        self, device: BaseDeviceDict | DeviceDict, plugin, raw_config: RawConfigDict
    ):
        # Return a deferred that will fire with None once the device
        # synchronization is completed.
        logger.info('Synchronizing device %s with plugin %s', device[ID_KEY], plugin.id)
        _set_defaults_raw_config(raw_config)
        return plugin.synchronize(device, raw_config)

    @defer.inlineCallbacks
    def _dev_synchronize_if_possible(self, device: BaseDeviceDict | DeviceDict):
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
    def _dev_get_or_raise(self, device_id: str):
        try:
            device = yield defer.ensureDeferred(self.device_dao.get(device_id))
        except EntryNotFoundException:
            raise InvalidIdError(f'invalid device ID "{device_id}"')
        logger.debug('Trying to get device %s as dict', device)
        device_dict = self._dev_create_dict_from_model(device)
        logger.debug('Device dict = %s', device_dict)
        defer.returnValue(device_dict)

    @_wlock
    @defer.inlineCallbacks
    def dev_insert(self, device: DeviceDict):
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
                device['tenant_uuid'] = self._tenant_uuid  # type: ignore

            device['is_new'] = device['tenant_uuid'] == self._tenant_uuid
            yield defer.ensureDeferred(
                self.tenant_dao.get_or_create(UUID(device['tenant_uuid']))
            )
            if not device.get('id'):
                device['id'] = next(get_id_generator_factory('default')())

            try:
                logger.critical('AFDEBUG pre-insert')
                check_device_validity(device)
                device_model = self._dev_create_model_from_dict(device)
                added_device = yield defer.ensureDeferred(
                    self.device_dao.create(device_model)
                )
                device_id = added_device.id
                logger.critical('AFDEBUG created device with id: %s', device_id)
            except PersistInvalidIdError as e:
                raise InvalidIdError(e)
            else:
                configured = yield self._dev_configure_if_possible(device)
                device['configured'] = configured
                if configured:
                    logging.debug('AFDEBUG Device %s configured', device['id'])
                    device_model = self._dev_create_model_from_dict(device)
                    yield defer.ensureDeferred(self.device_dao.update(device_model))
                else:
                    logging.debug('Could not configure device %s', device['id'])
                defer.returnValue(device_id)
        except Exception:
            logger.error('Error while inserting device', exc_info=True)
            raise

    @_wlock
    @defer.inlineCallbacks
    def dev_update(self, device: DeviceDict, pre_update_hook=None):
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
                check_device_validity(device)
                old_device = yield self._dev_get_or_raise(device_id)
                if needs_reconfiguration(old_device, device):
                    # Deconfigure old device it was configured
                    if old_device['configured']:
                        self._dev_deconfigure_if_possible(old_device)
                    # Configure new device if possible
                    configured = yield self._dev_configure_if_possible(device)
                    device['configured'] = configured
                    if configured:
                        device_model = self._dev_create_model_from_dict(device)
                        yield defer.ensureDeferred(self.device_dao.update(device_model))
                else:
                    device['configured'] = old_device['configured']
                if pre_update_hook is not None:
                    config_model = yield self.device_config_dao.get(
                        device.get('config')
                    )
                    config = config_model.as_dict()
                    pre_update_hook(device, config)
                # Update device collection if the device is different from
                # the old device
                if device != old_device:
                    device['is_new'] = device['tenant_uuid'] == self._tenant_uuid
                    yield defer.ensureDeferred(
                        self.tenant_dao.get_or_create(UUID(device['tenant_uuid']))
                    )
                    device_model = self._dev_create_model_from_dict(device)
                    yield defer.ensureDeferred(self.device_dao.update(device_model))
                    # check if old device was using a transient config that is
                    # no more in use
                    if old_device.get('config') != device.get('config'):
                        old_device_cfg_id = old_device['config']
                        try:
                            old_device_cfg_model = yield defer.ensureDeferred(
                                self.device_config_dao.get(old_device_cfg_id)
                            )
                            old_device_cfg = old_device_cfg_model.as_dict()
                        except EntryNotFoundException:
                            old_device_cfg = None
                        if old_device_cfg and old_device_cfg.get('transient'):
                            # if no devices are using this transient config, delete it
                            try:
                                yield defer.ensureDeferred(
                                    self.device_dao.find_one_from_config(
                                        old_device_cfg_id
                                    )
                                )
                            except EntryNotFoundException:
                                yield defer.ensureDeferred(
                                    self.device_config_dao.delete(old_device_cfg_id)
                                )
                else:
                    logger.info('Not updating device %s: not changed', device_id)
        except Exception:
            logger.error('Error while updating device', exc_info=True)
            raise

    @_wlock
    @defer.inlineCallbacks
    def dev_delete(self, device_id: str):
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
            device_model = self._dev_create_model_from_dict(device)
            # Next line should never raise an exception since we successfully
            # retrieve the device with the same id just before and we are
            # using the write lock
            yield defer.ensureDeferred(self.device_dao.delete(device_model))
            # check if device was using a transient config that is no more in use
            if device.get('config'):
                device_cfg_id = device['config']
                device_cfg_model = yield defer.ensureDeferred(
                    self.device_config_dao.get(device_cfg_id)
                )
                device_cfg = self._cfg_create_dict_from_model(device_cfg_model)
                if device_cfg and device_cfg.get('transient'):
                    # if no devices are using this transient config, delete it
                    try:
                        yield defer.ensureDeferred(
                            self.device_dao.find_one_from_config(device_cfg_id)
                        )
                    except EntryNotFoundException:
                        yield defer.ensureDeferred(
                            self.device_config_dao.delete(device_cfg_id)
                        )
            if device['configured']:
                self._dev_deconfigure_if_possible(device)
        except Exception:
            logger.error('Error while deleting device', exc_info=True)
            raise

    def dev_find(self, selector, *args, **kwargs) -> Deferred:
        results_deferred = defer.ensureDeferred(
            self.device_dao.find(selector, *args, **kwargs)
        )

        def convert_to_dict(results):
            dict_results = []
            for result in results:
                dict_results.append(self._dev_create_dict_from_model(result))
            return defer.succeed(dict_results)

        results_deferred.addCallback(convert_to_dict)
        results_deferred.addErrback(self._handle_error)
        return results_deferred

    def dev_find_one(self, selector, *args, **kwargs):
        results_deferred = defer.ensureDeferred(
            self.device_dao.find(selector, *args, **kwargs)
        )

        def convert_to_dict(results):
            for result in results:
                return defer.succeed(self._dev_create_dict_from_model(result))

        results_deferred.addCallback(convert_to_dict)
        results_deferred.addErrback(self._handle_error)
        return results_deferred

    def dev_get(
        self, device_id: str, tenant_uuids: list[str] | None = None
    ) -> Deferred:
        tenant_uuid_converted = (
            [UUID(str(tenant_uuid)) for tenant_uuid in tenant_uuids]
            if tenant_uuids
            else None
        )
        result_deferred = defer.ensureDeferred(
            self.device_dao.get(device_id, tenant_uuids=tenant_uuid_converted)
        )

        def convert_to_dict(result):
            return defer.succeed(self._dev_create_dict_from_model(result))

        result_deferred.addCallback(convert_to_dict)
        result_deferred.addErrback(self._handle_error)
        return result_deferred

    @_wlock
    @defer.inlineCallbacks
    def dev_reconfigure(self, device_id: str):
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
                device['configured'] = False
                device_model = self._dev_create_model_from_dict(device)
                yield defer.ensureDeferred(self.device_dao.update(device_model))

            configured = yield self._dev_configure_if_possible(device)
            if device['configured'] != configured:
                device['configured'] = configured
                device_model = self._dev_create_model_from_dict(device)
                yield defer.ensureDeferred(self.device_dao.update(device_model))
            defer.returnValue(configured)
        except Exception:
            logger.error('Error while reconfiguring device', exc_info=True)
            raise

    @_rlock
    @defer.inlineCallbacks
    def dev_synchronize(self, device_id: str):
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
    def _cfg_get_or_raise(self, config_id: str):
        try:
            config_model = yield defer.ensureDeferred(
                self.device_config_dao.get(config_id)
            )
        except EntryNotFoundException:
            raise InvalidIdError(f'Invalid config ID "{config_id}"')
        logger.debug('Config model is: %s', config_model)
        defer.returnValue(self._cfg_create_dict_from_model(config_model))

    def _cfg_create_dict_from_model(self, config_model: DeviceConfig) -> ConfigDict:
        try:
            config_schema = ConfigSchema.validate(config_model.as_dict())
            return config_schema.dict()
        except ValidationError as e:
            logger.error('Could not load config %s: %s', config_model.id, e, exc_info=e)
            raise

    @_wlock
    @defer.inlineCallbacks
    def cfg_insert(self, config: ConfigDict):
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
                config_dict = check_config_validity(config)
                config_dict = config_types_fixes(config_dict)
                config_model = DeviceConfig.from_dict(config_dict)
                new_config = yield defer.ensureDeferred(
                    self.device_config_dao.create(config_model)
                )
                config_id = new_config.id
            except (
                PersistInvalidIdError
            ) as e:  # NOTE(afournier): this is never raised by the DAO
                raise InvalidIdError(e)
            else:
                # configure each device that depend on the newly inserted config
                # 1. get the set of affected configs
                affected_cfg_models = yield defer.ensureDeferred(
                    self.device_config_dao.get_descendants(config_id)
                )
                affected_cfg_ids = {cfg_model.id for cfg_model in affected_cfg_models}
                affected_cfg_ids.add(config_id)
                # 2. get the raw_config of every affected config
                raw_configs = {}
                for affected_cfg_id in affected_cfg_ids:
                    raw_config = self.cfg_retrieve_raw_config(affected_cfg_id)
                    raw_configs[affected_cfg_id] = raw_config

                # 3. reconfigure/deconfigure each affected devices
                affected_devices = yield defer.ensureDeferred(
                    self.device_dao.find_from_configs(list(affected_cfg_ids))
                )
                for device_model in affected_devices:
                    device = self._dev_create_dict_from_model(device_model)
                    plugin = self._dev_get_plugin(device)
                    if plugin is not None:
                        raw_config = raw_configs[device['config']]
                        logger.debug('1 raw_config is %s', raw_config)
                        assert raw_config is not None
                        # deconfigure
                        if device['configured']:
                            self._dev_deconfigure(device, plugin)
                        # configure
                        configured = yield self._dev_configure(
                            device, plugin, raw_config
                        )
                        # update device if it has changed
                        if device['configured'] != configured:
                            device['configured'] = configured
                            device_model = Device(**device)
                            yield defer.ensureDeferred(
                                self.device_dao.update(device_model)
                            )
                # 4. return the device id
                defer.returnValue(config_id)
        except Exception:
            logger.error('Error while inserting config', exc_info=True)
            raise

    @_wlock
    @defer.inlineCallbacks
    def cfg_update(self, config: ConfigDict):
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
            logger.debug('Complete config is: %s', config)
            old_config = yield self._cfg_get_or_raise(config_id)
            if old_config == config:
                logger.info('config has not changed, ignoring update')
            else:
                config_dict = check_config_validity(config)
                config_dict = config_types_fixes(config_dict)
                config_model = DeviceConfig.from_dict(config_dict)
                yield defer.ensureDeferred(self.device_config_dao.update(config_model))

                affected_cfg_models = yield defer.ensureDeferred(
                    self.device_config_dao.get_descendants(config_id)
                )
                affected_cfg_ids = {cfg_model.id for cfg_model in affected_cfg_models}
                affected_cfg_ids.add(config_id)
                # 2. get the raw_config of every affected config
                raw_configs = {}
                for affected_cfg_id in affected_cfg_ids:
                    raw_config = self.cfg_retrieve_raw_config(affected_cfg_id)

                    raw_configs[affected_cfg_id] = raw_config

                # 3. reconfigure each device having a direct dependency on
                #    one of the affected cfg id
                affected_devices = yield defer.ensureDeferred(
                    self.device_dao.find_from_configs(list(affected_cfg_ids))
                )
                for device_model in affected_devices:
                    device = self._dev_create_dict_from_model(device_model)
                    plugin = self._dev_get_plugin(device)
                    if plugin is not None:
                        raw_config = raw_configs[device['config']]
                        logger.debug('2 raw_config is %s', raw_config)
                        assert raw_config is not None
                        # deconfigure
                        if device['configured']:
                            self._dev_deconfigure(device, plugin)
                        # configure
                        configured = yield self._dev_configure(
                            device, plugin, raw_config
                        )
                        # update device if it has changed
                        if device['configured'] != configured:
                            device['configured'] = configured
                            device_model = Device(**device)
                            yield defer.ensureDeferred(
                                self.device_dao.update(device_model)
                            )
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
                device_config_model = yield defer.ensureDeferred(
                    self.device_config_dao.get(config_id)
                )
            except EntryNotFoundException as e:
                raise InvalidIdError(e)

            if not device_config_model.deletable:
                raise NonDeletableError(device_config_model)

            yield defer.ensureDeferred(
                self.device_config_dao.delete(device_config_model)
            )

            # 1. get the set of affected configs
            affected_cfg_models = yield defer.ensureDeferred(
                self.device_config_dao.get_descendants(config_id)
            )
            affected_cfg_ids = {cfg_model.id for cfg_model in affected_cfg_models}
            affected_cfg_ids.add(config_id)

            # 2. get the raw_config of every affected config
            raw_configs = {}
            for affected_cfg_id in affected_cfg_ids:
                raw_config = self.cfg_retrieve_raw_config(affected_cfg_id)
                raw_configs[affected_cfg_id] = raw_config

            # 3. reconfigure/deconfigure each affected devices
            affected_devices = yield defer.ensureDeferred(
                self.device_dao.find_from_configs(list(affected_cfg_ids))
            )

            for device_model in affected_devices:
                device = self._dev_create_dict_from_model(device_model)
                plugin = self._dev_get_plugin(device)
                if plugin is not None:
                    raw_config = raw_configs[device['config']]
                    logger.debug('3 raw_config is %s', raw_config)
                    # deconfigure
                    if device['configured']:
                        self._dev_deconfigure(device, plugin)
                    # configure if device config is not the deleted config
                    if device['config'] == config_id:
                        assert raw_config is None
                        # update device if it has changed
                        if device['configured']:
                            device['configured'] = False
                            device_model = self._dev_create_model_from_dict(device)
                            yield defer.ensureDeferred(
                                self.device_dao.update(device_model)
                            )
                    else:
                        assert raw_config is not None
                        configured = yield self._dev_configure(
                            device, plugin, raw_config
                        )
                        # update device if it has changed
                        if device['configured'] != configured:
                            device_model = self._dev_create_model_from_dict(device)
                            yield defer.ensureDeferred(
                                self.device_dao.update(device_model)
                            )
        except Exception:
            logger.error('Error while deleting config', exc_info=True)
            raise

    @defer.inlineCallbacks
    def cfg_retrieve(self, config_id):
        """Return a deferred that fire with the config with the given ID, or
        fire with None if there's no such document.

        """
        try:
            logger.debug('Trying to retrieve config %s', config_id)
            config_model = yield defer.ensureDeferred(
                self.device_config_dao.get(config_id)
            )
            output_config = self._cfg_create_dict_from_model(config_model)
            defer.returnValue(output_config)
        except EntryNotFoundException:
            raise
        except Exception as e:
            logger.error('Unexpected exception', exc_info=e, stack_info=True)
            raise

    @defer.inlineCallbacks
    def cfg_retrieve_raw_config(self, config_id):
        try:
            raw_config_model = yield defer.ensureDeferred(
                self.device_raw_config_dao.get(config_id)
            )
            raw_config_schema = RawConfigSchema.validate(raw_config_model.as_dict())
            defer.returnValue(raw_config_schema.dict())
        except EntryNotFoundException:
            raise
        except Exception as e:
            logger.error('Unexpected exception', exc_info=e, stack_info=True)
            raise

    @_rlock
    @defer.inlineCallbacks
    def cfg_find(self, selector, *args, **kwargs):
        config_models = yield defer.ensureDeferred(
            self.device_config_dao.find(selector, *args, **kwargs)
        )
        configs_output = []
        for config_model in config_models:
            config = self._cfg_create_dict_from_model(config_model)
            configs_output.append(config)

        defer.returnValue(configs_output)

    def cfg_find_one(self, selector, *args, **kwargs):
        return defer.ensureDeferred(
            self.device_config_dao.find_one(selector, *args, **kwargs)
        )

    @_wlock
    @defer.inlineCallbacks
    def cfg_create_new(
        self,
    ) -> Generator[None, DeviceConfig | DeviceRawConfig | None, None]:
        """Create a new config from the config with the autocreate role.

        Return a deferred that will fire with the ID of the newly created
        config, or fire with None if there's no config with the autocreate
        role or if the config factory returned None.

        """
        logger.info('Creating new config')
        try:
            new_config = None
            config_result = yield defer.ensureDeferred(
                self.device_config_dao.find_one({'role': 'autocreate'})
            )
            if not config_result:
                logger.warning('No config with the autocreate role found')
                defer.returnValue(None)

            config = cast(ConfigDict, config_result.as_dict())

            # remove the role of the config, so we don't create new config
            # with the autocreate role
            del config['role']
            # remove factory and validation as it is automatically created
            if new_config := build_autocreate_config(config):
                cast_new_config = cast(dict, new_config)
                new_config_model = DeviceConfig.from_dict(cast_new_config)
                new_config = yield defer.ensureDeferred(
                    self.device_config_dao.create(new_config_model)
                )
                logger.debug('Autocreated config: %s', new_config)
            else:
                logger.debug('Autocreate config factory returned null config')
            defer.returnValue(new_config.id)
        except Exception:
            logger.error('Error while autocreating config', exc_info=True)
            raise

    # plugin methods

    def _pg_load_all(self, catch_error: bool = False) -> None:
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

    def _pg_configure_pg(self, plugin_id: str) -> None:
        logger.debug('AFDEBUG entering _pg_configure_pg with plugin_id: %s', plugin_id)
        # Raise an exception if configure_common fail
        plugin = self.pg_mgr[plugin_id]
        common_config = deepcopy(self._base_raw_config)
        logger.info('Configuring plugin %s with config %s', plugin_id, common_config)
        try:
            plugin.configure_common(common_config)
        except Exception:
            logger.error('Error while configuring plugin %s', plugin_id, exc_info=True)
            raise
        logger.debug('AFDEBUG exiting _pg_configure_pg with plugin_id: %s', plugin_id)

    def _pg_load(self, plugin_id: str) -> None:
        logger.debug('AFDEBUG entering _pg_load with plugin_id: %s', plugin_id)
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
        logger.debug('AFDEBUG exiting _pg_load with plugin_id: %s', plugin_id)

    def _pg_unload(self, plugin_id: str) -> None:
        # This method should never raise an exception
        try:
            self.pg_mgr.unload(plugin_id)
        except PluginNotLoadedError:
            # this is the case were an incompatible/bogus plugin has been
            # installed successfully but the plugin was not loadable
            logger.info('Plugin %s was not loaded ', plugin_id)

    @defer.inlineCallbacks
    def _pg_configure_all_devices(self, plugin_id: str):
        logger.info('Reconfiguring all devices using plugin %s', plugin_id)
        devices = yield defer.ensureDeferred(
            self.device_dao.find({'plugin': plugin_id})
        )
        for device_model in devices:
            device_dict = self._dev_create_dict_from_model(device_model)
            logger.debug('AFDEBUG In device loop, device = %s', device_model)
            # deconfigure
            if device_model.configured:
                logger.debug('AFDEBUG device is configured, deconfiguring...')
                device_model.configured = self._dev_deconfigure_if_possible(
                    device_model
                )
                yield defer.ensureDeferred(self.device_dao.update(device_model))
                logger.debug('AFDEBUG device deconfigured')
            # configure
            device_dict = self._dev_create_dict_from_model(device_model)
            configured = yield self._dev_configure_if_possible(device_dict)
            if device_model.configured != configured:
                logger.debug(
                    'configured = %s, was %s', configured, device_model.configured
                )
                device_model.configured = configured
                yield defer.ensureDeferred(self.device_dao.update(device_model))

    def pg_install(self, plugin_id: str) -> tuple[Deferred, OperationInProgress]:
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

    def pg_upgrade(self, plugin_id: str) -> tuple[Deferred, OperationInProgress]:
        """Upgrade the plugin with the given id.

        Same contract as pg_install, except that the plugin must already be
        installed.

        Affected devices are automatically reconfigured if needed.

        """
        logger.info('Upgrading and reloading plugin %s', plugin_id)
        if not self.pg_mgr.is_installed(plugin_id):
            logger.error('Error: plugin %s is not already installed', plugin_id)
            raise Exception(f'plugin {plugin_id} is not already installed')

        def callback1(_: Any) -> None:
            # reset the state to in progress
            oip.state = OIP_PROGRESS

        @_wlock_arg(self._rw_lock)
        def callback2(_: Any):
            # The lock apply only to the deferred return by this function
            # and not on the function itself
            if plugin_id in self.pg_mgr:
                self._pg_unload(plugin_id)
            # next line might raise an exception, which is ok
            self._pg_load(plugin_id)
            return self._pg_configure_all_devices(plugin_id)

        def callback3(_: Any) -> None:
            oip.state = OIP_SUCCESS

        def errback3(err: Exception) -> Exception:
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
    def pg_uninstall(self, plugin_id: str):
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
        affected_devices = yield defer.ensureDeferred(
            self.device_dao.find({'plugin': plugin_id, 'configured': True})
        )
        for device in affected_devices:
            device.configured = False
            yield defer.ensureDeferred(self.device_dao.update(device))

    @_wlock
    @defer.inlineCallbacks
    def pg_reload(self, plugin_id: str):
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

        devices = yield defer.ensureDeferred(
            self.device_dao.find({'plugin': plugin_id})
        )
        devices = list(devices)

        # unload plugin
        if plugin_id in self.pg_mgr:
            plugin = self.pg_mgr[plugin_id]
            for device_model in devices:
                device = self._dev_create_dict_from_model(device_model)
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
                if device.configured:
                    device.configured = False
                    yield defer.ensureDeferred(self.device_dao.update(device))
            raise

        # reconfigure every device
        for device_model in devices:
            device = self._dev_create_dict_from_model(device_model)
            configured = yield self._dev_configure_if_possible(device)
            if device_model.configured != configured:
                device_model.configured = configured
                yield defer.ensureDeferred(self.device_dao.update(device_model))

    def pg_retrieve(self, plugin_id: str):
        return self.pg_mgr[plugin_id]


def _check_is_server_url(value: str | None) -> None:
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


def _check_is_proxy(value: str | None) -> None:
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


def _check_is_https_proxy(value: str | None) -> None:
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


def _is_string_url_safe(value: str) -> bool:
    safe_str_pattern = re.compile(r"^[a-zA-Z0-9\-$~.]+$")
    return safe_str_pattern.match(value) is not None


class ApplicationConfigureService:
    VIRTUAL_ATTRIBUTES = {'provisioning_key': {'parent': 'tenants'}}

    def __init__(self, pg_mgr: PluginManager, proxies, app: ProvisioningApplication):
        self._pg_mgr = pg_mgr
        self._proxies = proxies
        self._app = app
        self._tenant_dao = app.tenant_dao
        self._configuration_dao = app.configuration_dao

    def _get_param_locale(self, *args: Any, **kwargs: Any) -> str | None:
        l10n_service = get_localization_service()
        if l10n_service is None:
            logger.info('No localization service registered')
            return None
        return l10n_service.get_locale()

    def _set_param_locale(self, value: str | None, *args: Any, **kwargs: Any) -> None:
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

    def _generic_set_proxy(
        self, key: str, value: str | None, *args: Any, **kwargs: Any
    ) -> None:
        if not value:
            if key in self._proxies:
                del self._proxies[key]
        else:
            self._proxies[key] = value

    def _get_param_http_proxy(self, *args: Any, **kwargs: Any) -> str | None:
        return self._proxies.get('http')

    def _set_param_http_proxy(
        self, value: str | None, *args: Any, **kwargs: Any
    ) -> Deferred:
        _check_is_proxy(value)
        self._generic_set_proxy('http', value)
        return defer.ensureDeferred(
            self._configuration_dao.update_key('http_proxy', value)
        )

    def _get_param_ftp_proxy(self, *args: Any, **kwargs: Any) -> str | None:
        return self._proxies.get('ftp')

    def _set_param_ftp_proxy(self, value, *args, **kwargs) -> Deferred:
        _check_is_proxy(value)
        self._generic_set_proxy('ftp', value)
        return defer.ensureDeferred(
            self._configuration_dao.update_key('ftp_proxy', value)
        )

    def _get_param_https_proxy(self, *args, **kwargs) -> str | None:
        return self._proxies.get('https')

    def _set_param_https_proxy(
        self, value: str | None, *args: Any, **kwargs: Any
    ) -> Deferred:
        _check_is_https_proxy(value)
        self._generic_set_proxy('https', value)
        return defer.ensureDeferred(
            self._configuration_dao.update_key('https_proxy', value)
        )

    def _get_param_plugin_server(self, *args: Any, **kwargs: Any):
        return self._pg_mgr.server

    def _set_param_plugin_server(
        self, value: str | None, *args: Any, **kwargs: Any
    ) -> Deferred:
        _check_is_server_url(value)
        self._pg_mgr.server = value
        return defer.ensureDeferred(
            self._configuration_dao.update_key('plugin_server', value)
        )

    def _get_param_NAT(self, *args, **kwargs) -> int:
        return self._app.nat

    def _set_param_NAT(self, value, *args, **kwargs) -> Deferred:
        if value is None or value == '0':
            value = False
        elif value == '1':
            value = True
        else:
            raise InvalidParameterError(value)

        self._app.nat = 1 if value else 0
        return defer.ensureDeferred(
            self._configuration_dao.update_key('nat_enabled', value)
        )

    def _get_tenant_config(self, tenant_uuid: str) -> dict[str, Any] | None:
        return self._app.tenants.get(tenant_uuid)

    def _create_tenant_config(
        self, tenant_uuid: str, config: dict[str, Any] | None = None
    ) -> Deferred:
        tenant_config = {}
        if config is not None:
            tenant_config.update(config)
        new_tenant = TenantModel(uuid=UUID(tenant_uuid), **tenant_config)

        def return_tenant(_):
            self._app.tenants[tenant_uuid] = tenant_config
            return self._get_tenant_config(tenant_uuid)

        def errback(fail: failure.Failure):
            logger.error('Error creating new tenant: %s', fail.value)

        d = defer.ensureDeferred(self._tenant_dao.create(new_tenant))
        d.addCallbacks(return_tenant, errback)
        return d

    def _get_param_provisioning_key(self, tenant_uuid: str) -> Deferred:
        tenant_config = self._get_tenant_config(tenant_uuid)
        if tenant_config is None:

            def on_callback(value):
                return value.get('provisioning_key')

            def on_errback(fail: failure.Failure):
                logger.error('Cannot create empty tenant configuration: %s', fail.value)

            tenant_config_deferred = self._create_tenant_config(tenant_uuid)
            tenant_config_deferred.addCallbacks(on_callback, on_errback)
            return tenant_config_deferred
        return defer.succeed(tenant_config.get('provisioning_key'))

    def _set_param_provisioning_key(
        self, provisioning_key: str, tenant_uuid: str
    ) -> Deferred:
        if provisioning_key:
            if len(provisioning_key) < 8 or len(provisioning_key) > 256:
                raise InvalidParameterError(
                    '`provisioning_key` should be [8, 256] characters long.'
                )

            if not _is_string_url_safe(provisioning_key):
                raise InvalidParameterError(
                    '`provisioning_key` should only contain the following characters: '
                    '`a-z, A-Z, 0-9, -, $, ~, .`'
                )

            existing_tenant_uuid = self.get_tenant_from_provisioning_key(
                provisioning_key
            )
            if existing_tenant_uuid and existing_tenant_uuid != tenant_uuid:
                raise InvalidParameterError(
                    'another tenant already uses this provisioning key.'
                )

        tenant_config = self._get_tenant_config(tenant_uuid)

        if tenant_config is None:
            new_config = {'provisioning_key': provisioning_key}
            tenant_config_deferred = self._create_tenant_config(tenant_uuid, new_config)
            return tenant_config_deferred

        logger.debug('Tenant config already exists, updating: %s', tenant_config)
        tenant_config['provisioning_key'] = provisioning_key
        tenant_model = TenantModel(uuid=UUID(tenant_uuid), **tenant_config)
        return defer.ensureDeferred(self._tenant_dao.update(tenant_model))

    def get_tenant_from_provisioning_key(self, provisioning_key: str) -> str | None:
        for tenant, config in self._app.tenants.items():
            if config.get('provisioning_key') == provisioning_key:
                return tenant
        return None

    def _set_param_tenants(
        self, tenants: dict[str, dict[str, Any]], *args: Any, **kwargs: Any
    ) -> None:
        self._app.tenants = tenants

    def _get_param_tenants(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, dict[str, Any]]:
        return self._app.tenants

    def get(self, name: str, *args: Any, **kwargs: Any) -> Deferred:
        get_fun_name = f'_get_param_{name}'
        try:
            get_fun = getattr(self, get_fun_name)
        except AttributeError:
            return defer.fail(KeyError(name))
        return defer.maybeDeferred(get_fun, *args, **kwargs)

    def set(self, name: str, value: Any, *args: Any, **kwargs: Any) -> Deferred:
        set_fun_name = f'_set_param_{name}'
        try:
            set_fun = getattr(self, set_fun_name)
        except AttributeError:
            return defer.fail(KeyError(name))
        else:
            return defer.maybeDeferred(set_fun, value, *args, **kwargs)

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
