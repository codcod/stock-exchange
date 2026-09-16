"""
Clearing service — trade record keeper.

Receives TradeExecuted events from the Matching Engine outbox relay and
persists each trade to the clearing.trades table. Account settlement
(cash and position updates) is owned by the Account service.

Environment variables:
- `DATABASE_URL`: PostgreSQL connection string (required).
- `PORT`: HTTP port (default: 8004).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

from services.clearing.repository import TradeRepository
from services.clearing.service import ClearingService
from services.clearing.tables import ensure_tables
from shared.domain.api_schemas import TradeExecutedEvent
from shared.domain.events import TradeExecuted
from shared.platform.db.connection import get_engine

logger = logging.getLogger(__name__)


@dataclass
class _AppState:
    svc: ClearingService | None = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_engine()
    await ensure_tables(db)
    _state.svc = ClearingService(TradeRepository(db))
    yield


app = FastAPI(title='Clearing Service', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


@app.post('/events/trade-executed')
async def on_trade_executed(req: TradeExecutedEvent) -> dict:
    """Persist the trade record for the audit ledger."""
    event = TradeExecuted(
        trade_id=req.trade_id,
        buy_order_id=req.buy_order_id,
        sell_order_id=req.sell_order_id,
        buyer_account_id=req.buyer_account_id,
        seller_account_id=req.seller_account_id,
        ticker=req.ticker,
        quantity=req.quantity,
        price=req.price,
    )
    await _state.svc.on_trade_executed(event)
    return {}
