"""
services/market_data/service.py

Subscribes to MarketDataUpdate events and maintains the latest
price / depth snapshot for each ticker. Clients poll this service
for quotes and trade history.
"""

from __future__ import annotations

import logging
import typing as tp
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from shared.models.domain import MarketDataUpdate, TradeExecuted

logger = logging.getLogger(__name__)

MAX_TRADE_HISTORY = 200  # keep last N trades per ticker


@dataclass
class Quote:
    ticker: str
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    volume_today: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TickerTrade:
    ticker: str
    price: float
    quantity: int
    executed_at: datetime


class MarketDataService:
    def __init__(self) -> None:
        self._quotes: tp.Dict[str, Quote] = {}
        self._trade_history: tp.Dict[str, tp.Deque[TickerTrade]] = {}

    # ------------------------------------------------------------------
    # Query interface
    # ------------------------------------------------------------------

    def get_quote(self, ticker: str) -> tp.Optional[Quote]:
        return self._quotes.get(ticker)

    def get_trade_history(self, ticker: str, limit: int = 20) -> tp.List[TickerTrade]:
        history = self._trade_history.get(ticker, deque())
        return list(history)[-limit:]

    def all_tickers(self) -> tp.List[str]:
        return list(self._quotes.keys())

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_market_data_update(self, event: MarketDataUpdate) -> None:
        quote = self._quotes.setdefault(
            event.ticker,
            Quote(ticker=event.ticker),
        )
        quote.bid = event.bid
        quote.ask = event.ask
        if event.last_price:
            quote.last_price = event.last_price
        quote.volume_today += event.volume
        quote.updated_at = datetime.now(timezone.utc)

    async def on_trade_executed(self, event: TradeExecuted) -> None:
        if event.ticker not in self._trade_history:
            self._trade_history[event.ticker] = deque(maxlen=MAX_TRADE_HISTORY)
        self._trade_history[event.ticker].append(
            TickerTrade(
                ticker=event.ticker,
                price=event.price,
                quantity=event.quantity,
                executed_at=datetime.now(timezone.utc),
            )
        )
