"""create provd_tenant table

Revision ID: 1e605e2719e4
Revises: 8763295f8c44
Create Date: 2024-02-20 16:25:32.377455

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '1e605e2719e4'
down_revision = '8763295f8c44'
branch_labels = None
depends_on = None

TABLE_NAME = 'provd_tenant'


def upgrade():
    op.create_table(
        TABLE_NAME,
        sa.Column(
            'uuid',
            sa.String(36),
            server_default=sa.text('uuid_generate_v4()'),
            primary_key=True,
        ),
        sa.Column(
            'provisioning_key',
            sa.String,
            nullable=True,
        ),
    )


def downgrade():
    op.drop_table(TABLE_NAME)
