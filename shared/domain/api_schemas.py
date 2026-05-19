"""
shared/domain/api_schemas.py

Pydantic models for inter-service HTTP contracts.

These schemas cross service boundaries — they define the "wire format" for
events and requests sent between services. Using a single shared source of
truth eliminates the three-way duplication of RegisterAccountRequest,
TradeExecutedEvent, etc. that previously lived in each service's schemas.py.

External / customer-facing DTOs (e.g. SubmitOrderRequest, AccountResponse)
remain in services/gateway/schemas.py.
"""

from __future__ import annotations

import typing as tp

from pydantic import BaseModel

from shared.domain.models import Order, OrderStatus, OrderType, Side

# ---------------------------------------------------------------------------
# Account & instrument registration (inter-service)
# ---------------------------------------------------------------------------


class RegisterAccountRequest(BaseModel):
    """Full account state sent between Clearing and Risk Engine."""

    account_id: str
    name: str
    cash_balance: float
    reserved_cash: float = 0.0
    positions: tp.Dict[str, int] = {}
    reserved_shares: tp.Dict[str, int] = {}


class RegisterInstrumentRequest(BaseModel):
    """Instrument details sent from Gateway → Risk Engine."""

    ticker: str
    name: str
    lot_size: int = 1
    max_order_size: int = 10_000
    is_tradeable: bool = True
    last_price: tp.Optional[float] = None


class ReserveRequest(BaseModel):
    """
    Cash or share reservation delta sent from Order Management → Clearing.

    A positive delta increases the reservation; a negative delta releases it.
    """

    delta: float


# ---------------------------------------------------------------------------
# Order wire format
# ---------------------------------------------------------------------------


class OrderRequest(BaseModel):
    """Order passed between services (Gateway → OMS → Risk → Matching)."""

    order_id: str
    account_id: str
    ticker: str
    side: str
    order_type: str
    quantity: int
    price: tp.Optional[float] = None
    status: str = OrderStatus.PENDING.value
    filled_quantity: int = 0
    average_fill_price: tp.Optional[float] = None
    reject_reason: tp.Optional[str] = None
    created_at: tp.Optional[str] = None
    updated_at: tp.Optional[str] = None

    def to_domain(self) -> Order:
        order = Order(
            account_id=self.account_id,
            ticker=self.ticker,
            side=Side(self.side),
            order_type=OrderType(self.order_type),
            quantity=self.quantity,
            price=self.price,
            order_id=self.order_id,
            status=OrderStatus(self.status),
            filled_quantity=self.filled_quantity,
            average_fill_price=self.average_fill_price,
            reject_reason=self.reject_reason,
        )
        if self.created_at:
            from datetime import datetime

            order.created_at = datetime.fromisoformat(self.created_at)
        if self.updated_at:
            from datetime import datetime

            order.updated_at = datetime.fromisoformat(self.updated_at)
        return order


# ---------------------------------------------------------------------------
# Risk check result
# ---------------------------------------------------------------------------


class RiskCheckResult(BaseModel):
    """Return value from the Risk Engine's pre-trade check."""

    passed: bool
    reason: tp.Optional[str] = None


# ---------------------------------------------------------------------------
# Event wire formats (Matching Engine → downstream services)
# ---------------------------------------------------------------------------


class TradeExecutedEvent(BaseModel):
    """
    Matching Engine → Clearing and Market Data.
    Signals that two orders were matched and a trade was executed.
    """

    trade_id: str
    buy_order_id: str
    sell_order_id: str
    buyer_account_id: str
    seller_account_id: str
    ticker: str
    quantity: int
    price: float


class OrderFilledEvent(BaseModel):
    """
    Matching Engine → Order Management.
    Signals that an order was partially or fully filled.
    """

    order_id: str
    account_id: str
    fill_quantity: int
    fill_price: float
    is_fully_filled: bool = False


class MarketDataUpdateEvent(BaseModel):
    """
    Matching Engine → Market Data.
    Signals a change in top-of-book or last trade price.
    """

    ticker: str
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    volume: int = 0
