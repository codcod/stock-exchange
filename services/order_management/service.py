"""
services/order_management/service.py

Owns the lifecycle of every order:
  - Validates incoming order structure
  - Assigns IDs and persists to the order store
  - Routes to the risk engine, then the matching engine
  - Processes cancellation requests
  - Listens for fill events to update order status
"""

from __future__ import annotations

import logging
import typing as tp

from shared.events.bus import (
    EventBus,
    OrderAccepted,
    OrderCancelled,
    OrderFilled,
    OrderRejected,
    OrderSubmitted,
)
from shared.models.domain import Order, OrderStatus, OrderType, Side

if tp.TYPE_CHECKING:
    from shared.db.repositories import OrderRepository

logger = logging.getLogger(__name__)


class OrderManagementService:
    """
    Central coordinator: receives orders, runs risk, sends to matching engine.
    """

    def __init__(
        self,
        risk_engine: tp.Any,
        matching_engine: tp.Any,
        event_bus: EventBus,
        order_repo: tp.Optional['OrderRepository'] = None,
    ) -> None:
        self._risk = risk_engine
        self._matching = matching_engine
        self._bus = event_bus
        self._orders: tp.Dict[str, Order] = {}
        self._order_repo = order_repo

        self._bus.subscribe(OrderFilled, self.on_order_filled)

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
        if self._order_repo:
            await self._order_repo.save(order)
        await self._bus.publish(
            OrderSubmitted(
                order_id=order.order_id,
                account_id=order.account_id,
                ticker=order.ticker,
            )
        )

        risk_result = await self._risk.check(order)
        if not risk_result.passed:
            order.status = OrderStatus.REJECTED
            order.reject_reason = risk_result.reason
            if self._order_repo:
                await self._order_repo.update(order)
            await self._bus.publish(
                OrderRejected(
                    order_id=order.order_id,
                    reason=risk_result.reason or 'Risk check failed',
                )
            )
            return order

        self._reserve(order)
        await self._bus.publish(OrderAccepted(order_id=order.order_id))
        await self._matching.submit(order)

        # Persist final state (fill/partial-fill already written via _on_order_filled;
        # this catches the OPEN case where no fill occurred)
        if self._order_repo:
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
            self._release(order)
            if self._order_repo:
                await self._order_repo.update(order)
            await self._bus.publish(OrderCancelled(order_id=order_id))
        return cancelled

    def get_order(self, order_id: str) -> tp.Optional[Order]:
        return self._orders.get(order_id)

    def get_orders_for_account(self, account_id: str) -> tp.List[Order]:
        return [o for o in self._orders.values() if o.account_id == account_id]

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_order_filled(self, event: OrderFilled) -> None:
        order = self._orders.get(event.order_id)
        if not order:
            return
        if order.status == OrderStatus.FILLED:
            self._release(order)
        if self._order_repo:
            await self._order_repo.update(order)

    # ------------------------------------------------------------------
    # Fund / share reservation
    # ------------------------------------------------------------------

    def _reserve(self, order: Order) -> None:
        if order.order_type == OrderType.LIMIT:
            if order.side == Side.BUY and order.price:
                self._risk.update_reserved_cash(
                    order.account_id, order.price * order.quantity
                )
            elif order.side == Side.SELL:
                self._risk.update_reserved_shares(
                    order.account_id, order.ticker, order.quantity
                )

    def _release(self, order: Order) -> None:
        remaining = order.remaining_quantity
        if remaining <= 0:
            return
        if order.order_type == OrderType.LIMIT:
            if order.side == Side.BUY and order.price:
                self._risk.update_reserved_cash(
                    order.account_id, -(order.price * remaining)
                )
            elif order.side == Side.SELL:
                self._risk.update_reserved_shares(
                    order.account_id, order.ticker, -remaining
                )
