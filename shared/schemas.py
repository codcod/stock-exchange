"""
shared/schemas.py

Pydantic request/response models shared across multiple internal services.
Each service also has its own schemas.py for service-specific types.
"""

from __future__ import annotations

import typing as tp
from datetime import datetime

from pydantic import BaseModel

from shared.models.domain import Order, OrderStatus, OrderType, Side


class OrderRequest(BaseModel):
    """Wire format for an Order passed between services."""

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
            order.created_at = datetime.fromisoformat(self.created_at)
        if self.updated_at:
            order.updated_at = datetime.fromisoformat(self.updated_at)
        return order
