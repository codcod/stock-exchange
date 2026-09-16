"""
Tests for AccountService.

Covers settlement (apply_settlement), reservation management
(reserve_cash, reserve_shares), and register_account.
"""

import pytest

from services.account.service import AccountService
from shared.domain.events import TradeExecuted
from shared.domain.models import Account

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class FakeAccountRepo:
    def __init__(self) -> None:
        self.saved: dict = {}

    async def save(self, account: Account) -> None:
        self.saved[account.account_id] = account

    async def save_with_conn(self, conn, account: Account) -> None:
        self.saved[account.account_id] = account

    async def load_all(self):
        return list(self.saved.values())


class _FakeConn:
    """Minimal async connection stub that records outbox inserts."""

    def __init__(self) -> None:
        self.executed = []
        self._scalar_result = None

    async def execute(self, stmt, *args, **kwargs):
        self.executed.append(stmt)

    async def scalar(self, stmt):
        return self._scalar_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


class FakeEngine:
    """Fake AsyncEngine that yields a FakeConn from begin()."""

    def __init__(self, already_processed: bool = False) -> None:
        self.conn = _FakeConn()
        self.conn._scalar_result = 'exists' if already_processed else None

    def begin(self):
        return self.conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_svc(already_processed: bool = False) -> tuple:
    repo = FakeAccountRepo()
    engine = FakeEngine(already_processed=already_processed)
    svc = AccountService(account_repo=repo, engine=engine)
    return svc, repo, engine


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
# apply_settlement — cash and position settlement
# ---------------------------------------------------------------------------


async def test_buyer_cash_reduced_and_shares_credited():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=1000.0)
    seller = make_seller(shares=10)
    svc._accounts['buyer'] = buyer
    svc._accounts['seller'] = seller

    await svc.apply_settlement(trade_event(qty=5, price=100.0))

    assert buyer.cash_balance == pytest.approx(500.0)
    assert buyer.positions['AAPL'] == 5


async def test_seller_cash_credited_and_shares_reduced():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=1000.0)
    seller = make_seller(shares=10)
    svc._accounts['buyer'] = buyer
    svc._accounts['seller'] = seller

    await svc.apply_settlement(trade_event(qty=5, price=100.0))

    assert seller.cash_balance == pytest.approx(500.0)
    assert seller.positions['AAPL'] == 5


async def test_buyer_reserved_cash_released_on_settlement():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=1000.0, reserved_cash=500.0)
    seller = make_seller(shares=10)
    svc._accounts['buyer'] = buyer
    svc._accounts['seller'] = seller

    await svc.apply_settlement(trade_event(qty=5, price=100.0))

    assert buyer.reserved_cash == pytest.approx(0.0)


async def test_seller_reserved_shares_released_on_settlement():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=1000.0, reserved_cash=500.0)
    seller = make_seller(shares=10, reserved=5)
    svc._accounts['buyer'] = buyer
    svc._accounts['seller'] = seller

    await svc.apply_settlement(trade_event(qty=5, price=100.0))

    assert seller.reserved_shares.get('AAPL', 0) == 0


async def test_settlement_persisted_to_repo():
    svc, repo, _ = make_svc()
    buyer = make_buyer(cash=500.0, reserved_cash=500.0)
    seller = make_seller(shares=5, reserved=5)
    svc._accounts['buyer'] = buyer
    svc._accounts['seller'] = seller

    await svc.apply_settlement(trade_event(qty=5, price=100.0))

    assert 'buyer' in repo.saved
    assert 'seller' in repo.saved


async def test_partial_fill_settlement():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=2000.0, reserved_cash=2000.0)
    seller = make_seller(shares=20, reserved=20)
    svc._accounts['buyer'] = buyer
    svc._accounts['seller'] = seller

    await svc.apply_settlement(trade_event(qty=5, price=100.0))

    assert buyer.positions['AAPL'] == 5
    assert seller.positions['AAPL'] == 15
    assert buyer.reserved_cash == pytest.approx(1500.0)


async def test_unknown_buyer_is_skipped_gracefully():
    svc, _, _ = make_svc()
    seller = make_seller(shares=10, reserved=5)
    svc._accounts['seller'] = seller

    await svc.apply_settlement(trade_event(qty=5, price=100.0))

    assert seller.cash_balance == pytest.approx(500.0)


async def test_idempotent_settlement_skipped():
    """Re-delivery of the same event_id must not double-settle."""
    svc, repo, _ = make_svc(already_processed=True)
    buyer = make_buyer(cash=1000.0)
    svc._accounts['buyer'] = buyer

    buyer_out, seller_out = await svc.apply_settlement(trade_event())

    assert buyer_out is None
    assert buyer.cash_balance == pytest.approx(1000.0)  # unchanged


# ---------------------------------------------------------------------------
# reserve_cash / reserve_shares
# ---------------------------------------------------------------------------


async def test_reserve_cash_updates_in_memory():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=1000.0, reserved_cash=0.0)
    svc._accounts['buyer'] = buyer

    account = await svc.reserve_cash('buyer', 300.0)

    assert account is buyer
    assert buyer.reserved_cash == pytest.approx(300.0)


async def test_reserve_shares_updates_in_memory():
    svc, _, _ = make_svc()
    seller = make_seller(shares=10, reserved=0)
    svc._accounts['seller'] = seller

    account = await svc.reserve_shares('seller', 'AAPL', 5)

    assert account is seller
    assert seller.reserved_shares['AAPL'] == 5


async def test_reserve_cash_cannot_go_below_zero():
    svc, _, _ = make_svc()
    buyer = make_buyer(cash=1000.0, reserved_cash=100.0)
    svc._accounts['buyer'] = buyer

    await svc.reserve_cash('buyer', -500.0)

    assert buyer.reserved_cash == 0.0


async def test_reserve_returns_none_for_unknown_account():
    svc, _, _ = make_svc()

    result = await svc.reserve_cash('nonexistent', 100.0)
    assert result is None
