"""
Dict ↔ domain-object converters used by service clients.
"""

from __future__ import annotations

import typing as tp
from datetime import datetime

from shared.domain.models import (
    Account,
    Instrument,
    Order,
    OrderStatus,
    OrderType,
    Side,
    Trade,
)


def order_to_dict(order: Order) -> tp.Dict[str, tp.Any]:
    """Convert an Order domain object to a JSON-serialisable dictionary."""
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


def dict_to_order(d: tp.Dict[str, tp.Any]) -> Order:
    """Convert a dictionary to an Order domain object."""
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


def account_to_dict(account: Account) -> tp.Dict[str, tp.Any]:
    """Convert an Account domain object to a JSON-serialisable dictionary."""
    return {
        'account_id': account.account_id,
        'name': account.name,
        'cash_balance': account.cash_balance,
        'reserved_cash': account.reserved_cash,
        'positions': account.positions,
        'reserved_shares': account.reserved_shares,
        'created_at': account.created_at.isoformat(),
    }


def dict_to_account(d: tp.Dict[str, tp.Any]) -> Account:
    """Convert a dictionary to an Account domain object."""
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


def instrument_to_dict(instrument: Instrument) -> tp.Dict[str, tp.Any]:
    """Convert an Instrument domain object to a JSON-serialisable dictionary."""
    return {
        'ticker': instrument.ticker,
        'name': instrument.name,
        'lot_size': instrument.lot_size,
        'max_order_size': instrument.max_order_size,
        'is_tradeable': instrument.is_tradeable,
        'last_price': instrument.last_price,
    }


def dict_to_trade(d: tp.Dict[str, tp.Any]) -> Trade:
    """Convert a dictionary to a Trade domain object."""
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
