"""
Tests for MarketDataService.
Covers: quote updates, stale bid/ask cleared when book side empties.
"""

import pytest

from services.market_data.service import MarketDataService
from shared.models.domain import MarketDataUpdate


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
