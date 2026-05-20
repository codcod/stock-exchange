"""
Outbox relay for the Matching Engine.

Polls the outbox table for unpublished events and delivers them via HTTP
to the appropriate downstream services.

Routing map:
  TradeExecuted   → Clearing, Market Data
  OrderFilled     → Order Management
  MarketDataUpdate → Market Data
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone

import httpx

from services.matching_engine.outbox_repo import OutboxRepository, write_outbox_rows

logger = logging.getLogger(__name__)

_CLEARING_URL = os.getenv('CLEARING_URL', 'http://localhost:8004')
_OMS_URL = os.getenv('ORDER_MANAGEMENT_URL', 'http://localhost:8001')
_MARKET_DATA_URL = os.getenv('MARKET_DATA_URL', 'http://localhost:8005')
_ACCOUNT_URL = os.getenv('ACCOUNT_URL', 'http://localhost:8006')
_NOTIFICATIONS_URL = os.getenv('NOTIFICATIONS_URL', 'http://localhost:8007')

EVENT_DESTINATIONS: dict = {
    'TradeExecuted': ['clearing', 'market_data', 'account', 'notifications'],
    'OrderFilled': ['order_management', 'notifications'],
    'MarketDataUpdate': ['market_data'],
}
DESTINATION_URLS: dict = {
    'clearing': _CLEARING_URL,
    'order_management': _OMS_URL,
    'market_data': _MARKET_DATA_URL,
    'account': _ACCOUNT_URL,
    'notifications': _NOTIFICATIONS_URL,
}
ENDPOINT_FOR_EVENT_TYPE: dict = {
    'TradeExecuted': '/events/trade-executed',
    'OrderFilled': '/events/order-filled',
    'MarketDataUpdate': '/events/market-data-update',
}

POLL_INTERVAL = float(os.getenv('OUTBOX_POLL_INTERVAL', '0.5'))


async def enqueue_events(conn, events: list) -> None:
    """
    Serialize a list of domain events and write them to the outbox table
    within a single database transaction.
    """
    now = datetime.now(timezone.utc)
    rows = []
    for event in events:
        event_type = type(event).__name__
        payload = json.dumps(asdict(event), default=str)
        for dest in EVENT_DESTINATIONS.get(event_type, []):
            rows.append(
                {
                    'event_id': event.event_id,
                    'event_type': event_type,
                    'destination': dest,
                    'payload': payload,
                    'created_at': now,
                    'published_at': None,
                }
            )
    await write_outbox_rows(conn, rows)


async def run_relay(http: httpx.AsyncClient, db) -> None:
    """
    Poll the outbox and deliver unpublished events to their destinations.

    Runs until cancelled (i.e. until the FastAPI lifespan shuts down).
    """
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
                    logger.exception('Relay failed for outbox row %d', row['id'])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Outbox relay poll error')
        await asyncio.sleep(POLL_INTERVAL)
