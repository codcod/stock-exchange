"""HTTP client for the Risk Engine service."""

from __future__ import annotations

import httpx

from shared.domain.api_schemas import RiskCheckResult
from shared.domain.models import Account, Instrument, Order
from shared.platform.clients.converters import (
    account_to_dict,
    instrument_to_dict,
    order_to_dict,
)
from shared.platform.http_client import http_post


class RiskEngineClient:
    """HTTP client for the Risk Engine service."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def check(self, order: Order) -> RiskCheckResult:
        """Run pre-trade risk checks on a new order."""
        data = await http_post(
            self._client, f'{self._base}/orders/check', order_to_dict(order)
        )
        return RiskCheckResult(passed=data['passed'], reason=data.get('reason'))

    async def register_account(self, account: Account) -> None:
        """Inform the risk engine of a new trading account."""
        await http_post(
            self._client, f'{self._base}/accounts', account_to_dict(account)
        )

    async def register_instrument(self, instrument: Instrument) -> None:
        """Inform the risk engine of a new tradeable instrument."""
        await http_post(
            self._client,
            f'{self._base}/instruments',
            instrument_to_dict(instrument),
        )

    async def halt_ticker(self, ticker: str) -> None:
        """Temporarily halt trading for a specific ticker."""
        await http_post(self._client, f'{self._base}/halt/{ticker}', {})

    async def resume_ticker(self, ticker: str) -> None:
        """Resume trading for a halted ticker."""
        await http_post(self._client, f'{self._base}/resume/{ticker}', {})
