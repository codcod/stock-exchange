"""HTTP client for the Order Management service."""

from __future__ import annotations

import typing as tp

import httpx

from shared.domain.models import Order
from shared.platform.clients.converters import dict_to_order, order_to_dict
from shared.platform.http_client import http_delete, http_get, http_post


class OrderManagementClient:
    """HTTP client for the Order Management Service."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def submit_order(self, order: Order) -> Order:
        """Submit a new order."""
        data = await http_post(
            self._client, f'{self._base}/orders', order_to_dict(order)
        )
        return dict_to_order(data)

    async def cancel_order(self, order_id: str, account_id: str) -> bool:
        """Cancel an open order."""
        data = await http_delete(
            self._client,
            f'{self._base}/orders/{order_id}?account_id={account_id}',
        )
        return data.get('cancelled', False)

    async def get_order(self, order_id: str) -> tp.Optional[Order]:
        """Retrieve an order by its ID."""
        try:
            data = await http_get(self._client, f'{self._base}/orders/{order_id}')
            return dict_to_order(data)
        except Exception:
            return None

    async def get_open_orders(self) -> tp.List[Order]:
        """Get all orders with OPEN or PARTIALLY_FILLED status."""
        data = await http_get(self._client, f'{self._base}/orders/open')
        return [dict_to_order(o) for o in data]

    async def get_orders_for_account(self, account_id: str) -> tp.List[Order]:
        """Get all orders (historical and open) for a specific account."""
        data = await http_get(
            self._client, f'{self._base}/accounts/{account_id}/orders'
        )
        return [dict_to_order(o) for o in data]
