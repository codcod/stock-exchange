"""
Manages the entire lifecycle of every order, from submission to final
settlement.

This service is responsible for:
- Persisting incoming orders, with order IDs assigned by the `Order`
  constructor.
- Routing orders to the risk engine for pre-trade checks and then to
  the matching engine for execution.
- Reserving cash or shares through the Clearing service for the
  duration that an order is open.
- Processing cancellation requests for open orders.
- Listening for fill events from the matching engine to update the
  order status accordingly.
"""

from __future__ import annotations

import logging
import typing as tp

from shared.domain.events import OrderFilled
from shared.domain.models import Order, OrderStatus, OrderType, Side

if tp.TYPE_CHECKING:
    from services.order_management.repository import OrderRepository
    from shared.platform.clients.account import AccountClient
    from shared.platform.clients.matching_engine import MatchingEngineClient
    from shared.platform.clients.risk_engine import RiskEngineClient

logger = logging.getLogger(__name__)


class OrderManagementService:
    """
    A central coordinator that receives orders, performs risk checks,
    and sends them to the matching engine. It also delegates reservation
    management to the Clearing service to ensure that funds and shares
    are appropriately handled.
    """

    def __init__(
        self,
        risk_engine: 'RiskEngineClient',
        matching_engine: 'MatchingEngineClient',
        order_repo: 'OrderRepository',
        account_client: 'AccountClient',
    ) -> None:
        self._risk = risk_engine
        self._matching = matching_engine
        self._orders: tp.Dict[str, Order] = {}
        self._order_repo = order_repo
        self._account = account_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit_order(self, order: Order) -> Order:
        """
        Submit a new order, validate it, and route it to the matching engine.

        This is the main entry point for order submission. The method performs
        the following steps:
        1. Persists the order to the database.
        2. Sends the order to the Risk Engine for pre-trade checks.
        3. If the checks pass, it reserves the required cash or shares via
           the Clearing service.
        4. Finally, it submits the order to the Matching Engine.

        Returns the order with its final status set after processing.
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
        """
        Request cancellation of an active order.

        The request is forwarded to the Matching Engine. If the cancellation
        is successful, any reserved cash or shares are released.
        """
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
            order.status = OrderStatus.CANCELLED
            await self._release(order)
            await self._order_repo.update(order)
        return cancelled

    def get_order(self, order_id: str) -> tp.Optional[Order]:
        """Retrieve a single order by its ID."""
        return self._orders.get(order_id)

    def get_orders_for_account(self, account_id: str) -> tp.List[Order]:
        """Retrieve all orders belonging to a specific account."""
        return [o for o in self._orders.values() if o.account_id == account_id]

    def get_open_orders(self) -> tp.List[Order]:
        """Retrieve all orders that are currently active (open or partially filled)."""
        return [o for o in self._orders.values() if o.is_active]

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_order_filled(self, event: OrderFilled) -> None:
        """
        Handle an `OrderFilled` event from the Matching Engine.

        This method updates the order's filled quantity, average fill price,
        and status. The changes are then persisted to the database.
        """
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
        """
        Reserve cash for a BUY order or shares for a SELL order.

        For limit orders, this method calls the Clearing service to place a
        hold on the required assets, ensuring they are not used by other orders.
        """
        if order.order_type != OrderType.LIMIT:
            return
        if order.side == Side.BUY and order.price:
            await self._account.reserve_cash(
                order.account_id, order.price * order.quantity
            )
        elif order.side == Side.SELL:
            await self._account.reserve_shares(
                order.account_id, order.ticker, order.quantity
            )

    async def _release(self, order: Order) -> None:
        """
        Release any remaining reserved cash or shares for a cancelled order.

        If an order is cancelled before it is fully filled, this method calls
        the Clearing service to release the hold on the remaining assets.
        """
        remaining = order.remaining_quantity
        if remaining <= 0 or order.order_type != OrderType.LIMIT:
            return
        if order.side == Side.BUY and order.price:
            await self._account.reserve_cash(
                order.account_id, -(order.price * remaining)
            )
        elif order.side == Side.SELL:
            await self._account.reserve_shares(
                order.account_id, order.ticker, -remaining
            )
