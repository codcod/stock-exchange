"""
Notifications service — per-account event feed.

Persists order and trade lifecycle events for each account and exposes
an HTTP backfill endpoint. WebSocket subscribers are managed in app.py.
"""

from __future__ import annotations

import typing as tp
import uuid
from datetime import datetime

if tp.TYPE_CHECKING:
    from services.notifications.repository import NotificationRepository


class NotificationService:
    """Persists per-account notifications and returns the stored record."""

    def __init__(self, repo: 'NotificationRepository') -> None:
        self._repo = repo

    async def add(self, account_id: str, event_type: str, payload: dict) -> dict:
        """Persist a notification and return the stored record for broadcasting."""
        notification_id = str(uuid.uuid4())
        return await self._repo.save(notification_id, account_id, event_type, payload)

    async def list_for_account(
        self,
        account_id: str,
        since: tp.Optional[datetime] = None,
        limit: int = 50,
    ) -> tp.List[dict]:
        """Return recent notifications for an account (HTTP backfill)."""
        return await self._repo.list_for_account(account_id, since=since, limit=limit)
