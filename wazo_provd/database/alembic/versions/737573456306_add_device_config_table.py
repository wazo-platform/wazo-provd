"""add device config table

Revision ID: 737573456306
Revises: e250275f13ce
Create Date: 2024-03-12 15:02:42.290896

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '737573456306'
down_revision = 'e250275f13ce'
branch_labels = None
depends_on = None

TABLE_NAME = 'provd_device_config'


def upgrade():
    op.create_table(
        TABLE_NAME,
        sa.Column('id', sa.Text, primary_key=True),
        sa.Column('parent_id', sa.Text, sa.ForeignKey(f'{TABLE_NAME}.id')),
        sa.Column('deletable', sa.Boolean, server_default=sa.sql.text('true')),
        sa.Column('type', sa.Text),
        sa.Column('role', sa.Text),
        sa.Column('configdevice', sa.Text),
        sa.Column('transient', sa.Boolean, server_default=sa.sql.text('false')),
    )


def downgrade():
    op.drop_table(TABLE_NAME)
