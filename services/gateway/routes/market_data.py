import typing as tp
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from services.gateway.auth import require_api_key
from services.gateway.dependencies import ServiceClients, get_clients
from services.gateway.schemas import DepthLevel, DepthResponse, QuoteResponse, TradeItem

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get('/tickers', response_model=tp.List[str])
async def list_tickers(clients: ServiceClients = Depends(get_clients)):
    return await clients.market_data.all_tickers()


@router.get('/{ticker}/quote', response_model=QuoteResponse)
async def get_quote(ticker: str, clients: ServiceClients = Depends(get_clients)):
    quote = await clients.market_data.get_quote(ticker)
    if quote is None:
        raise HTTPException(status_code=404, detail='No quote data for ticker')
    return QuoteResponse(
        ticker=quote['ticker'],
        bid=quote['bid'],
        ask=quote['ask'],
        last_price=quote['last_price'],
        volume_today=quote['volume_today'],
        updated_at=datetime.fromisoformat(quote['updated_at']),
    )


@router.get('/{ticker}/depth', response_model=DepthResponse)
async def get_depth(ticker: str, clients: ServiceClients = Depends(get_clients)):
    depth = await clients.matching.snapshot(ticker)
    if depth is None:
        raise HTTPException(status_code=404, detail='No order book for ticker')
    return DepthResponse(
        ticker=depth['ticker'],
        bids=[DepthLevel(**b) for b in depth['bids']],
        asks=[DepthLevel(**a) for a in depth['asks']],
        last_price=depth.get('last_price'),
    )


@router.get('/{ticker}/trades', response_model=tp.List[TradeItem])
async def get_trades(
    ticker: str,
    limit: int = Query(20, le=200),
    clients: ServiceClients = Depends(get_clients),
):
    trades = await clients.market_data.get_trade_history(ticker, limit)
    return [
        TradeItem(
            ticker=t['ticker'],
            price=t['price'],
            quantity=t['quantity'],
            executed_at=datetime.fromisoformat(t['executed_at']),
        )
        for t in trades
    ]
