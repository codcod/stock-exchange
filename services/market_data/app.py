"""
services/market_data/app.py

Standalone FastAPI service wrapping MarketDataService.
Receives market data and trade events from the Matching Engine via HTTP,
and serves quotes, depth, and trade history to the Gateway.

Environment variables:
  PORT  — default 8005
"""

from __future__ import annotations

import typing as tp
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Query

from services.market_data.schemas import MarketDataUpdateEvent, TradeExecutedEvent
from services.market_data.service import MarketDataService
from shared.models.domain import MarketDataUpdate, TradeExecuted


@dataclass
class _AppState:
    svc: tp.Optional[MarketDataService] = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state.svc = MarketDataService()
    yield


app = FastAPI(title='Market Data Service', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


# ---------------------------------------------------------------------------
# Query endpoints
# ---------------------------------------------------------------------------


@app.get('/tickers', response_model=tp.List[str])
async def list_tickers() -> tp.List[str]:
    return _state.svc.all_tickers()


@app.get('/quotes/{ticker}')
async def get_quote(ticker: str) -> dict:
    quote = _state.svc.get_quote(ticker)
    if quote is None:
        raise HTTPException(status_code=404, detail='No quote data for ticker')
    return {
        'ticker': quote.ticker,
        'bid': quote.bid,
        'ask': quote.ask,
        'last_price': quote.last_price,
        'volume_today': quote.volume_today,
        'updated_at': quote.updated_at.isoformat(),
    }


@app.get('/trades/{ticker}')
async def get_trades(ticker: str, limit: int = Query(20, le=200)) -> tp.List[dict]:
    return [
        {
            'ticker': t.ticker,
            'price': t.price,
            'quantity': t.quantity,
            'executed_at': t.executed_at.isoformat(),
        }
        for t in _state.svc.get_trade_history(ticker, limit)
    ]


# ---------------------------------------------------------------------------
# Event endpoints (called by Matching Engine after trades)
# ---------------------------------------------------------------------------


@app.post('/events/market-data-update')
async def on_market_data_update(req: MarketDataUpdateEvent) -> dict:
    event = MarketDataUpdate(
        ticker=req.ticker,
        bid=req.bid,
        ask=req.ask,
        last_price=req.last_price,
        volume=req.volume,
    )
    await _state.svc.on_market_data_update(event)
    return {}


@app.post('/events/trade-executed')
async def on_trade_executed(req: TradeExecutedEvent) -> dict:
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
