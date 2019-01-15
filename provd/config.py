# -*- coding: utf-8 -*-
# Copyright 2010-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Provisioning server configuration module.

Read raw parameter values from different sources and return a dictionary
with well defined values.

The following parameters are defined (parameters that can be set in the
configuration file are documented in provd.conf):
    config_file
    extra_config_files
    general:
        _raw_config_file
        _raw_config
            The dictionary holding the base raw config.
        request_config_dir
        cache_dir
        cache_plugin
        check_compat_min
        check_compat_max
        base_storage_dir
        plugin_server
        info_extractor
        retriever
        updater
        external_ip
        http_port
        tftp_port
        rest_port
        rest_ip
        rest_username
        rest_password
        rest_authentication
        rest_ssl
        rest_ssl_certfile
        rest_ssl_keyfile
        verbose
        sync_service_type
        asterisk_ami_servers
    database:
        type
        generator
        ensure_common_indexes
        json_db_dir
    plugin_config:
        *
            *
        where the first * subsection is a plugin ID and each sub-subsection * is a parameter
        for the plugin with the given ID
    proxy:
        http
        ftp
        https
        *
            The proxy for * protocol requests.

"""


# XXX there's is some naming confusion between application configuration
#     and device configuration, since both used the word 'config' and
#     raw config yet it means different thing

import logging
import json
import os.path
import socket
from twisted.python import usage
from xivo.chain_map import ChainMap
from xivo.config_helper import read_config_file_hierarchy

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raise when an error occur while getting configuration."""
    pass


class Options(usage.Options):
    # The 'stderr' option should probably be defined somewhere else but
    # it's more practical to define it here. It SHOULD NOT be inserted
    # in the config though.
    optFlags = [
        ('stderr', 's', 'Log to standard error instead of syslog.'),
        ('verbose', 'v', 'Increase verbosity.'),
    ]

    optParameters = [
        ('config-file', 'f', None,
         'The configuration file'),
        ('config-dir', 'c', None,
         'The directory where request processing configuration file can be found'),
        ('http-port', None, None,
         'The HTTP port to listen on.'),
        ('tftp-port', None, None,
         'The TFTP port to listen on.'),
        ('rest-port', None, None,
         'The port to listen on.'),
    ]


def _convert_cli_to_config(options):
    raw_config = {'general': {}}
    for option_name, (section, param_name) in _OPTION_TO_PARAM_LIST:
        if options[option_name] is not None:
            raw_config[section][param_name] = options[option_name]
    if options['verbose']:
        raw_config['general']['verbose'] = True
    return raw_config


def _port_number(raw_value):
    port = int(raw_value)
    if not 1 <= port <= 65535:
        raise ValueError('invalid port number "%s"' % str)
    return port


def _ip_address(raw_value):
    return norm_ip(raw_value)


def _ip_address_or_star(raw_value):
    if raw_value == '*':
        return raw_value
    else:
        return _ip_address(raw_value)


_BOOL_TRUE = ['True', 'true', '1']
_BOOL_FALSE = ['False', 'false', '0']


def _bool(raw_value):
    if raw_value in _BOOL_TRUE:
        return True
    elif raw_value in _BOOL_FALSE:
        return False
    else:
        raise ValueError('invalid boolean raw value "%s"' % raw_value)


def _bool_or_str(raw_value):
    if raw_value in _BOOL_TRUE:
        return True
    elif raw_value in _BOOL_FALSE:
        return False
    else:
        return raw_value


def _ast_ami_server(raw_value):
    try:
        value = eval(raw_value)
    except Exception as e:
        raise ValueError(e)
    else:
        if isinstance(value, list):
            for e in value:
                if isinstance(e, tuple) and len(e) == 5:
                    pass
                else:
                    break
            else:
                return value
        raise ValueError('invalid asterisk ami server: %s' % value)


def _load_json_file(raw_value):
    # Return a dictionary representing the JSON document contained in the
    # file pointed by raw value. The file must be encoded in UTF-8.
    fobj = open(raw_value)
    try:
        return json.load(fobj)
    finally:
        fobj.close()


def _process_aliases(raw_config):
    if 'general.ip' in raw_config and 'general.external_ip' not in raw_config:
        raw_config['general.external_ip'] = raw_config['general.ip']


_PARAMS_DEFINITION = [
    # list only the mandatory parameters or the parameters that need
    # transformation
    # (<param name>: (<transform/check function>, <is mandatory?>))
    ('general.base_raw_config_file', (str, True)),
    ('general.request_config_dir', (str, True)),
    ('general.cache_dir', (str, True)),
    ('general.cache_plugin', (_bool, True)),
    ('general.check_compat_min', (_bool, True)),
    ('general.check_compat_max', (_bool, True)),
    ('general.base_storage_dir', (str, True)),
    ('general.info_extractor', (str, True)),
    ('general.retriever', (str, True)),
    ('general.updater', (str, True)),
    ('general.external_ip', (_ip_address, False)),
    ('general.http_port', (_port_number, True)),
    ('general.tftp_port', (_port_number, True)),
    ('general.rest_ip', (_ip_address_or_star, True)),
    ('general.rest_port', (_port_number, True)),
    ('general.wazo_auth_host', (str, True)),
    ('general.wazo_auth_port', (int, True)),
    ('general.wazo_auth_verify_certificate', (_bool_or_str, True)),
    ('general.rest_ssl', (_bool, True)),
    ('general.verbose', (_bool, True)),
    ('general.sync_service_type', (str, True)),
    ('general.asterisk_ami_servers', (_ast_ami_server, False)),
    ('database.type', (str, True)),
    ('database.generator', (str, True)),
    ('database.ensure_common_indexes', (_bool, True))
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
            except Exception as e:
                raise ConfigError('parameter "%s" is invalid: %s' % (param_name, e))
    if raw_config['general.rest_ssl']:
        if 'general.rest_ssl_certfile' not in raw_config:
            raise ConfigError('Missing parameter "rest_ssl_certfile"')
        if 'general.rest_ssl_keyfile' not in raw_config:
            raise ConfigError('Missing parameter "rest_ssl_keyfile"')
    # load base_raw_config_file JSON document
    # XXX maybe we should put this in a separate method since it's more or less
    #     a check and not really a convert...
    raw_config['general.base_raw_config'] = _load_json_file(raw_config['general.base_raw_config_file'])


_BASE_RAW_CONFIG_UPDATE_LIST = [
    # (<dev raw config param name, app raw config param name>
    (u'http_port', 'general.http_port'),
    (u'tftp_port', 'general.tftp_port'),
]


def _get_ip_fallback():
    # This function might return an IP address of a loopback interface, but we
    # don't care since it's not possible to determine implicitly which IP address
    # we should use anyway.
    return socket.gethostbyname(socket.gethostname())


def _update_general_base_raw_config(app_raw_config):
    # warning: raw_config in the function name means device raw config and
    # the app_raw_config argument means application configuration.
    base_raw_config = app_raw_config['general.base_raw_config']
    for key, source_param_name in _BASE_RAW_CONFIG_UPDATE_LIST:
        if key not in base_raw_config:
            # currently, we only refer to always specified config parameters,
            # so next line will never raise a KeyError
            base_raw_config[key] = app_raw_config[source_param_name]
    if u'ip' not in base_raw_config:
        if 'general.external_ip' in app_raw_config:
            external_ip = app_raw_config['general.external_ip']
        else:
            external_ip = _get_ip_fallback()
            logger.warning('Using "%s" for base raw config ip parameter', external_ip)
        base_raw_config[u'ip'] = external_ip


def _post_update_raw_config(raw_config):
    # Update raw config after transformation/check
    _update_general_base_raw_config(raw_config)
    # update json_db_dir to absolute dir
    if 'database.json_db_dir' in raw_config:
        raw_config['database.json_db_dir'] = os.path.join(raw_config['general.base_storage_dir'],
                                                          raw_config['database.json_db_dir'])


def get_config(argv):
    """Pull the raw parameters values from the configuration sources and
    return a config dictionary.
    """
    cli_config = _convert_cli_to_config(argv)
    file_config = read_config_file_hierarchy(ChainMap(cli_config, _DEFAULT_CONFIG))
    raw_config = ChainMap(cli_config, file_config, _DEFAULT_CONFIG)
    _process_aliases(raw_config)
    _check_and_convert_parameters(raw_config)
    _post_update_raw_config(raw_config)
    return raw_config
