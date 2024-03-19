"""create device table

Revision ID: 2d180b54c811
Revises: 17b1b0e1ce6a
Create Date: 2024-03-19 14:41:32.591554

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '2d180b54c811'
down_revision = '17b1b0e1ce6a'
branch_labels = None
depends_on = None

TABLE_NAME = 'provd_device'


def upgrade():
    op.create_table(
        TABLE_NAME,
        sa.Column('id', sa.Text, primary_key=True),
        sa.Column(
            'tenant_uuid', UUID, sa.ForeignKey('provd_tenant.uuid'), nullable=False
        ),
        sa.Column('config_id', sa.Text, sa.ForeignKey('provd_device_config.id')),
        sa.Column('mac', sa.Text),
        sa.Column('ip', sa.Text),
        sa.Column('vendor', sa.Text),
        sa.Column('model', sa.Text),
        sa.Column('version', sa.Text),
        sa.Column('plugin', sa.Text),
        sa.Column('configured', sa.Boolean),
        sa.Column('auto_added', sa.Boolean),
        sa.Column('is_new', sa.Boolean),
    )


def downgrade():
    op.drop_table(TABLE_NAME)
