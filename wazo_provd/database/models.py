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
    http_port: int
    http_base_url: str
    tftp_port: int
    dns_enabled: bool
    dns_ip: str
    ntp_enabled: bool
    ntp_ip: str
    vlan_enabled: bool
    vlan_id: int
    vlan_priority: int
    vlan_pc_port_id: int
    syslog_enabled: bool
    syslog_ip: str
    syslog_port: int
    syslog_level: int
    admin_username: str
    admin_password: str
    user_username: str
    user_password: str
    timezone: str
    locale: str
    protocol: str  # ENUM sip,sccp
    sip_proxy_ip: str
    sip_proxy_port: int
    sip_backup_proxy_ip: str
    sip_backup_proxy_port: int
    sip_registrar_ip: str
    sip_registrar_port: int
    sip_backup_registrar_ip: str
    sip_backup_registrar_port: int
    sip_outbound_proxy_ip: str
    sip_outbound_proxy_port: int
    sip_dtmf_mode: str
    sip_srtp_mode: str
    sip_transport: str
    sip_servers_root_and_intermediate_certificates: str
    sip_local_root_and_intermediate_certificates: str
    sip_local_certificate: str
    sip_local_key: str
    sip_subscribe_mwi: str
    exten_dnd: str
    exten_fwd_unconditional: str
    exten_fwd_no_answer: str
    exten_fwd_busy: str
    exten_fwd_disable_all: str
    exten_park: str
    exten_pickup_group: str
    exten_pickup_call: str
    exten_voicemail: str

    _meta = {'primary_key': 'config_id'}


@dataclasses.dataclass
class SIPLine(Model):
    uuid: UUID
    config_id: str
    proxy_ip: str
    proxy_port: int
    backup_proxy_ip: str
    backup_proxy_port: int
    registrar_ip: str
    registrar_port: int
    backup_registrar_ip: str
    backup_registrar_port: int
    outbound_proxy_ip: str
    outbound_proxy_port: int
    username: str
    password: str
    auth_username: str
    display_name: str
    number: str
    dtmf_mode: str  # "RTP-in-band, RTP-out-of-band, SIP-INFO": enum
    srtp_mode: str  # "disabled, preferred, required": enum
    voicemail: str

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
