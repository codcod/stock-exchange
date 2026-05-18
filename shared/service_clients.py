"""
This module provides a collection of client classes that act as typed
wrappers around the HTTP APIs of the various microservices.

These clients simplify inter-service communication by abstracting away
the underlying HTTP requests and providing a clean, method-based interface.
"""

from __future__ import annotations

import typing as tp
from dataclasses import dataclass
from datetime import datetime

import httpx

from shared.http_client import http_delete, http_get, http_post
from shared.models.domain import (
    Account,
    Instrument,
    Order,
    OrderStatus,
    OrderType,
    Side,
    Trade,
)

# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _order_to_dict(order: Order) -> tp.Dict[str, tp.Any]:
    return {
        'order_id': order.order_id,
        'account_id': order.account_id,
        'ticker': order.ticker,
        'side': order.side.value,
        'order_type': order.order_type.value,
        'quantity': order.quantity,
        'price': order.price,
        'status': order.status.value,
        'filled_quantity': order.filled_quantity,
        'average_fill_price': order.average_fill_price,
        'reject_reason': order.reject_reason,
        'created_at': order.created_at.isoformat(),
        'updated_at': order.updated_at.isoformat(),
    }


def _dict_to_order(d: tp.Dict[str, tp.Any]) -> Order:
    order = Order(
        account_id=d['account_id'],
        ticker=d['ticker'],
        side=Side(d['side']),
        order_type=OrderType(d['order_type']),
        quantity=d['quantity'],
        price=d.get('price'),
        order_id=d['order_id'],
        status=OrderStatus(d['status']),
        filled_quantity=d['filled_quantity'],
        average_fill_price=d.get('average_fill_price'),
        reject_reason=d.get('reject_reason'),
    )
    if d.get('created_at'):
        order.created_at = datetime.fromisoformat(d['created_at'])
    if d.get('updated_at'):
        order.updated_at = datetime.fromisoformat(d['updated_at'])
    return order


def _account_to_dict(account: Account) -> tp.Dict[str, tp.Any]:
    return {
        'account_id': account.account_id,
        'name': account.name,
        'cash_balance': account.cash_balance,
        'reserved_cash': account.reserved_cash,
        'positions': account.positions,
        'reserved_shares': account.reserved_shares,
        'created_at': account.created_at.isoformat(),
    }


def _dict_to_account(d: tp.Dict[str, tp.Any]) -> Account:
    account = Account(
        account_id=d['account_id'],
        name=d['name'],
        cash_balance=d['cash_balance'],
        reserved_cash=d.get('reserved_cash', 0.0),
    )
    account.positions = d.get('positions', {})
    account.reserved_shares = d.get('reserved_shares', {})
    if d.get('created_at'):
        account.created_at = datetime.fromisoformat(d['created_at'])
    return account


def _instrument_to_dict(instrument: Instrument) -> tp.Dict[str, tp.Any]:
    return {
        'ticker': instrument.ticker,
        'name': instrument.name,
        'lot_size': instrument.lot_size,
        'max_order_size': instrument.max_order_size,
        'is_tradeable': instrument.is_tradeable,
        'last_price': instrument.last_price,
    }


def _dict_to_trade(d: tp.Dict[str, tp.Any]) -> Trade:
    trade = Trade(
        trade_id=d['trade_id'],
        ticker=d['ticker'],
        buy_order_id=d['buy_order_id'],
        sell_order_id=d['sell_order_id'],
        buyer_account_id=d['buyer_account_id'],
        seller_account_id=d['seller_account_id'],
        quantity=d['quantity'],
        price=d['price'],
    )
    if d.get('executed_at'):
        trade.executed_at = datetime.fromisoformat(d['executed_at'])
    return trade


# ---------------------------------------------------------------------------
# RiskCheckResult
# ---------------------------------------------------------------------------


@dataclass
class RiskCheckResult:
    passed: bool
    reason: tp.Optional[str] = None


# ---------------------------------------------------------------------------
# RiskEngineClient
# ---------------------------------------------------------------------------


class RiskEngineClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def check(self, order: Order) -> RiskCheckResult:
        data = await http_post(
            self._client, f'{self._base}/orders/check', _order_to_dict(order)
        )
        return RiskCheckResult(passed=data['passed'], reason=data.get('reason'))

    async def register_account(self, account: Account) -> None:
        await http_post(
            self._client, f'{self._base}/accounts', _account_to_dict(account)
        )

    async def register_instrument(self, instrument: Instrument) -> None:
        await http_post(
            self._client,
            f'{self._base}/instruments',
            _instrument_to_dict(instrument),
        )

    async def halt_ticker(self, ticker: str) -> None:
        await http_post(self._client, f'{self._base}/halt/{ticker}', {})

    async def resume_ticker(self, ticker: str) -> None:
        await http_post(self._client, f'{self._base}/resume/{ticker}', {})


# ---------------------------------------------------------------------------
# MatchingEngineClient
# ---------------------------------------------------------------------------


class MatchingEngineClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def submit(self, order: Order) -> None:
        await http_post(self._client, f'{self._base}/orders', _order_to_dict(order))

    async def cancel(self, order: Order) -> bool:
        data = await http_delete(self._client, f'{self._base}/orders/{order.order_id}')
        return data.get('cancelled', False)


# ---------------------------------------------------------------------------
# ClearingClient
# ---------------------------------------------------------------------------


class ClearingClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def register_account(self, account: Account) -> None:
        await http_post(
            self._client, f'{self._base}/accounts', _account_to_dict(account)
        )

    async def get_account(self, account_id: str) -> tp.Optional[Account]:
        try:
            data = await http_get(self._client, f'{self._base}/accounts/{account_id}')
            return _dict_to_account(data)
        except httpx.HTTPStatusError:
            return None

    async def reserve_cash(self, account_id: str, delta: float) -> None:
        await http_post(
            self._client,
            f'{self._base}/accounts/{account_id}/reserve/cash',
            {'delta': delta},
        )

    async def reserve_shares(self, account_id: str, ticker: str, delta: int) -> None:
        await http_post(
            self._client,
            f'{self._base}/accounts/{account_id}/reserve/shares/{ticker}',
            {'delta': delta},
        )


# ---------------------------------------------------------------------------
# MarketDataClient
# ---------------------------------------------------------------------------


class MarketDataClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def all_tickers(self) -> tp.List[str]:
        return await http_get(self._client, f'{self._base}/tickers')

    async def get_quote(self, ticker: str) -> tp.Optional[dict]:
        try:
            return await http_get(self._client, f'{self._base}/quotes/{ticker}')
        except httpx.HTTPStatusError:
            return None

    async def get_trade_history(self, ticker: str, limit: int = 20) -> tp.List[dict]:
        return await http_get(
            self._client, f'{self._base}/trades/{ticker}?limit={limit}'
        )


# ---------------------------------------------------------------------------
# OrderManagementClient
# ---------------------------------------------------------------------------


class OrderManagementClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip('/')
        self._client = client

    async def submit_order(self, order: Order) -> Order:
        data = await http_post(
            self._client, f'{self._base}/orders', _order_to_dict(order)
        )
        return _dict_to_order(data)

    async def cancel_order(self, order_id: str, account_id: str) -> bool:
        data = await http_delete(
            self._client,
            f'{self._base}/orders/{order_id}?account_id={account_id}',
        )
        return data.get('cancelled', False)

    async def get_order(self, order_id: str) -> tp.Optional[Order]:
        try:
            data = await http_get(self._client, f'{self._base}/orders/{order_id}')
            return _dict_to_order(data)
        except httpx.HTTPStatusError:
            return None

    async def get_open_orders(self) -> tp.List[Order]:
        data = await http_get(self._client, f'{self._base}/orders/open')
        return [_dict_to_order(o) for o in data]

    async def get_orders_for_account(self, account_id: str) -> tp.List[Order]:
        data = await http_get(
            self._client, f'{self._base}/accounts/{account_id}/orders'
        )
        return [_dict_to_order(o) for o in data]
