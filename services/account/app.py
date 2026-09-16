"""
Account service — authoritative source of truth for account state.

Owns cash balances, share positions, and reservations. Settling a trade
and managing reservations happen here. Every mutation fans out an
AccountUpdated event so the Risk Engine stays current.

Two-track notification for the Risk Engine:
  1. Direct synchronous HTTP push (best-effort, fast) — keeps risk checks
     accurate with zero lag.
  2. Outbox relay (resilient, async) — handles restarts and retries.

Environment variables:
- `DATABASE_URL`: PostgreSQL connection string (required).
- `RISK_ENGINE_URL`: Risk Engine URL (default: http://localhost:8002).
- `PORT`: HTTP port (default: 8006).
"""

from __future__ import annotations

import asyncio
import logging
import os
import typing as tp
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, HTTPException

from services.account.outbox_relay import run_relay
from services.account.repository import AccountRepository
from services.account.service import AccountService
from services.account.tables import ensure_tables
from shared.domain.api_schemas import (
    RegisterAccountRequest,
    ReserveRequest,
    TradeExecutedEvent,
)
from shared.domain.events import TradeExecuted
from shared.domain.models import Account
from shared.platform.clients.risk_engine import RiskEngineClient
from shared.platform.db.connection import get_engine

logger = logging.getLogger(__name__)

_RISK_URL = os.getenv('RISK_ENGINE_URL', 'http://localhost:8002')


@dataclass
class _AppState:
    svc: tp.Optional[AccountService] = None
    risk: tp.Optional[RiskEngineClient] = None
    http: tp.Optional[httpx.AsyncClient] = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state.http = httpx.AsyncClient(timeout=10.0)
    _state.risk = RiskEngineClient(_RISK_URL, _state.http)
    db = get_engine()
    await ensure_tables(db)
    repo = AccountRepository(db)
    _state.svc = AccountService(repo, db)
    for account in await repo.load_all():
        _state.svc._accounts[account.account_id] = account

    relay_task = asyncio.create_task(run_relay(_state.http, db))
    try:
        yield
    finally:
        relay_task.cancel()
        try:
            await relay_task
        except asyncio.CancelledError:
            pass
        await _state.http.aclose()


app = FastAPI(title='Account Service', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------


@app.post('/accounts', status_code=201)
async def register_account(req: RegisterAccountRequest) -> dict:
    """Register a new trading account."""
    account = Account(
        account_id=req.account_id,
        name=req.name,
        cash_balance=req.cash_balance,
        reserved_cash=req.reserved_cash,
    )
    account.positions = dict(req.positions)
    account.reserved_shares = dict(req.reserved_shares)
    await _state.svc.register_account(account)
    await _push_risk(account)
    return {}


@app.get('/accounts')
async def list_accounts() -> tp.List[dict]:
    """Return all registered trading accounts."""
    return [_account_dict(a) for a in _state.svc.list_accounts()]


@app.get('/accounts/{account_id}')
async def get_account(account_id: str) -> dict:
    """Retrieve the current state of a single trading account."""
    account = _state.svc.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    return _account_dict(account)


# ---------------------------------------------------------------------------
# Reservation management (called by Order Management)
# ---------------------------------------------------------------------------


@app.post('/accounts/{account_id}/reservations/cash')
async def reserve_cash(account_id: str, req: ReserveRequest) -> dict:
    """Reserve or release cash for an open order."""
    account = await _state.svc.reserve_cash(account_id, req.delta)
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    await _push_risk(account)
    return {}


@app.post('/accounts/{account_id}/reservations/shares/{ticker}')
async def reserve_shares(account_id: str, ticker: str, req: ReserveRequest) -> dict:
    """Reserve or release shares for an open order."""
    account = await _state.svc.reserve_shares(account_id, ticker, int(req.delta))
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    await _push_risk(account)
    return {}


# ---------------------------------------------------------------------------
# Settlement (called by Matching Engine outbox relay)
# ---------------------------------------------------------------------------


@app.post('/events/trade-executed')
async def on_trade_executed(req: TradeExecutedEvent) -> dict:
    """Apply post-trade settlement: debit/credit cash and shares for both parties."""
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
    buyer, seller = await _state.svc.apply_settlement(event)
    for account in filter(None, [buyer, seller]):
        await _push_risk(account)
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _push_risk(account: Account) -> None:
    """Best-effort direct push to Risk Engine — failure is non-fatal."""
    try:
        await _state.risk.register_account(account)
    except Exception:
        logger.warning(
            'Failed to sync account %s to Risk Engine (outbox will retry)',
            account.account_id,
        )


def _account_dict(a: Account) -> dict:
    return {
        'account_id': a.account_id,
        'name': a.name,
        'cash_balance': a.cash_balance,
        'reserved_cash': a.reserved_cash,
        'positions': a.positions,
        'reserved_shares': a.reserved_shares,
        'created_at': a.created_at.isoformat(),
    }
