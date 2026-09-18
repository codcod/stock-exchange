"""create clearing schema

Revision ID: 2dc68865422c
Revises:
Create Date: 2026-09-18 13:21:46.193502

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2dc68865422c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE SCHEMA IF NOT EXISTS clearing')
    op.create_table(
        'trades',
        sa.Column('trade_id', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('buy_order_id', sa.String(), nullable=False),
        sa.Column('sell_order_id', sa.String(), nullable=False),
        sa.Column('buyer_account_id', sa.String(), nullable=False),
        sa.Column('seller_account_id', sa.String(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(18, 6), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('trade_id'),
        schema='clearing',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('trades', schema='clearing')
