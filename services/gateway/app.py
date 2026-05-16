"""
services/gateway/app.py

FastAPI application. Wraps the Exchange facade with an HTTP interface.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.gateway import dependencies
from services.gateway.routes import accounts, instruments, market_data, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    dependencies._exchange = await dependencies.init_exchange()
    yield


app = FastAPI(title='Stock Exchange API', version='0.1.0', lifespan=lifespan)

app.include_router(orders.router, prefix='/orders', tags=['Orders'])
app.include_router(accounts.router, prefix='/accounts', tags=['Accounts'])
app.include_router(instruments.router, prefix='/instruments', tags=['Instruments'])
app.include_router(market_data.router, prefix='/market-data', tags=['Market Data'])


@app.get('/health', tags=['Health'])
async def health() -> dict:
    return {'status': 'ok'}
