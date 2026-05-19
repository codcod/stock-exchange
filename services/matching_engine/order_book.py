"""
Single-ticker order book with price-time priority matching.

`PriceLevel` holds resting orders at one price; `OrderBook` manages both
sides and runs the matching loop when a new order arrives.
"""

from __future__ import annotations

import logging
import typing as tp
from collections import deque
from dataclasses import dataclass, field

from shared.domain.models import Order, OrderStatus, OrderType, Side, Trade

logger = logging.getLogger(__name__)


@dataclass
class PriceLevel:
    """
    A collection of resting orders at a single price on one side of the book.
    Orders are processed in FIFO (first-in, first-out) order.
    """

    price: float
    orders: tp.Deque[Order] = field(default_factory=deque)

    def total_quantity(self) -> int:
        """Return the total quantity of all orders at this price level."""
        return sum(o.remaining_quantity for o in self.orders)


class OrderBook:
    """
    A single-ticker order book that matches trades on price-time priority.

    The book is structured with two sorted lists of price levels:
    - `bids`: A list of `PriceLevel` objects, sorted descending (best bid first).
    - `asks`: A list of `PriceLevel` objects, sorted ascending (best ask first).
    """

    def __init__(self, ticker: str) -> None:
        self.ticker = ticker
        self.bids: tp.List[PriceLevel] = []
        self.asks: tp.List[PriceLevel] = []
        self.last_price: tp.Optional[float] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add_order(self, order: Order) -> tp.List[Trade]:
        """
        Add a new order to the book and attempt to match it.

        If the order is a limit order and is not fully filled, it will be
        added to the resting orders in the book.

        Returns the list of trades produced during matching.
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
        """
        Re-insert a resting order from storage without triggering matching.

        This is used during service startup to rebuild the order book from
        any orders that were active before a shutdown.
        """
        assert order.ticker == self.ticker
        self._rest(order)

    def cancel_order(self, order_id: str) -> bool:
        """Remove an order from the book. Returns True if found and removed."""
        return self._remove_resting_order(order_id)

    def best_bid(self) -> tp.Optional[float]:
        """Return the highest bid price, or None if no bids exist."""
        return self.bids[0].price if self.bids else None

    def best_ask(self) -> tp.Optional[float]:
        """Return the lowest ask price, or None if no asks exist."""
        return self.asks[0].price if self.asks else None

    def depth_snapshot(self, levels: int = 10) -> dict:
        """
        Return a snapshot of the order book depth.

        The snapshot includes the top N price levels for both bids and asks,
        along with the total quantity at each level.
        """
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
        """Attempt to match an incoming order against resting orders in the book."""
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
        """
        Create a trade and update the state of the involved orders.

        This method updates the filled quantity and average fill price for both
        the incoming and resting orders, sets their status, and creates a
        `Trade` object to represent the execution.
        """
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
        """Remove empty price levels from the specified side of the book."""
        if len(book_side) > 0 and len(book_side[0].orders) == 0:
            book_side.pop(0)

    def _remove_resting_order(self, order_id: str) -> bool:
        """Remove an order by ID. Returns True if found and removed."""
        for book_side in (self.bids, self.asks):
            for level in book_side:
                if level.orders and level.orders[0].order_id == order_id:
                    level.orders.popleft()
                    self._cleanup(book_side)
                    return True
        return False
