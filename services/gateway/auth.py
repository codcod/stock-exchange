import os

from fastapi import Header, HTTPException, status

_API_KEY = os.getenv('EXCHANGE_API_KEY')


def require_api_key(x_api_key: str = Header(default='')) -> None:
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid API key'
        )
