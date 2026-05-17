"""
shared/http_client.py

Async HTTP helpers for inter-service communication.
Each service creates one httpx.AsyncClient (in its lifespan) and passes it here.
"""

from __future__ import annotations

import typing as tp

import httpx


async def http_get(client: httpx.AsyncClient, url: str) -> tp.Any:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()


async def http_post(client: httpx.AsyncClient, url: str, data: tp.Any) -> tp.Any:
    resp = await client.post(url, json=data)
    resp.raise_for_status()
    return resp.json()


async def http_delete(client: httpx.AsyncClient, url: str) -> tp.Any:
    resp = await client.delete(url)
    resp.raise_for_status()
    return resp.json()
