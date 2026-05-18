"""
shared/http_client.py

Async HTTP helpers for inter-service communication.
Each service creates one httpx.AsyncClient (in its lifespan) and passes it here.

X-Request-ID is forwarded automatically when set in the current request context.
"""

from __future__ import annotations

import typing as tp

import httpx

from shared.request_context import request_id as _request_id_ctx


def _correlation_headers() -> tp.Dict[str, str]:
    rid = _request_id_ctx.get()
    return {'X-Request-ID': rid} if rid else {}


async def http_get(client: httpx.AsyncClient, url: str) -> tp.Any:
    resp = await client.get(url, headers=_correlation_headers())
    resp.raise_for_status()
    return resp.json()


async def http_post(client: httpx.AsyncClient, url: str, data: tp.Any) -> tp.Any:
    resp = await client.post(url, json=data, headers=_correlation_headers())
    resp.raise_for_status()
    return resp.json()


async def http_delete(client: httpx.AsyncClient, url: str) -> tp.Any:
    resp = await client.delete(url, headers=_correlation_headers())
    resp.raise_for_status()
    return resp.json()
