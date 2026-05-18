"""Repository for Order persistence."""

from __future__ import annotations

import typing as tp
from datetime import datetime, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from shared.db.tables import orders as orders_t
from shared.models.domain import Order, OrderStatus, OrderType, Side


def _f(val) -> tp.Optional[float]:
    return float(val) if val is not None else None


class OrderRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, order: Order) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                insert(orders_t).values(
                    order_id=order.order_id,
                    account_id=order.account_id,
                    ticker=order.ticker,
                    side=order.side.value,
                    order_type=order.order_type.value,
                    quantity=order.quantity,
                    price=order.price,
                    status=order.status.value,
                    filled_quantity=order.filled_quantity,
                    average_fill_price=order.average_fill_price,
                    reject_reason=order.reject_reason,
                    created_at=order.created_at,
                    updated_at=order.updated_at,
                )
            )

    async def update(self, order: Order) -> None:
        order.updated_at = datetime.now(timezone.utc)
        async with self._engine.begin() as conn:
            await conn.execute(
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

    async def load_all(self) -> tp.List[Order]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(orders_t))).mappings().all()
        return [_row_to_order(r) for r in rows]

    async def load_open(self) -> tp.List[Order]:
        """Return only orders with OPEN or PARTIALLY_FILLED status."""
        async with self._engine.connect() as conn:
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
