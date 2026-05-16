"""
services/clearing/app.py

Standalone FastAPI service wrapping ClearingService.
Settles trades (via HTTP event callbacks from the Matching Engine) and
manages account registration and queries.

Environment variables:
  DATABASE_URL  — Postgres URL (optional)
  PORT          — default 8004
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException

from services.clearing.service import ClearingService
from shared.db.connection import get_engine
from shared.db.repositories import AccountRepository, TradeRepository
from shared.db.tables import ensure_tables
from shared.events.bus import EventBus, TradeExecuted
from shared.models.domain import Account

_state = SimpleNamespace(svc=None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    account_repo = None
    trade_repo = None
    if os.getenv('DATABASE_URL'):
        db = get_engine()
        await ensure_tables(db)
        account_repo = AccountRepository(db)
        trade_repo = TradeRepository(db)

    local_bus = EventBus()
    _state.svc = ClearingService(
        local_bus, account_repo=account_repo, trade_repo=trade_repo
    )

    if account_repo:
        for account in await account_repo.load_all():
            _state.svc.register_account(account)

    yield


app = FastAPI(title='Clearing Service', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------


@app.post('/accounts', status_code=201)
async def register_account(data: dict) -> dict:
    assert _state.svc is not None
    account = Account(
        account_id=data['account_id'],
        name=data['name'],
        cash_balance=data['cash_balance'],
        reserved_cash=data.get('reserved_cash', 0.0),
    )
    account.positions = data.get('positions', {})
    account.reserved_shares = data.get('reserved_shares', {})
    _state.svc.register_account(account)

    if os.getenv('DATABASE_URL'):
        await AccountRepository(get_engine()).save(account)

    return {}


@app.get('/accounts/{account_id}')
async def get_account(account_id: str) -> dict:
    assert _state.svc is not None
    account = _state.svc.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    return {
        'account_id': account.account_id,
        'name': account.name,
        'cash_balance': account.cash_balance,
        'reserved_cash': account.reserved_cash,
        'positions': account.positions,
        'reserved_shares': account.reserved_shares,
        'created_at': account.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Event endpoint (called by Matching Engine after trades)
# ---------------------------------------------------------------------------


@app.post('/events/trade-executed')
async def on_trade_executed(data: dict) -> dict:
    assert _state.svc is not None
    event = TradeExecuted(
        trade_id=data['trade_id'],
        buy_order_id=data['buy_order_id'],
        sell_order_id=data['sell_order_id'],
        buyer_account_id=data['buyer_account_id'],
        seller_account_id=data['seller_account_id'],
        ticker=data['ticker'],
        quantity=data['quantity'],
        price=data['price'],
    )
    await _state.svc.on_trade_executed(event)
    return {}
