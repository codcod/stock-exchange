"""
Outbox relay for the Order Management Service.

Polls the outbox table for unpublished order lifecycle events and delivers
them via HTTP to the Notifications service.

Routing map:
  OrderAccepted  → Notifications
  OrderRejected  → Notifications
  OrderCancelled → Notifications
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import httpx

from services.order_management.outbox_repo import OutboxRepository

logger = logging.getLogger(__name__)

_NOTIFICATIONS_URL = os.getenv('NOTIFICATIONS_URL', 'http://localhost:8007')

EVENT_DESTINATIONS: dict = {
    'OrderAccepted': ['notifications'],
    'OrderRejected': ['notifications'],
    'OrderCancelled': ['notifications'],
}
DESTINATION_URLS: dict = {
    'notifications': _NOTIFICATIONS_URL,
}
ENDPOINT_FOR_EVENT_TYPE: dict = {
    'OrderAccepted': '/events/order-accepted',
    'OrderRejected': '/events/order-rejected',
    'OrderCancelled': '/events/order-cancelled',
}

POLL_INTERVAL = float(os.getenv('OMS_OUTBOX_POLL_INTERVAL', '0.5'))


async def run_relay(http: httpx.AsyncClient, db) -> None:
    """Poll the outbox and deliver unpublished events to their destinations."""
    repo = OutboxRepository(db)
    while True:
        try:
            rows = await repo.fetch_unpublished()
            for row in rows:
                dest_url = DESTINATION_URLS.get(row['destination'])
                endpoint = ENDPOINT_FOR_EVENT_TYPE.get(row['event_type'])
                if not dest_url or not endpoint:
                    logger.warning(
                        'Unknown destination/event: %s / %s',
                        row['destination'],
                        row['event_type'],
                    )
                    continue
                try:
                    resp = await http.post(
                        f'{dest_url}{endpoint}',
                        json=json.loads(row['payload']),
                    )
                    resp.raise_for_status()
                    await repo.mark_published(row['id'])
                except Exception:
                    logger.exception('OMS relay failed for outbox row %d', row['id'])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('OMS outbox relay poll error')
        await asyncio.sleep(POLL_INTERVAL)
