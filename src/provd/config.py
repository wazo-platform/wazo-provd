# -*- coding: UTF-8 -*-

"""Provisioning server configuration module.

Read raw parameter values from different sources and return a dictionary
with well defined values.

The following parameters are defined:
    general.config_file
    general.base_raw_config_file
        File containing a JSON document representing the base raw config.
    general.base_raw_config
        A dictionary holding the base raw config.
    general.request_config_dir 
        Directory where request processing configuration files can be found
    general.cache_dir
    general.plugins_dir
    general.http_proxy
        HTTP proxy for plugin downloads, etc
    general.plugin_server
        URL of the plugin server (where plugins are downloaded)
    general.info_extractor
    general.retriever
    general.updater
    general.router
    general.ip
        The IP address to bind to, or '*' to bind on all local IP.
    general.http_port
    general.tftp_port
    general.rest_port
    general.rest_ip
    general.rest_username
    general.rest_password
    general.rest_is_public
    database.type
        The type of the 'database' used for storing devices and configs.
    database.generator
        The kind of generator used to generate ID for devices and configs.
    database.shelve_dir
        For 'shelve' database, the directory where files are stored.
    database.mongo_uri
        For 'mongo' database, the URI of the database.
    plugin_config.*.*
        where the first * is a plugin ID and the second * is a parameter
        name for the plugin with the given ID

"""

__version__ = "$Revision$ $Date$"
__license__ = """
    Copyright (C) 2010-2011  Proformatique <technique@proformatique.com>

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# XXX right now, bad parameter names will be silently ignored, and we might
#     want to raise an exception when we see a parameter that is invalid
# XXX better parameter documentation...
# XXX there's is some naming confusion between application configuration
#     and device configuration, since both used the word 'config' and
#     raw config yet it means different thing

import ConfigParser
import logging
import json
from provd.util import norm_ip
from twisted.python import usage

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raise when an error occur while getting configuration."""
    pass


class ConfigSourceError(ConfigError):
    """Raise when an error occur while pulling raw parameter values from
    a config source.
    
    """
    pass


class DefaultConfigSource(object):
    """A source of raw parameter values that always return the same default
    values.
    
    """
    
    _DEFAULT_RAW_PARAMETERS = [
        # (parameter name, parameter value)
        ('general.config_file', '/etc/pf-xivo/provd/provd.conf'),
        ('general.base_raw_config_file', '/etc/pf-xivo/provd/base_raw_config.json'),
        ('general.request_config_dir', '/etc/pf-xivo/provd'),
        ('general.cache_dir', '/var/cache/pf-xivo/provd'),
        ('general.plugins_dir', '/var/lib/pf-xivo/provd/plugins'),
        ('general.info_extractor', 'default'),
        ('general.retriever', 'default'),
        ('general.updater', 'default'),
        ('general.router', 'default'),
        ('general.ip', '*'),
        ('general.http_port', '8667'),
        ('general.tftp_port', '69'),
        ('general.rest_port', '8666'),
        ('general.rest_username', 'admin'),
        ('general.rest_password', 'admin'),
        ('general.rest_is_public', 'False'),
        ('database.type', 'shelve'),
        ('database.generator', 'default'),
        ('database.shelve_dir', '/var/lib/pf-xivo/provd/shelvedb'),
    ]
    
    def pull(self):
        return dict(self._DEFAULT_RAW_PARAMETERS)


class Options(usage.Options):
    # The 'stderr' and 'debug' options should probably be defined somewhere
    # else but it's more practical to define them here. They SHOULD NOT be
    # inserted in the config though.
    optFlags = [
        ('stderr', 's', 'Log to standard error instead of syslog.'),
        ('verbose', 'v', 'Increase verbosity.'),
    ]
    
    optParameters = [
        ('config-file', 'f', None,
         'The configuration file'),
        ('config-dir', 'c', None,
         'The directory where request processing configuration file can be found'),
        ('ip', None, None,
         'The IP address to listen on, or * to listen on every.'),
        ('http-port', None, None,
         'The HTTP port to listen on.'),
        ('tftp-port', None, None,
         'The TFTP port to listen on.'),
        ('rest-port', None, None,
         'The port to listen on.'),
    ]


class CommandLineConfigSource(object):
    """A source of raw parameter values coming from the an instance of the
    Options class defined above.
    
    """
    
    _OPTION_TO_PARAM_LIST = [
        # (<option name, param name>)
        ('config-file', 'general.config_file'),
        ('config-dir', 'general.request_config_dir'),
        ('ip', 'general.ip'),
        ('http-port', 'general.http_port'),
        ('tftp-port', 'general.tftp_port'),
        ('rest-port', 'general.rest_port'),
    ]
    
    def __init__(self, options):
        self.options = options
    
    def pull(self):
        raw_config = {}
        for option_name, param_name in self._OPTION_TO_PARAM_LIST:
            if self.options[option_name] is not None:
                raw_config[param_name] = self.options[option_name]
        return raw_config


class ConfigFileConfigSource(object):
    """A source of raw parameter values coming from a configuration file.
    See the example file to see what is the syntax of the configuration file.
    
    """
    
    _BASE_SECTIONS = ['general', 'database']
    _PLUGIN_SECTION_PREFIX = 'pluginconfig_'
    
    def __init__(self, filename):
        self.filename = filename
    
    def _get_config_from_section(self, config, section):
        # Note: config is a [Raw]ConfigParser object
        raw_config = {}
        if config.has_section(section):
            for name, value in config.items(section):
                raw_config_name = section + '.' + name 
                raw_config[raw_config_name] = value
        return raw_config
    
    def _get_pluginconfig_from_section(self, config, section):
        # Pre: config.has_section(section)
        # Pre: section.startswith(self._PLUGIN_SECTION_PREFIX)
        # Note: config is a [Raw]ConfigParser object
        raw_config = {}
        base_name = 'plugin_config.' + section[len(self._PLUGIN_SECTION_PREFIX):]
        for name, value in config.items(section):
            raw_config_name = base_name + '.' + name
            raw_config[raw_config_name] = value
        return raw_config
    
    def _get_pluginconfig(self, config):
        # Note: config is a [Raw]ConfigParser object
        raw_config = {}
        for section in config.sections():
            if section.startswith(self._PLUGIN_SECTION_PREFIX):
                raw_config.update(self._get_pluginconfig_from_section(config, section))
        return raw_config
    
    def _do_pull(self):
        config = ConfigParser.RawConfigParser()
        fobj = open(self.filename)
        try:
            config.readfp(fobj)
        finally:
            fobj.close()
        
        raw_config = {}
        for section in self._BASE_SECTIONS:
            raw_config.update(self._get_config_from_section(config, section))
        raw_config.update(self._get_pluginconfig(config))
        return raw_config
    
    def pull(self):
        try:
            return self._do_pull()
        except Exception, e:
            raise ConfigSourceError(e)


def _pull_config_from_sources(config_sources):
    raw_config = {}
    for config_source in config_sources:
        current_raw_config = config_source.pull()
        raw_config.update(current_raw_config)
    return raw_config


_RAW_CONFIG_UPDATE_LIST = [
    # <param name to set if absent>, <source param name to use if present>
    ('general.rest_ip', 'general.ip'),
]

def _pre_update_raw_config(raw_config):
    # Update raw config before transformation/check
    for param_name, source_param_name in _RAW_CONFIG_UPDATE_LIST:
        if param_name not in raw_config:
            if source_param_name in raw_config:
                raw_config[param_name] = raw_config[source_param_name]
            else:
                logger.info('Could not set config parameter "%s" because '
                            'source parameter "%s" is absent' %
                            (param_name, source_param_name))


def _port_number(raw_value):
    # Return a port number as an integer or raise a ValueError
    port = int(raw_value)
    if not 1 <= port <= 65535:
        raise ValueError('invalid port number "%s"' % str)
    return port


def _ip_address(raw_value):
    # Return an IP address as a string or raise a ValueError
    return norm_ip(raw_value)


def _ip_address_or_star(raw_value):
    if raw_value == '*':
        return raw_value
    else:
        return _ip_address(raw_value)


_BOOL_TRUE = ['True', 'true']
_BOOL_FALSE = ['False', 'false']

def _bool(raw_value):
    # Return a boolean (type boolean) from a boolean string representation
    if raw_value in _BOOL_TRUE:
        return True
    elif raw_value in _BOOL_FALSE:
        return False
    else:
        raise ValueError('invalid boolean raw value "%s"' % raw_value)


def _load_json_file(raw_value):
    # Return a dictionary representing the JSON document contained in the
    # file pointed by raw value. The file must be encoded in UTF-8.
    fobj = open(raw_value)
    try:
        return json.load(fobj)
    finally:
        fobj.close()


_PARAMS_DEFINITION = [
    # list only the mandatory parameters or the parameters that need
    # transformation
    # (<param name>: (<transform/check function>, <is mandatory?>))
    ('general.base_raw_config_file', (str, True)),
    ('general.request_config_dir', (str, True)),
    ('general.cache_dir', (str, True)),
    ('general.plugins_dir', (str, True)),
    ('general.info_extractor', (str, True)),
    ('general.retriever', (str, True)),
    ('general.updater', (str, True)),
    ('general.router', (str, True)),
    ('general.ip', (_ip_address_or_star, True)),
    ('general.http_port', (_port_number, True)),
    ('general.tftp_port', (_port_number, True)),
    ('general.rest_port', (_port_number, True)),
    ('general.rest_ip', (_ip_address_or_star, True)),
    ('general.rest_username', (str, True)),
    ('general.rest_password', (str, True)),
    ('general.rest_is_public', (_bool, True)),
    ('database.type', (str, True)),
    ('database.generator', (str, True)),
]

def _check_and_convert_parameters(raw_config):
    for param_name, (fun, mandatory) in _PARAMS_DEFINITION:
        # check if mandatory parameter is present
        if mandatory:
            if param_name not in raw_config:
                logger.warning('Mandatory parameter "%s" is missing', param_name)
                raise ConfigError('parameter "%s" is missing' % param_name)
        # convert parameter if present
        if param_name in raw_config:
            try:
                raw_config[param_name] = fun(raw_config[param_name])
            except Exception, e:
                logger.warning('Error while transforming/checking parameter "%s"',
                               param_name, exc_info=True)
                raise ConfigError('parameter "%s" is invalid: %s' %
                                  param_name, e)
    # load base_raw_config_file JSON document
    # XXX maybe we should put this in a separate method since it's more or less
    #     a check and not really a convert...
    raw_config['general.base_raw_config'] = _load_json_file(raw_config['general.base_raw_config_file'])


_BASE_RAW_CONFIG_UPDATE_LIST = [
    # (<dev raw config param name, app raw config param name>, <include if predicate>)
    (u'ip', 'general.ip', lambda x: x != '*'),
    (u'http_port', 'general.http_port', None),
    (u'tftp_port', 'general.tftp_port', None),
]

def _update_general_base_raw_config(app_raw_config):
    # warning: raw_config in the function name means device raw config and
    # the app_raw_config argument means application configuration.
    base_raw_config = app_raw_config['general.base_raw_config']
    for key, source_param_name, include_fun in _BASE_RAW_CONFIG_UPDATE_LIST:
        if key not in base_raw_config:
            # currently, we only refer to always specified config parameters,
            # so next line will never raise a KeyError
            source_param_value = app_raw_config[source_param_name]
            if include_fun is None or include_fun(source_param_value):
                base_raw_config[key] = source_param_value
            else:
                logger.info('Not including parameter "%s" in base raw config '
                            'because parameter value "%s" is not acceptable for '
                            'raw config parameter "%s"' %
                            (source_param_name, source_param_value, key))


def _post_update_raw_config(raw_config):
    # Update raw config after transformation/check
    _update_general_base_raw_config(raw_config)


def get_config(config_sources):
    """Pull the raw parameters values from the configuration sources and
    return a config dictionary.
    
    config_source is a sequence/iterable of objects with a pull method taking
    no arguments and returning a dictionary of raw parameter values.
    
    """
    raw_config = _pull_config_from_sources(config_sources)
    _pre_update_raw_config(raw_config)
    _check_and_convert_parameters(raw_config)
    _post_update_raw_config(raw_config)
    return raw_config
