"""
Tests for ClearingService.

Clearing is now a pure trade-record keeper. The only behaviour to test
is that on_trade_executed persists the correct trade to the repository.
Settlement logic lives in services/account/tests/.
"""

import pytest

from services.clearing.service import ClearingService
from shared.domain.events import TradeExecuted
from shared.domain.models import Trade


class FakeTradeRepo:
    def __init__(self) -> None:
        self.saved: list = []

    async def save(self, trade: Trade) -> None:
        self.saved.append(trade)


def make_svc() -> tuple:
    trade_repo = FakeTradeRepo()
    svc = ClearingService(trade_repo=trade_repo)
    return svc, trade_repo


def trade_event(
    trade_id: str = 't1',
    qty: int = 5,
    price: float = 100.0,
) -> TradeExecuted:
    return TradeExecuted(
        trade_id=trade_id,
        buy_order_id='b1',
        sell_order_id='s1',
        buyer_account_id='buyer',
        seller_account_id='seller',
        ticker='AAPL',
        quantity=qty,
        price=price,
    )


async def test_trade_persisted_on_event():
    svc, repo = make_svc()
    await svc.on_trade_executed(trade_event())
    assert len(repo.saved) == 1
    t = repo.saved[0]
    assert t.trade_id == 't1'
    assert t.ticker == 'AAPL'
    assert t.quantity == 5
    assert t.price == pytest.approx(100.0)


async def test_trade_buyer_seller_recorded():
    svc, repo = make_svc()
    await svc.on_trade_executed(trade_event())
    t = repo.saved[0]
    assert t.buyer_account_id == 'buyer'
    assert t.seller_account_id == 'seller'


async def test_multiple_trades_all_persisted():
    svc, repo = make_svc()
    await svc.on_trade_executed(trade_event('t1'))
    await svc.on_trade_executed(trade_event('t2'))
    assert len(repo.saved) == 2
    assert {t.trade_id for t in repo.saved} == {'t1', 't2'}
