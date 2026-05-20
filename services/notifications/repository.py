"""Repository for Notification persistence."""

from __future__ import annotations

import json
import typing as tp
from datetime import datetime, timezone

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from services.notifications.tables import notifications as notifications_t


class NotificationRepository:
    """Persists and queries per-account notification records."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(
        self, notification_id: str, account_id: str, event_type: str, payload: dict
    ) -> dict:
        """Persist a single notification and return the stored record."""
        now = datetime.now(timezone.utc)
        async with self._engine.begin() as conn:
            await conn.execute(
                insert(notifications_t).values(
                    notification_id=notification_id,
                    account_id=account_id,
                    event_type=event_type,
                    payload=json.dumps(payload),
                    created_at=now,
                )
            )
        return {
            'notification_id': notification_id,
            'account_id': account_id,
            'event_type': event_type,
            'payload': payload,
            'created_at': now.isoformat(),
        }

    async def list_for_account(
        self,
        account_id: str,
        since: tp.Optional[datetime] = None,
        limit: int = 50,
    ) -> tp.List[dict]:
        """Return notifications for an account, newest first."""
        async with self._engine.connect() as conn:
            stmt = (
                select(notifications_t)
                .where(notifications_t.c.account_id == account_id)
                .order_by(notifications_t.c.created_at.desc())
                .limit(limit)
            )
            if since is not None:
                stmt = stmt.where(notifications_t.c.created_at > since)
            rows = (await conn.execute(stmt)).mappings().all()
        return [
            {
                'notification_id': r['notification_id'],
                'account_id': r['account_id'],
                'event_type': r['event_type'],
                'payload': json.loads(r['payload']),
                'created_at': r['created_at'].isoformat(),
            }
            for r in rows
        ]
