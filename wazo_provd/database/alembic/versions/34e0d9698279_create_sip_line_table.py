"""create sip_line table

Revision ID: 34e0d9698279
Revises: 22e95044345e
Create Date: 2024-03-18 15:19:47.640775

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '34e0d9698279'
down_revision = '22e95044345e'
branch_labels = None
depends_on = None

TABLE_NAME = 'provd_sip_line'


def upgrade():
    op.create_table(
        TABLE_NAME,
        sa.Column('uuid', UUID, primary_key=True),
        sa.Column(
            'config_id',
            sa.Text,
            sa.ForeignKey('provd_device_config.id'),
            nullable=False,
        ),
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
    op.create_check_constraint(
        'ck_dtmf_mode',
        TABLE_NAME,
        sa.sql.column('dtmf_mode').in_(['RTP-in-band', 'RTP-out-of-band', 'SIP-INFO']),
    )
    op.create_check_constraint(
        'ck_srtp_mode',
        TABLE_NAME,
        sa.sql.column('srtp_mode').in_(['disabled', 'preferred', 'required']),
    )


def downgrade():
    op.drop_constraint('ck_dtmf_mode', TABLE_NAME)
    op.drop_constraint('ck_srtp_mode', TABLE_NAME)
    op.drop_table(TABLE_NAME)
