"""add raw config table

Revision ID: 2d34f402fb01
Revises: 737573456306
Create Date: 2024-03-12 16:08:13.225768

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '2d34f402fb01'
down_revision = '737573456306'
branch_labels = None
depends_on = None

TABLE_NAME = 'provd_device_raw_config'


def upgrade():
    op.create_table(
        TABLE_NAME,
        sa.Column(
            'config_id',
            sa.Text,
            sa.ForeignKey('provd_device_config.id'),
            primary_key=True,
        ),
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
    op.create_check_constraint(
        'ck_protocol',
        TABLE_NAME,
        sa.sql.column('protocol').in_(['sip', 'sccp']),
    )


def downgrade():
    op.drop_constraint('ck_protocol', TABLE_NAME)
    op.drop_table(TABLE_NAME)
