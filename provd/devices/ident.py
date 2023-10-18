# Copyright 2010-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Request processing service definition."""
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from enum import Enum
from operator import itemgetter
from os.path import basename
from typing import TYPE_CHECKING, TypedDict, cast, Any, Union, Protocol

from provd.devices.device import copy as copy_device
from provd.plugins import BasePluginManagerObserver
from provd.security import log_security_msg
from provd.servers.http_site import Request
from provd.servers.tftp.packet import ERR_UNDEF
from provd.servers.tftp.service import TFTPNullService, TFTPRequest
from twisted.internet import defer
from twisted.internet.defer import Deferred
from twisted.web.http import INTERNAL_SERVER_ERROR
from twisted.web.resource import Resource, NoResource, ErrorPage
from twisted.web import rewrite

from provd.util import decode_bytes


if TYPE_CHECKING:
    from ..servers.tftp.proto import _Response
    from ..main import ProvisioningApplication

    class Request(Request):  # type: ignore[no-redef]
        num_http_proxies: int | None


class DeviceInfoUpdaterProtocol(Protocol):
    dev_info: DeviceInfo

    def update(self, dev_info: DeviceInfo) -> None:
        ...


class ExtractorProtocol(Protocol):
    def extract(
        self, request: Request | DHCPRequest | TFTPRequest, request_type: RequestType
    ) -> Deferred:
        ...


class DevTFTPRequest(TFTPRequest, total=False):
    prov_dev: DeviceInfo


class DeviceInfoDict(TypedDict, total=False):
    ip: str
    mac: str


DeviceInfo = Union[DeviceInfoDict, dict[str, Any]]


class RequestType(Enum):
    HTTP = 'http'
    TFTP = 'tftp'
    DHCP = 'dhcp'


class DHCPRequest(TypedDict):
    ip: str
    mac: str
    options: dict[int, bytes]


logger = logging.getLogger(__name__)


def _get_ip_from_request(
    request: Request | DHCPRequest | TFTPRequest, request_type: RequestType
) -> str:
    if request_type == RequestType.HTTP:
        http_request: Request = request  # type: ignore
        if not http_request.num_http_proxies:
            return http_request.getClientIP()
        return _get_ip_from_http_request_with_proxies(
            http_request, http_request.num_http_proxies
        )
    if request_type == RequestType.TFTP:
        tftp_request: TFTPRequest = request  # type: ignore
        return tftp_request['address'][0]
    if request_type == RequestType.DHCP:
        dhcp_request: DHCPRequest = request  # type: ignore
        return dhcp_request['ip']
    raise RuntimeError(f'invalid request_type: {request_type}')


def _get_ip_from_http_request_with_proxies(
    request: Request, num_http_proxies: int
) -> str:
    if num_http_proxies <= 0:
        raise RuntimeError(
            'This function must be used with at least one expected proxy'
        )
    # Example with num_http_proxies = 2
    # X-Forwarded-For:   W.W.W.W,   X.X.X.X,     Y.Y.Y.Y,       Z.Z.Z.Z
    # X-Forwarded-For: untrusted, untrusted, entry proxy, backend proxy
    untrusted_forwarded_for = request.getHeader('X-Forwarded-For') or ''
    untrusted_forwarded_for = [
        client_ip.strip() for client_ip in untrusted_forwarded_for.split(',')
    ]
    trusted_forwarded_for = untrusted_forwarded_for[-num_http_proxies:]
    proxied_client_ip = trusted_forwarded_for[0]
    if not proxied_client_ip:
        raise RuntimeError(
            f'Invalid client IP address "{proxied_client_ip}" from header '
            f'"X-Forwarded-For: {untrusted_forwarded_for}"'
        )
    return str(proxied_client_ip)


def _get_filename_from_request(
    request: Request | DHCPRequest | TFTPRequest, request_type: RequestType
) -> str | None:
    if request_type == RequestType.HTTP:
        http_request = cast(Request, request)
        return basename(http_request.path.decode('ascii'))
    if request_type == RequestType.TFTP:
        tftp_request = cast(TFTPRequest, request)
        filename: str | bytes = tftp_request['packet']['filename']
        if isinstance(filename, bytes):
            filename = filename.decode()
        return basename(filename)
    if request_type == RequestType.DHCP:
        return None
    raise RuntimeError(f'invalid request_type: {request_type}')


class AbstractDeviceInfoExtractor(metaclass=ABCMeta):
    """A device info extractor object extract device information from
    requests. In our context, requests are either HTTP, TFTP or DHCP
    requests.

    Example of information that can be extracted are:
    - IP address
    - MAC address
    - vendor name
    - model name
    - version number
    - serial number

    Note: DHCP requests are not processed by the provisioning server per se.
    The provisioning server use them only to get information from it and update
    the corresponding device object. For example, with a valid source of DHCP
    information, we can then always make sure the IP <-> MAC for a device is
    up-to-date.

    """

    @abstractmethod
    def extract(self, request: Request, request_type: RequestType) -> Deferred:
        """Return a deferred that will fire with either a non-empty
        device info object or an object that evaluates to false in a boolean
        context if no information could be extracted.

        So far, request_type is either 'http', 'tftp' or 'dhcp'. See the
        various {HTTP,TFTP,DHCP}RequestProcessingService for more information
        about the type of each request.

        """


class StandardDeviceInfoExtractor(AbstractDeviceInfoExtractor):
    """Device info extractor that return standard and readily available
    information from requests, like IP addresses, or MAC addresses for DHCP
    requests.

    You SHOULD always use this extractor.

    """

    def extract(
        self, request: Request | DHCPRequest | TFTPRequest, request_type: RequestType
    ) -> Deferred:
        dev_info = {'ip': _get_ip_from_request(request, request_type)}
        if request_type == RequestType.DHCP:
            dhcp_request: DHCPRequest = request  # type: ignore[assignment]
            dev_info['mac'] = dhcp_request['mac']
        return defer.succeed(dev_info)


class LastSeenUpdater:
    """Updater for CollaboratingDeviceInfoExtractor that, on conflict, keep
    the last seen value.

    """

    def __init__(self) -> None:
        self.dev_info: DeviceInfo = {}

    def update(self, dev_info: DeviceInfo) -> None:
        self.dev_info |= dev_info


KeyPool = dict[Any, int]


class VotingUpdater:
    """Updater for CollaboratingDeviceInfoExtractor that will return a device
    info object such that values are the most popular one.

    Note that in the case of a tie, it returns any of the most popular values.

    """

    def __init__(self) -> None:
        self._votes: defaultdict[str, KeyPool] = defaultdict(dict)

    def _vote(self, key: str, value: Any) -> None:
        key_pool = self._votes[key]
        key_pool[value] = key_pool.get(value, 0) + 1

    def _get_winner(self, key_pool: KeyPool) -> str:
        # Pre: key_pool is non-empty
        # XXX we are not doing any conflict resolution if key_pool has
        #     a tie. The worst is that it's not totally deterministic.
        return max(key_pool.items(), key=itemgetter(1))[0]

    @property
    def dev_info(self) -> DeviceInfo:
        dev_info: dict[str, Any] = {}
        for key, key_pool in self._votes.items():
            dev_info[key] = self._get_winner(key_pool)
        return dev_info

    def update(self, dev_info: DeviceInfo):
        for key, value in dev_info.items():
            self._vote(key, value)


class CollaboratingDeviceInfoExtractor(AbstractDeviceInfoExtractor):
    """Composite device info extractor that return a device info object
    which is the composition of every device info objects returned.

    Takes an Updater factory to control the way the returned device info
    object is built.

    An Updater is an object with an:
    - 'update' method, taking a dev_info object and returning nothing
    - 'dev_info' attribute, which is the current computed dev_info

    """

    def __init__(
        self,
        updater_factory: type[DeviceInfoUpdaterProtocol],
        extractors: list[ExtractorProtocol],
    ):
        self._updater_factory = updater_factory
        self._extractors = extractors

    @defer.inlineCallbacks
    def extract(self, request: Request, request_type: RequestType) -> Deferred:
        logging.debug('extractors: %s', self._extractors)
        dlist = defer.DeferredList(
            [extractor.extract(request, request_type) for extractor in self._extractors]
        )
        dlist_results = yield dlist
        updater = self._updater_factory()
        for success, result in dlist_results:
            if success and result:
                logger.debug('extract result: %s', result)
                updater.update(result)
        defer.returnValue(updater.dev_info)


class AllPluginsDeviceInfoExtractor(AbstractDeviceInfoExtractor):
    """Composite device info extractor that forward extraction requests to
    device info extractors of every loaded plugins.

    """

    def __init__(self, extractor_factory, pg_mgr):
        """
        extractor_factory -- a function taking a list of extractors and
          returning an extractor.
        """
        self.extractor_factory = extractor_factory
        self._pg_mgr = pg_mgr
        self._set_xtors()
        # observe plugin loading/unloading and keep a reference to the weakly
        # referenced observer
        self._obs = BasePluginManagerObserver(
            self._on_plugin_load_or_unload, self._on_plugin_load_or_unload
        )
        pg_mgr.attach(self._obs)

    def _xtor_name(self, request_type):
        return f'_{request_type}_xtor'

    def _set_xtors(self) -> None:
        logger.debug('Updating extractors for %s', self)
        for request_type in RequestType:
            pg_extractors = []
            for pg in self._pg_mgr.values():
                pg_extractor = getattr(pg, f'{request_type.value}_dev_info_extractor')
                if pg_extractor is not None:
                    logger.debug('Adding %s extractor from %s', request_type.value, pg)
                    pg_extractors.append(pg_extractor)
            xtor = self.extractor_factory(pg_extractors)
            setattr(self, self._xtor_name(request_type), xtor)

    def _on_plugin_load_or_unload(self, pg_id):
        self._set_xtors()

    def extract(self, request, request_type: RequestType) -> Deferred:
        xtor = getattr(self, self._xtor_name(request_type))
        return xtor.extract(request, request_type)


class AbstractDeviceRetriever(metaclass=ABCMeta):
    """A device retriever return a device object from device information.

    Instances providing this interface MAY have some side effect on the
    application, like adding a new device.

    """

    @abstractmethod
    def retrieve(self, dev_info: DeviceInfo) -> Deferred | None:
        """Return a deferred that will fire with either a device object
        or None if it can't find such object.

        """


class SearchDeviceRetriever(AbstractDeviceRetriever):
    """Device retriever who search in the application for a device with a
    key's value the same as a device info key's value, and return the first
    one found.

    """

    def __init__(self, app: ProvisioningApplication, key: str) -> None:
        self._app = app
        self._key = key

    def retrieve(self, dev_info) -> Deferred:
        if self._key in dev_info:
            return self._app.dev_find_one({self._key: dev_info[self._key]})
        return defer.succeed(None)


class IpDeviceRetriever(AbstractDeviceRetriever):
    def __init__(self, app: ProvisioningApplication):
        self._app = app

    @defer.inlineCallbacks
    def retrieve(self, dev_info):
        if 'ip' in dev_info:
            devices = yield self._app.dev_find({'ip': dev_info['ip']})
            matching_device = self._get_matching_device(devices, dev_info)
            defer.returnValue(matching_device)
        defer.returnValue(None)

    def _get_matching_device(self, devices, dev_info):
        candidate_devices = self._get_candidate_devices(devices, dev_info)
        nb_candidates = len(candidate_devices)
        if nb_candidates == 1:
            return candidate_devices[0]
        elif nb_candidates > 1:
            logger.warning(
                'Multiple device match in IP device retriever: %r', candidate_devices
            )
        return None

    def _get_candidate_devices(self, devices, dev_info):
        devices_by_id = {device['id']: device for device in devices}
        self._filter_devices_by_key(devices_by_id, dev_info, 'mac')
        self._filter_devices_by_key(devices_by_id, dev_info, 'vendor')
        self._filter_devices_by_key(devices_by_id, dev_info, 'model')
        return list(devices_by_id.values())

    def _filter_devices_by_key(self, devices_by_id, dev_info, key):
        if key in dev_info:
            key_value = dev_info[key]
            for device in list(devices_by_id.values()):
                if key in device:
                    if device[key] != key_value:
                        device_id = device['id']
                        del devices_by_id[device_id]


def MacDeviceRetriever(app: ProvisioningApplication) -> SearchDeviceRetriever:
    """Retrieve device object by looking up in a device manager for an
    object which MAC is the same as the device info object.

    """
    return SearchDeviceRetriever(app, 'mac')


def SerialNumberDeviceRetriever(app: ProvisioningApplication) -> SearchDeviceRetriever:
    """Retrieve device object by looking up in a device manager for an
    object which serial number is the same as the device info object.

    """
    return SearchDeviceRetriever(app, 'sn')


def UUIDDeviceRetriever(app: ProvisioningApplication) -> SearchDeviceRetriever:
    """Retrieve device object by looking up in a device manager for an
    object which UUID is the same as the device info object.

    """
    return SearchDeviceRetriever(app, 'uuid')


class AddDeviceRetriever(AbstractDeviceRetriever):
    """A device retriever that does no lookup and always insert a new device
    in the application.

    Mostly useful if used in a FirstCompositeDeviceRetriever at the end of
    the list, in a way that it will be called only if the other retrievers
    don't find anything.

    """

    def __init__(self, app: ProvisioningApplication) -> None:
        self._app = app

    @defer.inlineCallbacks
    def retrieve(self, dev_info):
        device = dict(dev_info)
        device['added'] = 'auto'
        try:
            device_id = yield self._app.dev_insert(device)
        except Exception:
            defer.returnValue(None)
        else:
            device_ip = dev_info.get('ip')
            if device_ip:
                log_security_msg(
                    'New device created automatically from %s: %s', device_ip, device_id
                )
            defer.returnValue(device)


class FirstCompositeDeviceRetriever(AbstractDeviceRetriever):
    """Composite device retriever which return the device its first retriever
    returns.

    """

    def __init__(self, retrievers=None) -> None:
        self.retrievers = [] if retrievers is None else retrievers

    @defer.inlineCallbacks
    def retrieve(self, dev_info):
        retrievers = self.retrievers[:]
        for retriever in retrievers:
            device = yield retriever.retrieve(dev_info)
            if device is not None:
                defer.returnValue(device)
        defer.returnValue(None)


class AbstractDeviceUpdater(metaclass=ABCMeta):
    """Update a device object device from an info object.

    This operation can have side effect, like updating the device. In fact,
    being able to do side effects is why this interface exist.

    """

    def update(self, device, dev_info, request, request_type):
        """Update a device object, returning a deferred that will fire once
        the device object has been updated.

        device -- a nonempty device object
        dev_info -- a potentially empty device info object

        """


class NullDeviceUpdater(AbstractDeviceUpdater):
    """Device updater that updates nothing."""

    def update(self, device, dev_info, request, request_type):
        return defer.succeed(None)


class DynamicDeviceUpdater(AbstractDeviceUpdater):
    """Device updater that updates zero or more of the device key with the
    value of the device info key.

    If the key is already present in the device, then the device will be
    updated only if force_update is true.

    Its update method always return false, i.e. does not force a device
    reconfiguration.

    """

    def __init__(self, keys: str | list[str], force_update: bool = False) -> None:
        if isinstance(keys, str):
            keys = [keys]
        self._keys = list(keys)
        self._force_update = force_update

    def update(self, device, dev_info, request, request_type):
        for key in self._keys:
            if key in dev_info:
                if self._force_update or key not in device:
                    device[key] = dev_info[key]
        return defer.succeed(None)


class AddInfoDeviceUpdater(AbstractDeviceUpdater):
    """Device updater that add any missing information to the device from
    the device info.

    Its update method always return false, i.e. does not force a device
    reconfiguration.

    """

    def update(self, device, dev_info, request, request_type):
        for key in dev_info:
            if key not in device:
                device[key] = dev_info[key]
        return defer.succeed(None)


class AutocreateConfigDeviceUpdater(AbstractDeviceUpdater):
    """Device updater that set an auto-created config to the device if the
    device has no config.

    """

    def __init__(self, app: ProvisioningApplication) -> None:
        self._app = app

    @defer.inlineCallbacks
    def update(self, device, dev_info, request, request_type):
        if 'config' not in device:
            new_config_id = yield self._app.cfg_create_new()
            if new_config_id is not None:
                device['config'] = new_config_id
        defer.returnValue(None)


class RemoveOutdatedIpDeviceUpdater(AbstractDeviceUpdater):
    def __init__(self, app: ProvisioningApplication) -> None:
        self._app = app

    @defer.inlineCallbacks
    def update(self, device, dev_info, request, request_type):
        if not self._app.nat and 'ip' in dev_info:
            selector = {'ip': dev_info['ip'], 'id': {'$ne': device['id']}}
            outdated_devices = yield self._app.dev_find(selector)
            for outdated_device in outdated_devices:
                del outdated_device['ip']
                self._app.dev_update(outdated_device)


class CompositeDeviceUpdater(AbstractDeviceUpdater):
    def __init__(self, updaters=None) -> None:
        self.updaters = [] if updaters is None else updaters

    @defer.inlineCallbacks
    def update(self, device, dev_info, request, request_type):
        for updater in self.updaters:
            yield updater.update(device, dev_info, request, request_type)


class RequestProcessingService:
    """The base object responsible for dynamically modifying the process state
    when processing a request from a device.

    """

    def __init__(
        self,
        app: ProvisioningApplication,
        dev_info_extractor,
        dev_retriever,
        dev_updater,
    ) -> None:
        self._app = app
        self._dev_info_extractor = dev_info_extractor
        self._dev_retriever = dev_retriever
        self._dev_updater = dev_updater
        self._req_id = 0  # used for logging

    def _new_request_id(self):
        req_id = f"{self._req_id:d}"
        self._req_id = (self._req_id + 1) % 100
        return req_id

    @defer.inlineCallbacks
    def process(self, request, request_type):
        """Return a deferred that will eventually fire with a (device, pg_id)
        pair, where:

        - device is a device object or None, identifying which device is doing
          this request.
        - pg_id is a plugin identifier or None, identifying which plugin should
          continue to process this request.

        """
        helper = _RequestHelper(
            self._app, request, request_type, self._new_request_id()
        )

        dev_info = yield helper.extract_device_info(self._dev_info_extractor)
        device = yield helper.retrieve_device(self._dev_retriever, dev_info)
        yield helper.update_device(self._dev_updater, device, dev_info)
        pg_id = helper.get_plugin_id(device)

        defer.returnValue((device, pg_id))


class _RequestHelper:
    def __init__(
        self, app: ProvisioningApplication, request, request_type, request_id
    ) -> None:
        self._app = app
        self._request = request
        self._request_type = request_type
        self._request_id = request_id

    @defer.inlineCallbacks
    def extract_device_info(self, dev_info_extractor):
        dev_info = yield dev_info_extractor.extract(self._request, self._request_type)
        if not dev_info:
            logger.info('<%s> No device info extracted', self._request_id)
            dev_info = {}
        else:
            logger.info('<%s> Extracted device info: %s', self._request_id, dev_info)

        defer.returnValue(dev_info)

    @defer.inlineCallbacks
    def retrieve_device(self, dev_retriever, dev_info):
        device = yield dev_retriever.retrieve(dev_info)
        if device is None:
            logger.info('<%s> No device retrieved', self._request_id)
        else:
            logger.info('<%s> Retrieved device id: %s', self._request_id, device['id'])

        defer.returnValue(device)

    @defer.inlineCallbacks
    def update_device(self, dev_updater, device, dev_info):
        if device is None:
            defer.returnValue(None)

        orig_device = copy_device(device)
        yield dev_updater.update(device, dev_info, self._request, self._request_type)
        if device == orig_device:
            yield self._update_device_on_no_change(device)
        else:
            logger.info('<%s> Device has been updated', self._request_id)
            yield self._update_device_on_change(device)

    @defer.inlineCallbacks
    def _update_device_on_no_change(self, device):
        if not device.get('configured'):
            defer.returnValue(None)

        if not self._should_update_remote_state(device):
            defer.returnValue(None)

        config = yield self._app.cfg_retrieve(device['config'])
        if not config:
            defer.returnValue(None)

        if self._update_remote_state_sip_username(device, config):
            yield self._app.dev_update(device)

    def _update_device_on_change(self, device):
        if self._should_update_remote_state(device):
            pre_update_hook = self._pre_update_hook
        else:
            pre_update_hook = None

        return self._app.dev_update(device, pre_update_hook=pre_update_hook)

    def _should_update_remote_state(self, device):
        filename = _get_filename_from_request(self._request, self._request_type)
        if not filename:
            return False

        plugin_id = device.get('plugin')
        if not plugin_id:
            return False

        plugin = self._app.pg_mgr.get(plugin_id)
        if plugin is None:
            return False

        trigger_fun = getattr(plugin, 'get_remote_state_trigger_filename', None)
        if trigger_fun is None:
            return False

        trigger_filename = trigger_fun(device)
        if not trigger_filename:
            return False

        if trigger_filename != filename:
            return False

        config_id = device.get('config')
        if not config_id:
            return False

        return True

    def _pre_update_hook(self, device, config):
        if not config:
            return

        if not device['configured']:
            return

        self._update_remote_state_sip_username(device, config)

    def _update_remote_state_sip_username(self, device, config):
        sip_username = self._get_sip_username(config)
        if not sip_username:
            return False

        if sip_username == device.get('remote_state_sip_username'):
            return False

        device['remote_state_sip_username'] = sip_username
        logger.debug('Remote state SIP username updated')

        return True

    def _get_sip_username(self, config):
        sip_lines = config['raw_config'].get('sip_lines')
        if not sip_lines:
            return None

        sip_line = sip_lines.get('1')
        if not sip_line:
            return None

        return sip_line.get('username')

    def get_plugin_id(self, device):
        pg_id = self._get_plugin_id(device)
        if pg_id is None:
            logger.info('<%s> No route found', self._request_id)
        else:
            logger.info('<%s> Routing request to plugin %s', self._request_id, pg_id)

        return pg_id

    def _get_plugin_id(self, device):
        if device is None:
            return None
        return device.get('plugin')


def _null_service_factory(pg_id: str, pg_service):
    return pg_service


def _log_sensitive_request(
    plugin, request: Request | DHCPRequest | TFTPRequest, request_type
) -> None:
    is_sensitive_filename = getattr(plugin, 'is_sensitive_filename', None)
    if is_sensitive_filename is None:
        return

    filename = decode_bytes(_get_filename_from_request(request, request_type))
    if is_sensitive_filename(filename):
        ip = _get_ip_from_request(request, request_type)
        log_security_msg('Sensitive file requested from %s: %s', ip, filename)


# @implementer(IHTTPService)
class HTTPRequestProcessingService(Resource):
    """An HTTP service that does HTTP request processing and routing to
    the HTTP service of plugins.

    It's possible to add additional processing between this service and the
    plugin service by using a 'service factory' object which is a callable
    taking a plugin ID and a HTTP service and return a new service that will
    be used to continue with the processing of the request.

    Note that in the case the plugin doesn't offer an HTTP service, the
    'service factory' object is not used and the request is processed by
    the default service.

    If the process service returns an unknown plugin ID, a default service
    is used to continue with the request processing.

    """

    default_service = NoResource('Nowhere to route this request.')

    def __init__(self, process_service, pg_mgr, num_http_proxies) -> None:
        super().__init__()
        self._process_service = process_service
        self._pg_mgr = pg_mgr
        self.service_factory = _null_service_factory
        self._num_http_proxies = num_http_proxies

    @defer.inlineCallbacks
    def getChild(self, path: bytes, request: Request):
        logger.info('Processing HTTP request: %s', request.path)
        logger.debug('HTTP request: %s', request)
        logger.debug('postpath: %s', request.postpath)

        # Inject the number of trusted HTTP proxies
        request.num_http_proxies = self._num_http_proxies

        try:
            device, pg_id = yield self._process_service.process(
                request, RequestType.HTTP
            )
        except Exception:
            logger.error('Error while processing HTTP request:', exc_info=True)
            defer.returnValue(
                ErrorPage(
                    INTERNAL_SERVER_ERROR,
                    'Internal processing error',
                    'Internal processing error',
                )
            )
        else:
            # Here we 'inject' the device object into the request object
            request.prov_dev = device
            service = self.default_service
            if pg_id in self._pg_mgr:
                plugin = self._pg_mgr[pg_id]
                if plugin.http_service is not None:
                    _log_sensitive_request(plugin, request, RequestType.HTTP)
                    service = self.service_factory(pg_id, plugin.http_service)
                    # If the plugin specifies a path preprocessing method, use it
                    if hasattr(service, 'path_preprocess'):
                        logger.debug('Rewriting paths to the HTTP Service')
                        service = rewrite.RewriterResource(
                            service, service.path_preprocess
                        )
            if service.isLeaf:
                request.postpath.insert(0, request.prepath.pop())
                defer.returnValue(service)
            else:
                defer.returnValue(service.getChildWithDefault(path, request))


# @implementer(ITFTPReadService)
class TFTPRequestProcessingService:
    """A TFTP read service that does TFTP request processing and routing to
    the TFTP read service of plugins.

    """

    default_service = TFTPNullService(errmsg="Nowhere to route this request")

    def __init__(self, process_service: RequestProcessingService, pg_mgr):
        self._process_service = process_service
        self._pg_mgr = pg_mgr
        self.service_factory = _null_service_factory

    def handle_read_request(self, request: DevTFTPRequest, response: _Response):
        logger.info('Processing TFTP request: %s', request['packet']['filename'])
        logger.debug('TFTP request: %s', request)

        def callback(plugin_for_device):
            # Here we 'inject' the device object into the request object
            (device, pg_id) = plugin_for_device
            request['prov_dev'] = device

            service = self.default_service
            if pg_id in self._pg_mgr:
                plugin = self._pg_mgr[pg_id]
                if plugin.tftp_service is not None:
                    _log_sensitive_request(plugin, request, RequestType.TFTP)
                    service = self.service_factory(pg_id, plugin.tftp_service)
            service.handle_read_request(request, response)

        def errback(failure):
            logger.error('Error while processing TFTP request: %s', failure)
            response.reject(ERR_UNDEF, 'Internal processing error')

        d = self._process_service.process(request, RequestType.TFTP)
        d.addCallbacks(callback, errback)


class DHCPRequestProcessingService(Resource):
    """A DHCP request service that does DHCP request processing.

    Contrary to the HTTP/TFTP request processing service, this service does
    not route the request to a plugin specific DHCP request service, since
    there's no such thing. It is only used to process DHCP request to
    extract information from it and potentially update affected device
    objects.

    Also, in this context, these are not real DHCP request, but more like
    DHCP transaction information objects. We use the term request for
    homogeneity’s sake.

    """

    def __init__(self, process_service):
        self._process_service = process_service

    def handle_dhcp_request(self, request: DHCPRequest):
        """Handle DHCP request.

        DHCP requests are dictionary objects with the following keys:
          'ip' -- the IP address of the client who made the request, in
            normalized format
          'mac' -- the MAC address of the client who made the request, in
            normalized format
          'options' -- a dictionary of client options, where keys are integers
            representing the option code, and values are byte string
            representing the raw value of the option
        """
        logger.info('Processing DHCP request: %s', request['ip'])
        logger.debug('DHCP request: %s', request)

        def errback(failure):
            logger.error('Error while processing DHCP request: %s', failure)

        d = self._process_service.process(request, RequestType.DHCP)
        d.addErrback(errback)
