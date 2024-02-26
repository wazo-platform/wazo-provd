# Copyright 2010-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import builtins
import logging
import os.path
from collections.abc import Generator
from typing import TYPE_CHECKING, Any, Callable

from twisted.application import internet
from twisted.application.service import IServiceMaker, MultiService, Service
from twisted.enterprise import adbapi
from twisted.internet import defer, reactor, ssl, task
from twisted.internet.defer import Deferred
from twisted.logger import STDLibLogObserver
from twisted.plugin import IPlugin
from twisted.python.util import sibpath
from twisted.web.resource import Resource as UnsecuredResource
from wazo_bus.consumer import BusConsumer
from xivo.status import Status
from xivo.token_renewer import TokenRenewer
from xivo.xivo_logging import setup_logging, silence_loggers
from zope.interface import implementer

import wazo_provd.config
import wazo_provd.localization
import wazo_provd.synchronize
from wazo_provd import security, status
from wazo_provd.app import ProvisioningApplication
from wazo_provd.config import Options
from wazo_provd.database import helpers
from wazo_provd.devices import ident, pgasso
from wazo_provd.devices.config import ConfigCollection
from wazo_provd.devices.device import DeviceCollection
from wazo_provd.persist.json_backend import JsonDatabaseFactory
from wazo_provd.rest.api.resource import ResponseFile
from wazo_provd.rest.server import auth
from wazo_provd.rest.server.server import new_authenticated_server_resource
from wazo_provd.servers.http_site import AuthResource, Site
from wazo_provd.servers.tftp.proto import TFTPProtocol

if TYPE_CHECKING:
    from .config import BusConfigDict, ProvdConfigDict
    from .persist.common import AbstractDatabase


logger = logging.getLogger(__name__)

LOG_FILE_NAME = '/var/log/wazo-provd.log'
API_VERSION = b'0.2'

ONE_DAY_SEC = 86400


# given in command line to redirect logs to standard logging
def twistd_logs() -> Callable[[dict[str, Any]], None]:
    return STDLibLogObserver()


class ProvisioningService(Service):
    # has an 'app' attribute after starting
    app: ProvisioningApplication

    _DB_FACTORIES = {
        'json': JsonDatabaseFactory(),
    }

    def __init__(self, config: ProvdConfigDict) -> None:
        self._config = config

    def _extract_database_specific_config(self) -> dict[str, Any]:
        return {
            k: v
            for k, v in self._config['database'].items()
            if k not in ['type', 'generator']
        }

    def _create_database(self) -> AbstractDatabase:
        db_type = self._config['database']['type']
        db_generator = self._config['database']['generator']
        db_specific_config = self._extract_database_specific_config()
        logger.info(
            'Using %s database with %s generator and config %s',
            db_type,
            db_generator,
            db_specific_config,
        )
        db_factory = self._DB_FACTORIES[db_type]
        return db_factory.new_database(db_type, db_generator, **db_specific_config)

    def _close_database(self) -> None:
        logger.info('Closing database...')
        try:
            self._database.close()
        except Exception:
            logger.error('Error while closing database', exc_info=True)
        logger.info('/Database closed')

    def _create_sql_database(self) -> adbapi.ConnectionPool:
        db_uri = self._config['database']['uri']
        pool_size = self._config['database']['pool_size']
        return helpers.init_db(db_uri, pool_size=pool_size)

    def _close_sql_database(self) -> None:
        logger.info('Closing SQL database...')
        try:
            self._sql_database.close()
        except Exception:
            logger.error('Error while closing SQL database', exc_info=True)
        logger.info('/SQL database closed')

    def startService(self) -> None:
        self._database = self._create_database()
        self._sql_database = self._create_sql_database()

        try:
            cfg_collection = ConfigCollection(self._database.collection('configs'))
            dev_collection = DeviceCollection(self._database.collection('devices'))
            if self._config['database']['ensure_common_indexes']:
                logger.debug('Ensuring index existence on collections')
                try:
                    dev_collection.ensure_index('mac')
                    dev_collection.ensure_index('ip')
                    dev_collection.ensure_index('sn')
                except AttributeError as e:
                    logger.warning(
                        'This type of database doesn\'t seem to support index: %s', e
                    )
            self.app = ProvisioningApplication(
                cfg_collection, dev_collection, self._config
            )
        except Exception as e:
            try:
                logger.error(
                    f'An error occurred whilst starting the server: {e}', exc_info=True
                )
                raise
            finally:
                self._close_database()
                self._close_sql_database()
        else:
            Service.startService(self)

    def stopService(self) -> None:
        Service.stopService(self)
        try:
            self.app.close()
        except Exception:
            logger.error(
                'An error occurred whilst stopping the application', exc_info=True
            )
        self._close_database()
        self._close_sql_database()


class ProcessService(Service):
    request_processing: ident.RequestProcessingService

    def __init__(
        self, prov_service: ProvisioningService, config: ProvdConfigDict
    ) -> None:
        self._prov_service = prov_service
        self._config = config

    def _get_conf_file_globals(self) -> dict[str, Any]:
        # This creates a dict of all variables, classes and methods in both the
        # `ident` and `pgasso` module with `app` mushed in there. It would be
        # unrealistic and unreliable to type all values. But perhaps there must be a better way.
        # Pre: hasattr(self._prov_service, 'app')
        conf_file_globals: dict[str, Any] = {}
        conf_file_globals |= ident.__dict__
        conf_file_globals |= pgasso.__dict__
        conf_file_globals['app'] = self._prov_service.app
        return conf_file_globals

    def _create_processor(self, name: str) -> dict[str, Any]:
        # name is the name of the processor, for example 'info_extractor'
        dirname = self._config['general']['request_config_dir']
        config_name = self._config['general'][name]  # type: ignore[literal-required]
        filename = f'{name}.py.conf.{config_name}'
        pathname = os.path.join(dirname, filename)
        conf_file_globals = self._get_conf_file_globals()
        try:
            with open(pathname) as f:
                exec(compile(f.read(), pathname, 'exec'), conf_file_globals)
        except Exception as e:
            logger.error(
                'error while executing process config file "%s": %s', pathname, e
            )
            raise
        if name not in conf_file_globals:
            raise Exception(
                f'process config file "{pathname}" doesn\'t define a "{name}" name'
            )
        return conf_file_globals[name]

    def startService(self) -> None:
        # Pre: hasattr(self._prov_service, 'app')
        dev_info_extractor = self._create_processor('info_extractor')
        dev_retriever = self._create_processor('retriever')
        dev_updater = self._create_processor('updater')
        self.request_processing = ident.RequestProcessingService(
            self._prov_service.app, dev_info_extractor, dev_retriever, dev_updater
        )
        Service.startService(self)


class HTTPProxiedProcessService(Service):
    def __init__(
        self,
        prov_service: ProvisioningService,
        process_service: ProcessService,
        config: ProvdConfigDict,
    ):
        self._prov_service = prov_service
        self._process_service = process_service
        self._config = config

    def startService(self):
        app = self._prov_service.app
        config = self._config['general']
        process_service = self._process_service.request_processing
        trusted_proxies_count = config['http_proxied_trusted_proxies_count']
        http_process_service = ident.HTTPRequestProcessingService(
            process_service, app.pg_mgr, trusted_proxies_count
        )
        if app.use_provisioning_key:
            logger.info('Using in-URL provisioning key')
            http_process_service = ident.HTTPKeyVerifyingHook(app, http_process_service)
        site = Site(http_process_service)
        interface = config['http_proxied_listen_interface']
        port = config['http_proxied_listen_port']
        logger.info('Binding HTTP-proxied provisioning service to port %s', port)
        self._tcp_server = internet.TCPServer(
            port, site, backlog=128, interface=interface
        )
        self._tcp_server.startService()
        Service.startService(self)

    def stopService(self):
        Service.stopService(self)
        return self._tcp_server.stopService()


class TFTPProcessService(Service):
    def __init__(
        self,
        prov_service: ProvisioningService,
        process_service: ProcessService,
        config: ProvdConfigDict,
    ) -> None:
        self._prov_service = prov_service
        self._process_service = process_service
        self._config = config
        self._tftp_protocol = TFTPProtocol()

    def privilegedStartService(self) -> None:
        port = self._config['general']['tftp_port']
        logger.info('Binding TFTP provisioning service to port %s', port)
        self._udp_server = internet.UDPServer(port, self._tftp_protocol)
        self._udp_server.privilegedStartService()
        Service.privilegedStartService(self)

    def startService(self) -> None:
        app = self._prov_service.app
        process_service = self._process_service.request_processing
        tftp_process_service = ident.TFTPRequestProcessingService(
            process_service, app.pg_mgr
        )
        self._tftp_protocol.set_tftp_request_processing_service(tftp_process_service)
        Service.startService(self)

    def stopService(self) -> Deferred:
        Service.stopService(self)
        return self._udp_server.stopService()


class DHCPProcessService(Service):
    # has a 'dhcp_request_processing_service' attribute once started
    dhcp_request_processing_service: ident.DHCPRequestProcessingService

    def __init__(self, process_service: ProcessService) -> None:
        self._process_service = process_service

    def startService(self) -> None:
        process_service = self._process_service.request_processing
        self.dhcp_request_processing_service = ident.DHCPRequestProcessingService(
            process_service
        )
        Service.startService(self)


class RemoteConfigurationService(Service):
    def __init__(
        self,
        prov_service: ProvisioningService,
        dhcp_process_service: DHCPProcessService,
        config: ProvdConfigDict,
    ) -> None:
        self._prov_service = prov_service
        self._dhcp_process_service = dhcp_process_service
        self._config = config
        auth_client = auth.get_auth_client(**self._config['auth'])
        auth.get_auth_verifier().set_client(auth_client)

    def startService(self) -> None:
        app = self._prov_service.app
        dhcp_request_processing_service = (
            self._dhcp_process_service.dhcp_request_processing_service
        )
        server_resource = new_authenticated_server_resource(
            app, dhcp_request_processing_service
        )
        logger.info('Authentication is required for REST API')
        # /{version}
        root_resource = AuthResource()
        root_resource.putChild(API_VERSION, server_resource)

        # /{version}/api/api.yml
        api_resource = UnsecuredResource()
        api_resource.putChild(
            b'api.yml', ResponseFile(sibpath(__file__, 'rest/api/api.yml'))
        )
        server_resource.putChild(b'api', api_resource)

        rest_site = Site(root_resource)

        port = self._config['rest_api']['port']
        interface = self._config['rest_api']['ip']
        if interface == '*':
            interface = ''
        logger.info('Binding HTTP REST API service to "%s:%s"', interface, port)
        if self._config['rest_api']['ssl']:
            logger.warning(
                'Using service SSL configuration is deprecated. Please use NGINX instead.'
            )
            context_factory = ssl.DefaultOpenSSLContextFactory(
                self._config['rest_api']['ssl_keyfile'],
                self._config['rest_api']['ssl_certfile'],
            )
            self._tcp_server = internet.SSLServer(
                port, rest_site, context_factory, interface=interface
            )
        else:
            self._tcp_server = internet.TCPServer(port, rest_site, interface=interface)
        self._tcp_server.startService()
        Service.startService(self)

    def stopService(self) -> Deferred:
        Service.stopService(self)
        return self._tcp_server.stopService()


class SynchronizeService(Service):
    def __init__(self, config: ProvdConfigDict) -> None:
        self._config = config

    def _new_sync_service_asterisk_ami(
        self,
    ) -> wazo_provd.synchronize.AsteriskAMISynchronizeService:
        amid_client = wazo_provd.synchronize.get_AMID_client(**self._config['amid'])
        return wazo_provd.synchronize.AsteriskAMISynchronizeService(amid_client)

    def _new_sync_service_none(self) -> None:
        return None

    def _new_sync_service(
        self, sync_service_type: str
    ) -> wazo_provd.synchronize.AsteriskAMISynchronizeService | None:
        name = f'_new_sync_service_{sync_service_type}'
        try:
            fun = getattr(self, name)
        except AttributeError:
            raise ValueError(f'unknown sync_service_type: {sync_service_type}')

        return fun()

    def startService(self) -> None:
        sync_service = self._new_sync_service(
            self._config['general']['sync_service_type']
        )
        if sync_service is not None:
            wazo_provd.synchronize.register_sync_service(sync_service)
        Service.startService(self)

    def stopService(self) -> None:
        Service.stopService(self)
        wazo_provd.synchronize.unregister_sync_service()


class LocalizationService(Service):
    def startService(self) -> None:
        l10n_service = wazo_provd.localization.LocalizationService()
        wazo_provd.localization.register_localization_service(l10n_service)
        Service.startService(self)

    def stopService(self) -> None:
        Service.stopService(self)
        wazo_provd.localization.unregister_localization_service()


class TokenRenewerService(Service):
    _token_renewer: TokenRenewer

    def __init__(
        self, prov_service: ProvisioningService, config: ProvdConfigDict
    ) -> None:
        self._config = config
        self._prov_service = prov_service

    def startService(self) -> None:
        app = self._prov_service.app
        auth_client = auth.get_auth_client(**self._config['auth'])
        amid_client = wazo_provd.synchronize.get_AMID_client(**self._config['amid'])
        self._token_renewer = TokenRenewer(auth_client)
        self._token_renewer.subscribe_to_token_change(app.set_token)
        self._token_renewer.subscribe_to_token_change(auth_client.set_token)
        self._token_renewer.subscribe_to_token_change(amid_client.set_token)
        self._token_renewer.start()
        Service.startService(self)

    def stopService(self) -> None:
        self._token_renewer.stop()
        Service.stopService(self)


class ProvdBusConsumer(BusConsumer):
    @classmethod
    def from_config(cls, bus_config: BusConfigDict) -> ProvdBusConsumer:
        return cls(name='wazo-provd', **bus_config)

    def provide_status(self, status: dict[str, Any]) -> None:
        status['bus_consumer']['status'] = (
            Status.ok if self.consumer_connected() else Status.fail
        )


class ResourcesDeletionService(Service):
    def __init__(self, prov_service, config):
        self._prov_service = prov_service
        self._config = config

    @defer.inlineCallbacks
    def delete_devices(self, tenant_uuid):
        app = self._prov_service.app
        find_arguments = {'selector': {'tenant_uuid': tenant_uuid}}
        devices = yield app.dev_find(**find_arguments)
        for device in devices:
            yield app.dev_delete(device['id'])

    def delete_tenant_configuration(self, tenant_uuid):
        configure_service = self._prov_service.app.configure_service
        all_tenants = configure_service.get('tenants')
        try:
            del all_tenants[tenant_uuid]
            configure_service.set('tenants', all_tenants)
        except KeyError:
            pass


class BusEventConsumerService(ResourcesDeletionService):
    _bus_consumer: BusConsumer | None

    @defer.inlineCallbacks
    def _auth_tenant_deleted(
        self, event: dict[str, Any]
    ) -> Generator[Deferred, None, None]:
        logger.info("auth_tenant_deleted event consumed: %s", event)
        tenant_uuid = event['uuid']
        yield self.delete_devices(tenant_uuid)
        self.delete_tenant_configuration(tenant_uuid)

    def startService(self) -> None:
        self._bus_consumer = ProvdBusConsumer.from_config(self._config['bus'])
        status.get_status_aggregator().add_provider(self._bus_consumer.provide_status)
        self._bus_consumer.subscribe('auth_tenant_deleted', self._auth_tenant_deleted)

        self._bus_consumer.start()
        Service.startService(self)

    def stopService(self) -> None:
        if self._bus_consumer:
            self._bus_consumer.stop()
        self._bus_consumer = None
        Service.stopService(self)


class SyncdbService(ResourcesDeletionService):
    def __init__(
        self, prov_service: ProvisioningService, config: ProvdConfigDict
    ) -> None:
        super().__init__(prov_service, config)
        auth_client = auth.get_auth_client(**self._config['auth'])
        auth.get_auth_verifier().set_client(auth_client)
        self._looping_call = task.LoopingCall(self.remove_resources_for_deleted_tenants)

    def startService(self) -> None:
        start_sec = int(self._config['general']['syncdb']['start_sec'])
        reactor.callLater(start_sec, self.on_service_started)

    def on_service_started(self) -> None:
        interval_sec = ONE_DAY_SEC
        try:
            interval_sec = int(self._config['general']['syncdb']['interval_sec'])
        except KeyError:
            pass
        self._looping_call.start(
            interval_sec,
            now=True,
        )

    @defer.inlineCallbacks
    def remove_resources_for_deleted_tenants(self) -> Deferred:
        auth_client = auth.get_auth_client()
        auth_tenants = {
            tenant['uuid'] for tenant in auth_client.tenants.list()['items']
        }
        yield self.remove_devices_for_deleted_tenants(auth_tenants)
        self.remove_configuration_for_deleted_tenants(auth_tenants)

    @defer.inlineCallbacks
    def remove_devices_for_deleted_tenants(self, auth_tenants) -> Deferred:
        app = self._prov_service.app

        find_arguments = {'selector': {'tenant_uuid': {'$nin': list(auth_tenants)}}}
        devices = yield app.dev_find(**find_arguments)
        provd_tenants = {device['tenant_uuid'] for device in devices}
        removed_tenants = provd_tenants - auth_tenants

        for t in removed_tenants:
            yield self.delete_devices(t)

    def remove_configuration_for_deleted_tenants(self, auth_tenants) -> None:
        app = self._prov_service.app

        provd_tenants = set(app.configure_service.get('tenants'))
        removed_tenants = provd_tenants - auth_tenants

        for tenant in removed_tenants:
            self.delete_tenant_configuration(tenant)

    def stopService(self) -> None:
        try:
            self._looping_call.stop()
        except builtins.AssertionError:
            logger.warning('Cannot stop looping call')
        Service.stopService(self)


@implementer(IServiceMaker, IPlugin)
class ProvisioningServiceMaker:
    tapname = 'wazo-provd'
    description = 'A provisioning server.'
    options = wazo_provd.config.Options

    def _configure_logging(self, options: Options) -> None:
        setup_logging(LOG_FILE_NAME, debug=options['verbose'])
        security.setup_logging()
        silence_loggers(['amqp.connection.Connection.heartbeat_tick'], logging.INFO)

    def _read_config(self, options: Options) -> ProvdConfigDict:
        logger.info('Reading application configuration')
        return wazo_provd.config.get_config(options)

    def makeService(self, options: Options) -> MultiService:
        self._configure_logging(options)

        config = self._read_config(options)
        top_service = MultiService()

        # check config for verbosity
        if config['general']['verbose']:
            logging.getLogger().setLevel(logging.DEBUG)

        sync_service = SynchronizeService(config)
        sync_service.setServiceParent(top_service)

        l10n_service = LocalizationService()
        l10n_service.setServiceParent(top_service)

        prov_service = ProvisioningService(config)
        prov_service.setServiceParent(top_service)

        token_renewer_service = TokenRenewerService(prov_service, config)
        token_renewer_service.setServiceParent(top_service)

        process_service = ProcessService(prov_service, config)
        process_service.setServiceParent(top_service)

        http_proxied_process_service = HTTPProxiedProcessService(
            prov_service, process_service, config
        )
        http_proxied_process_service.setServiceParent(top_service)

        tftp_process_service = TFTPProcessService(prov_service, process_service, config)
        tftp_process_service.setServiceParent(top_service)

        dhcp_process_service = DHCPProcessService(process_service)
        dhcp_process_service.setServiceParent(top_service)

        remote_config_service = RemoteConfigurationService(
            prov_service, dhcp_process_service, config
        )
        remote_config_service.setServiceParent(top_service)

        consumer_service = BusEventConsumerService(prov_service, config)
        consumer_service.setServiceParent(top_service)

        syncdb_service = SyncdbService(prov_service, config)
        syncdb_service.setServiceParent(top_service)

        return top_service
