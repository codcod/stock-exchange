"""Table definitions for the Account service."""

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
)

from shared.platform.db.tables import ensure_tables as _ensure_tables

metadata = MetaData()
_SCHEMAS = ('account',)

accounts = Table(
    'accounts',
    metadata,
    Column('account_id', String, primary_key=True),
    Column('name', String, nullable=False),
    Column('cash_balance', Numeric(18, 6), nullable=False),
    Column('reserved_cash', Numeric(18, 6), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    schema='account',
)

positions = Table(
    'positions',
    metadata,
    Column('account_id', String, nullable=False),
    Column('ticker', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    PrimaryKeyConstraint('account_id', 'ticker'),
    schema='account',
)

reserved_shares = Table(
    'reserved_shares',
    metadata,
    Column('account_id', String, nullable=False),
    Column('ticker', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    PrimaryKeyConstraint('account_id', 'ticker'),
    schema='account',
)

outbox = Table(
    'outbox',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('event_id', String, nullable=False),
    Column('event_type', String, nullable=False),
    Column('destination', String, nullable=False),
    Column('payload', Text, nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('published_at', DateTime(timezone=True), nullable=True),
    schema='account',
)

processed_events = Table(
    'processed_events',
    metadata,
    Column('event_id', String, primary_key=True),
    schema='account',
)


async def ensure_tables(engine) -> None:
    await _ensure_tables(engine, metadata, _SCHEMAS)
