"""
The market data service is responsible for maintaining the current
state of the market and persisting all trades.

It stores the following information in memory:
- The last trade price for each ticker.
- The best bid and ask for each ticker.

This service also provides access to the complete history of trades,
which is stored in the database.
"""

from __future__ import annotations

import logging
import typing as tp
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from shared.models.domain import MarketDataUpdate, Trade, TradeExecuted

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

    async def handle_market_data_update(self, md: MarketDataUpdate) -> None:
        """
        Updates the in-memory market data state with the latest top-of-book information.
        """
        self.last_prices[md.ticker] = md.last_price
        self.best_bids[md.ticker] = md.best_bid
        self.best_asks[md.ticker] = md.best_ask

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

    async def handle_trade(self, trade: Trade) -> None:
        """
        Persists a trade to the database and updates the last trade price.
        """
        await self.trades.add_trade(trade)
        self.last_prices[trade.ticker] = trade.price
