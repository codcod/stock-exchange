"""HTTP client for the Matching Engine service."""

from __future__ import annotations

import typing as tp

import httpx

from shared.domain.models import Order
from shared.platform.clients.converters import order_to_dict
from shared.platform.http_client import http_delete, http_get, http_post


class MatchingEngineClient:
    """HTTP client for the Matching Engine service."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def submit(self, order: Order) -> None:
        """Submit a new order to the matching engine."""
        await http_post(self._client, f'{self._base}/orders', order_to_dict(order))

    async def cancel(self, order: Order) -> bool:
        """Request to cancel an open order."""
        data = await http_delete(self._client, f'{self._base}/orders/{order.order_id}')
        return data.get('cancelled', False)

    async def snapshot(self, ticker: str, levels: int = 10) -> tp.Optional[dict]:
        """Fetch the order book depth snapshot for a ticker."""
        try:
            return await http_get(
                self._client, f'{self._base}/books/{ticker}/depth?levels={levels}'
            )
        except Exception:
            return None
