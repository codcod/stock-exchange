"""Unit of work for the Order Management service."""

from __future__ import annotations

import typing as tp
from typing import Self

from base.unit_of_work import SqlAlchemyUnitOfWork

from order_management.repository import OrderRepository


class OrderManagementUnitOfWork(SqlAlchemyUnitOfWork):
    orders: OrderRepository

    @tp.override
    async def __aenter__(self) -> Self:
        _ = await super().__aenter__()
        self.orders = OrderRepository(self.connection)
        return self
