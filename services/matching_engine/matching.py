"""
Multi-ticker matching engine.

Owns one `OrderBook` per ticker and generates outbox events from `submit()`.
"""

from __future__ import annotations

import typing as tp

from services.matching_engine.order_book import OrderBook
from shared.domain.events import MarketDataUpdate, OrderFilled, TradeExecuted
from shared.domain.models import Order, Trade


class MatchingEngine:
    """
    A multi-ticker matching engine that manages one `OrderBook` per ticker.

    This class is the main entry point for submitting and canceling orders.
    It returns events from `submit()` so the caller can persist them using
    the outbox pattern, rather than pushing directly to a message bus.
    """

    def __init__(self) -> None:
        self._books: tp.Dict[str, OrderBook] = {}

    def get_or_create_book(self, ticker: str) -> OrderBook:
        """Return the order book for a ticker, creating it if it doesn't exist."""
        if ticker not in self._books:
            self._books[ticker] = OrderBook(ticker)
        return self._books[ticker]

    async def submit(self, order: Order) -> tp.Tuple[tp.List[Trade], tp.List]:
        """
        Submit an order to the appropriate order book and generate events.

        This method returns a tuple containing:
        - A list of `Trade` objects that were executed.
        - A list of events (`TradeExecuted`, `OrderFilled`, `MarketDataUpdate`)
          to be sent to downstream services.
        """
        book = self.get_or_create_book(order.ticker)
        trades = book.add_order(order)
        events: tp.List = []

        for trade in trades:
            events.append(
                TradeExecuted(
                    trade_id=trade.trade_id,
                    buy_order_id=trade.buy_order_id,
                    sell_order_id=trade.sell_order_id,
                    buyer_account_id=trade.buyer_account_id,
                    seller_account_id=trade.seller_account_id,
                    ticker=trade.ticker,
                    quantity=trade.quantity,
                    price=trade.price,
                )
            )
            for order_id, account_id in [
                (trade.buy_order_id, trade.buyer_account_id),
                (trade.sell_order_id, trade.seller_account_id),
            ]:
                events.append(
                    OrderFilled(
                        order_id=order_id,
                        account_id=account_id,
                        fill_quantity=trade.quantity,
                        fill_price=trade.price,
                        is_fully_filled=False,
                    )
                )

        bid = book.best_bid()
        ask = book.best_ask()
        if bid or ask or book.last_price:
            events.append(
                MarketDataUpdate(
                    ticker=order.ticker,
                    bid=bid or 0.0,
                    ask=ask or 0.0,
                    last_price=book.last_price or 0.0,
                    volume=sum(t.quantity for t in trades),
                )
            )

        return trades, events

    def restore_order(self, order: Order) -> None:
        """Re-insert a resting order from storage without triggering matching."""
        book = self.get_or_create_book(order.ticker)
        book.restore_order(order)

    async def cancel(self, order: Order) -> bool:
        """Cancel an active order in the corresponding order book."""
        book = self._books.get(order.ticker)
        if book:
            return book.cancel_order(order.order_id)
        return False

    def snapshot(self, ticker: str, levels: int = 10) -> tp.Optional[dict]:
        """Return a depth snapshot for a given ticker's order book."""
        book = self._books.get(ticker)
        return book.depth_snapshot(levels) if book else None
