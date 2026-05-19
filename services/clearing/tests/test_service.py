"""
Tests for ClearingService.

Covers settlement logic (on_trade_executed) and reservation management.
The two critical invariants: cash is never double-spent and positions
are never negative after settlement.
"""

import pytest

from services.clearing.service import ClearingService
from shared.domain.events import TradeExecuted
from shared.domain.models import Account, Trade

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class FakeAccountRepo:
    def __init__(self) -> None:
        self.saved: dict = {}

    async def save(self, account: Account) -> None:
        self.saved[account.account_id] = account


class FakeTradeRepo:
    def __init__(self) -> None:
        self.saved: list = []

    async def save(self, trade: Trade) -> None:
        self.saved.append(trade)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_svc() -> tuple:
    account_repo = FakeAccountRepo()
    trade_repo = FakeTradeRepo()
    svc = ClearingService(account_repo=account_repo, trade_repo=trade_repo)
    return svc, account_repo, trade_repo


def make_buyer(cash: float = 1000.0, reserved_cash: float = 0.0) -> Account:
    a = Account(
        account_id='buyer', name='Buyer', cash_balance=cash, reserved_cash=reserved_cash
    )
    return a


def make_seller(shares: int = 10, reserved: int = 0) -> Account:
    a = Account(account_id='seller', name='Seller', cash_balance=0.0)
    a.positions['AAPL'] = shares
    a.reserved_shares['AAPL'] = reserved
    return a


def trade_event(qty: int = 5, price: float = 100.0) -> TradeExecuted:
    return TradeExecuted(
        trade_id='t1',
        buy_order_id='b1',
        sell_order_id='s1',
        buyer_account_id='buyer',
        seller_account_id='seller',
        ticker='AAPL',
        quantity=qty,
        price=price,
    )


# ---------------------------------------------------------------------------
# on_trade_executed — cash and position settlement
# ---------------------------------------------------------------------------


async def test_buyer_cash_reduced_and_shares_credited():
    svc, repo, _ = make_svc()
    buyer = make_buyer(cash=1000.0)
    seller = make_seller(shares=10)
    svc.register_account(buyer)
    svc.register_account(seller)

    await svc.on_trade_executed(trade_event(qty=5, price=100.0))

    assert buyer.cash_balance == pytest.approx(500.0)
    assert buyer.positions['AAPL'] == 5


async def test_seller_cash_credited_and_shares_reduced():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=1000.0)
    seller = make_seller(shares=10)
    svc.register_account(buyer)
    svc.register_account(seller)

    await svc.on_trade_executed(trade_event(qty=5, price=100.0))

    assert seller.cash_balance == pytest.approx(500.0)
    assert seller.positions['AAPL'] == 5


async def test_buyer_reserved_cash_released_on_settlement():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=1000.0, reserved_cash=500.0)
    seller = make_seller(shares=10)
    svc.register_account(buyer)
    svc.register_account(seller)

    await svc.on_trade_executed(trade_event(qty=5, price=100.0))

    assert buyer.reserved_cash == pytest.approx(0.0)


async def test_seller_reserved_shares_released_on_settlement():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=1000.0, reserved_cash=500.0)
    seller = make_seller(shares=10, reserved=5)
    svc.register_account(buyer)
    svc.register_account(seller)

    await svc.on_trade_executed(trade_event(qty=5, price=100.0))

    assert seller.reserved_shares.get('AAPL', 0) == 0


async def test_settlement_persisted_to_repos():
    svc, account_repo, trade_repo = make_svc()
    buyer = make_buyer(cash=500.0, reserved_cash=500.0)
    seller = make_seller(shares=5, reserved=5)
    svc.register_account(buyer)
    svc.register_account(seller)

    await svc.on_trade_executed(trade_event(qty=5, price=100.0))

    assert 'buyer' in account_repo.saved
    assert 'seller' in account_repo.saved
    assert len(trade_repo.saved) == 1
    assert trade_repo.saved[0].trade_id == 't1'


async def test_partial_fill_settlement():
    """Only the traded quantity should be settled; rest stays in positions."""
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=2000.0, reserved_cash=2000.0)
    seller = make_seller(shares=20, reserved=20)
    svc.register_account(buyer)
    svc.register_account(seller)

    await svc.on_trade_executed(trade_event(qty=5, price=100.0))

    assert buyer.positions['AAPL'] == 5
    assert seller.positions['AAPL'] == 15
    assert buyer.reserved_cash == pytest.approx(1500.0)


async def test_unknown_buyer_is_skipped_gracefully():
    """Settlement continues for the known counterparty even if the other is unknown."""
    svc, _, _ = make_svc()
    seller = make_seller(shares=10, reserved=5)
    svc.register_account(seller)

    await svc.on_trade_executed(trade_event(qty=5, price=100.0))

    assert seller.cash_balance == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# reserve_cash / reserve_shares
# ---------------------------------------------------------------------------


async def test_reserve_cash_persists_and_updates_in_memory():
    svc, account_repo, _ = make_svc()
    buyer = make_buyer(cash=1000.0, reserved_cash=0.0)
    svc.register_account(buyer)

    account = await svc.reserve_cash('buyer', 300.0)

    assert account is buyer
    assert buyer.reserved_cash == pytest.approx(300.0)
    assert 'buyer' in account_repo.saved


async def test_reserve_shares_persists_and_updates_in_memory():
    svc, account_repo, _ = make_svc()
    seller = make_seller(shares=10, reserved=0)
    svc.register_account(seller)

    account = await svc.reserve_shares('seller', 'AAPL', 5)

    assert account is seller
    assert seller.reserved_shares['AAPL'] == 5
    assert 'seller' in account_repo.saved


async def test_reserve_cash_cannot_go_below_zero():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=1000.0, reserved_cash=100.0)
    svc.register_account(buyer)

    await svc.reserve_cash('buyer', -500.0)

    assert buyer.reserved_cash == 0.0


async def test_reserve_returns_none_for_unknown_account():
    svc, _, _ = make_svc()

    result = await svc.reserve_cash('nonexistent', 100.0)
    assert result is None
