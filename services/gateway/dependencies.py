"""
Provides a FastAPI dependency for accessing service HTTP clients.

Each client is responsible for communicating with a downstream service
over HTTP. This module ensures that clients are initialised once and
reused across requests.
"""

from __future__ import annotations

import os
import typing as tp
from dataclasses import dataclass

import httpx

from shared.platform.clients.clearing import ClearingClient
from shared.platform.clients.market_data import MarketDataClient
from shared.platform.clients.matching_engine import MatchingEngineClient
from shared.platform.clients.order_management import OrderManagementClient
from shared.platform.clients.risk_engine import RiskEngineClient

_clients: tp.Optional['ServiceClients'] = None


@dataclass
class ServiceClients:
    """A container for all downstream service clients."""

    oms: OrderManagementClient
    clearing: ClearingClient
    market_data: MarketDataClient
    risk: RiskEngineClient
    matching: MatchingEngineClient


def init_clients(http: httpx.AsyncClient) -> 'ServiceClients':
    """
    Initialise all service clients with the given HTTP client.

    Service URLs are read from environment variables with sensible defaults
    for local development.
    """
    return ServiceClients(
        oms=OrderManagementClient(
            os.getenv('ORDER_MANAGEMENT_URL', 'http://localhost:8001'), http
        ),
        clearing=ClearingClient(
            os.getenv('CLEARING_URL', 'http://localhost:8004'), http
        ),
        market_data=MarketDataClient(
            os.getenv('MARKET_DATA_URL', 'http://localhost:8005'), http
        ),
        risk=RiskEngineClient(
            os.getenv('RISK_ENGINE_URL', 'http://localhost:8002'), http
        ),
        matching=MatchingEngineClient(
            os.getenv('MATCHING_ENGINE_URL', 'http://localhost:8003'), http
        ),
    )


async def get_clients() -> 'ServiceClients':
    """FastAPI dependency to get the initialised service clients."""
    assert _clients is not None, 'ServiceClients not initialised'
    return _clients
