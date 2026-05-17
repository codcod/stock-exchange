from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.schema import CreateTable

metadata = MetaData()

_SCHEMAS = ('order_management', 'risk_engine', 'clearing', 'matching_engine')

# Arbitrary fixed lock ID — serialises DDL across all services at startup.
_DDL_LOCK_ID = 20260516


async def ensure_tables(engine) -> None:
    """Create all schemas and tables.

    Uses a pg advisory lock so concurrent service starts don't race on DDL.
    IF NOT EXISTS on every statement makes the whole block idempotent.
    """
    async with engine.begin() as conn:
        await conn.execute(text(f'SELECT pg_advisory_xact_lock({_DDL_LOCK_ID})'))
        for schema in _SCHEMAS:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {schema}'))
        for table in metadata.sorted_tables:
            await conn.execute(CreateTable(table, if_not_exists=True))


# ---------------------------------------------------------------------------
# Backward-compat shim — callers that still pass a conn get a clear error.
# ---------------------------------------------------------------------------


async def create_schemas(engine) -> None:
    """Deprecated: use ensure_tables() instead."""
    await ensure_tables(engine)


# schema= must follow all positional Column args (SQLAlchemy Table signature)

orders = Table(
    'orders',
    metadata,
    Column('order_id', String, primary_key=True),
    Column('account_id', String, nullable=False),
    Column('ticker', String, nullable=False),
    Column('side', String, nullable=False),
    Column('order_type', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    Column('price', Numeric(18, 6), nullable=True),
    Column('status', String, nullable=False),
    Column('filled_quantity', Integer, nullable=False),
    Column('average_fill_price', Numeric(18, 6), nullable=True),
    Column('reject_reason', Text, nullable=True),
    Column('created_at', DateTime(timezone=True), nullable=False),
    Column('updated_at', DateTime(timezone=True), nullable=False),
    schema='order_management',
)

accounts = Table(
    'accounts',
    metadata,
    Column('account_id', String, primary_key=True),
    Column('name', String, nullable=False),
    Column('cash_balance', Numeric(18, 6), nullable=False),
    Column('reserved_cash', Numeric(18, 6), nullable=False),
    Column('created_at', DateTime(timezone=True), nullable=False),
    schema='clearing',
)

positions = Table(
    'positions',
    metadata,
    Column('account_id', String, nullable=False),
    Column('ticker', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    PrimaryKeyConstraint('account_id', 'ticker'),
    schema='clearing',
)

reserved_shares = Table(
    'reserved_shares',
    metadata,
    Column('account_id', String, nullable=False),
    Column('ticker', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    PrimaryKeyConstraint('account_id', 'ticker'),
    schema='clearing',
)

instruments = Table(
    'instruments',
    metadata,
    Column('ticker', String, primary_key=True),
    Column('name', String, nullable=False),
    Column('lot_size', Integer, nullable=False),
    Column('max_order_size', Integer, nullable=False),
    Column('is_tradeable', Boolean, nullable=False),
    Column('last_price', Numeric(18, 6), nullable=True),
    schema='risk_engine',
)

trades = Table(
    'trades',
    metadata,
    Column('trade_id', String, primary_key=True),
    Column('ticker', String, nullable=False),
    Column('buy_order_id', String, nullable=False),
    Column('sell_order_id', String, nullable=False),
    Column('buyer_account_id', String, nullable=False),
    Column('seller_account_id', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    Column('price', Numeric(18, 6), nullable=False),
    Column('executed_at', DateTime(timezone=True), nullable=False),
    schema='clearing',
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
    schema='matching_engine',
)
