"""
Tests for OrderManagementService.

Covers order status transitions and fill event handling — the two classes
of bug where OMS updates in-memory state but fails to persist it correctly.
"""

import typing as tp

import pytest

from services.order_management.service import OrderManagementService
from services.risk_engine.engine import RiskResult
from shared.models.domain import Order, OrderFilled, OrderStatus, OrderType, Side

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class FakeRiskEngine:
    def __init__(self, passes: bool = True, reason: str = '') -> None:
        self._result = RiskResult(passed=passes, reason=reason or None)

    async def check(self, order: Order) -> RiskResult:
        return self._result

    async def register_account(self, account) -> None:
        pass


class FakeMatchingEngine:
    async def submit(self, order: Order) -> tp.List:
        return []

    async def cancel(self, order: Order) -> bool:
        return True


class FakeClearingEngine:
    async def reserve_cash(self, account_id: str, delta: float) -> None:
        pass

    async def reserve_shares(self, account_id: str, ticker: str, delta: int) -> None:
        pass


class FakeOrderRepo:
    """Captures save/update calls so tests can assert on persisted state."""

    def __init__(self) -> None:
        self.saved: tp.Dict[str, Order] = {}
        self.updates: tp.List[Order] = []

    async def save(self, order: Order) -> None:
        self.saved[order.order_id] = order

    async def update(self, order: Order) -> None:
        self.updates.append(
            Order(
                account_id=order.account_id,
                ticker=order.ticker,
                side=order.side,
                order_type=order.order_type,
                quantity=order.quantity,
                price=order.price,
                order_id=order.order_id,
                status=order.status,
                filled_quantity=order.filled_quantity,
                average_fill_price=order.average_fill_price,
            )
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def limit_buy(quantity: int = 10, price: float = 100.0, account: str = 'acc1') -> Order:
    return Order(
        account_id=account,
        ticker='AAPL',
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=price,
    )


def make_svc(
    risk: FakeRiskEngine | None = None,
    repo: FakeOrderRepo | None = None,
) -> tuple:
    repo = repo or FakeOrderRepo()
    svc = OrderManagementService(
        risk_engine=risk or FakeRiskEngine(),
        matching_engine=FakeMatchingEngine(),
        order_repo=repo,
        clearing_engine=FakeClearingEngine(),
    )
    return svc, repo


# ---------------------------------------------------------------------------
# submit_order — status transitions
# ---------------------------------------------------------------------------


async def test_submit_order_persists_open_status():
    svc, repo = make_svc()
    order = limit_buy()

    await svc.submit_order(order)

    persisted_statuses = [u.status for u in repo.updates]
    assert OrderStatus.OPEN in persisted_statuses, (
        'Order should be persisted as OPEN after being sent to the matching engine'
    )


async def test_submit_order_never_persists_pending_after_acceptance():
    svc, repo = make_svc()
    order = limit_buy()

    await svc.submit_order(order)

    final_status = repo.updates[-1].status
    assert final_status != OrderStatus.PENDING, (
        'Final DB write after matching engine submission must not be PENDING'
    )


async def test_submit_rejected_order_persists_rejected_status():
    svc, repo = make_svc(risk=FakeRiskEngine(passes=False, reason='Insufficient funds'))
    order = limit_buy()

    result = await svc.submit_order(order)

    assert result.status == OrderStatus.REJECTED
    final_status = repo.updates[-1].status
    assert final_status == OrderStatus.REJECTED


# ---------------------------------------------------------------------------
# on_order_filled — fill application
# ---------------------------------------------------------------------------


async def test_partial_fill_sets_partially_filled_status():
    svc, repo = make_svc()
    order = limit_buy(quantity=10)
    await svc.submit_order(order)

    await svc.on_order_filled(
        OrderFilled(
            order_id=order.order_id,
            account_id=order.account_id,
            fill_quantity=4,
            fill_price=100.0,
        )
    )

    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.filled_quantity == 4
    persisted = repo.updates[-1]
    assert persisted.status == OrderStatus.PARTIALLY_FILLED
    assert persisted.filled_quantity == 4


async def test_full_fill_sets_filled_status():
    svc, repo = make_svc()
    order = limit_buy(quantity=10)
    await svc.submit_order(order)

    await svc.on_order_filled(
        OrderFilled(
            order_id=order.order_id,
            account_id=order.account_id,
            fill_quantity=10,
            fill_price=100.0,
        )
    )

    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 10
    persisted = repo.updates[-1]
    assert persisted.status == OrderStatus.FILLED


async def test_two_partial_fills_accumulate_to_filled():
    svc, repo = make_svc()
    order = limit_buy(quantity=10)
    await svc.submit_order(order)

    await svc.on_order_filled(
        OrderFilled(
            order_id=order.order_id,
            account_id=order.account_id,
            fill_quantity=4,
            fill_price=100.0,
        )
    )
    await svc.on_order_filled(
        OrderFilled(
            order_id=order.order_id,
            account_id=order.account_id,
            fill_quantity=6,
            fill_price=110.0,
        )
    )

    assert order.filled_quantity == 10
    assert order.status == OrderStatus.FILLED


async def test_fill_computes_average_price():
    svc, repo = make_svc()
    order = limit_buy(quantity=10)
    await svc.submit_order(order)

    await svc.on_order_filled(
        OrderFilled(
            order_id=order.order_id,
            account_id=order.account_id,
            fill_quantity=4,
            fill_price=100.0,
        )
    )
    await svc.on_order_filled(
        OrderFilled(
            order_id=order.order_id,
            account_id=order.account_id,
            fill_quantity=6,
            fill_price=110.0,
        )
    )

    # (4*100 + 6*110) / 10 = 106.0
    assert order.average_fill_price == pytest.approx(106.0)


async def test_fill_for_unknown_order_is_ignored():
    svc, _ = make_svc()

    # Should not raise
    await svc.on_order_filled(
        OrderFilled(
            order_id='nonexistent',
            account_id='acc1',
            fill_quantity=5,
            fill_price=100.0,
        )
    )
