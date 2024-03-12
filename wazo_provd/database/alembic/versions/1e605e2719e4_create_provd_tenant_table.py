"""create provd_tenant table

Revision ID: 1e605e2719e4
Revises:
Create Date: 2024-02-20 16:25:32.377455

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '1e605e2719e4'
down_revision = None
branch_labels = None
depends_on = None

TABLE_NAME = 'provd_tenant'


def upgrade():
    op.create_table(
        TABLE_NAME,
        sa.Column('uuid', UUID, primary_key=True),
        sa.Column('provisioning_key', sa.Text, nullable=True),
    )


def downgrade():
    op.drop_table(TABLE_NAME)
