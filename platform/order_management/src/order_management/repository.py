"""Repository for Order persistence."""

from __future__ import annotations

import typing as tp
from datetime import datetime, timezone

from base.domain.models import Order, OrderStatus, OrderType, Side
from base.repository import AbstractRepository
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from order_management.tables import orders as orders_t


def _f(val) -> tp.Optional[float]:
    return float(val) if val is not None else None


class OrderRepository(AbstractRepository[Order]):
    """Repository for Order persistence."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, item: Order) -> None:
        """Insert a new Order using this repository's connection."""
        await self._connection.execute(
            insert(orders_t).values(
                order_id=item.order_id,
                account_id=item.account_id,
                ticker=item.ticker,
                side=item.side.value,
                order_type=item.order_type.value,
                quantity=item.quantity,
                price=item.price,
                status=item.status.value,
                filled_quantity=item.filled_quantity,
                average_fill_price=item.average_fill_price,
                reject_reason=item.reject_reason,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )

    async def get(self, id: str) -> Order | None:
        """Fetch a single order by id."""
        row = (
            (
                await self._connection.execute(
                    select(orders_t).where(orders_t.c.order_id == id)
                )
            )
            .mappings()
            .first()
        )
        return _row_to_order(row) if row is not None else None

    async def update(self, order: Order) -> None:
        """Update an existing Order in the database."""
        order.updated_at = datetime.now(timezone.utc)
        await self._connection.execute(
            update(orders_t)
            .where(orders_t.c.order_id == order.order_id)
            .values(
                status=order.status.value,
                filled_quantity=order.filled_quantity,
                average_fill_price=order.average_fill_price,
                reject_reason=order.reject_reason,
                updated_at=order.updated_at,
            )
        )


async def load_all_orders(engine: AsyncEngine) -> tp.List[Order]:
    """Load all orders from the database (startup hydration)."""
    async with engine.connect() as conn:
        rows = (await conn.execute(select(orders_t))).mappings().all()
    return [_row_to_order(r) for r in rows]


async def load_open_orders(engine: AsyncEngine) -> tp.List[Order]:
    """Return only orders with OPEN or PARTIALLY_FILLED status (startup hydration)."""
    async with engine.connect() as conn:
        rows = (
            (
                await conn.execute(
                    select(orders_t).where(
                        orders_t.c.status.in_(
                            [
                                OrderStatus.OPEN.value,
                                OrderStatus.PARTIALLY_FILLED.value,
                            ]
                        )
                    )
                )
            )
            .mappings()
            .all()
        )
    return [_row_to_order(r) for r in rows]


def _row_to_order(r) -> Order:
    """Convert a database row to an Order domain object."""
    return Order(
        account_id=r['account_id'],
        ticker=r['ticker'],
        side=Side(r['side']),
        order_type=OrderType(r['order_type']),
        quantity=int(r['quantity']),
        price=_f(r['price']),
        order_id=r['order_id'],
        status=OrderStatus(r['status']),
        filled_quantity=int(r['filled_quantity']),
        average_fill_price=_f(r['average_fill_price']),
        reject_reason=r['reject_reason'],
        created_at=r['created_at'],
        updated_at=r['updated_at'],
    )
