"""
HTTP calls to the five instrumented services' `GET /metrics` endpoints.
Each returns `None` on timeout/connection error — treated as "service down"
by the card renderer, not a crash. The existing `GET /health` per card still
drives the UP/DOWN status pill; a `/metrics` failure only blanks that card's
stat values.
"""

from __future__ import annotations

import httpx


async def _get_metrics(client: httpx.AsyncClient, base_url: str) -> dict | None:
    try:
        resp = await client.get(f'{base_url.rstrip("/")}/metrics')
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        return None


async def get_gateway_metrics(client: httpx.AsyncClient, base_url: str) -> dict | None:
    return await _get_metrics(client, base_url)


async def get_market_data_metrics(
    client: httpx.AsyncClient, base_url: str
) -> dict | None:
    return await _get_metrics(client, base_url)


async def get_risk_engine_metrics(
    client: httpx.AsyncClient, base_url: str
) -> dict | None:
    return await _get_metrics(client, base_url)


async def get_matching_engine_metrics(
    client: httpx.AsyncClient, base_url: str
) -> dict | None:
    return await _get_metrics(client, base_url)


async def get_notifications_metrics(
    client: httpx.AsyncClient, base_url: str
) -> dict | None:
    return await _get_metrics(client, base_url)
