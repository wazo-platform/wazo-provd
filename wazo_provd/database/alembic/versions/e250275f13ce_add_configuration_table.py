"""add configuration table

Revision ID: e250275f13ce
Revises: 1e605e2719e4
Create Date: 2024-03-05 11:11:01.010851

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = 'e250275f13ce'
down_revision = '1e605e2719e4'
branch_labels = None
depends_on = None

TABLE_NAME = 'provd_configuration'


def upgrade():
    op.create_table(
        TABLE_NAME,
        sa.Column('uuid', UUID, primary_key=True),
        sa.Column('nat_enabled', sa.Boolean, server_default=sa.sql.text('false')),
        sa.Column('plugin_server', sa.Text),
        sa.Column('http_proxy', sa.Text),
        sa.Column('https_proxy', sa.Text),
        sa.Column('ftp_proxy', sa.Text),
        sa.Column('locale', sa.Text),
    )


def downgrade():
    op.drop_table(TABLE_NAME)
