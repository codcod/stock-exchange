"""Request/response models for the Market Data Service."""

from __future__ import annotations

from pydantic import BaseModel


class MarketDataUpdateEvent(BaseModel):
    ticker: str
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    volume: int = 0


class TradeExecutedEvent(BaseModel):
    trade_id: str
    buy_order_id: str
    sell_order_id: str
    buyer_account_id: str
    seller_account_id: str
    ticker: str
    quantity: int
    price: float
