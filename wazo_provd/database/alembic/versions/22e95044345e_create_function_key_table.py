"""create function key table

Revision ID: 22e95044345e
Revises: 2d34f402fb01
Create Date: 2024-03-18 15:19:35.691653

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '22e95044345e'
down_revision = '2d34f402fb01'
branch_labels = None
depends_on = None

TABLE_NAME = 'provd_function_key'


def upgrade():
    op.create_table(
        TABLE_NAME,
        sa.Column('uuid', UUID, primary_key=True),
        sa.Column('config_id', sa.Text, sa.ForeignKey('provd_device_config.id')),
        sa.Column('type', sa.Text),
        sa.Column('value', sa.Text),
        sa.Column('label', sa.Text),
        sa.Column('line', sa.Text),
    )
    op.create_check_constraint(
        'ck_fkey_type',
        TABLE_NAME,
        sa.sql.column('type').in_(['speeddial', 'blf', 'park']),
    )


def downgrade():
    op.drop_constraint('ck_fkey_type', TABLE_NAME)
    op.drop_table(TABLE_NAME)
