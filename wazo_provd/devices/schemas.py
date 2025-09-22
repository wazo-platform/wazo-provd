"""
Copyright 2023-2024 The Wazo Authors  (see the AUTHORS file)
SPDX-License-Identifier: GPL-3.0-or-later

**NOTE**: `annotations` are not intentionally imported from __future__.
This is to avoid lazy evaluation of annotations in this file and simplify the logic
of the `create_model_from_typeddict`. This can be remedied if we upgrade to
pydantic 1.9+ and can use their more robust implementation.
"""
import re
from enum import Enum
from ipaddress import IPv4Address
from typing import Any, Literal, TypedDict
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
    extra = "allow"
    use_enum_values = True
    arbitrary_types_allowed = True


class SipLineDict(TypedDict):
    proxy_ip: str | None
    proxy_port: int | None
    backup_proxy_ip: str | None
    backup_proxy_port: int | None
    registrar_ip: str | None
    registrar_port: int | None
    backup_registrar_ip: str | None
    backup_registrar_port: int | None
    outbound_proxy_ip: str | None
    outbound_proxy_port: int | None
    username: str | None
    password: str | None
    auth_username: str | None
    display_name: str | None
    number: str | None
    dtmf_mode: DtmfMode | None
    srtp_mode: SrtpMode | None
    voicemail: str | None


SipLineSchema = create_model_from_typeddict(SipLineDict, config=SchemaConfig)


class CallManagerDict(TypedDict):
    ip: str
    port: int | None


CallManagerSchema = create_model_from_typeddict(CallManagerDict, {'ip': Field(...)})


class FuncKeyDict(TypedDict):
    type: FuncKeyType
    value: str | None
    label: str | None
    line: str | None


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
)


class RawConfigDict(TypedDict):
    ip: str | None
    http_port: int | None
    http_base_url: str
    tftp_port: int | None
    dns_enabled: bool | None
    dns_ip: str | None
    ntp_enabled: bool | None
    ntp_ip: str | None
    vlan_enabled: bool | None
    vlan_id: int | None
    vlan_priority: int | None
    vlan_pc_port_id: int | None
    syslog_enabled: bool | None
    syslog_ip: str | None
    syslog_port: int
    syslog_level: SyslogLevel
    admin_username: str | None
    admin_password: str | None
    user_username: str | None
    user_password: str | None
    timezone: ZoneInfo | str | None
    locale: str | None
    protocol: Literal['SIP', 'SCCP'] | None
    sip_proxy_ip: str | None
    sip_proxy_port: int | None
    sip_backup_proxy_ip: str | None
    sip_backup_proxy_port: int | None
    sip_registrar_ip: str | None
    sip_registrar_port: int | None
    sip_backup_registrar_ip: str | None
    sip_backup_registrar_port: int | None
    sip_outbound_proxy_ip: str | None
    sip_outbound_proxy_port: int | None
    sip_dtmf_mode: DtmfMode | None
    sip_srtp_mode: SrtpMode | None
    sip_transport: Transport | None
    sip_servers_root_and_intermediate_certificates: list[str] | None
    sip_local_root_and_intermediate_certificates: list[str] | None
    sip_local_certificate: str | None
    sip_local_key: str | None
    sip_subscribe_mwi: bool | None
    sip_lines: dict[str, SipLineDict]
    sccp_call_managers: dict[str, CallManagerDict]
    exten_dnd: str | None
    exten_fwd_unconditional: str | None
    exten_fwd_no_answer: str | None
    exten_fwd_busy: str | None
    exten_fwd_disable_all: str | None
    exten_park: str | None
    exten_pickup_group: str | None
    exten_pickup_call: str | None
    exten_voicemail: str | None
    funckeys: FuncKeyDict
    X_xivo_phonebook_ip: str | None
    config_version: (
        int | None
    )  # NOTE(afournier): this variable is unused. See WAZO-3619


@validator('timezone', allow_reuse=True)
def validate_timezone(cls: type[BaseModel], value: str | None) -> ZoneInfo | None:
    return ZoneInfo(value) if value else None


@validator('sccp_call_managers', 'funckeys', allow_reuse=True)
def validate_numeric_keys(
    cls: type[BaseModel], value: dict[str, Any]
) -> dict[str, Any]:
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

    custom_fields = set(values) - {field.alias for field in cls.__fields__.values()}
    invalid_custom_fields = [
        custom_field
        for custom_field in custom_fields
        if not custom_field.startswith('X_')
    ]
    if any(invalid_custom_fields):
        raise ValueError('Custom fields must start with `X_`', invalid_custom_fields)

    return values


RawConfigSchema = create_model_from_typeddict(
    RawConfigDict,
    {
        "ip": Field(),
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
    type_overrides={
        'funckeys': dict[str, FuncKeySchema],  # type: ignore[valid-type]
        'sip_lines': dict[str, SipLineSchema],  # type: ignore[valid-type]
        'sccp_call_managers': dict[str, CallManagerSchema],  # type: ignore[valid-type]
    },
)


class BaseConfigDict(TypedDict):
    id: str | None
    parent_ids: list[str]
    raw_config: RawConfigDict


class ConfigDict(BaseConfigDict, total=False):
    transient: bool
    deletable: bool
    role: str


ConfigSchema = create_model_from_typeddict(
    ConfigDict,
    {
        "id": Field(),
        "parent_ids": Field(...),
        "raw_config": Field(...),
    },
    type_overrides={'raw_config': RawConfigSchema},  # type: ignore[valid-type]
)


class BaseDeviceDict(TypedDict, total=False):
    id: str | None
    mac: str | None
    ip: IPv4Address | str
    config: str | None
    model: str | None
    plugin: str | None
    description: str | None
    configured: bool
    is_new: bool
    vendor: str | None
    version: str | None


class DeviceDict(BaseDeviceDict, total=False):
    tenant_uuid: str


DeviceSchema = create_model_from_typeddict(
    DeviceDict,
    {
        "mac": Field(regex=_NORMED_MAC.pattern),
    },
)
