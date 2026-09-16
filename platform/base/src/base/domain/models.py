"""
shared/domain/models.py

Core domain entities shared across all services: the exchange's universal vocabulary.
"""

from __future__ import annotations

import typing as tp
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Side(str, Enum):
    """The side of an order, either BUY or SELL."""

    BUY = 'BUY'
    SELL = 'SELL'


class OrderType(str, Enum):
    """The type of an order, either MARKET or LIMIT."""

    MARKET = 'MARKET'  # execute immediately at best available price
    LIMIT = 'LIMIT'  # execute only at the specified price or better


class OrderStatus(str, Enum):
    """The lifecycle status of an order."""

    PENDING = 'PENDING'  # received, not yet risk-checked
    OPEN = 'OPEN'  # in the order book, waiting to match
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    FILLED = 'FILLED'  # fully executed
    CANCELLED = 'CANCELLED'
    REJECTED = 'REJECTED'  # failed risk check or validation


@dataclass
class Order:
    """Represents a single instruction to buy or sell a quantity of a ticker."""

    account_id: str
    ticker: str
    side: Side
    order_type: OrderType
    quantity: int  # number of shares
    price: tp.Optional[float]  # None for market orders

    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    average_fill_price: tp.Optional[float] = None
    reject_reason: tp.Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def remaining_quantity(self) -> int:
        """The number of shares that have not yet been filled."""
        return self.quantity - self.filled_quantity

    @property
    def is_active(self) -> bool:
        """Whether the order is in a state where it can be matched."""
        return self.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)


@dataclass
class Trade:
    """A record of a single match between a buy and a sell order."""

    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ticker: str = ''
    buy_order_id: str = ''
    sell_order_id: str = ''
    buyer_account_id: str = ''
    seller_account_id: str = ''
    quantity: int = 0
    price: float = 0.0
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Account:
    """A trading account, holding cash and share positions."""

    account_id: str
    name: str
    cash_balance: float = 0.0
    # ticker -> quantity
    positions: dict = field(default_factory=dict)
    # Cash reserved by open buy orders
    reserved_cash: float = 0.0
    # Shares reserved by open sell orders (ticker -> quantity)
    reserved_shares: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def available_cash(self) -> float:
        """The amount of cash not currently reserved by open orders."""
        return self.cash_balance - self.reserved_cash

    def available_shares(self, ticker: str) -> int:
        """The number of shares of a ticker not currently reserved by open orders."""
        held = self.positions.get(ticker, 0)
        reserved = self.reserved_shares.get(ticker, 0)
        return held - reserved


@dataclass
class Instrument:
    """A tradeable instrument, such as a stock."""

    ticker: str
    name: str
    lot_size: int = 1  # minimum tradeable quantity
    max_order_size: int = 10_000
    is_tradeable: bool = True
    last_price: tp.Optional[float] = None
