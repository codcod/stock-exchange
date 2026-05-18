"""Request/response models for the Clearing Service."""

from __future__ import annotations

import typing as tp

from pydantic import BaseModel


class RegisterAccountRequest(BaseModel):
    """Request model for registering a new trading account."""

    account_id: str
    name: str
    cash_balance: float
    reserved_cash: float = 0.0
    positions: tp.Dict[str, int] = {}
    reserved_shares: tp.Dict[str, int] = {}


class TradeExecutedEvent(BaseModel):
    """
    Event model sent from the Matching Engine to Clearing when a trade
    has been executed and needs to be settled.
    """

    trade_id: str
    buy_order_id: str
    sell_order_id: str
    buyer_account_id: str
    seller_account_id: str
    ticker: str
    quantity: int
    price: float


class ReserveRequest(BaseModel):
    """
    Request model for reserving or releasing cash or shares. A positive
    delta increases the reservation, while a negative delta decreases it.
    """

    delta: float
