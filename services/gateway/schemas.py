"""
services/gateway/schemas.py

Pydantic request/response models for the HTTP layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel

from shared.models.domain import OrderStatus, OrderType, Side

if TYPE_CHECKING:
    from shared.models.domain import Account, Order


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class SubmitOrderRequest(BaseModel):
    account_id: str
    ticker: str
    side: Side
    order_type: OrderType
    quantity: int
    price: Optional[float] = None


class RegisterAccountRequest(BaseModel):
    account_id: str
    name: str
    cash_balance: float = 0.0


class RegisterInstrumentRequest(BaseModel):
    ticker: str
    name: str
    lot_size: int = 1
    max_order_size: int = 10_000
    last_price: Optional[float] = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class OrderResponse(BaseModel):
    order_id: str
    account_id: str
    ticker: str
    side: Side
    order_type: OrderType
    quantity: int
    price: Optional[float]
    status: OrderStatus
    filled_quantity: int
    remaining_quantity: int
    average_fill_price: Optional[float]
    reject_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


class AccountResponse(BaseModel):
    account_id: str
    name: str
    cash_balance: float
    available_cash: float
    positions: dict
    reserved_cash: float
    reserved_shares: dict
    created_at: datetime


class QuoteResponse(BaseModel):
    ticker: str
    bid: float
    ask: float
    last_price: float
    volume_today: int
    updated_at: datetime


class DepthLevel(BaseModel):
    price: float
    quantity: int


class DepthResponse(BaseModel):
    ticker: str
    bids: List[DepthLevel]
    asks: List[DepthLevel]
    last_price: Optional[float]


class TradeItem(BaseModel):
    ticker: str
    price: float
    quantity: int
    executed_at: datetime


class CancelledResponse(BaseModel):
    cancelled: bool


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------


def order_to_response(order: 'Order') -> OrderResponse:
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
