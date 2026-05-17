"""
services/gateway/app.py

Public HTTP entry point for the exchange.
Delegates every request to the appropriate downstream service via ServiceClients:
  - Orders  → OrderManagementService (:8001)
  - Accounts / instruments → RiskEngine (:8002) and ClearingService (:8004)
  - Market data → MarketDataService (:8005)

Authentication is opt-in: when EXCHANGE_API_KEY is set every request must
include the matching X-API-Key header.

Environment variables:
  ORDER_MANAGEMENT_URL  — default http://localhost:8001
  RISK_ENGINE_URL       — default http://localhost:8002
  CLEARING_URL          — default http://localhost:8004
  MARKET_DATA_URL       — default http://localhost:8005
  PORT                  — default 8000
  EXCHANGE_API_KEY      — optional; enables X-API-Key authentication
"""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from services.gateway import dependencies
from services.gateway.routes import accounts, instruments, market_data, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    http = httpx.AsyncClient(timeout=10.0)
    dependencies._clients = dependencies.init_clients(http)
    yield
    await http.aclose()


app = FastAPI(title='Stock Exchange API', version='0.1.0', lifespan=lifespan)

app.include_router(orders.router, prefix='/orders', tags=['Orders'])
app.include_router(accounts.router, prefix='/accounts', tags=['Accounts'])
app.include_router(instruments.router, prefix='/instruments', tags=['Instruments'])
app.include_router(market_data.router, prefix='/market-data', tags=['Market Data'])


@app.get('/health', tags=['Health'])
async def health() -> dict:
    return {'status': 'ok'}
