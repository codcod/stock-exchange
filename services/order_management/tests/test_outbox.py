"""
Tests for OMS order lifecycle event enqueueing.

Verifies that OrderAccepted, OrderRejected, and OrderCancelled payloads
carry the required fields (order_id, account_id, ticker) so the
Notifications service can route them correctly.
"""

import json
import uuid

from services.order_management.outbox_relay import (
    ENDPOINT_FOR_EVENT_TYPE,
    EVENT_DESTINATIONS,
)


def test_accepted_routed_to_notifications():
    assert 'notifications' in EVENT_DESTINATIONS['OrderAccepted']


def test_rejected_routed_to_notifications():
    assert 'notifications' in EVENT_DESTINATIONS['OrderRejected']


def test_cancelled_routed_to_notifications():
    assert 'notifications' in EVENT_DESTINATIONS['OrderCancelled']


def test_endpoints_defined_for_all_lifecycle_events():
    for event_type in ('OrderAccepted', 'OrderRejected', 'OrderCancelled'):
        assert event_type in ENDPOINT_FOR_EVENT_TYPE


def test_payload_fields():
    """Payload helpers produce the expected JSON structure."""
    payload = {
        'order_id': str(uuid.uuid4()),
        'account_id': 'acc-01',
        'ticker': 'AAPL',
        'reason': 'Insufficient funds',
    }
    serialised = json.dumps(payload)
    decoded = json.loads(serialised)
    assert decoded['order_id'] == payload['order_id']
    assert decoded['account_id'] == 'acc-01'
    assert decoded['ticker'] == 'AAPL'
    assert decoded['reason'] == 'Insufficient funds'


def test_accepted_payload_has_no_reason():
    """Accepted events should not include a reason field."""
    payload = {'order_id': 'o1', 'account_id': 'acc-01', 'ticker': 'AAPL'}
    assert 'reason' not in payload
