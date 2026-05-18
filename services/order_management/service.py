"""
services/order_management/service.py

Owns the lifecycle of every order:
  - Persists incoming orders (IDs are assigned by the Order constructor)
  - Routes to the risk engine, then the matching engine
  - Reserves cash or shares via the Clearing service while an order is open
  - Processes cancellation requests
  - Listens for fill events to update order status
"""

from __future__ import annotations

import logging
import typing as tp

from shared.models.domain import Order, OrderFilled, OrderStatus, OrderType, Side

if tp.TYPE_CHECKING:
    from shared.db.repos import OrderRepository

logger = logging.getLogger(__name__)


class OrderManagementService:
    """
    Central coordinator: receives orders, runs risk, sends to matching engine.
    Delegates reservation management to the Clearing service.
    """

    def __init__(
        self,
        risk_engine: tp.Any,
        matching_engine: tp.Any,
        order_repo: 'OrderRepository',
        clearing_engine: tp.Any,
    ) -> None:
        self._risk = risk_engine
        self._matching = matching_engine
        self._orders: tp.Dict[str, Order] = {}
        self._order_repo = order_repo
        self._clearing = clearing_engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit_order(self, order: Order) -> Order:
        """
        Main entry point. Returns the order with its final status set.
        """
        logger.info(
            'Received order %s | %s %s %d @ %s',
            order.order_id,
            order.side.value,
            order.ticker,
            order.quantity,
            order.price or 'MARKET',
        )

        self._orders[order.order_id] = order
        await self._order_repo.save(order)

        risk_result = await self._risk.check(order)
        if not risk_result.passed:
            order.status = OrderStatus.REJECTED
            order.reject_reason = risk_result.reason
            await self._order_repo.update(order)
            return order

        await self._reserve(order)
        order.status = OrderStatus.OPEN
        await self._matching.submit(order)
        await self._order_repo.update(order)

        return order

    async def cancel_order(self, order_id: str, account_id: str) -> bool:
        order = self._orders.get(order_id)
        if not order:
            logger.warning('Cancel request for unknown order %s', order_id)
            return False
        if order.account_id != account_id:
            logger.warning('Cancel request for order %s by wrong account', order_id)
            return False
        if not order.is_active:
            logger.info('Order %s is not active, cannot cancel', order_id)
            return False

        cancelled = await self._matching.cancel(order)
        if cancelled:
            await self._release(order)
            await self._order_repo.update(order)
        return cancelled

    def get_order(self, order_id: str) -> tp.Optional[Order]:
        return self._orders.get(order_id)

    def get_orders_for_account(self, account_id: str) -> tp.List[Order]:
        return [o for o in self._orders.values() if o.account_id == account_id]

    def get_open_orders(self) -> tp.List[Order]:
        return [o for o in self._orders.values() if o.is_active]

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_order_filled(self, event: OrderFilled) -> None:
        order = self._orders.get(event.order_id)
        if not order:
            return

        prev_filled = order.filled_quantity
        order.filled_quantity += event.fill_quantity

        prev_value = (order.average_fill_price or 0.0) * prev_filled
        order.average_fill_price = (
            prev_value + event.fill_price * event.fill_quantity
        ) / order.filled_quantity

        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        await self._order_repo.update(order)

    # ------------------------------------------------------------------
    # Fund / share reservation — delegated to Clearing
    # ------------------------------------------------------------------

    async def _reserve(self, order: Order) -> None:
        if order.order_type != OrderType.LIMIT:
            return
        if order.side == Side.BUY and order.price:
            await self._clearing.reserve_cash(
                order.account_id, order.price * order.quantity
            )
        elif order.side == Side.SELL:
            await self._clearing.reserve_shares(
                order.account_id, order.ticker, order.quantity
            )

    async def _release(self, order: Order) -> None:
        remaining = order.remaining_quantity
        if remaining <= 0 or order.order_type != OrderType.LIMIT:
            return
        if order.side == Side.BUY and order.price:
            await self._clearing.reserve_cash(
                order.account_id, -(order.price * remaining)
            )
        elif order.side == Side.SELL:
            await self._clearing.reserve_shares(
                order.account_id, order.ticker, -remaining
            )
