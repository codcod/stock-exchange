"""
A standalone FastAPI service that wraps the OrderManagementService,
responsible for handling the lifecycle of orders.

This service receives orders from the gateway, communicates with the
Risk Engine and Matching Engine via HTTP, and processes fill-event
callbacks from the Matching Engine.

Order lifecycle events (Accepted/Rejected/Cancelled) are published to the
Notifications service via a transactional outbox + background relay.

Environment variables:
- `DATABASE_URL`: The URL for the PostgreSQL database (required).
- `RISK_ENGINE_URL`: URL for the Risk Engine (default: http://localhost:8002).
- `MATCHING_ENGINE_URL`: URL for the Matching Engine (default: http://localhost:8003).
- `ACCOUNT_URL`: URL for the Account service (default: http://localhost:8006).
- `NOTIFICATIONS_URL`: URL for the Notifications service (default: http://localhost:8007).
- `PORT`: HTTP port (default: 8001).
"""

from __future__ import annotations

import asyncio
import json
import os
import typing as tp
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Query

from services.order_management.outbox_relay import run_relay
from services.order_management.outbox_repo import write_outbox_rows
from services.order_management.repository import OrderRepository
from services.order_management.service import OrderManagementService
from services.order_management.tables import ensure_tables
from shared.domain.api_schemas import OrderFilledEvent, OrderRequest
from shared.domain.events import OrderFilled
from shared.domain.models import OrderStatus
from shared.platform.clients.account import AccountClient
from shared.platform.clients.converters import order_to_dict
from shared.platform.clients.matching_engine import MatchingEngineClient
from shared.platform.clients.risk_engine import RiskEngineClient
from shared.platform.db.connection import get_engine

_RISK_URL = os.getenv('RISK_ENGINE_URL', 'http://localhost:8002')
_MATCHING_URL = os.getenv('MATCHING_ENGINE_URL', 'http://localhost:8003')
_ACCOUNT_URL = os.getenv('ACCOUNT_URL', 'http://localhost:8006')


@dataclass
class _AppState:
    svc: tp.Optional[OrderManagementService] = None
    http: tp.Optional[httpx.AsyncClient] = None
    db: object = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state.http = httpx.AsyncClient(timeout=10.0)
    _state.db = get_engine()
    await ensure_tables(_state.db)
    order_repo = OrderRepository(_state.db)

    risk_client = RiskEngineClient(_RISK_URL, _state.http)
    matching_client = MatchingEngineClient(_MATCHING_URL, _state.http)
    account_client = AccountClient(_ACCOUNT_URL, _state.http)
    _state.svc = OrderManagementService(
        risk_client, matching_client, order_repo, account_client
    )

    for order in await order_repo.load_all():
        _state.svc._orders[order.order_id] = order

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


app = FastAPI(title='Order Management Service', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# Order CRUD
# ---------------------------------------------------------------------------


@app.post('/orders', status_code=201)
async def submit_order(req: OrderRequest) -> dict:
    """Submit a new order for processing."""
    result = await _state.svc.submit_order(req.to_domain())
    event_type = (
        'OrderRejected' if result.status == OrderStatus.REJECTED else 'OrderAccepted'
    )
    await _enqueue_order_event(
        result.order_id,
        result.account_id,
        result.ticker,
        event_type,
        result.reject_reason,
    )
    return order_to_dict(result)


@app.get('/orders/open')
async def list_open_orders() -> tp.List[dict]:
    """Return all active orders for Matching Engine startup sync."""
    return [order_to_dict(o) for o in _state.svc.get_open_orders()]


@app.get('/orders/{order_id}')
async def get_order(order_id: str) -> dict:
    """Retrieve a single order by its unique ID."""
    order = _state.svc.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail='Order not found')
    return order_to_dict(order)


@app.delete('/orders/{order_id}')
async def cancel_order(order_id: str, account_id: str = Query(...)) -> dict:
    """Request cancellation of an active order."""
    order = _state.svc.get_order(order_id)
    cancelled = await _state.svc.cancel_order(order_id, account_id)
    if cancelled and order is not None:
        await _enqueue_order_event(
            order.order_id, order.account_id, order.ticker, 'OrderCancelled'
        )
    return {'cancelled': cancelled}


@app.get('/accounts/{account_id}/orders')
async def list_orders(account_id: str) -> tp.List[dict]:
    """Retrieve all orders for a specific account."""
    return [order_to_dict(o) for o in _state.svc.get_orders_for_account(account_id)]


# ---------------------------------------------------------------------------
# Event endpoint (called by Matching Engine after fills)
# ---------------------------------------------------------------------------


@app.post('/events/order-filled')
async def on_order_filled(req: OrderFilledEvent) -> dict:
    """Handle a fill event from the Matching Engine."""
    event = OrderFilled(
        order_id=req.order_id,
        account_id=req.account_id,
        fill_quantity=req.fill_quantity,
        fill_price=req.fill_price,
        is_fully_filled=req.is_fully_filled,
    )
    await _state.svc.on_order_filled(event)
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _enqueue_order_event(
    order_id: str,
    account_id: str,
    ticker: str,
    event_type: str,
    reason: tp.Optional[str] = None,
) -> None:
    payload: dict = {'order_id': order_id, 'account_id': account_id, 'ticker': ticker}
    if reason:
        payload['reason'] = reason
    now = datetime.now(timezone.utc)
    async with _state.db.begin() as conn:
        await write_outbox_rows(
            conn,
            [
                {
                    'event_id': str(uuid.uuid4()),
                    'event_type': event_type,
                    'destination': 'notifications',
                    'payload': json.dumps(payload),
                    'created_at': now,
                    'published_at': None,
                }
            ],
        )
