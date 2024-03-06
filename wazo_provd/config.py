# Copyright 2010-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Provisioning server configuration module.

Read raw parameter values from different sources and return a dictionary
with well-defined values.

The following parameters are defined:
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
        tftp_port
        verbose
        sync_service_type
        asterisk_ami_servers
        advertised_http_url
            The HTTP URL advertised to phones
    rest_api:
        ip
        port
        ssl
        ssl_certfile
        ssl_keyfile
    auth:
        host
        port
        prefix
        https
        key_file
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


# XXX there is some naming confusion between application configuration
#     and device configuration, since both used the word 'config' and
#     raw config, yet they mean different things
from __future__ import annotations

import json
import logging
import os.path
from typing import Any, Literal, TypedDict, Union, cast
from urllib.parse import urlparse

from twisted.python import usage
from xivo.chain_map import ChainMap
from xivo.config_helper import parse_config_file, read_config_file_hierarchy


class AuthCredentialDict(TypedDict):
    username: Union[str, None]
    password: Union[str, None]


class AuthKeyFileDict(TypedDict):
    auth: AuthCredentialDict


class SyncDbConfigDict(TypedDict):
    interval_sec: int
    start_sec: int


class GeneralConfig(TypedDict):
    http_proxied_listen_interface: str
    http_proxied_listen_port: int
    http_proxied_trusted_proxies_count: int
    advertised_http_url: Union[str, None]
    base_raw_config: dict[str, Any]
    base_raw_config_file: str
    request_config_dir: str
    cache_dir: str
    cache_plugin: bool
    check_compat_min: bool
    check_compat_max: bool
    base_storage_dir: str
    plugin_server: str
    info_extractor: str
    retriever: str
    updater: str
    tftp_port: int
    verbose: bool
    sync_service_type: str
    syncdb: SyncDbConfigDict
    http_auth_strategy: Union[Literal['url_key'], None]


class RestApiConfigDict(TypedDict):
    ip: str
    port: int
    ssl: bool
    ssl_certfile: Union[str, None]
    ssl_keyfile: Union[str, None]


class AuthConfigDict(TypedDict):
    host: str
    port: int
    prefix: Union[str, None]
    https: bool
    key_file: str


class DatabaseConfigDict(TypedDict):
    type: str
    generator: Literal['default', 'numeric', 'uuid']
    ensure_common_indexes: bool
    json_db_dir: str
    uri: str
    pool_size: int


class AmidConfigDict(TypedDict):
    host: str
    port: int
    prefix: Union[str, None]
    https: bool


class BusConfigDict(TypedDict):
    username: str
    password: str
    host: str
    port: int
    exchange_name: str
    exchange_type: str


class ProvdConfigDict(TypedDict):
    config_file: str
    extra_config_files: str
    general: GeneralConfig
    rest_api: RestApiConfigDict
    auth: AuthConfigDict
    database: DatabaseConfigDict
    amid: AmidConfigDict
    bus: BusConfigDict
    plugin_config: dict[str, Any]
    tenants: dict[str, dict]
    proxy: dict[str, str]


logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: ProvdConfigDict = {
    'config_file': '/etc/wazo-provd/config.yml',
    'extra_config_files': '/etc/wazo-provd/conf.d',
    'general': {
        'advertised_http_url': None,
        'base_raw_config': {},
        'base_raw_config_file': '/etc/wazo-provd/base_raw_config.json',
        'request_config_dir': '/etc/wazo-provd',
        'cache_dir': '/var/cache/wazo-provd',
        'cache_plugin': True,
        'check_compat_min': True,
        'check_compat_max': True,
        'base_storage_dir': '/var/lib/wazo-provd',
        'plugin_server': 'http://provd.wazo.community/plugins/2/stable/',
        'info_extractor': 'default',
        'retriever': 'default',
        'updater': 'default',
        'tftp_port': 69,
        'http_proxied_listen_interface': '127.0.0.1',
        'http_proxied_listen_port': 18667,
        'http_proxied_trusted_proxies_count': 1,
        'verbose': False,
        'sync_service_type': 'none',
        'syncdb': {
            'interval_sec': 86400,
            'start_sec': 60,
        },
        'http_auth_strategy': None,
    },
    'rest_api': {
        'ip': '127.0.0.1',
        'port': 8666,
        'ssl': False,
        'ssl_certfile': None,
        'ssl_keyfile': None,
    },
    'auth': {
        'host': 'localhost',
        'port': 9497,
        'prefix': None,
        'https': False,
        'key_file': '/var/lib/wazo-auth-keys/wazo-provd-key.yml',
    },
    'database': {
        'type': 'json',
        'generator': 'default',
        'ensure_common_indexes': True,
        'json_db_dir': 'jsondb',
        'uri': (
            'postgresql://asterisk:proformatique'
            '@localhost/asterisk?application_name=wazo-provd'
        ),
        'pool_size': 16,
    },
    'amid': {
        'host': 'localhost',
        'port': 9491,
        'prefix': None,
        'https': False,
    },
    'bus': {
        'username': 'guest',
        'password': 'guest',
        'host': 'localhost',
        'port': 5672,
        'exchange_name': 'wazo-headers',
        'exchange_type': 'headers',
    },
    'plugin_config': {},
    'proxy': {},
    'tenants': {},
}

_OPTION_TO_PARAM_LIST = [
    # (<option name, (<section, param name>)>)
    ('config-file', ('general', 'config_file')),
    ('config-dir', ('general', 'request_config_dir')),
    ('tftp-port', ('general', 'tftp_port')),
    ('rest-port', ('general', 'rest_port')),
]


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
        ('config-file', 'f', None, 'The configuration file'),
        (
            'config-dir',
            'c',
            None,
            'The directory where request processing configuration file can be found',
        ),
        ('tftp-port', None, None, 'The TFTP port to listen on.'),
        ('rest-port', None, None, 'The port to listen on.'),
    ]


def _convert_cli_to_config(options: Options) -> dict[str, Any]:
    raw_config: dict[str, Any] = {'general': {}}
    for option_name, (section, param_name) in _OPTION_TO_PARAM_LIST:
        if options[option_name] is not None:
            raw_config[section][param_name] = options[option_name]
    if options['verbose']:
        raw_config['general']['verbose'] = True
    return raw_config


def _load_json_file(raw_value: str) -> dict[str, Any]:
    # Return a dictionary representing the JSON document contained in the
    # file pointed by raw value. The file must be encoded in UTF-8.
    with open(raw_value) as f:
        return json.load(f)


def _check_and_convert_parameters(raw_config: dict[str, Any]) -> None:
    if raw_config['rest_api']['ssl']:
        if 'ssl_certfile' not in raw_config['rest_api']:
            raise ConfigError('Missing parameter "ssl_certfile"')
        if 'ssl_keyfile' not in raw_config['rest_api']:
            raise ConfigError('Missing parameter "ssl_keyfile"')

    # load base_raw_config_file JSON document
    # XXX maybe we should put this in a separate method since it's more or less
    #     a check and not really a convert...
    raw_config['general']['base_raw_config'] = _load_json_file(
        raw_config['general']['base_raw_config_file']
    )


def _update_general_base_raw_config(app_raw_config: dict[str, Any]) -> None:
    # warning: raw_config in the function name means device raw config and
    # the app_raw_config argument means application configuration.
    base_raw_config = app_raw_config['general']['base_raw_config']
    if 'tftp_port' not in base_raw_config:
        base_raw_config['tftp_port'] = app_raw_config['general']['tftp_port']
    if 'http_base_url' not in base_raw_config:
        base_raw_config['http_base_url'] = app_raw_config['general'][
            'advertised_http_url'
        ]
    # Compatibility for plugins released before 23.17
    if 'ip' not in base_raw_config:
        base_raw_config['ip'] = urlparse(base_raw_config['http_base_url']).hostname
    if 'http_port' not in base_raw_config:
        extracted_port = urlparse(base_raw_config['http_base_url']).port
        base_raw_config['http_port'] = extracted_port or '8667'


def _post_update_raw_config(raw_config: dict[str, Any]) -> None:
    # Update raw config after transformation/check
    _update_general_base_raw_config(raw_config)
    # update json_db_dir to absolute dir
    if 'json_db_dir' in raw_config['database']:
        raw_config['database']['json_db_dir'] = os.path.join(
            raw_config['general']['base_storage_dir'],
            raw_config['database']['json_db_dir'],
        )


def _load_key_file(config: dict[str, Any]) -> AuthKeyFileDict:
    key_file = parse_config_file(config['auth']['key_file'])
    return {
        'auth': {
            'username': key_file.get('service_id'),
            'password': key_file.get('service_key'),
        }
    }


def get_config(argv: Options) -> ProvdConfigDict:
    """Pull the raw parameters values from the configuration sources and
    return a config dictionary.
    """
    cli_config = _convert_cli_to_config(argv)
    file_config = read_config_file_hierarchy(ChainMap(cli_config, _DEFAULT_CONFIG))
    service_key = _load_key_file(ChainMap(cli_config, file_config, _DEFAULT_CONFIG))
    raw_config = ChainMap(cli_config, service_key, file_config, _DEFAULT_CONFIG)
    _check_and_convert_parameters(raw_config)
    _post_update_raw_config(raw_config)
    return cast(ProvdConfigDict, raw_config)
