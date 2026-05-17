"""
services/gateway/dependencies.py

FastAPI dependency providing service HTTP clients.
Each client calls the relevant downstream service over HTTP.
"""

from __future__ import annotations

import os
import typing as tp
from dataclasses import dataclass

import httpx

from shared.service_clients import (
    ClearingClient,
    MarketDataClient,
    MatchingEngineClient,
    OrderManagementClient,
    RiskEngineClient,
)

_clients: tp.Optional['ServiceClients'] = None


@dataclass
class ServiceClients:
    oms: OrderManagementClient
    clearing: ClearingClient
    market_data: MarketDataClient
    risk: RiskEngineClient
    matching: MatchingEngineClient


def init_clients(http: httpx.AsyncClient) -> 'ServiceClients':
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
    assert _clients is not None, 'ServiceClients not initialised'
    return _clients
