"""Repository for Instrument persistence."""

from __future__ import annotations

import typing as tp

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from shared.db.tables import instruments as instruments_t
from shared.models.domain import Instrument


def _f(val) -> tp.Optional[float]:
    return float(val) if val is not None else None


class InstrumentRepository:
    """Repository for Instrument persistence."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, instrument: Instrument) -> None:
        """Save an Instrument, inserting or updating as necessary."""
        async with self._engine.begin() as conn:
            await conn.execute(
                pg_insert(instruments_t)
                .values(
                    ticker=instrument.ticker,
                    name=instrument.name,
                    lot_size=instrument.lot_size,
                    max_order_size=instrument.max_order_size,
                    is_tradeable=instrument.is_tradeable,
                    last_price=instrument.last_price,
                )
                .on_conflict_do_update(
                    index_elements=['ticker'],
                    set_=dict(
                        name=instrument.name,
                        lot_size=instrument.lot_size,
                        max_order_size=instrument.max_order_size,
                        is_tradeable=instrument.is_tradeable,
                        last_price=instrument.last_price,
                    ),
                )
            )

    async def update_last_price(self, ticker: str, last_price: float) -> None:
        """Update the last traded price for a single instrument."""
        async with self._engine.begin() as conn:
            await conn.execute(
                update(instruments_t)
                .where(instruments_t.c.ticker == ticker)
                .values(last_price=last_price)
            )

    async def load_all(self) -> tp.List[Instrument]:
        """Load all instruments from the database."""
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(instruments_t))).mappings().all()
        return [
            Instrument(
                ticker=r['ticker'],
                name=r['name'],
                lot_size=int(r['lot_size']),
                max_order_size=int(r['max_order_size']),
                is_tradeable=bool(r['is_tradeable']),
                last_price=_f(r['last_price']),
            )
            for r in rows
        ]
