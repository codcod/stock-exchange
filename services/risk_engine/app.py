"""
A standalone FastAPI service that wraps the RiskEngine, providing
endpoints for risk checks, account and instrument registration, and
trading halts.

This service is responsible for ensuring that all trading activities
comply with the defined risk rules before they are processed by the
matching engine.

Environment variables:
- `DATABASE_URL`: The URL for the PostgreSQL database (required).
- `PORT`: The HTTP port on which the service will run (default: 8002).
"""

from __future__ import annotations

import typing as tp
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI

from services.risk_engine.engine import RiskEngine
from services.risk_engine.schemas import (
    RegisterAccountRequest,
    RegisterInstrumentRequest,
)
from shared.db.connection import get_engine
from shared.db.repos import AccountRepository, InstrumentRepository
from shared.db.tables import ensure_tables
from shared.models.domain import Account, Instrument
from shared.schemas import OrderRequest

_engine_svc: RiskEngine = RiskEngine()


@dataclass
class _AppState:
    instrument_repo: tp.Optional[InstrumentRepository] = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_engine()
    await ensure_tables(db)
    _state.instrument_repo = InstrumentRepository(db)
    for instrument in await _state.instrument_repo.load_all():
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
async def register_account(req: RegisterAccountRequest) -> dict:
    """Register a new trading account in the risk engine's cache."""
    account = Account(
        account_id=req.account_id,
        name=req.name,
        cash_balance=req.cash_balance,
        reserved_cash=req.reserved_cash,
    )
    account.positions = dict(req.positions)
    account.reserved_shares = dict(req.reserved_shares)
    _engine_svc.register_account(account)
    return {}


@app.post('/instruments', status_code=201)
async def register_instrument(req: RegisterInstrumentRequest) -> dict:
    """Register a new tradeable instrument."""
    instrument = Instrument(
        ticker=req.ticker,
        name=req.name,
        lot_size=req.lot_size,
        max_order_size=req.max_order_size,
        is_tradeable=req.is_tradeable,
        last_price=req.last_price,
    )
    await _state.instrument_repo.save(instrument)
    _engine_svc.register_instrument(instrument)
    return {}


# ---------------------------------------------------------------------------
# Risk check
# ---------------------------------------------------------------------------


@app.post('/orders/check')
async def check_order(req: OrderRequest) -> dict:
    """Run pre-trade risk checks on a new order."""
    result = await _engine_svc.check(req.to_domain())
    return {'passed': result.passed, 'reason': result.reason}


# ---------------------------------------------------------------------------
# Trading halts
# ---------------------------------------------------------------------------


@app.post('/halt/{ticker}')
async def halt(ticker: str) -> dict:
    """Temporarily halt trading for a specific ticker."""
    _engine_svc.halt_ticker(ticker)
    return {}


@app.post('/resume/{ticker}')
async def resume(ticker: str) -> dict:
    """Resume trading for a halted ticker."""
    _engine_svc.resume_ticker(ticker)
    return {}
