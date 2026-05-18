"""
A standalone FastAPI service that wraps the ClearingService.

This service is responsible for settling trades by updating account
balances for cash and shares. It also manages reservations to ensure
that funds and securities are held appropriately while orders are open.

Environment variables:
- `DATABASE_URL`: The URL for the PostgreSQL database (required).
- `PORT`: The HTTP port on which the service will run (default: `8004`).
"""

from __future__ import annotations

import logging
import os
import typing as tp
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, HTTPException

from services.clearing.schemas import (
    RegisterAccountRequest,
    ReserveRequest,
    TradeExecutedEvent,
)
from services.clearing.service import ClearingService
from shared.db.connection import get_engine
from shared.db.repos import AccountRepository, TradeRepository
from shared.db.tables import ensure_tables
from shared.models.domain import Account, TradeExecuted
from shared.service_clients import RiskEngineClient

logger = logging.getLogger(__name__)

_RISK_URL = os.getenv('RISK_ENGINE_URL', 'http://localhost:8002')


@dataclass
class _AppState:
    svc: tp.Optional[ClearingService] = None
    account_repo: tp.Optional[AccountRepository] = None
    risk: tp.Optional[RiskEngineClient] = None
    http: tp.Optional[httpx.AsyncClient] = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state.http = httpx.AsyncClient(timeout=10.0)
    db = get_engine()
    await ensure_tables(db)
    _state.account_repo = AccountRepository(db)
    trade_repo = TradeRepository(db)
    _state.risk = RiskEngineClient(_RISK_URL, _state.http)

    _state.svc = ClearingService(
        account_repo=_state.account_repo, trade_repo=trade_repo
    )

    for account in await _state.account_repo.load_all():
        _state.svc.register_account(account)

    yield
    await _state.http.aclose()


app = FastAPI(title='Clearing Service', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------


@app.post('/accounts', status_code=201)
async def register_account(req: RegisterAccountRequest) -> dict:
    """
    Register a new trading account or update an existing one.

    The account state is persisted to the database and synchronized with
    the in-memory cache of the Risk Engine.
    """
    account = Account(
        account_id=req.account_id,
        name=req.name,
        cash_balance=req.cash_balance,
        reserved_cash=req.reserved_cash,
    )
    account.positions = dict(req.positions)
    account.reserved_shares = dict(req.reserved_shares)
    _state.svc.register_account(account)
    await _state.account_repo.save(account)
    # Notify Risk Engine so its in-memory cache stays current.
    try:
        await _state.risk.register_account(account)
    except Exception:
        logger.warning(
            'Failed to sync new account %s to Risk Engine', account.account_id
        )
    return {}


@app.get('/accounts/{account_id}')
async def get_account(account_id: str) -> dict:
    """Retrieve the current state of a single trading account."""
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
# Reservation management (Clearing is the single owner of account state)
# ---------------------------------------------------------------------------


@app.post('/accounts/{account_id}/reserve/cash')
async def reserve_cash(account_id: str, req: ReserveRequest) -> dict:
    """
    Reserve or release cash for an account.

    This endpoint is called by the Order Management Service when an order
    is submitted or cancelled. The updated account state is then synced
    to the Risk Engine.
    """
    account = await _state.svc.reserve_cash(account_id, req.delta)
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    try:
        await _state.risk.register_account(account)
    except Exception:
        logger.warning('Failed to sync reservation for %s to Risk Engine', account_id)
    return {}


@app.post('/accounts/{account_id}/reserve/shares/{ticker}')
async def reserve_shares(account_id: str, ticker: str, req: ReserveRequest) -> dict:
    """
    Reserve or release shares for an account.

    This endpoint is called by the Order Management Service when an order
    is submitted or cancelled. The updated account state is then synced
    to the Risk Engine.
    """
    account = await _state.svc.reserve_shares(account_id, ticker, int(req.delta))
    if account is None:
        raise HTTPException(status_code=404, detail='Account not found')
    try:
        await _state.risk.register_account(account)
    except Exception:
        logger.warning('Failed to sync reservation for %s to Risk Engine', account_id)
    return {}


# ---------------------------------------------------------------------------
# Event endpoint (called by Matching Engine after trades)
# ---------------------------------------------------------------------------


@app.post('/events/trade-executed')
async def on_trade_executed(req: TradeExecutedEvent) -> dict:
    """
    Endpoint for the Matching Engine to report that a trade has been
    executed and needs to be settled.
    """
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
    buyer, seller = await _state.svc.on_trade_executed(event)
    # Sync Risk Engine cache so available-cash/shares checks reflect the settlement.
    for account in filter(None, [buyer, seller]):
        try:
            await _state.risk.register_account(account)
        except Exception:
            logger.warning(
                'Failed to sync settled account %s to Risk Engine', account.account_id
            )
    return {}
