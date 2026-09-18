"""create risk_engine schema

Revision ID: 053483c893bc
Revises:
Create Date: 2026-09-18 06:21:46.129579

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '053483c893bc'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE SCHEMA IF NOT EXISTS risk_engine')
    op.create_table(
        'instruments',
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('lot_size', sa.Integer(), nullable=False),
        sa.Column('max_order_size', sa.Integer(), nullable=False),
        sa.Column('is_tradeable', sa.Boolean(), nullable=False),
        sa.Column('last_price', sa.Numeric(18, 6), nullable=True),
        sa.PrimaryKeyConstraint('ticker'),
        schema='risk_engine',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('instruments', schema='risk_engine')
