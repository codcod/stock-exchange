"""create order_management schema

Revision ID: 2cf07e1f37fd
Revises:
Create Date: 2026-09-18 09:37:16.592187

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2cf07e1f37fd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS order_management')
    op.create_table(
        'outbox',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('destination', sa.String(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='order_management',
    )
    op.create_table(
        'orders',
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('order_type', sa.String(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(18, 6), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('filled_quantity', sa.Integer(), nullable=False),
        sa.Column('average_fill_price', sa.Numeric(18, 6), nullable=True),
        sa.Column('reject_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('order_id'),
        schema='order_management',
    )


def downgrade() -> None:
    op.drop_table('orders', schema='order_management')
    op.drop_table('outbox', schema='order_management')
