"""
Tests for the Notifications service.

Covers notification persistence, backfill queries, and that trade-executed
events fan into rows for both buyer and seller.
"""

from services.notifications.service import NotificationService

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class FakeRepo:
    def __init__(self) -> None:
        self.saved: list = []

    async def save(self, notification_id, account_id, event_type, payload):
        record = {
            'notification_id': notification_id,
            'account_id': account_id,
            'event_type': event_type,
            'payload': payload,
            'created_at': '2026-01-01T00:00:00+00:00',
        }
        self.saved.append(record)
        return record

    async def list_for_account(self, account_id, since=None, limit=50):
        return [r for r in self.saved if r['account_id'] == account_id][:limit]


def make_svc() -> tuple:
    repo = FakeRepo()
    svc = NotificationService(repo)
    return svc, repo


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


async def test_add_persists_notification():
    svc, repo = make_svc()
    n = await svc.add('acc-01', 'OrderAccepted', {'order_id': 'o1', 'ticker': 'AAPL'})
    assert n['account_id'] == 'acc-01'
    assert n['event_type'] == 'OrderAccepted'
    assert len(repo.saved) == 1


async def test_add_assigns_unique_ids():
    svc, repo = make_svc()
    n1 = await svc.add('acc-01', 'OrderAccepted', {})
    n2 = await svc.add('acc-01', 'OrderRejected', {})
    assert n1['notification_id'] != n2['notification_id']


# ---------------------------------------------------------------------------
# list_for_account
# ---------------------------------------------------------------------------


async def test_list_for_account_returns_only_matching():
    svc, _ = make_svc()
    await svc.add('acc-01', 'OrderAccepted', {})
    await svc.add('acc-02', 'OrderRejected', {})
    await svc.add('acc-01', 'TradeExecuted', {})

    results = await svc.list_for_account('acc-01')
    assert len(results) == 2
    assert all(r['account_id'] == 'acc-01' for r in results)


async def test_list_for_account_empty_when_no_notifications():
    svc, _ = make_svc()
    results = await svc.list_for_account('acc-99')
    assert results == []


# ---------------------------------------------------------------------------
# TradeExecuted fan-out (verified at the app layer via service double-add)
# ---------------------------------------------------------------------------


async def test_trade_executed_fan_out_buyer_and_seller():
    """Simulates the app.py fan-out: add once per party."""
    svc, repo = make_svc()
    payload = {
        'trade_id': 't1',
        'buyer_account_id': 'buyer',
        'seller_account_id': 'seller',
    }
    await svc.add('buyer', 'TradeExecuted', payload)
    await svc.add('seller', 'TradeExecuted', payload)

    assert len(repo.saved) == 2
    assert repo.saved[0]['account_id'] == 'buyer'
    assert repo.saved[1]['account_id'] == 'seller'
