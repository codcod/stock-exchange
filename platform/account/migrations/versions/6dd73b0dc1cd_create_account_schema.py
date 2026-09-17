"""create account schema

Revision ID: 6dd73b0dc1cd
Revises:
Create Date: 2026-09-17 09:12:48.455170

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6dd73b0dc1cd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE SCHEMA IF NOT EXISTS account')
    op.create_table(
        'accounts',
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('cash_balance', sa.Numeric(18, 6), nullable=False),
        sa.Column('reserved_cash', sa.Numeric(18, 6), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('account_id'),
        schema='account',
    )
    op.create_table(
        'positions',
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('account_id', 'ticker'),
        schema='account',
    )
    op.create_table(
        'reserved_shares',
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('account_id', 'ticker'),
        schema='account',
    )
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
        schema='account',
    )
    op.create_table(
        'processed_events',
        sa.Column('event_id', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('event_id'),
        schema='account',
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Not dropping the account schema itself: alembic's own version table
    # (version_table_schema="account") lives in it and still needs it to
    # record this downgrade.
    op.drop_table('processed_events', schema='account')
    op.drop_table('outbox', schema='account')
    op.drop_table('reserved_shares', schema='account')
    op.drop_table('positions', schema='account')
    op.drop_table('accounts', schema='account')
