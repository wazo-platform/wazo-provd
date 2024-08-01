"""
Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
SPDX-License-Identifier: GPL-3.0-or-later

**NOTE**: `annotations` are not intentionally imported from __future__.
This is to avoid lazy evaluation of annotations in this file and simplify the logic
of the `create_model_from_typeddict`. This can be remedied if we upgrade to
pydantic 1.9+ and can use their more robust implementation.
"""
import re
import uuid
from enum import Enum
from ipaddress import IPv4Address
from typing import Any, Literal, TypedDict, Union
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, root_validator, validator

from wazo_provd.util import _NORMED_MAC, create_model_from_typeddict

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


class SchemaConfig:
    extra = "ignore"
    use_enum_values = True
    arbitrary_types_allowed = True


class SipLineDict(TypedDict):
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
    username: Union[str, None]
    password: Union[str, None]
    auth_username: Union[str, None]
    display_name: Union[str, None]
    number: Union[str, None]
    dtmf_mode: Union[DtmfMode, None]
    srtp_mode: Union[SrtpMode, None]
    voicemail: Union[str, None]


SipLineSchema = create_model_from_typeddict(SipLineDict, config=SchemaConfig)


class CallManagerDict(TypedDict):
    ip: str
    port: Union[int, None]


CallManagerSchema = create_model_from_typeddict(
    CallManagerDict, {'ip': Field(...)}, config=SchemaConfig
)


class FuncKeyDict(TypedDict):
    type: FuncKeyType
    value: Union[str, None]
    label: Union[str, None]
    line: Union[str, None]


@root_validator(allow_reuse=True)
def validate_type_if_required(
    cls: type[BaseModel], values: dict[str, Any]
) -> dict[str, Any]:
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
    config=SchemaConfig,
)


class RawConfigDict(TypedDict):
    ip: Union[str, None]
    http_port: Union[int, None]
    http_base_url: str
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
    syslog_port: Union[int, None]
    syslog_level: Union[int, None]
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
    sip_lines: Union[dict[str, SipLineDict], None]
    sccp_call_managers: Union[dict[str, CallManagerDict], None]
    exten_dnd: Union[str, None]
    exten_fwd_unconditional: Union[str, None]
    exten_fwd_no_answer: Union[str, None]
    exten_fwd_busy: Union[str, None]
    exten_fwd_disable_all: Union[str, None]
    exten_park: Union[str, None]
    exten_pickup_group: Union[str, None]
    exten_pickup_call: Union[str, None]
    exten_voicemail: Union[str, None]
    funckeys: Union[dict[str, FuncKeyDict], None]
    X_xivo_phonebook_ip: Union[str, None]
    X_xivo_phonebook_profile: Union[str, None]
    X_xivo_user_uuid: Union[str, None]


@validator('timezone', allow_reuse=True)
def validate_timezone(
    cls: type[BaseModel], value: Union[str, None]
) -> Union[ZoneInfo, None]:
    return ZoneInfo(value) if value else None


@validator('sccp_call_managers', 'funckeys', allow_reuse=True)
def validate_numeric_keys(
    cls: type[BaseModel], value: Union[dict[str, Any], None]
) -> Union[dict[str, Any], None]:
    if not value:
        return None
    if not all(INTEGER_KEY_REGEX.match(k) for k in value):
        raise ValueError("Dictionary keys must be a positive integer in string format.")
    return value


@root_validator(allow_reuse=True)
def validate_values(cls: type[BaseModel], values: dict[str, Any]) -> dict[str, Any]:
    required_if_enabled = (
        ('dns', 'ip'),
        ('ntp', 'ip'),
        ('vlan', 'id'),
        ('syslog', 'ip'),
    )
    for field, name in required_if_enabled:
        if not values.get(f'{field}_{name}') and values.get(f'{field}_enabled'):
            raise ValueError(f'Field `{name}_{field}` is required if {name} is enabled')

    return values


RawConfigSchema = create_model_from_typeddict(
    RawConfigDict,
    {
        "ip": Field(),
        "funckeys": Field(default_factory=dict, alias="function_keys"),
        "locale": Field(regex=r'[a-z]{2}_[A-Z]{2}'),
        "syslog_port": Field(514),
        "syslog_level": Field(SyslogLevel.WARNING),
        "sip_srtp_mode": Field(SrtpMode.DISABLED),
        "sip_transport": Field(Transport.UDP),
        "sip_lines": Field(default_factory=dict),
        "sccp_call_managers": Field(default_factory=dict, alias="sccp_lines"),
        "vlan_id": Field(gte=0, lte=4094),
        "vlan_priority": Field(gte=0, lte=7),
        "vlan_pc_port_id": Field(gte=0, lte=4094),
        "X_xivo_phonebook_ip": Field(alias="phonebook_ip"),
        "X_xivo_phonebook_profile": Field(alias="phonebook_profile"),
        "X_xivo_user_uuid": Field(alias="user_uuid"),
    },
    {
        "validate_timezone": validate_timezone,
        "validate_numeric_keys": validate_numeric_keys,
        "validate_values": validate_values,
    },
    config=SchemaConfig,
    type_overrides={
        'funckeys': Union[dict[str, FuncKeySchema], None],  # type: ignore[valid-type]
        'sip_lines': Union[dict[str, SipLineSchema], None],  # type: ignore[valid-type]
        'sccp_call_managers': (
            Union[dict[str, CallManagerSchema], None]  # type: ignore[valid-type]
        ),
    },
)


class BaseConfigDict(TypedDict):
    id: Union[str, None]
    parent_id: Union[str, None]
    raw_config: Union[RawConfigDict, None]


class ConfigDict(BaseConfigDict, total=False):
    transient: bool
    deletable: bool
    X_type: Union[str, None]
    label: Union[str, None]
    role: Union[str, None]
    registrar_main: Union[str, None]
    registrar_main_port: Union[int, None]
    proxy_main: Union[str, None]
    proxy_main_port: Union[int, None]
    proxy_outbound: Union[str, None]
    proxy_outbound_port: Union[int, None]
    registrar_backup: Union[str, None]
    registrar_backup_port: Union[int, None]
    proxy_backup: Union[str, None]
    proxy_backup_port: Union[int, None]


ConfigSchema = create_model_from_typeddict(
    ConfigDict,
    {
        "id": Field(regex=r'^[0-9a-z_-]+$'),
        "X_type": Field(alias="type"),
    },
    config=SchemaConfig,
    type_overrides={'raw_config': Union[RawConfigSchema, None]},  # type: ignore[valid-type]
)


class BaseDeviceDict(TypedDict, total=False):
    id: Union[str, None]
    mac: Union[str, None]
    ip: Union[str, None]
    config: Union[str, None]
    model: Union[str, None]
    plugin: Union[str, None]
    description: Union[str, None]
    configured: bool
    is_new: bool
    vendor: Union[str, None]
    version: Union[str, None]


class DeviceDict(BaseDeviceDict, total=False):
    tenant_uuid: str
    added: str


@validator('tenant_uuid', pre=True)
def validate_tenant_uuid(
    cls: type[BaseModel], value: Union[uuid.UUID, None]
) -> Union[str, None]:
    return str(value) if value else None


@validator('ip')
def validate_ip(cls: type[BaseModel], value: Union[str, None]) -> Union[str, None]:
    return str(IPv4Address(value)) if value else None


DeviceSchema = create_model_from_typeddict(
    DeviceDict,
    {
        "id": Field(regex=r'^[0-9a-z]+$'),
        "mac": Field(regex=_NORMED_MAC.pattern),
        "config": Field(alias="config_id"),
        "added": Field(default="auto"),
    },
    {
        "validate_tenant_uuid": validate_tenant_uuid,
        "validate_ip": validate_ip,
    },
    config=SchemaConfig,
)
