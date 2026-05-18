"""
This module provides a simple asynchronous database connection manager.
"""

import functools
import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine


@functools.lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('DATABASE_URL environment variable is required')
    # Normalize bare postgresql:// or postgres:// to use asyncpg driver
    for prefix in ('postgresql://', 'postgres://'):
        if url.startswith(prefix):
            url = 'postgresql+asyncpg://' + url[len(prefix) :]
            break
    return create_async_engine(url)


@asynccontextmanager
async def get_connection() -> AsyncConnection:
    engine = get_engine()
    async with engine.acquire() as conn:
        yield conn
