"""Table definitions for the Risk Engine service."""

from sqlalchemy import Boolean, Column, Integer, MetaData, Numeric, String, Table

metadata = MetaData(schema='risk_engine')

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
