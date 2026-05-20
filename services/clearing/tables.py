"""Table definitions for the Clearing service — trade records only."""

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
)

from shared.platform.db.tables import ensure_tables as _ensure_tables

metadata = MetaData()
_SCHEMAS = ('clearing',)

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


async def ensure_tables(engine) -> None:
    await _ensure_tables(engine, metadata, _SCHEMAS)
