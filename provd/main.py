# -*- coding: utf-8 -*-

# Copyright 2010-2018 The Wazo Authors  (see the AUTHORS file)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import logging
import os.path
import provd.config
import provd.localization
import provd.synchronize
from provd import security
from provd.app import ProvisioningApplication
from provd.devices.config import ConfigCollection
from provd.devices.device import DeviceCollection
from provd.devices import ident
from provd.devices import pgasso
from provd.servers.tftp.proto import TFTPProtocol
from provd.servers.http_site import Site, Resource
from provd.persist.json_backend import JsonDatabaseFactory
from provd.rest.server.server import new_server_resource, \
    new_restricted_server_resource
from twisted.application.service import IServiceMaker, Service, MultiService
from twisted.application import internet
from twisted.internet import ssl
from twisted.plugin import IPlugin
from twisted.python import log
from twisted.python.util import sibpath
from provd.rest.api.resource import ResponseFile
from xivo.xivo_logging import setup_logging
from zope.interface.declarations import implements

logger = logging.getLogger(__name__)

LOG_FILE_NAME = '/var/log/xivo-provd.log'


# given in command line to redirect logs to standard logging
def twistd_logs():
    return log.PythonLoggingObserver().emit


class ProvisioningService(Service):
    # has an 'app' attribute after starting

    _DB_FACTORIES = {
        'json': JsonDatabaseFactory(),
    }

    def __init__(self, config):
        self._config = config

    def _extract_database_specific_config(self):
        db_config = {}
        for k, v in self._config.iteritems():
            pre, sep, post = k.partition('.')
            if pre == 'database' and sep and post not in ['type', 'generator']:
                db_config[post] = v
        return db_config

    def _create_database(self):
        db_type = self._config['database.type']
        db_generator = self._config['database.generator']
        db_specific_config = self._extract_database_specific_config()
        logger.info('Using %s database with %s generator and config %s',
                    db_type, db_generator, db_specific_config)
        db_factory = self._DB_FACTORIES[db_type]
        return db_factory.new_database(db_type, db_generator, **db_specific_config)

    def _close_database(self):
        logger.info('Closing database...')
        try:
            self._database.close()
        except Exception:
            logger.error('Error while closing database', exc_info=True)
        logger.info('Database closed')

    def startService(self):
        self._database = self._create_database()
        try:
            cfg_collection = ConfigCollection(self._database.collection('configs'))
            dev_collection = DeviceCollection(self._database.collection('devices'))
            if self._config['database.ensure_common_indexes']:
                logger.debug('Ensuring index existence on collections')
                try:
                    dev_collection.ensure_index(u'mac')
                    dev_collection.ensure_index(u'ip')
                    dev_collection.ensure_index(u'sn')
                except AttributeError, e:
                    logger.warning('This type of database doesn\'t seem to support index: %s', e)
            self.app = ProvisioningApplication(cfg_collection, dev_collection, self._config)
        except Exception:
            try:
                raise
            finally:
                self._close_database()
        else:
            Service.startService(self)

    def stopService(self):
        Service.stopService(self)
        try:
            self.app.close()
        except Exception:
            logger.error('Error while closing application', exc_info=True)
        self._close_database()


class ProcessService(Service):
    def __init__(self, prov_service, config):
        self._prov_service = prov_service
        self._config = config

    def _get_conffile_globals(self):
        # Pre: hasattr(self._prov_service, 'app')
        conffile_globals = {}
        conffile_globals.update(ident.__dict__)
        conffile_globals.update(pgasso.__dict__)
        conffile_globals['app'] = self._prov_service.app
        return conffile_globals

    def _create_processor(self, name):
        # name is the name of the processor, for example 'info_extractor'
        dirname = self._config['general.request_config_dir']
        config_name = self._config['general.' + name]
        filename = '%s.py.conf.%s' % (name, config_name)
        pathname = os.path.join(dirname, filename)
        conffile_globals = self._get_conffile_globals()
        try:
            execfile(pathname, conffile_globals)
        except Exception, e:
            logger.error('error while executing process config file "%s": %s', pathname, e)
            raise
        if name not in conffile_globals:
            raise Exception('process config file "%s" doesn\'t define a "%s" name',
                            pathname, name)
        return conffile_globals[name]

    def startService(self):
        # Pre: hasattr(self._prov_service, 'app')
        dev_info_extractor = self._create_processor('info_extractor')
        dev_retriever = self._create_processor('retriever')
        dev_updater = self._create_processor('updater')
        self.request_processing = ident.RequestProcessingService(self._prov_service.app, dev_info_extractor,
                                                                 dev_retriever, dev_updater)
        Service.startService(self)


class HTTPProcessService(Service):
    def __init__(self, prov_service, process_service, config):
        self._prov_service = prov_service
        self._process_service = process_service
        self._config = config

    def startService(self):
        app = self._prov_service.app
        process_service = self._process_service.request_processing
        http_process_service = ident.HTTPRequestProcessingService(process_service, app.pg_mgr)
        site = Site(http_process_service)
        port = self._config['general.http_port']
        logger.info('Binding HTTP provisioning service to port %s', port)
        self._tcp_server = internet.TCPServer(port, site, backlog=128)
        self._tcp_server.startService()
        Service.startService(self)

    def stopService(self):
        Service.stopService(self)
        return self._tcp_server.stopService()


class TFTPProcessService(Service):
    def __init__(self, prov_service, process_service, config):
        self._prov_service = prov_service
        self._process_service = process_service
        self._config = config
        self._tftp_protocol = TFTPProtocol()

    def privilegedStartService(self):
        port = self._config['general.tftp_port']
        logger.info('Binding TFTP provisioning service to port %s', port)
        self._udp_server = internet.UDPServer(port, self._tftp_protocol)
        self._udp_server.privilegedStartService()
        Service.privilegedStartService(self)

    def startService(self):
        app = self._prov_service.app
        process_service = self._process_service.request_processing
        tftp_process_service = ident.TFTPRequestProcessingService(process_service, app.pg_mgr)
        self._tftp_protocol.set_tftp_request_processing_service(tftp_process_service)
        Service.startService(self)

    def stopService(self):
        Service.stopService(self)
        return self._udp_server.stopService()


class DHCPProcessService(Service):
    # has a 'dhcp_request_processing_service' attribute once started
    def __init__(self, process_service):
        self._process_service = process_service

    def startService(self):
        process_service = self._process_service.request_processing
        self.dhcp_request_processing_service = ident.DHCPRequestProcessingService(process_service)
        Service.startService(self)


class RemoteConfigurationService(Service):
    def __init__(self, prov_service, dhcp_process_service, config):
        self._prov_service = prov_service
        self._dhcp_process_service = dhcp_process_service
        self._config = config

    def startService(self):
        app = self._prov_service.app
        dhcp_request_processing_service = self._dhcp_process_service.dhcp_request_processing_service
        if self._config['general.rest_authentication']:
            credentials = (self._config['general.rest_username'],
                           self._config['general.rest_password'])
            server_resource = new_restricted_server_resource(app, dhcp_request_processing_service, credentials)
            logger.info('Authentication is required for REST API')
        else:
            server_resource = new_server_resource(app, dhcp_request_processing_service)
            logger.warning('No authentication is required for REST API')
        root_resource = Resource()
        api_resource = Resource()
        api_resource.putChild('api.yml', ResponseFile(sibpath(__file__, 'rest/api/api.yml')))
        root_resource.putChild('api', api_resource)
        root_resource.putChild('provd', server_resource)
        rest_site = Site(root_resource)

        port = self._config['general.rest_port']
        interface = self._config['general.rest_ip']
        if interface == '*':
            interface = ''
        logger.info('Binding HTTP REST API service to "%s:%s"', interface, port)
        if self._config['general.rest_ssl']:
            logger.info('SSL enabled for REST API')
            context_factory = ssl.DefaultOpenSSLContextFactory(self._config['general.rest_ssl_keyfile'],
                                                               self._config['general.rest_ssl_certfile'])
            self._tcp_server = internet.SSLServer(port, rest_site, context_factory, interface=interface)
        else:
            self._tcp_server = internet.TCPServer(port, rest_site, interface=interface)
        self._tcp_server.startService()
        Service.startService(self)

    def stopService(self):
        Service.stopService(self)
        return self._tcp_server.stopService()


class SynchronizeService(Service):
    def __init__(self, config):
        self._config = config

    def _new_sync_service_asterisk_ami(self):
        server_list = self._config['general.asterisk_ami_servers']
        servers = []
        for server in server_list:
            host, port, tls, user, pwd = server
            servers.append({'host': host, 'port': port, 'enable_tls': tls,
                            'username': user, 'password': pwd})
        return provd.synchronize.AsteriskAMISynchronizeService(servers)

    def _new_sync_service_none(self):
        return None

    def _new_sync_service(self, sync_service_type):
        name = '_new_sync_service_' + sync_service_type
        try:
            fun = getattr(self, name)
        except AttributeError:
            raise ValueError('unknown sync_service_type: %s' %
                             sync_service_type)
        else:
            return fun()

    def startService(self):
        sync_service = self._new_sync_service(self._config['general.sync_service_type'])
        if sync_service is not None:
            provd.synchronize.register_sync_service(sync_service)
        Service.startService(self)

    def stopService(self):
        Service.stopService(self)
        provd.synchronize.unregister_sync_service()


class LocalizationService(Service):
    def _new_l10n_service(self):
        return provd.localization.LocalizationService()

    def startService(self):
        l10n_service = self._new_l10n_service()
        provd.localization.register_localization_service(l10n_service)
        Service.startService(self)

    def stopService(self):
        Service.stopService(self)
        provd.localization.unregister_localization_service()


class _CompositeConfigSource(object):
    def __init__(self, options):
        self._options = options

    def pull(self):
        raw_config = {}

        default = provd.config.DefaultConfigSource()
        raw_config.update(default.pull())

        command_line = provd.config.CommandLineConfigSource(self._options)
        raw_config.update(command_line.pull())

        config_file = provd.config.ConfigFileConfigSource(raw_config['general.config_file'])
        raw_config.update(config_file.pull())

        return raw_config


class ProvisioningServiceMaker(object):
    implements(IServiceMaker, IPlugin)

    tapname = 'xivo-provd'
    description = 'A provisioning server.'
    options = provd.config.Options

    def _configure_logging(self, options):
        setup_logging(LOG_FILE_NAME, options['stderr'], options['verbose'])
        security.setup_logging()

    def _read_config(self, options):
        logger.info('Reading application configuration')
        config_sources = [_CompositeConfigSource(options)]
        return provd.config.get_config(config_sources)

    def makeService(self, options):
        self._configure_logging(options)

        config = self._read_config(options)
        top_service = MultiService()

        # check config for verbosity
        if config['general.verbose']:
            logging.getLogger().setLevel(logging.DEBUG)

        sync_service = SynchronizeService(config)
        sync_service.setServiceParent(top_service)

        l10n_service = LocalizationService()
        l10n_service.setServiceParent(top_service)

        prov_service = ProvisioningService(config)
        prov_service.setServiceParent(top_service)

        process_service = ProcessService(prov_service, config)
        process_service.setServiceParent(top_service)

        http_process_service = HTTPProcessService(prov_service, process_service, config)
        http_process_service.setServiceParent(top_service)

        tftp_process_service = TFTPProcessService(prov_service, process_service, config)
        tftp_process_service.setServiceParent(top_service)

        dhcp_process_service = DHCPProcessService(process_service)
        dhcp_process_service.setServiceParent(top_service)

        remote_config_service = RemoteConfigurationService(prov_service, dhcp_process_service, config)
        remote_config_service.setServiceParent(top_service)

        return top_service
