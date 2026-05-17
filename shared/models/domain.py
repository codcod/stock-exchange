"""
shared/models/domain.py

Core domain types shared across all services.
These are plain dataclasses with minimal derived properties (available cash/shares,
remaining quantity, active status) co-located with the data they describe.
"""

from __future__ import annotations

import typing as tp
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Side(str, Enum):
    BUY = 'BUY'
    SELL = 'SELL'


class OrderType(str, Enum):
    MARKET = 'MARKET'  # execute immediately at best available price
    LIMIT = 'LIMIT'  # execute only at the specified price or better


class OrderStatus(str, Enum):
    PENDING = 'PENDING'  # received, not yet risk-checked
    OPEN = 'OPEN'  # in the order book, waiting to match
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    FILLED = 'FILLED'  # fully executed
    CANCELLED = 'CANCELLED'
    REJECTED = 'REJECTED'  # failed risk check or validation


# ---------------------------------------------------------------------------
# Core domain objects
# ---------------------------------------------------------------------------


@dataclass
class Order:
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
        return self.quantity - self.filled_quantity

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)


@dataclass
class Trade:
    """Produced by the matching engine when a buy and sell order agree on price."""

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
    account_id: str
    name: str
    cash_balance: float = 0.0
    # ticker -> quantity
    positions: dict = field(default_factory=dict)
    # ticker -> quantity reserved by open buy orders
    reserved_cash: float = 0.0
    # ticker -> quantity reserved by open sell orders
    reserved_shares: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def available_cash(self) -> float:
        return self.cash_balance - self.reserved_cash

    def available_shares(self, ticker: str) -> int:
        held = self.positions.get(ticker, 0)
        reserved = self.reserved_shares.get(ticker, 0)
        return held - reserved


@dataclass
class Instrument:
    ticker: str
    name: str
    lot_size: int = 1  # minimum tradeable quantity
    max_order_size: int = 10_000
    is_tradeable: bool = True
    last_price: tp.Optional[float] = None


# ---------------------------------------------------------------------------
# Domain events
# ---------------------------------------------------------------------------


@dataclass
class Event:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OrderSubmitted(Event):
    order_id: str = ''
    account_id: str = ''
    ticker: str = ''


@dataclass
class OrderAccepted(Event):
    order_id: str = ''


@dataclass
class OrderRejected(Event):
    order_id: str = ''
    reason: str = ''


@dataclass
class OrderCancelled(Event):
    order_id: str = ''


@dataclass
class TradeExecuted(Event):
    trade_id: str = ''
    buy_order_id: str = ''
    sell_order_id: str = ''
    buyer_account_id: str = ''
    seller_account_id: str = ''
    ticker: str = ''
    quantity: int = 0
    price: float = 0.0


@dataclass
class OrderFilled(Event):
    order_id: str = ''
    account_id: str = ''
    fill_quantity: int = 0
    fill_price: float = 0.0
    is_fully_filled: bool = False


@dataclass
class MarketDataUpdate(Event):
    ticker: str = ''
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    volume: int = 0
