"""
A standalone FastAPI service that wraps the MatchingEngine.

After each match, this service writes events to the
`matching_engine.outbox` table. A background relay then delivers these
events via HTTP to the appropriate downstream services, ensuring that
trade and market data are updated across the system.

The events are routed as follows:
- `TradeExecuted`: Sent to `ClearingService` and `MarketDataService`.
- `OrderFilled`: Sent to `OrderManagementService`.
- `MarketDataUpdate`: Sent to `MarketDataService`.

Environment variables:
- `DATABASE_URL`: The URL for the PostgreSQL database (required).
- `CLEARING_URL`: The URL for the Clearing Service (default: `http://localhost:8004`).
- `ORDER_MANAGEMENT_URL`: The URL for the Order Management Service (default: `http://localhost:8001`).
- `MARKET_DATA_URL`: The URL for the Market Data Service (default: `http://localhost:8005`).
- `PORT`: The HTTP port on which the service will run (default: `8003`).
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Query

from services.matching_engine.matching import MatchingEngine
from services.matching_engine.outbox_relay import enqueue_events, run_relay
from services.matching_engine.tables import ensure_tables
from shared.domain.api_schemas import OrderRequest
from shared.platform.clients.order_management import OrderManagementClient
from shared.platform.db.connection import get_engine

logger = logging.getLogger(__name__)

_engine_svc = MatchingEngine()

_OMS_URL = os.getenv('ORDER_MANAGEMENT_URL', 'http://localhost:8001')


@dataclass
class _AppState:
    http: httpx.AsyncClient | None = None
    db: object = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown logic.

    - Initializes HTTP and database clients.
    - Restores open orders from the Order Management Service.
    - Starts the outbox relay background task.
    """
    _state.http = httpx.AsyncClient(timeout=10.0)
    _state.db = get_engine()
    await ensure_tables(_state.db)

    try:
        oms_client = OrderManagementClient(_OMS_URL, _state.http)
        for order in await oms_client.get_open_orders():
            _engine_svc.restore_order(order)
    except Exception:
        logger.warning(
            'Could not restore open orders from OMS — starting with empty books'
        )

    relay_task = asyncio.create_task(run_relay(_state.http, _state.db))
    try:
        yield
    finally:
        relay_task.cancel()
        try:
            await relay_task
        except asyncio.CancelledError:
            pass
        await _state.http.aclose()


app = FastAPI(title='Matching Engine', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    """Health check endpoint."""
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# Order endpoints
# ---------------------------------------------------------------------------


@app.post('/orders', status_code=201)
async def submit_order(req: OrderRequest) -> dict:
    """Submit a new order to the matching engine."""
    trades, events = await _engine_svc.submit(req.to_domain())
    if events:
        async with _state.db.begin() as conn:
            await enqueue_events(conn, events)
    return {
        'trades': [
            {
                'trade_id': t.trade_id,
                'ticker': t.ticker,
                'buy_order_id': t.buy_order_id,
                'sell_order_id': t.sell_order_id,
                'buyer_account_id': t.buyer_account_id,
                'seller_account_id': t.seller_account_id,
                'quantity': t.quantity,
                'price': t.price,
                'executed_at': t.executed_at.isoformat(),
            }
            for t in trades
        ]
    }


@app.post('/orders/restore', status_code=201)
async def restore_order(req: OrderRequest) -> dict:
    """
    Restore a resting order into the book without triggering matching.

    This is used during startup to rebuild the book from active orders
    that existed before a service restart.
    """
    _engine_svc.restore_order(req.to_domain())
    return {}


@app.delete('/orders/{order_id}')
async def cancel_order(order_id: str) -> dict:
    """Cancel an active order."""
    book_order = _find_order(order_id)
    if book_order is None:
        return {'cancelled': False}
    cancelled = await _engine_svc.cancel(book_order)
    return {'cancelled': cancelled}


@app.get('/books/{ticker}/depth')
async def get_depth(ticker: str, levels: int = Query(10, ge=1, le=25)) -> dict:
    """Get a snapshot of the order book depth for a given ticker."""
    depth = _engine_svc.snapshot(ticker, levels)
    if depth is None:
        return {'ticker': ticker, 'bids': [], 'asks': [], 'last_price': None}
    return depth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_order(order_id: str):
    """Walk all books to find the Order object for cancellation."""
    for book in _engine_svc._books.values():
        for side in (book.bids, book.asks):
            for level in side:
                for o in level.orders:
                    if o.order_id == order_id:
                        return o
    return None
