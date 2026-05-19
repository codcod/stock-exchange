"""
Shared async HTTP client helpers for inter-service calls.

Propagates the X-Request-ID correlation header automatically.
"""

from __future__ import annotations

import typing as tp

import httpx

from shared.platform.request_context import request_id as _request_id_ctx


def _correlation_headers() -> tp.Dict[str, str]:
    """Get correlation headers for the current request context."""
    rid = _request_id_ctx.get()
    return {'X-Request-ID': rid} if rid else {}


async def http_get(client: httpx.AsyncClient, url: str) -> tp.Any:
    """Perform an HTTP GET request, raising an exception for non-2xx responses."""
    resp = await client.get(url, headers=_correlation_headers())
    resp.raise_for_status()
    return resp.json()


async def http_post(client: httpx.AsyncClient, url: str, data: tp.Any) -> tp.Any:
    """Perform an HTTP POST request, raising an exception for non-2xx responses."""
    resp = await client.post(url, json=data, headers=_correlation_headers())
    resp.raise_for_status()
    return resp.json()


async def http_delete(client: httpx.AsyncClient, url: str) -> tp.Any:
    """Perform an HTTP DELETE request, raising an exception for non-2xx responses."""
    resp = await client.delete(url, headers=_correlation_headers())
    resp.raise_for_status()
    return resp.json()
