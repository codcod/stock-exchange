"""Request/response models for the Risk Engine."""

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


class RegisterInstrumentRequest(BaseModel):
    """Request model for registering a new tradeable instrument."""

    ticker: str
    name: str
    lot_size: int = 1
    max_order_size: int = 10_000
    is_tradeable: bool = True
    last_price: tp.Optional[float] = None
