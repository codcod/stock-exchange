"""
Risk Engine — pre-trade validation service.

Caches account and instrument state in memory for fast order checks.
The cache is warmed at startup from the Account service and kept current
via AccountUpdated events delivered through the Account outbox relay.

Environment variables:
- `DATABASE_URL`: PostgreSQL connection string (required).
- `ACCOUNT_URL`: URL for the Account service (default: http://localhost:8006).
- `PORT`: HTTP port (default: 8002).
"""

from __future__ import annotations

import logging
import os
import typing as tp
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI

from services.risk_engine.engine import RiskEngine
from services.risk_engine.repository import InstrumentRepository
from services.risk_engine.tables import ensure_tables
from shared.domain.api_schemas import (
    AccountUpdatedEvent,
    OrderRequest,
    RegisterAccountRequest,
    RegisterInstrumentRequest,
)
from shared.domain.models import Account, Instrument
from shared.platform.clients.account import AccountClient
from shared.platform.db.connection import get_engine

logger = logging.getLogger(__name__)

_ACCOUNT_URL = os.getenv('ACCOUNT_URL', 'http://localhost:8006')

_engine_svc: RiskEngine = RiskEngine()


@dataclass
class _AppState:
    instrument_repo: tp.Optional[InstrumentRepository] = None
    http: tp.Optional[httpx.AsyncClient] = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state.http = httpx.AsyncClient(timeout=10.0)
    db = get_engine()
    await ensure_tables(db)
    _state.instrument_repo = InstrumentRepository(db)
    for instrument in await _state.instrument_repo.load_all():
        _engine_svc.register_instrument(instrument)
    account_client = AccountClient(_ACCOUNT_URL, _state.http)
    try:
        for account in await account_client.list_accounts():
            _engine_svc.register_account(account)
    except Exception:
        logger.warning(
            'Could not load accounts from Account service — starting with empty cache'
        )

    yield
    await _state.http.aclose()


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
# Account updates from Account service outbox
# ---------------------------------------------------------------------------


@app.post('/events/account-updated')
async def on_account_updated(req: AccountUpdatedEvent) -> dict:
    """Update the risk engine's account cache from an AccountUpdated event."""
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
