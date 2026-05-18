"""
The matching engine is responsible for maintaining a distinct order book
for each ticker and matching orders based on price-time priority.

The matching logic is as follows:
- The buy side is sorted in descending order by price, giving priority
  to the highest bid.
- The sell side is sorted in ascending order by price, giving priority
  to the lowest ask.
- A match occurs when the best bid is greater than or equal to the best ask.
"""

from __future__ import annotations

import logging
import typing as tp
from collections import deque
from dataclasses import dataclass, field

from shared.models.domain import (
    MarketDataUpdate,
    Order,
    OrderFilled,
    OrderStatus,
    OrderType,
    Side,
    Trade,
    TradeExecuted,
)

logger = logging.getLogger(__name__)


@dataclass
class PriceLevel:
    """
    Represents all resting orders at a single price on one side of the order book.
    """

    price: float
    orders: tp.Deque[Order] = field(default_factory=deque)

    def total_quantity(self) -> int:
        return sum(o.remaining_quantity for o in self.orders)


class OrderBook:
    """
    A single-ticker order book with the following internal structure:
    - `bids`: A list of `PriceLevel` objects, sorted in descending order
      (best bid first).
    - `asks`: A list of `PriceLevel` objects, sorted in ascending order
      (best ask first).
    """

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        self.bids: tp.List[PriceLevel] = []  # buy orders
        self.asks: tp.List[PriceLevel] = []  # sell orders
        self.last_price: tp.Optional[float] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add_order(self, order: Order) -> tp.List[Trade]:
        """
        Adds a new order to the book and attempts to match it. Returns
        the list of trades produced during matching.
        """
        assert order.ticker == self.ticker
        trades = self._match(order)

        # If the order is not fully filled, add it to the book
        if order.remaining_quantity > 0 and order.order_type == OrderType.LIMIT:
            self._rest(order)
            if order.status != OrderStatus.PARTIALLY_FILLED:
                order.status = OrderStatus.OPEN

        return trades

    def restore_order(self, order: Order) -> None:
        """Re-insert a resting order from storage without triggering matching."""
        assert order.ticker == self.ticker
        self._rest(order)

    def cancel_order(self, order_id: str) -> bool:
        """Removes an order from the book. Returns True if found and removed."""
        return self._remove_resting_order(order_id)

    def best_bid(self) -> tp.Optional[float]:
        return self.bids[0].price if self.bids else None

    def best_ask(self) -> tp.Optional[float]:
        return self.asks[0].price if self.asks else None

    def depth_snapshot(self, levels: int = 10) -> dict:
        return {
            'ticker': self.ticker,
            'bids': [
                {'price': lvl.price, 'quantity': lvl.total_quantity()}
                for lvl in self.bids[:levels]
            ],
            'asks': [
                {'price': lvl.price, 'quantity': lvl.total_quantity()}
                for lvl in self.asks[:levels]
            ],
            'last_price': self.last_price,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _match(self, incoming: Order) -> tp.List[Trade]:  # noqa: C901
        trades = []

        if incoming.side == Side.BUY:
            resting_side = self.asks

            def price_ok(resting_price: float) -> bool:
                if incoming.order_type == OrderType.MARKET:
                    return True
                return incoming.price >= resting_price  # type: ignore[operator]
        else:
            resting_side = self.bids

            def price_ok(resting_price: float) -> bool:
                if incoming.order_type == OrderType.MARKET:
                    return True
                return incoming.price <= resting_price  # type: ignore[operator]

        while incoming.remaining_quantity > 0 and resting_side:
            best_level = resting_side[0]
            if not price_ok(best_level.price):
                break

            while incoming.remaining_quantity > 0 and best_level.orders:
                resting = best_level.orders[0]
                fill_qty = min(incoming.remaining_quantity, resting.remaining_quantity)
                fill_price = best_level.price  # resting order sets the price

                trade = self._execute_fill(incoming, resting, fill_qty, fill_price)
                trades.append(trade)
                self.last_price = fill_price

                if resting.remaining_quantity == 0:
                    best_level.orders.popleft()

            if not best_level.orders:
                resting_side.pop(0)

        return trades

    def _execute_fill(
        self,
        incoming: Order,
        resting: Order,
        qty: int,
        price: float,
    ) -> Trade:
        # Update quantities and VWAP average fill price
        for order in (incoming, resting):
            old_filled = order.filled_quantity
            new_filled = old_filled + qty
            order.average_fill_price = (
                (order.average_fill_price or 0.0) * old_filled + price * qty
            ) / new_filled
            order.filled_quantity = new_filled

        # Update statuses
        for order in (incoming, resting):
            if order.filled_quantity == order.quantity:
                order.status = OrderStatus.FILLED
            elif order.filled_quantity > 0:
                order.status = OrderStatus.PARTIALLY_FILLED

        # Determine buy/sell sides
        if incoming.side == Side.BUY:
            buyer, seller = incoming, resting
        else:
            buyer, seller = resting, incoming

        trade = Trade(
            ticker=self.ticker,
            buy_order_id=buyer.order_id,
            sell_order_id=seller.order_id,
            buyer_account_id=buyer.account_id,
            seller_account_id=seller.account_id,
            quantity=qty,
            price=price,
        )

        logger.info(
            'TRADE %s | %s x %.2f | buyer=%s seller=%s',
            self.ticker,
            qty,
            price,
            buyer.account_id,
            seller.account_id,
        )
        return trade

    def _rest(self, order: Order) -> None:
        """Insert a limit order into the resting book at the correct price level."""
        book_side = self.bids if order.side == Side.BUY else self.asks
        reverse = order.side == Side.BUY  # bids sorted descending

        # Find the correct price level to insert the order
        for level in book_side:
            if level.price == order.price:
                level.orders.append(order)
                return

        # If no suitable level is found, add a new price level at the end
        book_side.append(PriceLevel(price=order.price, orders=deque([order])))
        book_side.sort(key=lambda lvl: lvl.price, reverse=reverse)

    @staticmethod
    def _cleanup(book_side: list[PriceLevel]) -> None:
        """
        Removes empty price levels from the specified side of the book.
        """
        if len(book_side) > 0 and len(book_side[0].orders) == 0:
            book_side.pop(0)

    def _remove_resting_order(self, order_id: str) -> bool:
        """Removes an order by ID. Returns True if found and removed."""
        for book_side in (self.bids, self.asks):
            for level in book_side:
                if level.orders and level.orders[0].order_id == order_id:
                    level.orders.popleft()
                    self._cleanup(book_side)
                    return True
        return False


class MatchingEngine:
    """
    Manages one OrderBook per ticker. Returns events from submit() so the
    caller can persist them (outbox pattern) rather than pushing via a bus.
    """

    def __init__(self) -> None:
        self._books: tp.Dict[str, OrderBook] = {}

    def get_or_create_book(self, ticker: str) -> OrderBook:
        if ticker not in self._books:
            self._books[ticker] = OrderBook(ticker)
        return self._books[ticker]

    async def submit(self, order: Order) -> tp.Tuple[tp.List[Trade], tp.List]:
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
        book = self._books.get(order.ticker)
        if book:
            return book.cancel_order(order.order_id)
        return False

    def snapshot(self, ticker: str, levels: int = 10) -> tp.Optional[dict]:
        book = self._books.get(ticker)
        return book.depth_snapshot(levels) if book else None
