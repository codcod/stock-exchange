import os
from typing import Optional

from exchange.main import Exchange
from shared.db.connection import get_engine

_exchange: Optional[Exchange] = None


async def get_exchange() -> Exchange:
    assert _exchange is not None, 'Exchange not initialised'
    return _exchange


async def init_exchange() -> Exchange:
    if os.getenv('DATABASE_URL'):
        return await Exchange.create(db_engine=get_engine())
    return await Exchange.create()
