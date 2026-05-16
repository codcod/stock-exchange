"""
services/market_data/service.py

Subscribes to MarketDataUpdate events and maintains the latest
price / depth snapshot for each ticker. Clients poll this service
for quotes and trade history.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, Dict, List, Optional

from shared.events.bus import EventBus, MarketDataUpdate, TradeExecuted

logger = logging.getLogger(__name__)

MAX_TRADE_HISTORY = 200  # keep last N trades per ticker


@dataclass
class Quote:
    ticker: str
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    volume_today: int = 0
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TickerTrade:
    ticker: str
    price: float
    quantity: int
    executed_at: datetime


class MarketDataService:
    def __init__(self, event_bus: EventBus) -> None:
        self._quotes: Dict[str, Quote] = {}
        self._trade_history: Dict[str, Deque[TickerTrade]] = {}

        event_bus.subscribe(MarketDataUpdate, self._on_market_data)
        event_bus.subscribe(TradeExecuted, self._on_trade_executed)

    # ------------------------------------------------------------------
    # Query interface
    # ------------------------------------------------------------------

    def get_quote(self, ticker: str) -> Optional[Quote]:
        return self._quotes.get(ticker)

    def get_trade_history(self, ticker: str, limit: int = 20) -> List[TickerTrade]:
        history = self._trade_history.get(ticker, deque())
        return list(history)[-limit:]

    def all_tickers(self) -> List[str]:
        return list(self._quotes.keys())

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _on_market_data(self, event: MarketDataUpdate) -> None:
        quote = self._quotes.setdefault(
            event.ticker,
            Quote(ticker=event.ticker),
        )
        if event.bid:
            quote.bid = event.bid
        if event.ask:
            quote.ask = event.ask
        if event.last_price:
            quote.last_price = event.last_price
        quote.volume_today += event.volume
        quote.updated_at = datetime.utcnow()

    async def _on_trade_executed(self, event: TradeExecuted) -> None:
        if event.ticker not in self._trade_history:
            self._trade_history[event.ticker] = deque(maxlen=MAX_TRADE_HISTORY)
        self._trade_history[event.ticker].append(
            TickerTrade(
                ticker=event.ticker,
                price=event.price,
                quantity=event.quantity,
                executed_at=datetime.utcnow(),
            )
        )
