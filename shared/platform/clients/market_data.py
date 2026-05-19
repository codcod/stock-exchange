"""HTTP client for the Market Data service."""

from __future__ import annotations

import typing as tp

import httpx

from shared.platform.http_client import http_get


class MarketDataClient:
    """HTTP client for the Market Data service."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def all_tickers(self) -> tp.List[str]:
        """Get a list of all tickers with available market data."""
        return await http_get(self._client, f'{self._base}/tickers')

    async def get_quote(self, ticker: str) -> tp.Optional[dict]:
        """Fetch the latest quote for a ticker."""
        try:
            return await http_get(self._client, f'{self._base}/quotes/{ticker}')
        except Exception:
            return None

    async def get_trade_history(self, ticker: str, limit: int = 20) -> tp.List[dict]:
        """Retrieve the most recent trades for a ticker."""
        return await http_get(
            self._client, f'{self._base}/trades/{ticker}?limit={limit}'
        )
