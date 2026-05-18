"""
Public HTTP entry point for the exchange, responsible for delegating
requests to the appropriate downstream services via ServiceClients.

This service routes orders to the OrderManagementService, account and
instrument-related requests to the RiskEngine and ClearingService, and
market data queries to the MarketDataService.

Authentication is optional and can be enabled by setting the
`EXCHANGE_API_KEY` environment variable. If set, all incoming requests
must include a matching `X-API-Key` header.

Environment variables:
- `ORDER_MANAGEMENT_URL`: The URL for the Order Management Service (default: `http://localhost:8001`).
- `RISK_ENGINE_URL`: The URL for the Risk Engine Service (default: `http://localhost:8002`).
- `CLEARING_URL`: The URL for the Clearing Service (default: `http://localhost:8004`).
- `MARKET_DATA_URL`: The URL for the Market Data Service (default: `http://localhost:8005`).
- `PORT`: The port on which the gateway service will run (default: `8000`).
- `EXCHANGE_API_KEY`: An optional API key to enable authentication.
"""

import logging
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response

from services.gateway import dependencies
from services.gateway.routes import accounts, instruments, market_data, orders
from shared.request_context import request_id as _request_id_ctx

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    http = httpx.AsyncClient(timeout=10.0)
    dependencies._clients = dependencies.init_clients(http)
    yield
    await http.aclose()


app = FastAPI(title='Stock Exchange API', version='0.1.0', lifespan=lifespan)


@app.middleware('http')
async def correlation_id_middleware(request: Request, call_next) -> Response:
    """
    Inject a correlation ID into the request context.

    If a `X-Request-ID` header is present, it will be used; otherwise, a new
    UUID will be generated. This ID is then propagated to all downstream
    service calls.
    """
    rid = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    token = _request_id_ctx.set(rid)
    logger.info('Request %s %s [request_id=%s]', request.method, request.url.path, rid)
    try:
        response = await call_next(request)
    finally:
        _request_id_ctx.reset(token)
    response.headers['X-Request-ID'] = rid
    return response


app.include_router(orders.router, prefix='/orders', tags=['Orders'])
app.include_router(accounts.router, prefix='/accounts', tags=['Accounts'])
app.include_router(instruments.router, prefix='/instruments', tags=['Instruments'])
app.include_router(market_data.router, prefix='/market-data', tags=['Market Data'])


@app.get('/health', tags=['Health'])
async def health() -> dict:
    return {'status': 'ok'}
