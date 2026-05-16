from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from exchange.main import Exchange
from services.gateway.auth import require_api_key
from services.gateway.dependencies import get_exchange
from services.gateway.schemas import DepthLevel, DepthResponse, QuoteResponse, TradeItem

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get('/tickers', response_model=List[str])
async def list_tickers(exchange: Exchange = Depends(get_exchange)):
    return exchange.market_data.all_tickers()


@router.get('/{ticker}/quote', response_model=QuoteResponse)
async def get_quote(ticker: str, exchange: Exchange = Depends(get_exchange)):
    quote = exchange.get_quote(ticker)
    if quote is None:
        raise HTTPException(status_code=404, detail='No quote data for ticker')
    return QuoteResponse(
        ticker=quote.ticker,
        bid=quote.bid,
        ask=quote.ask,
        last_price=quote.last_price,
        volume_today=quote.volume_today,
        updated_at=quote.updated_at,
    )


@router.get('/{ticker}/depth', response_model=DepthResponse)
async def get_depth(ticker: str, exchange: Exchange = Depends(get_exchange)):
    depth = exchange.get_depth(ticker)
    if depth is None:
        raise HTTPException(status_code=404, detail='No order book for ticker')
    return DepthResponse(
        ticker=depth['ticker'],
        bids=[DepthLevel(**b) for b in depth['bids']],
        asks=[DepthLevel(**a) for a in depth['asks']],
        last_price=depth['last_price'],
    )


@router.get('/{ticker}/trades', response_model=List[TradeItem])
async def get_trades(
    ticker: str,
    limit: int = Query(20, le=200),
    exchange: Exchange = Depends(get_exchange),
):
    return [
        TradeItem(
            ticker=t.ticker,
            price=t.price,
            quantity=t.quantity,
            executed_at=t.executed_at,
        )
        for t in exchange.market_data.get_trade_history(ticker, limit)
    ]
