"""Repository for Trade persistence in the Clearing service."""

from __future__ import annotations

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from services.clearing.tables import trades as trades_t
from shared.domain.models import Trade


class TradeRepository:
    """Persists trade records produced by the matching engine."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, trade: Trade) -> None:
        """Insert a new trade record."""
        async with self._engine.begin() as conn:
            await conn.execute(
                insert(trades_t).values(
                    trade_id=trade.trade_id,
                    ticker=trade.ticker,
                    buy_order_id=trade.buy_order_id,
                    sell_order_id=trade.sell_order_id,
                    buyer_account_id=trade.buyer_account_id,
                    seller_account_id=trade.seller_account_id,
                    quantity=trade.quantity,
                    price=trade.price,
                    executed_at=trade.executed_at,
                )
            )
