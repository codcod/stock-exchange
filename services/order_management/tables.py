"""Table definitions for the Order Management service."""

from sqlalchemy import Column, DateTime, Integer, MetaData, Numeric, String, Table, Text

from shared.platform.db.tables import ensure_tables as _ensure_tables

metadata = MetaData()
_SCHEMAS = ('order_management',)

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


async def ensure_tables(engine) -> None:
    await _ensure_tables(engine, metadata, _SCHEMAS)
