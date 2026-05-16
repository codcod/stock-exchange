"""
services/matching_engine/app.py

Standalone FastAPI service wrapping MatchingEngine.
After each match, events are fanned out via HTTP to downstream services:
  - TradeExecuted  → ClearingService + MarketDataService
  - OrderFilled    → OrderManagementService
  - MarketDataUpdate → MarketDataService

Environment variables:
  DATABASE_URL          — Postgres URL (optional)
  CLEARING_URL          — default http://localhost:8004
  ORDER_MANAGEMENT_URL  — default http://localhost:8001
  MARKET_DATA_URL       — default http://localhost:8005
  PORT                  — default 8003
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
from fastapi import FastAPI

from services.matching_engine.engine import MatchingEngine
from shared.db.connection import get_engine
from shared.db.repositories import OrderRepository
from shared.db.tables import ensure_tables
from shared.events.bus import EventBus, MarketDataUpdate, OrderFilled, TradeExecuted
from shared.models.domain import Order, OrderStatus, OrderType, Side

_local_bus = EventBus()
_engine_svc = MatchingEngine(_local_bus)
_state = SimpleNamespace(http=None)

_CLEARING_URL = os.getenv('CLEARING_URL', 'http://localhost:8004')
_OMS_URL = os.getenv('ORDER_MANAGEMENT_URL', 'http://localhost:8001')
_MARKET_DATA_URL = os.getenv('MARKET_DATA_URL', 'http://localhost:8005')


# ---------------------------------------------------------------------------
# HTTP event fan-out adapters (subscribe to local bus, forward via HTTP)
# ---------------------------------------------------------------------------


async def _forward_trade_executed(event: TradeExecuted) -> None:
    assert _state.http is not None
    payload = {
        'trade_id': event.trade_id,
        'buy_order_id': event.buy_order_id,
        'sell_order_id': event.sell_order_id,
        'buyer_account_id': event.buyer_account_id,
        'seller_account_id': event.seller_account_id,
        'ticker': event.ticker,
        'quantity': event.quantity,
        'price': event.price,
    }
    await asyncio.gather(
        _state.http.post(f'{_CLEARING_URL}/events/trade-executed', json=payload),
        _state.http.post(f'{_MARKET_DATA_URL}/events/trade-executed', json=payload),
        return_exceptions=True,
    )


async def _forward_order_filled(event: OrderFilled) -> None:
    assert _state.http is not None
    payload = {
        'order_id': event.order_id,
        'account_id': event.account_id,
        'fill_quantity': event.fill_quantity,
        'fill_price': event.fill_price,
        'is_fully_filled': event.is_fully_filled,
    }
    await _state.http.post(f'{_OMS_URL}/events/order-filled', json=payload)


async def _forward_market_data_update(event: MarketDataUpdate) -> None:
    assert _state.http is not None
    payload = {
        'ticker': event.ticker,
        'bid': event.bid,
        'ask': event.ask,
        'last_price': event.last_price,
        'volume': event.volume,
    }
    await _state.http.post(
        f'{_MARKET_DATA_URL}/events/market-data-update', json=payload
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state.http = httpx.AsyncClient(timeout=10.0)

    # Wire up HTTP event fan-out
    _local_bus.subscribe(TradeExecuted, _forward_trade_executed)
    _local_bus.subscribe(OrderFilled, _forward_order_filled)
    _local_bus.subscribe(MarketDataUpdate, _forward_market_data_update)

    # Restore active orders from DB
    if os.getenv('DATABASE_URL'):
        db = get_engine()
        await ensure_tables(db)
        for order in await OrderRepository(db).load_all():
            if order.is_active:
                _engine_svc.restore_order(order)

    yield
    await _state.http.aclose()


app = FastAPI(title='Matching Engine', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# Order endpoints
# ---------------------------------------------------------------------------


@app.post('/orders', status_code=201)
async def submit_order(data: dict) -> dict:
    order = _parse_order(data)
    trades = await _engine_svc.submit(order)
    return {
        'trades': [
            {
                'trade_id': t.trade_id,
                'ticker': t.ticker,
                'buy_order_id': t.buy_order_id,
                'sell_order_id': t.sell_order_id,
                'buyer_account_id': t.buyer_account_id,
                'seller_account_id': t.seller_account_id,
                'quantity': t.quantity,
                'price': t.price,
                'executed_at': t.executed_at.isoformat(),
            }
            for t in trades
        ]
    }


@app.post('/orders/restore', status_code=201)
async def restore_order(data: dict) -> dict:
    order = _parse_order(data)
    _engine_svc.restore_order(order)
    return {}


@app.delete('/orders/{order_id}')
async def cancel_order(order_id: str) -> dict:
    # Reconstruct a minimal Order for the cancel call
    book_orders = _find_order(order_id)
    if book_orders is None:
        return {'cancelled': False}
    cancelled = await _engine_svc.cancel(book_orders)
    return {'cancelled': cancelled}


@app.get('/books/{ticker}/depth')
async def get_depth(ticker: str) -> dict:
    depth = _engine_svc.snapshot(ticker)
    if depth is None:
        return {'ticker': ticker, 'bids': [], 'asks': [], 'last_price': None}
    return depth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_order(data: dict) -> Order:
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
    return order


def _find_order(order_id: str):
    """Walk all books to find the Order object for cancellation."""
    for book in _engine_svc._books.values():
        for side in (book.bids, book.asks):
            for level in side:
                for o in level.orders:
                    if o.order_id == order_id:
                        return o
    return None
