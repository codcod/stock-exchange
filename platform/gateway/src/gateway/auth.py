"""
Provides a simple, optional API key authentication dependency for FastAPI.

If the `EXCHANGE_API_KEY` environment variable is set, this dependency
will require that all incoming requests include a matching `X-API-Key`
header. If the variable is not set, no authentication is performed.
"""

import os

from fastapi import Header, HTTPException, status

_API_KEY = os.getenv('EXCHANGE_API_KEY')


def require_api_key(x_api_key: str = Header(default='')) -> None:
    """
    FastAPI dependency that requires a valid API key if one is configured.
    """
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid API key'
        )
