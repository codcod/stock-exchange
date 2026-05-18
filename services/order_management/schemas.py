"""Request/response models for the Order Management Service."""

from __future__ import annotations

from pydantic import BaseModel


class OrderFilledEvent(BaseModel):
    """
    Event model sent from the Matching Engine to Order Management when an
    order has been partially or fully filled.
    """

    order_id: str
    account_id: str
    fill_quantity: int
    fill_price: float
    is_fully_filled: bool = False
