"""
Integration test: full order lifecycle from submission to settlement.
Tests the Exchange facade end-to-end.
"""

import pytest

from exchange.main import Exchange
from shared.models.domain import (
    Account,
    Instrument,
    Order,
    OrderStatus,
    OrderType,
    Side,
)


@pytest.fixture
async def exchange():
    ex = await Exchange.create()
    await ex.register_instrument(Instrument('AAPL', 'Apple', last_price=175.0))
    alice = Account('alice', 'Alice', cash_balance=50_000.0)
    bob = Account('bob', 'Bob', cash_balance=50_000.0)
    alice.positions['AAPL'] = 100
    bob.positions['AAPL'] = 100
    await ex.register_account(alice)
    await ex.register_account(bob)
    return ex


async def test_full_trade_lifecycle(exchange):
    # Bob sells 10 shares at 175
    sell = await exchange.submit_order(
        Order(
            account_id='bob',
            ticker='AAPL',
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=10,
            price=175.0,
        )
    )
    assert sell.status == OrderStatus.OPEN

    # Alice buys 10 shares at 175 — should match immediately
    buy = await exchange.submit_order(
        Order(
            account_id='alice',
            ticker='AAPL',
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            price=175.0,
        )
    )
    assert buy.status == OrderStatus.FILLED
    assert sell.status == OrderStatus.FILLED

    # Clearing: check balances updated
    alice = exchange.get_account('alice')
    bob = exchange.get_account('bob')

    assert alice.cash_balance == 50_000 - (175.0 * 10)
    assert alice.positions['AAPL'] == 110  # had 100, bought 10

    assert bob.cash_balance == 50_000 + (175.0 * 10)
    assert bob.positions['AAPL'] == 90  # had 100, sold 10


async def test_rejected_order_does_not_affect_balances(exchange):
    alice_before = exchange.get_account('alice').cash_balance

    bad_order = await exchange.submit_order(
        Order(
            account_id='alice',
            ticker='AAPL',
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=10_000,  # exceeds max_order_size
            price=175.0,
        )
    )
    assert bad_order.status == OrderStatus.REJECTED
    assert exchange.get_account('alice').cash_balance == alice_before


async def test_cancel_resting_order(exchange):
    sell = await exchange.submit_order(
        Order(
            account_id='bob',
            ticker='AAPL',
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=10,
            price=200.0,  # above market, won't match
        )
    )
    assert sell.status == OrderStatus.OPEN

    cancelled = await exchange.cancel_order(sell.order_id, 'bob')
    assert cancelled
    assert sell.status == OrderStatus.CANCELLED


async def test_market_data_updates_after_trade(exchange):
    await exchange.submit_order(
        Order(
            account_id='bob',
            ticker='AAPL',
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=5,
            price=175.0,
        )
    )
    await exchange.submit_order(
        Order(
            account_id='alice',
            ticker='AAPL',
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=5,
            price=175.0,
        )
    )

    quote = exchange.get_quote('AAPL')
    assert quote is not None
    assert quote.last_price == 175.0
    assert quote.volume_today == 5


async def test_partial_fill(exchange):
    # Bob offers 20 shares
    sell = await exchange.submit_order(
        Order(
            account_id='bob',
            ticker='AAPL',
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=20,
            price=175.0,
        )
    )

    # Alice only buys 10
    buy = await exchange.submit_order(
        Order(
            account_id='alice',
            ticker='AAPL',
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            price=175.0,
        )
    )

    assert buy.status == OrderStatus.FILLED
    assert sell.status == OrderStatus.PARTIALLY_FILLED
    assert sell.filled_quantity == 10
    assert sell.remaining_quantity == 10
