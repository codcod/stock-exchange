"""Table definitions for the Risk Engine service."""

from sqlalchemy import Boolean, Column, Integer, MetaData, Numeric, String, Table

from shared.platform.db.tables import ensure_tables as _ensure_tables

metadata = MetaData()
_SCHEMAS = ('risk_engine',)

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


async def ensure_tables(engine) -> None:
    await _ensure_tables(engine, metadata, _SCHEMAS)
