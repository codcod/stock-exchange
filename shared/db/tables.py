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
)

metadata = MetaData()

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
    Column('created_at', DateTime, nullable=False),
    Column('updated_at', DateTime, nullable=False),
)

accounts = Table(
    'accounts',
    metadata,
    Column('account_id', String, primary_key=True),
    Column('name', String, nullable=False),
    Column('cash_balance', Numeric(18, 6), nullable=False),
    Column('reserved_cash', Numeric(18, 6), nullable=False),
    Column('created_at', DateTime, nullable=False),
)

positions = Table(
    'positions',
    metadata,
    Column('account_id', String, nullable=False),
    Column('ticker', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    PrimaryKeyConstraint('account_id', 'ticker'),
)

reserved_shares = Table(
    'reserved_shares',
    metadata,
    Column('account_id', String, nullable=False),
    Column('ticker', String, nullable=False),
    Column('quantity', Integer, nullable=False),
    PrimaryKeyConstraint('account_id', 'ticker'),
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
    Column('executed_at', DateTime, nullable=False),
)
