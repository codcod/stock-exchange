"""Repository for the Account service transactional outbox table."""

from __future__ import annotations

import typing as tp
from datetime import datetime, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from services.account.tables import outbox as outbox_t


async def write_outbox_rows(conn, rows: tp.List[dict]) -> None:
    """Insert rows into the outbox table within an existing transaction."""
    if rows:
        await conn.execute(insert(outbox_t), rows)


class OutboxRepository:
    """Repository for the Account service transactional outbox table."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def fetch_unpublished(self) -> tp.List[dict]:
        """Fetch all outbox rows that have not yet been marked as published."""
        async with self._engine.connect() as conn:
            result = await conn.execute(
                select(outbox_t)
                .where(outbox_t.c.published_at.is_(None))
                .order_by(outbox_t.c.id)
            )
            return [dict(row) for row in result.mappings().all()]

    async def mark_published(self, row_id: int) -> None:
        """Mark a single outbox row as published."""
        async with self._engine.begin() as conn:
            await conn.execute(
                update(outbox_t)
                .where(outbox_t.c.id == row_id)
                .values(published_at=datetime.now(timezone.utc))
            )
