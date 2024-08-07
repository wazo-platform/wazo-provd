"""add default device configurations

Revision ID: 8d5a3f272aca
Revises: 2d180b54c811
Create Date: 2024-04-18 11:05:49.850700

"""
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '8d5a3f272aca'
down_revision = '2d180b54c811'
branch_labels = None
depends_on = None

key_aliases = {
    # JSON: database
    'X_xivo_phonebook_ip': 'phonebook_ip',
    'X_type': 'type',
}

base_config = {
    "deletable": False,
    "parent_id": None,
    "id": "base",
    "type": "internal",
    "raw_config": {
        "ntp_ip": "127.0.0.1",
        "X_xivo_phonebook_ip": "127.0.0.1",
        "ntp_enabled": True,
    },
}

default_config = {
    "label": "local",
    "type": "registrar",
    "parent_id": "base",
    "deletable": False,
    "raw_config": {},
    "id": "default",
}

default_config_device = {
    "type": "device",
    "label": "Default config device",
    "parent_id": "base",
    "deletable": False,
    "raw_config": {
        "ntp_ip": "127.0.0.1",
        "user_password": "aZp7chavVbm9rvLL",
        "admin_username": "admin",
        "user_username": "user",
        "ntp_enabled": True,
        "admin_password": "F1jWSUfT0Q6fexcS",
        "sip_dtmf_mode": "SIP-INFO",
    },
    "id": "defaultconfigdevice",
}

autoprov_config = {
    "type": "internal",
    "parent_id": "defaultconfigdevice",
    "role": "autocreate",
    "deletable": False,
    "raw_config": {
        "ip": "127.0.0.1",
        "http_port": 8667,
        "sip_lines": {
            "1": {
                "username": "anonymous",
                "display_name": "Autoprov",
                "number": "autoprov",
                "registrar_ip": "127.0.0.1",
                "proxy_ip": "127.0.0.1",
                "password": "autoprov",
            }
        },
        "sccp_call_managers": {
            "1": {
                "ip": "127.0.0.1",
            }
        },
    },
    "id": "autoprov",
}

configs_to_insert: list[dict[str, Any]] = [
    base_config,
    default_config,
    default_config_device,
    autoprov_config,
]

config_table = sa.sql.table(
    'provd_device_config',
    sa.Column('id', sa.Text),
    sa.Column('parent_id', sa.Text),
    sa.Column('label', sa.Text),
    sa.Column('deletable', sa.Boolean),
    sa.Column('type', sa.Text),
    sa.Column('role', sa.Text),
    sa.Column('configdevice', sa.Text),
    sa.Column('transient', sa.Boolean),
    sa.Column('registrar_main', sa.Text),
    sa.Column('registrar_main_port', sa.Integer),
    sa.Column('proxy_main', sa.Text),
    sa.Column('proxy_main_port', sa.Integer),
    sa.Column('proxy_outbound', sa.Text),
    sa.Column('proxy_outbound_port', sa.Integer),
    sa.Column('registrar_backup', sa.Text),
    sa.Column('registrar_backup_port', sa.Integer),
    sa.Column('proxy_backup', sa.Text),
    sa.Column('proxy_backup_port', sa.Integer),
)

raw_config_table = sa.sql.table(
    'provd_device_raw_config',
    sa.Column('config_id', sa.Text),
    sa.Column('ip', sa.Text),
    sa.Column('http_port', sa.Integer),
    sa.Column('http_base_url', sa.Text),
    sa.Column('tftp_port', sa.Integer),
    sa.Column('dns_enabled', sa.Boolean),
    sa.Column('dns_ip', sa.Text),
    sa.Column('ntp_enabled', sa.Boolean),
    sa.Column('ntp_ip', sa.Text),
    sa.Column('vlan_enabled', sa.Boolean),
    sa.Column('vlan_id', sa.Integer),
    sa.Column('vlan_priority', sa.Integer),
    sa.Column('vlan_pc_port_id', sa.Integer),
    sa.Column('syslog_enabled', sa.Boolean),
    sa.Column('syslog_ip', sa.Text),
    sa.Column('syslog_port', sa.Integer),
    sa.Column('syslog_level', sa.Integer),
    sa.Column('admin_username', sa.Text),
    sa.Column('admin_password', sa.Text),
    sa.Column('user_username', sa.Text),
    sa.Column('user_password', sa.Text),
    sa.Column('timezone', sa.Text),
    sa.Column('locale', sa.Text),
    sa.Column('protocol', sa.Text),
    sa.Column('sip_proxy_ip', sa.Text),
    sa.Column('sip_proxy_port', sa.Integer),
    sa.Column('sip_backup_proxy_ip', sa.Text),
    sa.Column('sip_backup_proxy_port', sa.Integer),
    sa.Column('sip_registrar_ip', sa.Text),
    sa.Column('sip_registrar_port', sa.Integer),
    sa.Column('sip_backup_registrar_ip', sa.Text),
    sa.Column('sip_backup_registrar_port', sa.Integer),
    sa.Column('sip_outbound_proxy_ip', sa.Text),
    sa.Column('sip_outbound_proxy_port', sa.Integer),
    sa.Column('sip_dtmf_mode', sa.Text),
    sa.Column('sip_srtp_mode', sa.Text),
    sa.Column('sip_transport', sa.Text),
    sa.Column('sip_servers_root_and_intermediate_certificates', sa.Text),
    sa.Column('sip_local_root_and_intermediate_certificates', sa.Text),
    sa.Column('sip_local_certificate', sa.Text),
    sa.Column('sip_local_key', sa.Text),
    sa.Column('sip_subscribe_mwi', sa.Text),
    sa.Column('exten_dnd', sa.Text),
    sa.Column('exten_fwd_unconditional', sa.Text),
    sa.Column('exten_fwd_no_answer', sa.Text),
    sa.Column('exten_fwd_busy', sa.Text),
    sa.Column('exten_fwd_disable_all', sa.Text),
    sa.Column('exten_park', sa.Text),
    sa.Column('exten_pickup_group', sa.Text),
    sa.Column('exten_pickup_call', sa.Text),
    sa.Column('exten_voicemail', sa.Text),
    sa.Column('phonebook_ip', sa.Text),
)

sip_line_table = sa.sql.table(
    'provd_sip_line',
    sa.Column('uuid', UUID),
    sa.Column('config_id', sa.Text),
    sa.Column('position', sa.Integer),
    sa.Column('proxy_ip', sa.Text),
    sa.Column('proxy_port', sa.Integer),
    sa.Column('backup_proxy_ip', sa.Text),
    sa.Column('backup_proxy_port', sa.Integer),
    sa.Column('registrar_ip', sa.Text),
    sa.Column('registrar_port', sa.Integer),
    sa.Column('backup_registrar_ip', sa.Text),
    sa.Column('backup_registrar_port', sa.Integer),
    sa.Column('outbound_proxy_ip', sa.Text),
    sa.Column('outbound_proxy_port', sa.Integer),
    sa.Column('username', sa.Text),
    sa.Column('password', sa.Text),
    sa.Column('auth_username', sa.Text),
    sa.Column('display_name', sa.Text),
    sa.Column('number', sa.Text),
    sa.Column('dtmf_mode', sa.Text),
    sa.Column('srtp_mode', sa.Text),
    sa.Column('voicemail', sa.Text),
)

sccp_line_table = sa.sql.table(
    'provd_sccp_line',
    sa.Column('uuid', UUID),
    sa.Column('config_id', sa.Text),
    sa.Column('position', sa.Integer),
    sa.Column('ip', sa.Text),
    sa.Column('port', sa.Integer),
)


def insert_sip_lines(conn, config_id: str, lines: dict[str, Any]) -> None:
    for position, line in lines.items():
        line_dict = {key_aliases.get(key, key): val for key, val in line.items()}
        line_dict['uuid'] = str(uuid4())
        line_dict['config_id'] = config_id
        line_dict['position'] = int(position)
        query = sip_line_table.insert().values(**line_dict)
        conn.execute(query)


def insert_sccp_lines(conn, config_id: str, lines: dict[str, Any]) -> None:
    for position, line in lines.items():
        line_dict = {key_aliases.get(key, key): val for key, val in line.items()}
        line_dict['uuid'] = str(uuid4())
        line_dict['config_id'] = config_id
        line_dict['position'] = int(position)
        query = sccp_line_table.insert().values(**line_dict)
        conn.execute(query)


def insert_raw_config(conn, raw_config: dict[str, Any]) -> None:
    sip_lines = raw_config.pop('sip_lines', None)
    sccp_lines = raw_config.pop('sccp_call_managers', None)
    raw_config_dict = {
        key_aliases.get(key, key): val for key, val in raw_config.items()
    }
    query = raw_config_table.insert().values(**raw_config_dict)
    conn.execute(query)

    if sip_lines:
        insert_sip_lines(conn, raw_config['config_id'], sip_lines)

    if sccp_lines:
        insert_sccp_lines(conn, raw_config['config_id'], sccp_lines)


def insert_config(conn, config: dict[str, Any]) -> None:
    raw_config = config.pop('raw_config', None)
    config_dict = {key_aliases.get(key, key): val for key, val in config.items()}
    query = config_table.insert().returning(config_table.c.id).values(**config_dict)
    inserted_config_id = conn.execute(query).scalar()
    if raw_config:
        raw_config['config_id'] = inserted_config_id
        insert_raw_config(conn, raw_config)


def upgrade():
    conn = op.get_bind()
    for config in configs_to_insert:
        insert_config(conn, config)


def downgrade():
    # Do we want to delete configs?
    pass
