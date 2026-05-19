"""
Defines the Pydantic request and response models for the HTTP layer.
"""

from __future__ import annotations

import typing as tp
from datetime import datetime

from pydantic import BaseModel

from shared.domain.models import OrderStatus, OrderType, Side

if tp.TYPE_CHECKING:
    from shared.domain.models import Account, Order


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class SubmitOrderRequest(BaseModel):
    """Request model for submitting a new order."""

    account_id: str
    ticker: str
    side: Side
    order_type: OrderType
    quantity: int
    price: tp.Optional[float] = None


class RegisterAccountRequest(BaseModel):
    """Request model for registering a new trading account."""

    account_id: str
    name: str
    cash_balance: float = 0.0
    positions: tp.Dict[str, int] = {}


class RegisterInstrumentRequest(BaseModel):
    """Request model for registering a new tradeable instrument."""

    ticker: str
    name: str
    lot_size: int = 1
    max_order_size: int = 10_000
    last_price: tp.Optional[float] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class OrderResponse(BaseModel):
    """Response model for an order."""

    order_id: str
    account_id: str
    ticker: str
    side: Side
    order_type: OrderType
    quantity: int
    price: tp.Optional[float]
    status: OrderStatus
    filled_quantity: int
    remaining_quantity: int
    average_fill_price: tp.Optional[float]
    reject_reason: tp.Optional[str]
    created_at: datetime
    updated_at: datetime


class AccountResponse(BaseModel):
    """Response model for a trading account."""

    account_id: str
    name: str
    cash_balance: float
    available_cash: float
    positions: dict
    reserved_cash: float
    reserved_shares: dict
    created_at: datetime


class QuoteResponse(BaseModel):
    """Response model for a market quote."""

    ticker: str
    bid: float
    ask: float
    last_price: float
    volume_today: int
    updated_at: datetime


class DepthLevel(BaseModel):
    """A single price level in the order book depth."""

    price: float
    quantity: int


class DepthResponse(BaseModel):
    """Response model for order book depth."""

    ticker: str
    bids: tp.List[DepthLevel]
    asks: tp.List[DepthLevel]
    last_price: tp.Optional[float]


class TradeItem(BaseModel):
    """A single trade in the trade history."""

    ticker: str
    price: float
    quantity: int
    executed_at: datetime


class CancelledResponse(BaseModel):
    """Response model for a cancellation request."""

    cancelled: bool


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------


def order_to_response(order: 'Order') -> OrderResponse:
    """Convert an Order domain object to a Pydantic response model."""
    return OrderResponse(
        order_id=order.order_id,
        account_id=order.account_id,
        ticker=order.ticker,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        price=order.price,
        status=order.status,
        filled_quantity=order.filled_quantity,
        remaining_quantity=order.remaining_quantity,
        average_fill_price=order.average_fill_price,
        reject_reason=order.reject_reason,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def account_to_response(account: 'Account') -> AccountResponse:
    """Convert an Account domain object to a Pydantic response model."""
    return AccountResponse(
        account_id=account.account_id,
        name=account.name,
        cash_balance=account.cash_balance,
        available_cash=account.available_cash(),
        positions=account.positions,
        reserved_cash=account.reserved_cash,
        reserved_shares=account.reserved_shares,
        created_at=account.created_at,
    )
