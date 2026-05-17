"""
services/order_management/app.py

Standalone FastAPI service wrapping OrderManagementService.
Receives orders from the gateway, calls Risk Engine and Matching Engine via HTTP,
and accepts fill-event callbacks from the Matching Engine.

Environment variables:
  DATABASE_URL          — Postgres URL (required)
  RISK_ENGINE_URL       — default http://localhost:8002
  MATCHING_ENGINE_URL   — default http://localhost:8003
  PORT                  — default 8001
"""

from __future__ import annotations

import os
import typing as tp
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
from fastapi import FastAPI, HTTPException, Query

from services.order_management.service import OrderManagementService
from shared.db.connection import get_engine
from shared.db.repositories import OrderRepository
from shared.db.tables import ensure_tables
from shared.models.domain import Order, OrderFilled, OrderStatus, OrderType, Side
from shared.service_clients import (
    MatchingEngineClient,
    RiskEngineClient,
    _order_to_dict,
)

_state = SimpleNamespace(svc=None, http=None)

_RISK_URL = os.getenv('RISK_ENGINE_URL', 'http://localhost:8002')
_MATCHING_URL = os.getenv('MATCHING_ENGINE_URL', 'http://localhost:8003')


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state.http = httpx.AsyncClient(timeout=10.0)

    db = get_engine()
    await ensure_tables(db)
    order_repo = OrderRepository(db)

    risk_client = RiskEngineClient(_RISK_URL, _state.http)
    matching_client = MatchingEngineClient(_MATCHING_URL, _state.http)
    _state.svc = OrderManagementService(risk_client, matching_client, order_repo)

    for order in await order_repo.load_all():
        _state.svc._orders[order.order_id] = order

    yield
    await _state.http.aclose()


app = FastAPI(title='Order Management Service', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# Order CRUD
# ---------------------------------------------------------------------------


@app.post('/orders', status_code=201)
async def submit_order(data: dict) -> dict:
    assert _state.svc is not None
    order = Order(
        account_id=data['account_id'],
        ticker=data['ticker'],
        side=Side(data['side']),
        order_type=OrderType(data['order_type']),
        quantity=data['quantity'],
        price=data.get('price'),
        order_id=data['order_id'],
        status=OrderStatus(data['status']),
        filled_quantity=data['filled_quantity'],
    )
    result = await _state.svc.submit_order(order)
    return _order_to_dict(result)


@app.get('/orders/{order_id}')
async def get_order(order_id: str) -> dict:
    assert _state.svc is not None
    order = _state.svc.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail='Order not found')
    return _order_to_dict(order)


@app.delete('/orders/{order_id}')
async def cancel_order(order_id: str, account_id: str = Query(...)) -> dict:
    assert _state.svc is not None
    cancelled = await _state.svc.cancel_order(order_id, account_id)
    return {'cancelled': cancelled}


@app.get('/accounts/{account_id}/orders')
async def list_orders(account_id: str) -> tp.List[dict]:
    assert _state.svc is not None
    return [_order_to_dict(o) for o in _state.svc.get_orders_for_account(account_id)]


# ---------------------------------------------------------------------------
# Event endpoint (called by Matching Engine after trades)
# ---------------------------------------------------------------------------


@app.post('/events/order-filled')
async def on_order_filled(data: dict) -> dict:
    assert _state.svc is not None
    event = OrderFilled(
        order_id=data['order_id'],
        account_id=data['account_id'],
        fill_quantity=data['fill_quantity'],
        fill_price=data['fill_price'],
        is_fully_filled=data.get('is_fully_filled', False),
    )
    await _state.svc.on_order_filled(event)
    return {}
