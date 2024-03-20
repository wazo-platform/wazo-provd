# Copyright 2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import abc
import dataclasses
import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Model(metaclass=abc.ABCMeta):
    _meta: ClassVar[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        self_dict = dataclasses.asdict(self)
        return self_dict


@dataclasses.dataclass
class Tenant(Model):
    uuid: UUID
    provisioning_key: str | None = dataclasses.field(default=None)

    _meta = {'primary_key': 'uuid'}


@dataclasses.dataclass
class ServiceConfiguration(Model):
    uuid: UUID
    plugin_server: str | None = dataclasses.field(default=None)
    http_proxy: str | None = dataclasses.field(default=None)
    https_proxy: str | None = dataclasses.field(default=None)
    ftp_proxy: str | None = dataclasses.field(default=None)
    locale: str | None = dataclasses.field(default=None)
    nat_enabled: bool | None = dataclasses.field(default=False)

    _meta = {'primary_key': 'uuid'}


@dataclasses.dataclass
class DeviceConfig(Model):
    id: str
    parent_id: str | None = dataclasses.field(default=None)
    deletable: bool = dataclasses.field(default=True)
    type: str | None = dataclasses.field(default=None)
    roles: str | None = dataclasses.field(default=None)
    configdevice: str | None = dataclasses.field(default=None)
    transient: bool = dataclasses.field(default=False)

    _meta = {'primary_key': 'id'}


@dataclasses.dataclass
class DeviceRawConfig(Model):
    config_id: str
    ip: str
    http_port: int | None = dataclasses.field(default=None)
    http_base_url: str | None = dataclasses.field(default=None)
    tftp_port: int | None = dataclasses.field(default=None)
    dns_enabled: bool | None = dataclasses.field(default=None)
    dns_ip: str | None = dataclasses.field(default=None)
    ntp_enabled: bool | None = dataclasses.field(default=None)
    ntp_ip: str | None = dataclasses.field(default=None)
    vlan_enabled: bool | None = dataclasses.field(default=None)
    vlan_id: int | None = dataclasses.field(default=None)
    vlan_priority: int | None = dataclasses.field(default=None)
    vlan_pc_port_id: int | None = dataclasses.field(default=None)
    syslog_enabled: bool | None = dataclasses.field(default=None)
    syslog_ip: str | None = dataclasses.field(default=None)
    syslog_port: int | None = dataclasses.field(default=None)
    syslog_level: int | None = dataclasses.field(default=None)
    admin_username: str | None = dataclasses.field(default=None)
    admin_password: str | None = dataclasses.field(default=None)
    user_username: str | None = dataclasses.field(default=None)
    user_password: str | None = dataclasses.field(default=None)
    timezone: str | None = dataclasses.field(default=None)
    locale: str | None = dataclasses.field(default=None)
    protocol: str | None = dataclasses.field(default=None)  # ENUM sip,sccp
    sip_proxy_ip: str | None = dataclasses.field(default=None)
    sip_proxy_port: int | None = dataclasses.field(default=None)
    sip_backup_proxy_ip: str | None = dataclasses.field(default=None)
    sip_backup_proxy_port: int | None = dataclasses.field(default=None)
    sip_registrar_ip: str | None = dataclasses.field(default=None)
    sip_registrar_port: int | None = dataclasses.field(default=None)
    sip_backup_registrar_ip: str | None = dataclasses.field(default=None)
    sip_backup_registrar_port: int | None = dataclasses.field(default=None)
    sip_outbound_proxy_ip: str | None = dataclasses.field(default=None)
    sip_outbound_proxy_port: int | None = dataclasses.field(default=None)
    sip_dtmf_mode: str | None = dataclasses.field(default=None)
    sip_srtp_mode: str | None = dataclasses.field(default=None)
    sip_transport: str | None = dataclasses.field(default=None)
    sip_servers_root_and_intermediate_certificates: str | None = dataclasses.field(
        default=None
    )
    sip_local_root_and_intermediate_certificates: str | None = dataclasses.field(
        default=None
    )
    sip_local_certificate: str | None = dataclasses.field(default=None)
    sip_local_key: str | None = dataclasses.field(default=None)
    sip_subscribe_mwi: str | None = dataclasses.field(default=None)
    exten_dnd: str | None = dataclasses.field(default=None)
    exten_fwd_unconditional: str | None = dataclasses.field(default=None)
    exten_fwd_no_answer: str | None = dataclasses.field(default=None)
    exten_fwd_busy: str | None = dataclasses.field(default=None)
    exten_fwd_disable_all: str | None = dataclasses.field(default=None)
    exten_park: str | None = dataclasses.field(default=None)
    exten_pickup_group: str | None = dataclasses.field(default=None)
    exten_pickup_call: str | None = dataclasses.field(default=None)
    exten_voicemail: str | None = dataclasses.field(default=None)

    _meta = {'primary_key': 'config_id'}


@dataclasses.dataclass
class SIPLine(Model):
    uuid: UUID
    config_id: str
    proxy_ip: str | None = dataclasses.field(default=None)
    proxy_port: int | None = dataclasses.field(default=None)
    backup_proxy_ip: str | None = dataclasses.field(default=None)
    backup_proxy_port: int | None = dataclasses.field(default=None)
    registrar_ip: str | None = dataclasses.field(default=None)
    registrar_port: int | None = dataclasses.field(default=None)
    backup_registrar_ip: str | None = dataclasses.field(default=None)
    backup_registrar_port: int | None = dataclasses.field(default=None)
    outbound_proxy_ip: str | None = dataclasses.field(default=None)
    outbound_proxy_port: int | None = dataclasses.field(default=None)
    username: str | None = dataclasses.field(default=None)
    password: str | None = dataclasses.field(default=None)
    auth_username: str | None = dataclasses.field(default=None)
    display_name: str | None = dataclasses.field(default=None)
    number: str | None = dataclasses.field(default=None)
    dtmf_mode: str | None = dataclasses.field(
        default=None
    )  # "RTP-in-band, RTP-out-of-band, SIP-INFO": enum
    srtp_mode: str | None = dataclasses.field(
        default=None
    )  # "disabled, preferred, required": enum
    voicemail: str | None = dataclasses.field(default=None)

    _meta = {'primary_key': 'uuid'}


@dataclasses.dataclass
class SCCPLine(Model):
    uuid: UUID
    config_id: str
    ip: str
    port: int

    _meta = {'primary_key': 'uuid'}


@dataclasses.dataclass
class FunctionKey(Model):
    uuid: UUID
    config_id: str
    type: str  # enum "speeddial, blf, park"
    value: str
    label: str
    line: str

    _meta = {'primary_key': 'uuid'}


@dataclasses.dataclass
class Device(Model):
    id: str
    tenant_uuid: UUID
    config_id: str
    mac: str
    ip: str
    vendor: str
    model: str
    version: str
    plugin: str
    configured: bool
    auto_added: bool
    is_new: bool

    _meta = {'primary_key': 'id'}
