"""create notifications schema

Revision ID: 765fc0c017ee
Revises:
Create Date: 2026-09-18 13:58:04.936054

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '765fc0c017ee'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS notifications')
    op.create_table(
        'notifications',
        sa.Column('notification_id', sa.String(), nullable=False),
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('notification_id'),
        schema='notifications',
    )


def downgrade() -> None:
    op.drop_table('notifications', schema='notifications')
