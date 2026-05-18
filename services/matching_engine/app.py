"""
services/matching_engine/app.py

Standalone FastAPI service wrapping MatchingEngine.
After each match, events are written to the outbox table (matching_engine.outbox)
and a background relay delivers them via HTTP to downstream services:
  - TradeExecuted  → ClearingService + MarketDataService
  - OrderFilled    → OrderManagementService
  - MarketDataUpdate → MarketDataService

Environment variables:
  DATABASE_URL          — Postgres URL (required)
  CLEARING_URL          — default http://localhost:8004
  ORDER_MANAGEMENT_URL  — default http://localhost:8001
  MARKET_DATA_URL       — default http://localhost:8005
  PORT                  — default 8003
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Query

from services.matching_engine.engine import MatchingEngine
from services.matching_engine.schemas import OrderRequest
from shared.db.connection import get_engine
from shared.db.repos import OutboxRepository, write_outbox_rows
from shared.db.tables import ensure_tables
from shared.service_clients import OrderManagementClient

logger = logging.getLogger(__name__)

_engine_svc = MatchingEngine()

_CLEARING_URL = os.getenv('CLEARING_URL', 'http://localhost:8004')
_OMS_URL = os.getenv('ORDER_MANAGEMENT_URL', 'http://localhost:8001')
_MARKET_DATA_URL = os.getenv('MARKET_DATA_URL', 'http://localhost:8005')


@dataclass
class _AppState:
    http: httpx.AsyncClient | None = None
    db: object = None


_state = _AppState()

_EVENT_DESTINATIONS: dict = {
    'TradeExecuted': ['clearing', 'market_data'],
    'OrderFilled': ['order_management'],
    'MarketDataUpdate': ['market_data'],
}
_DESTINATION_URLS: dict = {
    'clearing': _CLEARING_URL,
    'order_management': _OMS_URL,
    'market_data': _MARKET_DATA_URL,
}
_ENDPOINT_FOR_EVENT_TYPE: dict = {
    'TradeExecuted': '/events/trade-executed',
    'OrderFilled': '/events/order-filled',
    'MarketDataUpdate': '/events/market-data-update',
}

_RELAY_POLL_INTERVAL = 0.5


# ---------------------------------------------------------------------------
# Outbox write helper
# ---------------------------------------------------------------------------


async def _enqueue_events(conn, events: list) -> None:
    now = datetime.now(timezone.utc)
    rows = []
    for event in events:
        event_type = type(event).__name__
        payload = json.dumps(asdict(event), default=str)
        for dest in _EVENT_DESTINATIONS.get(event_type, []):
            rows.append(
                {
                    'event_id': event.event_id,
                    'event_type': event_type,
                    'destination': dest,
                    'payload': payload,
                    'created_at': now,
                    'published_at': None,
                }
            )
    await write_outbox_rows(conn, rows)


# ---------------------------------------------------------------------------
# Outbox relay background task
# ---------------------------------------------------------------------------


async def _outbox_relay() -> None:
    repo = OutboxRepository(_state.db)
    while True:
        try:
            rows = await repo.fetch_unpublished()
            for row in rows:
                dest_url = _DESTINATION_URLS.get(row['destination'])
                endpoint = _ENDPOINT_FOR_EVENT_TYPE.get(row['event_type'])
                if not dest_url or not endpoint:
                    logger.warning(
                        'Unknown destination/event: %s / %s',
                        row['destination'],
                        row['event_type'],
                    )
                    continue
                try:
                    resp = await _state.http.post(
                        f'{dest_url}{endpoint}',
                        json=json.loads(row['payload']),
                    )
                    resp.raise_for_status()
                    await repo.mark_published(row['id'])
                except Exception:
                    logger.exception('Relay failed for outbox row %d', row['id'])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Outbox relay poll error')
        await asyncio.sleep(_RELAY_POLL_INTERVAL)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    relay_task = asyncio.create_task(_outbox_relay())
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
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# Order endpoints
# ---------------------------------------------------------------------------


@app.post('/orders', status_code=201)
async def submit_order(req: OrderRequest) -> dict:
    trades, events = await _engine_svc.submit(req.to_domain())
    if events:
        async with _state.db.begin() as conn:
            await _enqueue_events(conn, events)
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
    _engine_svc.restore_order(req.to_domain())
    return {}


@app.delete('/orders/{order_id}')
async def cancel_order(order_id: str) -> dict:
    book_order = _find_order(order_id)
    if book_order is None:
        return {'cancelled': False}
    cancelled = await _engine_svc.cancel(book_order)
    return {'cancelled': cancelled}


@app.get('/books/{ticker}/depth')
async def get_depth(ticker: str, levels: int = Query(10, ge=1, le=25)) -> dict:
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
