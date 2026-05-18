"""
Tests for MarketDataService.
Covers: quote updates, stale bid/ask cleared when book side empties.
"""

import pytest

from services.market_data.service import MAX_TRADE_HISTORY, MarketDataService
from shared.models.domain import MarketDataUpdate, TradeExecuted


@pytest.fixture
def svc():
    return MarketDataService()


def mdu(ticker='AAPL', bid=0.0, ask=0.0, last_price=0.0, volume=0):
    return MarketDataUpdate(
        ticker=ticker, bid=bid, ask=ask, last_price=last_price, volume=volume
    )


# ---------------------------------------------------------------------------
# Basic quote updates
# ---------------------------------------------------------------------------


async def test_quote_created_on_first_update(svc):
    await svc.on_market_data_update(mdu(bid=100.0, ask=101.0, last_price=100.5))
    q = svc.get_quote('AAPL')
    assert q is not None
    assert q.bid == 100.0
    assert q.ask == 101.0
    assert q.last_price == 100.5


async def test_volume_accumulates_across_updates(svc):
    await svc.on_market_data_update(mdu(volume=10))
    await svc.on_market_data_update(mdu(volume=5))
    assert svc.get_quote('AAPL').volume_today == 15


async def test_last_price_not_overwritten_by_zero(svc):
    await svc.on_market_data_update(mdu(last_price=150.0, volume=1))
    # Subsequent update with no trade (last_price=0.0) must not clear last_price.
    await svc.on_market_data_update(mdu(bid=149.0, ask=151.0))
    assert svc.get_quote('AAPL').last_price == 150.0


# ---------------------------------------------------------------------------
# Stale quote cleared when book side empties
# ---------------------------------------------------------------------------


async def test_ask_cleared_when_ask_side_empties(svc):
    # A sell order rests at 173.02.
    await svc.on_market_data_update(mdu(bid=172.0, ask=173.02))

    # All asks are consumed; matching engine sends ask=0.0.
    await svc.on_market_data_update(mdu(bid=175.48, ask=0.0))

    q = svc.get_quote('AAPL')
    assert q.ask == 0.0, (
        'Cached ask must be cleared to 0.0 when the ask side empties; '
        f'got {q.ask} instead of 0.0'
    )
    assert q.bid == 175.48


async def test_bid_cleared_when_bid_side_empties(svc):
    await svc.on_market_data_update(mdu(bid=100.0, ask=101.0))
    await svc.on_market_data_update(mdu(bid=0.0, ask=101.0))

    q = svc.get_quote('AAPL')
    assert q.bid == 0.0
    assert q.ask == 101.0


async def test_crossed_quote_cannot_persist_after_fix(svc):
    # Sequence that produced the bug: ask set, then ask side consumed while
    # bid rests above the old ask price.
    await svc.on_market_data_update(mdu(bid=172.0, ask=173.02))
    # Aggressive buy consumes the ask; remaining buy rests at 175.48.
    await svc.on_market_data_update(
        mdu(bid=175.48, ask=0.0, last_price=173.02, volume=11)
    )

    q = svc.get_quote('AAPL')
    # bid > ask would mean a crossed book in the cache — must not happen.
    assert not (q.bid > q.ask > 0), f'Crossed quote in cache: bid={q.bid} ask={q.ask}'


# ---------------------------------------------------------------------------
# Trade tape
# ---------------------------------------------------------------------------


def trade_evt(ticker='AAPL', price=100.0, qty=5):
    return TradeExecuted(
        ticker=ticker,
        trade_id='t1',
        buy_order_id='b1',
        sell_order_id='s1',
        buyer_account_id='acc1',
        seller_account_id='acc2',
        quantity=qty,
        price=price,
    )


async def test_trade_appended_to_tape(svc):
    await svc.on_trade_executed(trade_evt(price=100.0, qty=5))

    history = svc.get_trade_history('AAPL')
    assert len(history) == 1
    assert history[0].price == pytest.approx(100.0)
    assert history[0].quantity == 5


async def test_get_trade_history_limit(svc):
    for i in range(10):
        await svc.on_trade_executed(trade_evt(price=float(100 + i)))

    limited = svc.get_trade_history('AAPL', limit=3)
    assert len(limited) == 3


async def test_trade_tape_evicts_oldest_at_max_capacity(svc):
    for i in range(MAX_TRADE_HISTORY + 10):
        await svc.on_trade_executed(trade_evt(price=float(i)))

    history = svc.get_trade_history('AAPL', limit=MAX_TRADE_HISTORY + 10)
    assert len(history) == MAX_TRADE_HISTORY


async def test_trade_history_empty_for_unknown_ticker(svc):
    assert svc.get_trade_history('ZZZZ') == []


async def test_trade_tapes_are_per_ticker(svc):
    await svc.on_trade_executed(trade_evt('AAPL', price=100.0))
    await svc.on_trade_executed(trade_evt('GOOG', price=200.0))

    assert svc.get_trade_history('AAPL')[0].price == pytest.approx(100.0)
    assert svc.get_trade_history('GOOG')[0].price == pytest.approx(200.0)


async def test_all_tickers_includes_new_market_data_tickers(svc):
    await svc.on_market_data_update(mdu(ticker='AAPL'))
    await svc.on_market_data_update(mdu(ticker='GOOG'))

    tickers = svc.all_tickers()
    assert 'AAPL' in tickers
    assert 'GOOG' in tickers
