"""
Notifications service — event-driven per-account feed with WebSocket push.

Inbound event endpoints receive order lifecycle and trade events from the
OMS and Matching Engine outbox relays. Each event is persisted and
immediately broadcast to any connected WebSocket subscribers for the
relevant account.

HTTP backfill:
  GET /notifications/{account_id}?since=<iso>&limit=<n>

WebSocket push:
  GET /ws/notifications/{account_id}

Environment variables:
- `DATABASE_URL`: PostgreSQL connection string (required).
- `PORT`: HTTP port (default: 8007).
"""

from __future__ import annotations

import logging
import typing as tp
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect

from services.notifications.repository import NotificationRepository
from services.notifications.service import NotificationService
from services.notifications.tables import ensure_tables
from shared.domain.api_schemas import (
    OrderAcceptedEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderRejectedEvent,
    TradeExecutedEvent,
)
from shared.platform.db.connection import get_engine

logger = logging.getLogger(__name__)

_subscribers: tp.Dict[str, tp.Set[WebSocket]] = {}


@dataclass
class _AppState:
    svc: tp.Optional[NotificationService] = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_engine()
    await ensure_tables(db)
    _state.svc = NotificationService(NotificationRepository(db))
    yield


app = FastAPI(title='Notifications Service', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# WebSocket push
# ---------------------------------------------------------------------------


@app.websocket('/ws/notifications/{account_id}')
async def ws_notifications(account_id: str, ws: WebSocket) -> None:
    """Subscribe to live notifications for a specific account."""
    await ws.accept()
    _subscribers.setdefault(account_id, set()).add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _subscribers.get(account_id, set()).discard(ws)
    except Exception:
        _subscribers.get(account_id, set()).discard(ws)


# ---------------------------------------------------------------------------
# HTTP backfill
# ---------------------------------------------------------------------------


@app.get('/notifications/{account_id}')
async def get_notifications(
    account_id: str,
    since: tp.Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> tp.List[dict]:
    """Return recent notifications for an account (HTTP backfill)."""
    since_dt: tp.Optional[datetime] = None
    if since:
        since_dt = datetime.fromisoformat(since)
    return await _state.svc.list_for_account(account_id, since=since_dt, limit=limit)


# ---------------------------------------------------------------------------
# Inbound event endpoints (from OMS and Matching Engine outbox relays)
# ---------------------------------------------------------------------------


@app.post('/events/order-accepted')
async def on_order_accepted(req: OrderAcceptedEvent) -> dict:
    n = await _state.svc.add(req.account_id, 'OrderAccepted', req.model_dump())
    await _broadcast(req.account_id, n)
    return {}


@app.post('/events/order-rejected')
async def on_order_rejected(req: OrderRejectedEvent) -> dict:
    n = await _state.svc.add(req.account_id, 'OrderRejected', req.model_dump())
    await _broadcast(req.account_id, n)
    return {}


@app.post('/events/order-cancelled')
async def on_order_cancelled(req: OrderCancelledEvent) -> dict:
    n = await _state.svc.add(req.account_id, 'OrderCancelled', req.model_dump())
    await _broadcast(req.account_id, n)
    return {}


@app.post('/events/order-filled')
async def on_order_filled(req: OrderFilledEvent) -> dict:
    n = await _state.svc.add(req.account_id, 'OrderFilled', req.model_dump())
    await _broadcast(req.account_id, n)
    return {}


@app.post('/events/trade-executed')
async def on_trade_executed(req: TradeExecutedEvent) -> dict:
    """Fan trade-executed into one notification per party (buyer and seller)."""
    payload = req.model_dump()
    buyer_n = await _state.svc.add(req.buyer_account_id, 'TradeExecuted', payload)
    await _broadcast(req.buyer_account_id, buyer_n)
    if req.seller_account_id != req.buyer_account_id:
        seller_n = await _state.svc.add(req.seller_account_id, 'TradeExecuted', payload)
        await _broadcast(req.seller_account_id, seller_n)
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _broadcast(account_id: str, notification: dict) -> None:
    dead: tp.Set[WebSocket] = set()
    for ws in list(_subscribers.get(account_id, set())):
        try:
            await ws.send_json(notification)
        except Exception:
            dead.add(ws)
    _subscribers.get(account_id, set()).difference_update(dead)
