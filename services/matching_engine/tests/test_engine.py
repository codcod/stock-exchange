"""
Tests for the matching engine.
Covers: basic match, partial fill, price priority, no match, market order.
"""

import pytest

from services.matching_engine.matching import MatchingEngine
from services.matching_engine.order_book import OrderBook
from shared.domain.events import OrderFilled, TradeExecuted
from shared.domain.models import Order, OrderStatus, OrderType, Side


@pytest.fixture
def book():
    return OrderBook('AAPL')


@pytest.fixture
def engine():
    return MatchingEngine()


def limit_order(side, quantity, price, account='acc1'):
    return Order(
        account_id=account,
        ticker='AAPL',
        side=side,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=price,
    )


def market_order(side, quantity, account='acc1'):
    return Order(
        account_id=account,
        ticker='AAPL',
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        price=None,
    )


# ---------------------------------------------------------------------------
# Basic matching (OrderBook — sync, no bus involved)
# ---------------------------------------------------------------------------


def test_no_match_when_book_empty(book):
    buy = limit_order(Side.BUY, 10, 100.0)
    trades = book.add_order(buy)
    assert trades == []
    assert buy.status == OrderStatus.OPEN


def test_exact_match(book):
    sell = limit_order(Side.SELL, 10, 100.0, account='seller')
    book.add_order(sell)

    buy = limit_order(Side.BUY, 10, 100.0, account='buyer')
    trades = book.add_order(buy)

    assert len(trades) == 1
    assert trades[0].quantity == 10
    assert trades[0].price == 100.0
    assert buy.status == OrderStatus.FILLED
    assert sell.status == OrderStatus.FILLED


def test_no_match_bid_below_ask(book):
    sell = limit_order(Side.SELL, 10, 105.0)
    book.add_order(sell)

    buy = limit_order(Side.BUY, 10, 100.0)
    trades = book.add_order(buy)

    assert trades == []
    assert buy.status == OrderStatus.OPEN
    assert book.best_bid() == 100.0
    assert book.best_ask() == 105.0


def test_partial_fill(book):
    sell = limit_order(Side.SELL, 5, 100.0, account='seller')
    book.add_order(sell)

    buy = limit_order(Side.BUY, 10, 100.0, account='buyer')
    trades = book.add_order(buy)

    assert len(trades) == 1
    assert trades[0].quantity == 5
    assert buy.status == OrderStatus.PARTIALLY_FILLED
    assert buy.remaining_quantity == 5
    assert sell.status == OrderStatus.FILLED
    # Remaining buy rests in the book
    assert book.best_bid() == 100.0


def test_market_order_matches_best_ask(book):
    sell = limit_order(Side.SELL, 10, 99.0, account='seller')
    book.add_order(sell)

    buy = market_order(Side.BUY, 10, account='buyer')
    trades = book.add_order(buy)

    assert len(trades) == 1
    assert trades[0].price == 99.0
    assert buy.status == OrderStatus.FILLED


def test_price_priority(book):
    """Lower ask price should match first."""
    cheap = limit_order(Side.SELL, 5, 99.0, account='cheap_seller')
    expensive = limit_order(Side.SELL, 5, 101.0, account='pricey_seller')
    book.add_order(expensive)
    book.add_order(cheap)

    buy = limit_order(Side.BUY, 5, 105.0, account='buyer')
    trades = book.add_order(buy)

    assert len(trades) == 1
    assert trades[0].price == 99.0  # best ask matched first


def test_trade_uses_resting_price(book):
    """Price is set by the resting (passive) order."""
    sell = limit_order(Side.SELL, 10, 100.0, account='seller')
    book.add_order(sell)

    buy = limit_order(Side.BUY, 10, 110.0, account='buyer')  # willing to pay 110
    trades = book.add_order(buy)

    assert trades[0].price == 100.0  # seller's price, not buyer's


def test_cancel_removes_from_book(book):
    sell = limit_order(Side.SELL, 10, 100.0)
    book.add_order(sell)
    assert book.best_ask() == 100.0

    cancelled = book.cancel_order(sell.order_id)
    assert cancelled
    assert book.best_ask() is None


def test_depth_snapshot(book):
    for price in [100.0, 99.0, 98.0]:
        book.add_order(limit_order(Side.BUY, 10, price))
    for price in [101.0, 102.0]:
        book.add_order(limit_order(Side.SELL, 5, price))

    snap = book.depth_snapshot(levels=3)
    assert snap['bids'][0]['price'] == 100.0  # best bid first
    assert snap['asks'][0]['price'] == 101.0  # best ask first


# ---------------------------------------------------------------------------
# Engine-level (event return — async)
# ---------------------------------------------------------------------------


async def test_engine_returns_trade_events():
    engine = MatchingEngine()
    engine.get_or_create_book('AAPL')

    sell = limit_order(Side.SELL, 10, 100.0, account='seller')
    _, events = await engine.submit(sell)
    assert not any(isinstance(e, TradeExecuted) for e in events)

    buy = limit_order(Side.BUY, 10, 100.0, account='buyer')
    trades, events = await engine.submit(buy)

    assert len(trades) == 1
    trade_evts = [e for e in events if isinstance(e, TradeExecuted)]
    fill_evts = [e for e in events if isinstance(e, OrderFilled)]
    assert len(trade_evts) == 1
    assert trade_evts[0].ticker == 'AAPL'
    assert trade_evts[0].quantity == 10
    assert len(fill_evts) == 2
