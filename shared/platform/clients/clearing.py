"""HTTP client for the Clearing service."""

from __future__ import annotations

import typing as tp

import httpx

from shared.domain.models import Account
from shared.platform.clients.converters import account_to_dict, dict_to_account
from shared.platform.http_client import http_get, http_post


class ClearingClient:
    """HTTP client for the Clearing service."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def list_accounts(self) -> tp.List[Account]:
        """Retrieve all registered accounts."""
        data = await http_get(self._client, f'{self._base}/accounts')
        return [dict_to_account(item) for item in data]

    async def register_account(self, account: Account) -> None:
        """Register a new trading account."""
        await http_post(
            self._client, f'{self._base}/accounts', account_to_dict(account)
        )

    async def get_account(self, account_id: str) -> tp.Optional[Account]:
        """Retrieve account details by ID."""
        try:
            data = await http_get(self._client, f'{self._base}/accounts/{account_id}')
            return dict_to_account(data)
        except Exception:
            return None

    async def reserve_cash(self, account_id: str, delta: float) -> None:
        """Update the amount of cash reserved by open BUY orders."""
        await http_post(
            self._client,
            f'{self._base}/accounts/{account_id}/reserve/cash',
            {'delta': delta},
        )

    async def reserve_shares(self, account_id: str, ticker: str, delta: int) -> None:
        """Update the number of shares reserved by open SELL orders."""
        await http_post(
            self._client,
            f'{self._base}/accounts/{account_id}/reserve/shares/{ticker}',
            {'delta': delta},
        )
