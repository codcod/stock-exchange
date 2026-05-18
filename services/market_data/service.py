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

from shared.models.domain import MarketDataUpdate, TradeExecuted

logger = logging.getLogger(__name__)

MAX_TRADE_HISTORY = 200  # In-memory cache size for recent trades per ticker


@dataclass
class Quote:
    """A snapshot of the current market state for a single ticker."""

    ticker: str
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    volume_today: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TickerTrade:
    """A simplified representation of a trade for the public feed."""

    ticker: str
    price: float
    quantity: int
    executed_at: datetime


class MarketDataService:
    """
    An in-memory service that provides real-time and historical market data.

    This service subscribes to events from the matching engine to keep its
    internal state up-to-date. It provides query methods for clients to
    access quotes and trade history.
    """

    def __init__(self) -> None:
        self._quotes: tp.Dict[str, Quote] = {}
        self._trade_history: tp.Dict[str, tp.Deque[TickerTrade]] = {}

    # ------------------------------------------------------------------
    # Query interface
    # ------------------------------------------------------------------

    def get_quote(self, ticker: str) -> tp.Optional[Quote]:
        """Return the current quote for a given ticker."""
        return self._quotes.get(ticker)

    def get_trade_history(self, ticker: str, limit: int = 20) -> tp.List[TickerTrade]:
        """Return the most recent trades for a ticker, up to a given limit."""
        history = self._trade_history.get(ticker, deque())
        return list(history)[-limit:]

    def all_tickers(self) -> tp.List[str]:
        """Return a list of all tickers for which market data is available."""
        return list(self._quotes.keys())

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_market_data_update(self, md: MarketDataUpdate) -> None:
        """
        Handle a `MarketDataUpdate` event from the Matching Engine.

        This method updates the top-of-book quote, last trade price, and
        daily volume for the specified ticker.
        """
        quote = self._quotes.get(md.ticker)
        if quote is None:
            self._quotes[md.ticker] = Quote(
                ticker=md.ticker,
                bid=md.bid,
                ask=md.ask,
                last_price=md.last_price,
                volume_today=md.volume,
            )
        else:
            quote.bid = md.bid
            quote.ask = md.ask
            if md.last_price:
                quote.last_price = md.last_price
            quote.volume_today += md.volume
            quote.updated_at = datetime.now(timezone.utc)

    async def on_trade_executed(self, event: TradeExecuted) -> None:
        """
        Handle a `TradeExecuted` event from the Matching Engine.

        This method adds the trade to the in-memory history for the ticker.
        """
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
