# Copyright 2010-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Config and config collection module.

Config objects are dictionaries, with the usual restrictions associated with
the fact they may be persisted in a document collection.

Config objects have the following standardized keys:
  id -- the IDs of this config object (unicode) (mandatory)
  parent_ids -- the IDs of parent config object (list of unicode) (mandatory)
  raw_config -- the configuration parameters of this config (dict) (mandatory)
  role -- the role of the config (unicode) (optional).
    Right now, two roles have been standardized:
    - the 'default' role: a config with such a role means that this
      config should be used for devices which have
      no config associated. There should be zero or one config with such a role
      in a collection.
    - the 'autocreate' role: a config with such a role means that this config is
      used as a base config to create config with the autocreate config device
      updater.
  transient -- a boolean indicating if the config is transient (boolean).
    A transient config will be automatically deleted if no device depends on
    it. Note that you MUST not use a transient config as a parent of another
    config, or you'll get undefined behaviour.

Config collection objects are used as a storage for config objects.

"""
from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict
from copy import deepcopy
from enum import Enum
from functools import wraps
from pydantic import BaseModel, root_validator, Field, validator
from typing import Union, Any, Literal, TypedDict
from zoneinfo import ZoneInfo

from twisted.internet import defer

from provd.persist.common import ID_KEY
from provd.persist.util import ForwardingDocumentCollection
from provd.util import decode_bytes, create_model_from_typeddict

"""Specification of the configuration parameters.

This section specify the general form of configuration parameters and the
meaning and usage of standardized parameters.

This specification use the words MUST, SHOULD, MAY as defined in RFC2119.

Except when explicitly stated, unsupported parameters or supported parameters
with unsupported values SHOULD be ignored. For example, if your device has
no notion of timezone, or the plugin doesn't support configuring the timezone,
or the timezone value is not known from the plugin, then the timezone parameter
SHOULD be ignored and an exception SHOULD NOT be raised.

Parameter names are [unicode] string that MUST match the following regex:
[a-zA-Z_][a-zA-Z0-9_]*.

An IP address is a [unicode] string representing an IPv4 address in dotted
quad notation.

A port number is an integer between 1 and 65535 inclusive.

Beside each parameter definition is a specification telling if the parameter
must be found in the raw config passed to the plugin, and also specify what
the plugin can expect to receive.


_comment [optional]
  Used as a standard way to add a human-readable comment in the raw config.
  This value MUST be ignored by plugins.

ip [deprecated. Use http_base_url instead]
  The IP address or domain name of the provisioning server.
  If the followings are true:
  - this value represent a domain name
  - the device does not support the use of domain names
  then:
  - an exception (RawConfigError) MAY be raised or the device MAY be
    misconfigured.
  This means that if you use domain names, you should manually check that
  your devices support it or be prepared to see incorrect behaviour from
  your devices.

http_port [deprecated. Use http_base_url instead]
  The provisioning server HTTP port number.
  If the followings are true:
  - this value is defined
  - the device supports retrieving its configuration file via HTTP
  then:
  - the device MUST be configured to use HTTP to retrieve its configuration
    files (if applicable). If it does not support the port number value, it
    MUST raise an exception (RawConfigError).
  If the device only support HTTP yet this value is not defined, an Exception
  SHOULD be raised.

http_base_url [mandatory]
  Used in place of the ip and http_port to be able to define the URL at which
  the provisioning server is accessible from. This allows to set the provisioning
  server behind a reverse proxy.
  If you are using a `url_key` strategy for provisioning authentication (provisioning
  key), then you MUST use this setting as the key is appended to this value.
  This option has precedence over the deprecated ip + http_port combination.

tftp_port [mandatory if http_base_url is not defined]
  The provisioning server TFTP port number.
  If the followings are true:
  - this value is defined
  - the device supports retrieving its configuration file via TFTP
  - the http_base_url parameter is not defined or the device does not support
    retrieving its configuration file via HTTP
  then:
  - the device MUST be configured to use TFTP to retrieve its configuration
    files (if applicable). If it does not support the port number value, it
    MUST raise an Exception.
  If the device only support TFTP yet this value is not defined, an Exception
  SHOULD be raised.

dns_enabled [optional]
  A boolean indicating if DNS is enabled or not.
  If this parameter is not defined or is false, all the dns_* parameters
  MUST be ignored.

dns_ip [mandatory if dns_enabled is true]
  The IP address of a DNS server.

ntp_enabled [optional]
  A boolean indicating if NTP is enabled or not.
  If this parameter is not defined or is false, NTP MUST be disabled and
  all the ntp_* parameters MUST be ignored.

ntp_ip [mandatory if ntp_enabled is true]
  The IP address or domain name of a NTP server.
  See: ip (comment about domain name).

vlan_enabled [optional]
  A boolean indicating if VLAN is enabled or not.
  If this parameter is not defined or is false, VLAN must be disabled and
  all the vlan_* parameters MUST be ignored.

vlan_id [mandatory if vlan_enabled is true]
  The VLAN ID. An integer between 0 and 4094.
  A value of 0 means that the frame does not belong to any VLAN; in this
  case only a priority is specified.

vlan_priority [optional]
  The (802.1p) priority. A integer between 0 and 7 inclusive.

vlan_pc_port_id [optional]
  The VLAN ID of the PC port. An integer between 0 and 4094.
  This means that tagged frame with the specified VLAN ID received by
  the device on its LAN port should be forwarded (tagged) on the PC
  port, and vice-versa.
  If this parameter is not defined, then untagged frame received by the
  device on its LAN port SHOULD be forwarded untagged on the PC port, and
  vice-versa.

syslog_enabled [optional]
  A boolean indicating if syslog is enabled or not.
  If this parameter is not defined or is false, syslog MUST be disabled and
  all the syslog_* parameters MUST be ignored.

syslog_ip [mandatory if syslog_enabled]
  The IP address of a syslog server.

syslog_port [optional|default to 514]
  The port of the syslog server.

syslog_level [optional|default to 'warning']
  The debug level to enable on the device.
  This parameter can take one of the following value:
  - critical
  - error
  - warning
  - info
  - debug

admin_username [optional]
  The administrator username. When applicable, the administrator account gives
  full access to the device (either via a web interface or a physical interface
  like a phone UI for example).

admin_password [optional]
  The administrator password.
  See: admin_username.

user_username [optional]
  The user username. When applicable, the user account gives limited access to
  the device.
  See: admin_username.

user_password [optional]
  The user password.
  See: admin_password.

timezone [optional]
  The name of the timezone from the tz/zoneinfo/Olson database.
  Example:
  - Europe/Paris
  - America/Montreal
  See: http://www.twinsun.com/tz/tz-link.htm.

locale [optional]
  The locale name. This is an ISO 639-1 code followed by an ISO 3166-1 alpha-2
  code. The codes are similar to what is found in /etc/locale.gen, except that
  it doesn't use the modifier and charset part.
  Example of possible values:
  - fr_FR
  - en_CA

protocol [optional]
  The signaling protocol.
  This parameter can take one of the following value:
  - SIP
  - SCCP
  If the protocol is not supported by the device, an exception
  (RawConfigError) MAY be raised or the device MAY be misconfigured.
  You SHOULD only specify this parameter in the case your device and its
  associated plugin have multi-protocol support.

sip_proxy_ip [mandatory if proxy_ip is not defined on a per line basis and there's at least 1 line]
  The IP address of the SIP proxy.
  If the device does not support a SIP proxy on a per line basis and this
  this parameter is not defined, an exception SHOULD be raised.
  If the device does not support the proxy/registrar separation, the
  value of this parameter will be used as the registrar IP.

sip_proxy_port [optional]
  The port of the SIP proxy.

sip_backup_proxy_ip [optional]
  The IP address of the backup SIP proxy.

sip_backup_proxy_port [optional]
  The port of the backup SIP proxy.

sip_registrar_ip [optional|default to value of proxy_ip]
  The IP address of the SIP registrar.
  See: proxy_ip.

sip_registrar_port [optional]
  The port of the SIP registrar.

sip_backup_registrar_ip [optional]
  The IP address of the backup SIP registrar

sip_backup_registrar_port [optional]
  The port of the backup SIP registrar.

sip_outbound_proxy_ip [optional]
  The IP address of the SIP outbound proxy.

sip_outbound_proxy_port [optional]
  The port of the SIP outbound proxy.

sip_dtmf_mode [optional]
  The mode used to send DTMF and other events.
  This parameter can take one of the following value:
  - RTP-in-band
  - RTP-out-of-band
  - SIP-INFO
  If this parameter is not defined and the device has some support for
  automatically picking the DTMF mode, then the device should be
  configured this way.

sip_srtp_mode [optional|default to 'disabled']
  The RTP/SRTP mode.
  This parameter can take one of the following values:
  - disabled
  - preferred
  - required

sip_transport [optional|default to 'udp']
  The transport type for SIP messages.
  This parameter can take one of the following values:
  - udp
  - tcp
  - tls

sip_servers_root_and_intermediate_certificates [optional]
  The list of certificates that participated in the signing of the
  servers certificates, i.e. of the server the device will connect to,
  in PEM format. The list must be ordered by certificate signing, i.e.
  the root certificate must be the first in the list.

sip_local_root_and_intermediate_certificates [optional]
  The list of certificates that participated in the signing of the
  local certificate, in PEM format. The list must be ordered by
  certificate signing, i.e. the root certificate must be the first in
  the list.

sip_local_certificate [optional]
  The local certificate, in PEM format.

sip_local_key [optional]
  The private key which is related to the public key in the local
  certificate, in PEM format.

sip_subscribe_mwi [optional]
  A boolean indicating if we should explicitly subscribe for message
  notification or not.

sip_lines [optional|default to empty dictionary]
  A dictionary where keys are line number (unicode string) and values are
  dictionaries with the following keys:

    proxy_ip [mandatory if proxy_ip is not defined globally]
      See sip_proxy_ip.

    proxy_port [optional]
      See sip_proxy_port.

    backup_proxy_ip [optional]
      See sip_backup_proxy_ip.

    backup_proxy_port [optional]
      See sip_backup_proxy_port.

    registrar_ip [optional|default to value of proxy_ip]
      See sip_registrar_ip.

    registrar_port [optional]
      See sip_registrar_port.

    backup_registrar_ip [optional]
      See sip_backup_registrar_ip.

    backup_registrar_port [optional]
      See sip_backup_registrar_port.

    outbound_proxy_ip [optional]
      See sip_outbound_proxy_ip.

    outbound_proxy_port [optional]
      See sip_outbound_proxy_port.

    username [mandatory]
      The username of this SIP identity.

    auth_username [optional|default to value of username]
      The username used for authentication (i.e. the username in the SIP
      Authorization or Proxy-Authorization header field).
      If the device doesn't allow the auth username to be different from
      the username, then the username MUST be used for authentication.

    password [mandatory]
      The password used for authentication.

    display_name [mandatory]
      The display name to use in the From header field. It should also be
      usable as a label for the line.

    number [optional]
      The main extension number other users can dial to reach this line.
      This parameter is for display purpose only.

    dtmf_mode [optional]
      See: sip_dtmf_mode.

    srtp_mode [optional]
      See: sip_srtp_mode.

    voicemail [optional]
      The extension number to retrieve voicemail for this line.
      See: exten_voicemail.

sccp_call_managers [optional|default to empty dictionary]
  A dictionary where keys are priority number (unicode string representing
  integers > 0, where 1 is the highest priority) and values are dictionaries
  with the following keys:

    ip [mandatory]
      The IP address of the call manager.

    port [optional]
      The port number of the call manager.

exten_dnd [optional]
  The extension number to enable/disable 'do not disturb'.

exten_fwd_unconditional [optional]
  The extension number prefix to unable unconditional forward.

exten_fwd_no_answer [optional]
  The extension number prefix to unable forward on no-answer.

exten_fwd_busy [optional]
  The extension number prefix to unable forward on busy.

exten_fwd_disable_all [optional]
  The extension number prefix to disable every call forward.

exten_park [optional]
  The park extension number.

exten_pickup_group [optional]
  The extension number to pick up a call to a group.

exten_pickup_call [optional]
  The extension number prefix to pick up a call.

exten_voicemail [optional]
  The extension number to retrieve voicemail.

funckeys [optional|default to empty dictionary]
  A dictionary where keys are function key number (unicode string representing
  integers > 0) and values are dictionary:

    type [mandatory]
      The type of the function key.
      This parameter can take one of the following value:
      - speeddial
      - blf
      - park
      Note that when possible, a blf function key should also be usable as
      a speeddial function key.

    value [mandatory if type is speeddial or blf]
      The value of the function key.
      For the speeddial type, this is an extension number.
      For the blf type, this is the monitored extension number.
      For the park type, this is the parking extension number.

    label [optional]
      The label.

    line [optional]
      The line number (as an integer).

Non-standard parameter names must begin with 'X_'. A unique second level ID
should be used to prevent name clashes. Here's the list of parameters in
the 'X_xivo_' namespace:

X_xivo_phonebook_ip [optional]
  Remote XiVO phonebook service

Parameter names starting with 'XX_' must not be used. They are reserved for
plugins usage. For example, a plugin can use these names to push/pass plugin
specific values to a template.

"""

logger = logging.getLogger(__name__)

INTEGER_KEY_REGEX = re.compile(r"^[0-9]+$")


class SyslogLevel(str, Enum):
    CRITICAL = 'critical'
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'
    DEBUG = 'debug'


class DtmfMode(str, Enum):
    RTP_IN_BAND = 'RTP-in-band'
    RTP_OUT_OF_BAND = 'RTP-out-of-band'
    SIP_INFO = 'SIP-INFO'


class SrtpMode(str, Enum):
    DISABLED = 'disabled'
    PREFERRED = 'preferred'
    REQUIRED = 'required'


class Transport(str, Enum):
    UDP = 'udp'
    TCP = 'tcp'
    TLS = 'tls'


class FuncKeyType(str, Enum):
    SPEED_DIAL = 'speeddial'
    BLF = 'blf'
    PARK = 'park'


class SipLineSchema(BaseModel):
    proxy_ip: Union[str, None]
    proxy_port: Union[int, None]
    backup_proxy_ip: Union[str, None]
    backup_proxy_port: Union[int, None]
    registrar_ip: Union[str, None]
    registrar_port: Union[int, None]
    backup_registrar_ip: Union[str, None]
    backup_registrar_port: Union[int, None]
    outbound_proxy_ip: Union[str, None]
    outbound_proxy_port: Union[int, None]
    username: str = Field(...)
    password: str = Field(...)
    auth_username: Union[str, None]
    display_name: str = Field(...)
    number: Union[str, None]
    dtmf_mode: Union[DtmfMode, None]
    srtp_mode: Union[SrtpMode, None]
    voicemail: Union[str, None]

    class Config:
        use_enum_values = True


class CallManagerSchema(BaseModel):
    ip: str = Field(...)
    port: Union[int, None]


class FuncKeyDict(TypedDict):
    type: FuncKeyType
    value: Union[str, None]
    label: Union[str, None]
    line: Union[str, None]


@root_validator
def validate_type_if_required(cls, values: dict[str, Any]) -> dict[str, Any]:
    if not values.get('value') and values.get('type') in (
        FuncKeyType.BLF,
        FuncKeyType.SPEED_DIAL,
    ):
        raise ValueError('Value is required for BLF and Speed Dial types.')
    return values


FuncKeySchema = create_model_from_typeddict(
    FuncKeyDict,
    {"type": Field(...)},
    {'validate_type_if_required': validate_type_if_required},
)


class RawConfigDict(TypedDict):
    ip: str
    http_port: Union[int, None]
    http_base_url: Union[str, None]
    tftp_port: Union[int, None]
    dns_enabled: Union[bool, None]
    dns_ip: Union[str, None]
    ntp_enabled: Union[bool, None]
    ntp_ip: Union[str, None]
    vlan_enabled: Union[bool, None]
    vlan_id: Union[int, None]
    vlan_priority: Union[int, None]
    vlan_pc_port_id: Union[int, None]
    syslog_enabled: Union[bool, None]
    syslog_ip: Union[str, None]
    syslog_port: int
    syslog_level: SyslogLevel
    admin_username: Union[str, None]
    admin_password: Union[str, None]
    user_username: Union[str, None]
    user_password: Union[str, None]
    timezone: Union[ZoneInfo, str, None]
    locale: Union[str, None]
    protocol: Union[Literal['SIP', 'SCCP'], None]
    sip_proxy_ip: Union[str, None]
    sip_proxy_port: Union[int, None]
    sip_backup_proxy_ip: Union[str, None]
    sip_backup_proxy_port: Union[int, None]
    sip_registrar_ip: Union[str, None]
    sip_registrar_port: Union[int, None]
    sip_backup_registrar_ip: Union[str, None]
    sip_backup_registrar_port: Union[int, None]
    sip_outbound_proxy_ip: Union[str, None]
    sip_outbound_proxy_port: Union[int, None]
    sip_dtmf_mode: Union[DtmfMode, None]
    sip_srtp_mode: Union[SrtpMode, None]
    sip_transport: Union[Transport, None]
    sip_servers_root_and_intermediate_certificates: Union[list[str], None]
    sip_local_root_and_intermediate_certificates: Union[list[str], None]
    sip_local_certificate: Union[str, None]
    sip_local_key: Union[str, None]
    sip_subscribe_mwi: Union[bool, None]
    sip_lines: dict[str, SipLineSchema]
    sccp_call_managers: dict[str, CallManagerSchema]
    exten_dnd: Union[str, None]
    exten_fwd_unconditional: Union[str, None]
    exten_fwd_no_answer: Union[str, None]
    exten_fwd_busy: Union[str, None]
    exten_fwd_disable_all: Union[str, None]
    exten_park: Union[str, None]
    exten_pickup_group: Union[str, None]
    exten_pickup_call: Union[str, None]
    exten_voicemail: Union[str, None]
    funckeys: dict[str, FuncKeySchema]  # type: ignore[valid-type]
    X_xivo_phonebook_ip: Union[str, None]


class SchemaConfig:
    extra = "allow"
    use_enum_values = True
    arbitrary_types_allowed = True


@validator('timezone')
def validate_timezone(cls: type[BaseModel], value: str | None) -> ZoneInfo | None:
    return ZoneInfo(value) if value else None


@validator('sccp_call_managers', 'funckeys')
def validate_numeric_keys(
    cls: type[BaseModel], value: dict[str, Any]
) -> dict[str, Any]:
    if not all(INTEGER_KEY_REGEX.match(k) for k in value):
        raise ValueError("Dictionary keys must be a positive integer in string format.")
    return value


@root_validator
def validate_values(cls: type[BaseModel], values: dict[str, Any]) -> dict[str, Any]:
    if not values.get('tft_port') and not values.get('http_port'):
        raise ValueError('You must define either `tftp_port` or `http_port`.')

    required_if_enabled = (
        ('dns', 'ip'),
        ('ntp', 'ip'),
        ('vlan', 'id'),
        ('syslog', 'ip'),
    )
    for field, name in required_if_enabled:
        if not values.get(f'{field}_{name}') and values.get(f'{field}_enabled'):
            raise ValueError(f'Field `{name}_{field}` is required if {name} is enabled')

    custom_fields = set(values) - {field.alias for field in cls.__fields__.values()}
    if any(not custom_field.startswith('X_') for custom_field in custom_fields):
        raise ValueError('Custom fields must start with `X_`')

    return values


RawConfigSchema = create_model_from_typeddict(
    RawConfigDict,
    {
        "ip": Field(...),
        "funckeys": Field(default_factory=dict),
        "locale": Field(regex=r'[a-z]{2}_[A-Z]{2}'),
        "syslog_port": Field(514),
        "syslog_level": Field(SyslogLevel.WARNING),
        "sip_srtp_mode": Field(SrtpMode.DISABLED),
        "sip_transport": Field(Transport.UDP),
        "sip_lines": Field(default_factory=dict),
        "sccp_call_managers": Field(default_factory=dict),
        "vlan_id": Field(gte=0, lte=4094),
        "vlan_priority": Field(gte=0, lte=7),
        "vlan_pc_port_id": Field(gte=0, lte=4094),
    },
    {
        "validate_timezone": validate_timezone,
        "validate_numeric_keys": validate_numeric_keys,
        "validate_values": validate_values,
    },
    config=SchemaConfig,
)


class ConfigDict(BaseModel):
    id: str
    parent_ids: list[str]
    raw_config: RawConfigSchema  # type: ignore[valid-type]
    transient: bool


ConfigSchema = create_model_from_typeddict(
    ConfigDict,
    {
        "id": Field(...),
        "parent_ids": Field(...),
        "raw_config": Field(...),
        "transient": Field(...),
    },
)
ConfigSchema.update_forward_refs(RawConfigSchema=RawConfigSchema)


class RawConfigError(Exception):
    """Raised when the raw config is not valid."""

    pass


class RawConfigParamError(RawConfigError):
    """Raised when a specific parameter of the raw config is not valid."""

    pass


def _rec_update_dict(base_dict, overlay_dict):
    # update a base dictionary from another dictionary
    for k, v in overlay_dict.items():
        if isinstance(v, dict):
            old_v = base_dict.get(k)
            if isinstance(old_v, dict):
                _rec_update_dict(old_v, v)
            else:
                base_dict[k] = {}
                _rec_update_dict(base_dict[k], v)
        else:
            base_dict[k] = v


def _check_config_validity(config):
    if 'parent_ids' not in config:
        raise ValueError('missing "parent_ids" field in config')
    if not isinstance(config['parent_ids'], list):
        raise ValueError(
            '"parent_ids" field must be a list; is %s' % type(config['parent_ids'])
        )
    for parent_id in config['parent_ids']:
        if not isinstance(parent_id, str):
            raise ValueError(f'parent id must be a string; is {type(parent_id)}')

    if 'raw_config' not in config:
        raise ValueError('missing "raw_config" field in config')

    raw_config = config['raw_config']
    if not isinstance(raw_config, dict):
        raise ValueError(
            f'"raw_config" field must be a dict; is {type(config["raw_config"])}'
        )


def _needs_child_and_parent_indexes(fun):
    # Method wrapped by this decorator will return a deferred.
    # Note: to be used only with method on a ConfigCollection.
    @wraps(fun)
    def aux(self, *args, **kwargs):
        if self._has_child_and_parent_indexes():
            return defer.maybeDeferred(fun, self, *args, **kwargs)
        else:

            def callback(_):
                assert self._has_child_and_parent_indexes()
                return fun(self, *args, **kwargs)

            deferred = self._build_child_and_parent_indexes()
            deferred.addCallback(callback)
            return deferred

    return aux


# This method is for compatibility reasons for the following provisioning plugins:
# wazo-htek, xivo-aastra, xivo-alcatel, xivo-avaya, xivo-cisco-sccp, xivo-cisco-spa, xivo-fanvil,
# xivo-grandstream, xivo-jitsi, xivo-panasonic, xivo-patton, xivo-polycom, xivo-snom,
# xivo-technicolor, xivo-yealink, xivo-zenitel
# These plugins assume that because a key exists (with the in operator), the value is valid.
# However, sometimes the value is None and this causes issues.
def _remove_none_values_for_device(config):
    if config.get('X_type') == 'device':
        return _remove_none_values(config)
    return config


def _remove_none_values(config):
    if isinstance(config, list):
        return [_remove_none_values(x) for x in config]
    if isinstance(config, dict):
        return {k: _remove_none_values(v) for k, v in config.items() if v is not None}
    return config


class ConfigCollection(ForwardingDocumentCollection):
    @defer.inlineCallbacks
    def _build_child_and_parent_indexes(self):
        # XXX it's possible to have this method executed twice, for example
        #     if during the time to yield another methods call this method,
        #     etc, we should use a lock, twisted is such a pain sometimes,
        #     but then it's only about efficiency (doing the same job twice
        #     is less efficient than only once...)
        logger.debug('Building child and parent indexes')
        child_idx = defaultdict(list)
        parent_idx = {}
        configs = yield self._collection.find({})
        for config in configs:
            config_id = config[ID_KEY]
            parent_ids = config['parent_ids']
            for parent_id in parent_ids:
                child_idx[parent_id].append(config_id)
            # update parent_idx
            parent_idx[config_id] = list(parent_ids)
        self._child_idx = child_idx
        self._parent_idx = parent_idx

    def _has_child_and_parent_indexes(self):
        return hasattr(self, '_child_idx') and hasattr(self, '_parent_idx')

    @_needs_child_and_parent_indexes
    def insert(self, config):
        config = _remove_none_values_for_device(config)
        _check_config_validity(config)

        def callback(config_id):
            config_id = decode_bytes(config_id)
            parent_ids = config['parent_ids']
            # update child idx
            for parent_id in parent_ids:
                if parent_id in self._child_idx:
                    self._child_idx[parent_id].append(config_id)
                else:
                    self._child_idx[parent_id] = [config_id]
            # update parent idx
            self._parent_idx[config_id] = list(parent_ids)
            return config_id

        deferred = self._collection.insert(config)
        deferred.addCallback(callback)
        return deferred

    @_needs_child_and_parent_indexes
    def update(self, config):
        config = _remove_none_values_for_device(config)
        _check_config_validity(config)

        def callback(_):
            config_id = decode_bytes(config[ID_KEY])
            new_parent_ids = config['parent_ids']
            old_parent_ids = self._parent_idx[config_id]
            if new_parent_ids != old_parent_ids:
                # update idx of children
                for parent_id in old_parent_ids:
                    children = self._child_idx[parent_id]
                    children.remove(config_id)
                    if not children:
                        del self._child_idx[parent_id]
                for parent_id in new_parent_ids:
                    if parent_id in self._child_idx:
                        self._child_idx[parent_id].append(config_id)
                    else:
                        self._child_idx[parent_id] = [config_id]
                # update parent idx
                self._parent_idx[config_id] = list(new_parent_ids)

        deferred = self._collection.update(config)
        deferred.addCallback(callback)
        return deferred

    @_needs_child_and_parent_indexes
    def delete(self, config_id):
        config_id = decode_bytes(config_id)

        def callback(_):
            # update idx of children
            old_parent_ids = self._parent_idx[config_id]
            for parent_id in old_parent_ids:
                children = self._child_idx[parent_id]
                children.remove(config_id)
                if not children:
                    del self._child_idx[parent_id]
            # update parent idx
            del self._parent_idx[config_id]

        deferred = self._collection.delete(config_id)
        deferred.addCallback(callback)
        return deferred

    @_needs_child_and_parent_indexes
    def get_ancestors(self, config_id):
        """Return a deferred that will fire with the set of ancestors of the
        config with the given ID, i.e. the set of config ID that the given
        config depends on, directly or indirectly, or fire with an empty set
        if id is unknown.

        """
        visited = set()

        def aux(cur_id):
            if cur_id in self._parent_idx:
                for parent_id in self._parent_idx[cur_id]:
                    if parent_id not in visited:
                        visited.add(parent_id)
                        aux(parent_id)

        aux(decode_bytes(config_id))
        return visited

    @_needs_child_and_parent_indexes
    def get_descendants(self, config_id):
        """Return a deferred that will fire with the set of descendants of the
        config with the given ID, i.e. the set of config ID that depends on
        this config, directly or indirectly, or fire with an empty set if id
        is unknown.

        """
        visited = set()

        def aux(cur_id):
            if cur_id in self._child_idx:
                for child_id in self._child_idx[cur_id]:
                    if child_id not in visited:
                        visited.add(child_id)
                        aux(child_id)

        aux(decode_bytes(config_id))
        return visited

    def get_raw_config(self, config_id, base_raw_config=None):
        """Return a deferred that will fire with a raw config with every
        parameter from its ancestors' config, or fire with None if id is not
        a known ID.

        """
        # flattened_raw_config is set to a copy of base_raw_config only once
        # we know that the id is valid. This is a bit ugly, but it's the
        # simplest thing to do.
        # Also, flattened_raw_config is a list since we don't have a nonlocal
        # statement like in python3, and can't rebind the name in an inner
        # scope...
        flattened_raw_config = [None]
        visited = {config_id}
        if base_raw_config is None:
            base_raw_config = {}

        @defer.inlineCallbacks
        def aux(cur_id):
            config = yield self._collection.retrieve(cur_id)
            if config is not None:
                if flattened_raw_config[0] is None:
                    flattened_raw_config[0] = deepcopy(base_raw_config)
                for parent_id in config['parent_ids']:
                    if parent_id not in visited:
                        visited.add(parent_id)
                        yield aux(parent_id)
                _rec_update_dict(flattened_raw_config[0], config['raw_config'])

        d = aux(decode_bytes(config_id))
        d.addCallback(lambda _: flattened_raw_config[0])
        return d


def build_autocreate_config(config: dict[str, Any]) -> dict[str, Any] | None:
    try:
        config['raw_config']['sip_lines']['1']
    except KeyError:
        return None

    config_id = config['id']
    new_suffix = str(uuid.uuid4())
    return {
        'id': config_id + new_suffix,
        'parent_ids': [config_id],
        'raw_config': config['raw_config'],
        'transient': True,
    }
