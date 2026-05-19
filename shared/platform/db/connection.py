"""
Async database engine factory.
"""

import functools
import os

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@functools.lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """
    Create and return a new asynchronous SQLAlchemy engine.

    The engine is cached, so subsequent calls will return the same instance.
    The database URL is read from the `DATABASE_URL` environment variable.
    """
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('DATABASE_URL environment variable is required')
    # Normalize bare postgresql:// or postgres:// to use asyncpg driver
    for prefix in ('postgresql://', 'postgres://'):
        if url.startswith(prefix):
            url = 'postgresql+asyncpg://' + url[len(prefix) :]
            break
    return create_async_engine(url)
