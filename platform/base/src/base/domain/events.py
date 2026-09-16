"""
shared/domain/events.py

Domain events produced by the exchange and used for inter-service communication.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Event:
    """Base class for all domain events."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OrderSubmitted(Event):
    """Fired when an order is first submitted to the exchange."""

    order_id: str = ''
    account_id: str = ''
    ticker: str = ''


@dataclass
class OrderAccepted(Event):
    """Fired when an order passes risk checks and is sent to the matching engine."""

    order_id: str = ''


@dataclass
class OrderRejected(Event):
    """Fired when an order fails risk checks."""

    order_id: str = ''
    reason: str = ''


@dataclass
class OrderCancelled(Event):
    """Fired when an order is successfully cancelled."""

    order_id: str = ''


@dataclass
class TradeExecuted(Event):
    """Fired by the matching engine when two orders are matched."""

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
    """Fired by the matching engine to report a full or partial fill."""

    order_id: str = ''
    account_id: str = ''
    fill_quantity: int = 0
    fill_price: float = 0.0
    is_fully_filled: bool = False


@dataclass
class MarketDataUpdate(Event):
    """Fired by the matching engine after a trade or book change."""

    ticker: str = ''
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    volume: int = 0


@dataclass
class AccountUpdated(Event):
    """Fired by the Account service after every state mutation."""

    account_id: str = ''
    name: str = ''
    cash_balance: float = 0.0
    reserved_cash: float = 0.0
    positions: dict = field(default_factory=dict)
    reserved_shares: dict = field(default_factory=dict)
