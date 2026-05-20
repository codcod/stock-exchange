"""
Outbox relay for the Account service.

Polls the outbox table for unpublished events and delivers them via HTTP
to downstream services.

Routing map:
  AccountUpdated → Risk Engine
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

import httpx

from services.account.outbox_repo import OutboxRepository

logger = logging.getLogger(__name__)

_RISK_URL = os.getenv('RISK_ENGINE_URL', 'http://localhost:8002')

EVENT_DESTINATIONS: dict = {
    'AccountUpdated': ['risk_engine'],
}
DESTINATION_URLS: dict = {
    'risk_engine': _RISK_URL,
}
ENDPOINT_FOR_EVENT_TYPE: dict = {
    'AccountUpdated': '/events/account-updated',
}

POLL_INTERVAL = float(os.getenv('ACCOUNT_OUTBOX_POLL_INTERVAL', '0.5'))


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
                    logger.exception(
                        'Relay failed for account outbox row %d', row['id']
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Account outbox relay poll error')
        await asyncio.sleep(POLL_INTERVAL)
