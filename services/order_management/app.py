"""
A standalone FastAPI service that wraps the OrderManagementService,
responsible for handling the lifecycle of orders.

This service receives orders from the gateway, communicates with the
Risk Engine and Matching Engine via HTTP, and processes fill-event
callbacks from the Matching Engine.

Environment variables:
- `DATABASE_URL`: The URL for the PostgreSQL database (required).
- `RISK_ENGINE_URL`: The URL for the Risk Engine Service (default: `http://localhost:8002`).
- `MATCHING_ENGINE_URL`: The URL for the Matching Engine Service (default: `http://localhost:8003`).
- `PORT`: The HTTP port on which the service will run (default: `8001`).
"""

from __future__ import annotations

import os
import typing as tp
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, HTTPException, Query

from services.order_management.schemas import OrderFilledEvent
from services.order_management.service import OrderManagementService
from shared.db.connection import get_engine
from shared.db.repos import OrderRepository
from shared.db.tables import ensure_tables
from shared.models.domain import OrderFilled
from shared.schemas import OrderRequest
from shared.service_clients import (
    ClearingClient,
    MatchingEngineClient,
    RiskEngineClient,
    _order_to_dict,
)

_RISK_URL = os.getenv('RISK_ENGINE_URL', 'http://localhost:8002')
_MATCHING_URL = os.getenv('MATCHING_ENGINE_URL', 'http://localhost:8003')
_CLEARING_URL = os.getenv('CLEARING_URL', 'http://localhost:8004')


@dataclass
class _AppState:
    svc: tp.Optional[OrderManagementService] = None
    http: tp.Optional[httpx.AsyncClient] = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state.http = httpx.AsyncClient(timeout=10.0)

    db = get_engine()
    await ensure_tables(db)
    order_repo = OrderRepository(db)

    risk_client = RiskEngineClient(_RISK_URL, _state.http)
    matching_client = MatchingEngineClient(_MATCHING_URL, _state.http)
    clearing_client = ClearingClient(_CLEARING_URL, _state.http)
    _state.svc = OrderManagementService(
        risk_client, matching_client, order_repo, clearing_client
    )

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
async def submit_order(req: OrderRequest) -> dict:
    result = await _state.svc.submit_order(req.to_domain())
    return _order_to_dict(result)


@app.get('/orders/open')
async def list_open_orders() -> tp.List[dict]:
    """
    Returns a list of all `OPEN` and `PARTIALLY_FILLED` orders. This
    endpoint is intended for use by the Matching Engine during startup
    to synchronize its state.
    """
    return [_order_to_dict(o) for o in _state.svc.get_open_orders()]


@app.get('/orders/{order_id}')
async def get_order(order_id: str) -> dict:
    order = _state.svc.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail='Order not found')
    return _order_to_dict(order)


@app.delete('/orders/{order_id}')
async def cancel_order(order_id: str, account_id: str = Query(...)) -> dict:
    cancelled = await _state.svc.cancel_order(order_id, account_id)
    return {'cancelled': cancelled}


@app.get('/accounts/{account_id}/orders')
async def list_orders(account_id: str) -> tp.List[dict]:
    return [_order_to_dict(o) for o in _state.svc.get_orders_for_account(account_id)]


# ---------------------------------------------------------------------------
# Event endpoint (called by Matching Engine after trades)
# ---------------------------------------------------------------------------


@app.post('/events/order-filled')
async def on_order_filled(req: OrderFilledEvent) -> dict:
    event = OrderFilled(
        order_id=req.order_id,
        account_id=req.account_id,
        fill_quantity=req.fill_quantity,
        fill_price=req.fill_price,
        is_fully_filled=req.is_fully_filled,
    )
    await _state.svc.on_order_filled(event)
    return {}
