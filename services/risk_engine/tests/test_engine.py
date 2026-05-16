"""Tests for the risk engine pre-trade checks."""

import pytest

from services.risk_engine.engine import RiskEngine
from shared.models.domain import Account, Instrument, Order, OrderType, Side


@pytest.fixture
def engine():
    e = RiskEngine()
    e.register_instrument(Instrument('AAPL', 'Apple', last_price=175.0))
    acct = Account('acc1', 'Alice', cash_balance=10_000.0)
    acct.positions['AAPL'] = 100
    e.register_account(acct)
    return e


def buy(quantity=10, price=175.0, order_type=OrderType.LIMIT):
    return Order('acc1', 'AAPL', Side.BUY, order_type, quantity, price)


def sell(quantity=10, price=175.0):
    return Order('acc1', 'AAPL', Side.SELL, OrderType.LIMIT, quantity, price)


async def test_valid_buy_passes(engine):
    assert (await engine.check(buy())).passed


async def test_valid_sell_passes(engine):
    assert (await engine.check(sell())).passed


async def test_unknown_account_rejected(engine):
    order = Order('unknown', 'AAPL', Side.BUY, OrderType.LIMIT, 10, 175.0)
    result = await engine.check(order)
    assert not result.passed
    assert 'Unknown account' in result.reason


async def test_unknown_ticker_rejected(engine):
    order = Order('acc1', 'FAKE', Side.BUY, OrderType.LIMIT, 10, 50.0)
    result = await engine.check(order)
    assert not result.passed
    assert 'Unknown ticker' in result.reason


async def test_insufficient_cash_rejected(engine):
    # 10_000 / 175 = ~57 shares max; try 100
    result = await engine.check(buy(quantity=100, price=175.0))
    assert not result.passed
    assert 'Insufficient funds' in result.reason


async def test_insufficient_shares_rejected(engine):
    # Account has 100 shares; try to sell 200
    result = await engine.check(sell(quantity=200))
    assert not result.passed
    assert 'Insufficient shares' in result.reason


async def test_halted_ticker_rejected(engine):
    engine.halt_ticker('AAPL')
    result = await engine.check(buy())
    assert not result.passed
    assert 'halted' in result.reason


async def test_fat_finger_price_rejected(engine):
    # Price 10x above last price
    result = await engine.check(buy(price=1750.0))
    assert not result.passed
    assert 'fat-finger' in result.reason


async def test_zero_quantity_rejected(engine):
    result = await engine.check(buy(quantity=0))
    assert not result.passed


async def test_reserved_cash_reduces_availability(engine):
    # Reserve almost all cash
    engine.update_reserved_cash('acc1', 9_500.0)
    # Now only 500 available; a 10x175=1750 order should fail
    result = await engine.check(buy(quantity=10, price=175.0))
    assert not result.passed
    assert 'Insufficient funds' in result.reason
