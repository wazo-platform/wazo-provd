"""create sccp_line table

Revision ID: 17b1b0e1ce6a
Revises: 34e0d9698279
Create Date: 2024-03-18 15:19:56.583532

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '17b1b0e1ce6a'
down_revision = '34e0d9698279'
branch_labels = None
depends_on = None

TABLE_NAME = 'provd_sccp_line'


def upgrade():
    op.create_table(
        TABLE_NAME,
        sa.Column('uuid', UUID, primary_key=True),
        sa.Column(
            'config_id',
            sa.Text,
            sa.ForeignKey('provd_device_config.id', ondelete='CASCADE'),
        ),
        sa.Column('position', sa.Integer),
        sa.Column('ip', sa.Text),
        sa.Column('port', sa.Integer),
    )


def downgrade():
    op.drop_table(TABLE_NAME)
