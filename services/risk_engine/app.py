"""
services/risk_engine/app.py

Standalone FastAPI service wrapping RiskEngine.
Exposes risk checks, account/instrument registration, and trading halts.

Environment variables:
  DATABASE_URL  — Postgres URL (optional; in-memory if absent)
  PORT          — HTTP port (default 8002)
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.risk_engine.engine import RiskEngine
from shared.db.connection import get_engine
from shared.db.repositories import AccountRepository, InstrumentRepository
from shared.db.tables import ensure_tables
from shared.models.domain import (
    Account,
    Instrument,
    Order,
    OrderStatus,
    OrderType,
    Side,
)

_engine_svc: RiskEngine = RiskEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv('DATABASE_URL'):
        db = get_engine()
        await ensure_tables(db)
        for instrument in await InstrumentRepository(db).load_all():
            _engine_svc.register_instrument(instrument)
        for account in await AccountRepository(db).load_all():
            _engine_svc.register_account(account)

    yield


app = FastAPI(title='Risk Engine', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# Account & instrument registration
# ---------------------------------------------------------------------------


@app.post('/accounts', status_code=201)
async def register_account(data: dict) -> dict:
    account = Account(
        account_id=data['account_id'],
        name=data['name'],
        cash_balance=data['cash_balance'],
        reserved_cash=data.get('reserved_cash', 0.0),
    )
    account.positions = data.get('positions', {})
    account.reserved_shares = data.get('reserved_shares', {})
    _engine_svc.register_account(account)
    return {}


@app.post('/instruments', status_code=201)
async def register_instrument(data: dict) -> dict:
    instrument = Instrument(
        ticker=data['ticker'],
        name=data['name'],
        lot_size=data.get('lot_size', 1),
        max_order_size=data.get('max_order_size', 10_000),
        is_tradeable=data.get('is_tradeable', True),
        last_price=data.get('last_price'),
    )

    if os.getenv('DATABASE_URL'):
        await InstrumentRepository(get_engine()).save(instrument)

    _engine_svc.register_instrument(instrument)
    return {}


# ---------------------------------------------------------------------------
# Risk check
# ---------------------------------------------------------------------------


@app.post('/orders/check')
async def check_order(data: dict) -> dict:
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
    result = await _engine_svc.check(order)
    return {'passed': result.passed, 'reason': result.reason}


# ---------------------------------------------------------------------------
# Reservation management
# ---------------------------------------------------------------------------


@app.post('/accounts/{account_id}/reserve/cash')
async def reserve_cash(account_id: str, data: dict) -> dict:
    _engine_svc.update_reserved_cash(account_id, data['delta'])
    return {}


@app.post('/accounts/{account_id}/reserve/shares/{ticker}')
async def reserve_shares(account_id: str, ticker: str, data: dict) -> dict:
    _engine_svc.update_reserved_shares(account_id, ticker, int(data['delta']))
    return {}


# ---------------------------------------------------------------------------
# Trading halts
# ---------------------------------------------------------------------------


@app.post('/halt/{ticker}')
async def halt(ticker: str) -> dict:
    _engine_svc.halt_ticker(ticker)
    return {}


@app.post('/resume/{ticker}')
async def resume(ticker: str) -> dict:
    _engine_svc.resume_ticker(ticker)
    return {}
