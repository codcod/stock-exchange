"""HTTP client for the Notifications service."""

from __future__ import annotations

import typing as tp

import httpx


class NotificationsClient:
    """HTTP client for the Notifications service."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def get_notifications(
        self,
        account_id: str,
        since: tp.Optional[str] = None,
        limit: int = 50,
    ) -> tp.List[dict]:
        """Retrieve recent notifications for an account (HTTP backfill)."""
        params: tp.Dict[str, tp.Any] = {'limit': limit}
        if since:
            params['since'] = since
        resp = await self._client.get(
            f'{self._base}/notifications/{account_id}', params=params
        )
        resp.raise_for_status()
        return resp.json()
