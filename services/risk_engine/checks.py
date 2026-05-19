"""
Pre-trade risk check functions for the Risk Engine.

Each function takes an `Order` and the engine's cached state, and returns
a `RiskResult`. The engine runs them in sequence and stops on the first
failure — so the order here is the policy order visible to anyone reading
the codebase.
"""

from __future__ import annotations

import typing as tp

from services.risk_engine.engine import RiskResult
from shared.domain.models import Account, Instrument, Order, OrderType, Side

MAX_ORDER_VALUE = 1_000_000.0
MIN_CASH_BUFFER = 0.0


def check_account_exists(
    order: Order,
    accounts: tp.Dict[str, Account],
    instruments: tp.Dict[str, Instrument],
    halted: set,
) -> RiskResult:
    """Account must be registered before it can trade."""
    if order.account_id not in accounts:
        return RiskResult(False, f'Unknown account: {order.account_id}')
    return RiskResult(True)


def check_instrument(
    order: Order,
    accounts: tp.Dict[str, Account],
    instruments: tp.Dict[str, Instrument],
    halted: set,
) -> RiskResult:
    """Ticker must exist, be tradeable, and respect lot/max-size constraints."""
    instrument = instruments.get(order.ticker)
    if not instrument:
        return RiskResult(False, f'Unknown ticker: {order.ticker}')
    if not instrument.is_tradeable:
        return RiskResult(False, f'{order.ticker} is not tradeable')
    if order.quantity < instrument.lot_size:
        return RiskResult(
            False,
            f'Quantity {order.quantity} below lot size {instrument.lot_size}',
        )
    if order.quantity > instrument.max_order_size:
        return RiskResult(
            False,
            f'Quantity {order.quantity} exceeds max order size '
            f'{instrument.max_order_size}',
        )
    return RiskResult(True)


def check_market_halt(
    order: Order,
    accounts: tp.Dict[str, Account],
    instruments: tp.Dict[str, Instrument],
    halted: set,
) -> RiskResult:
    """Reject orders for halted tickers."""
    if order.ticker in halted:
        return RiskResult(False, f'Trading halted for {order.ticker}')
    return RiskResult(True)


def check_order_size(
    order: Order,
    accounts: tp.Dict[str, Account],
    instruments: tp.Dict[str, Instrument],
    halted: set,
) -> RiskResult:
    """Order quantity must be positive."""
    if order.quantity <= 0:
        return RiskResult(False, 'Order quantity must be positive')
    return RiskResult(True)


def check_price_sanity(
    order: Order,
    accounts: tp.Dict[str, Account],
    instruments: tp.Dict[str, Instrument],
    halted: set,
) -> RiskResult:
    """For limit orders: price must be positive and within 10%-300% of last price."""
    if order.order_type == OrderType.LIMIT:
        if order.price is None or order.price <= 0:
            return RiskResult(False, 'Limit order must have a positive price')
        instrument = instruments.get(order.ticker)
        if instrument and instrument.last_price:
            ratio = order.price / instrument.last_price
            if not (0.1 < ratio < 3.0):
                return RiskResult(
                    False,
                    f'Price {order.price:.2f} is too far from last price '
                    f'{instrument.last_price:.2f} (possible fat-finger)',
                )
    return RiskResult(True)


def check_funds_or_shares(
    order: Order,
    accounts: tp.Dict[str, Account],
    instruments: tp.Dict[str, Instrument],
    halted: set,
) -> RiskResult:
    """BUY orders need sufficient cash; SELL orders need sufficient shares."""
    account = accounts[order.account_id]

    if order.side == Side.BUY:
        if order.order_type == OrderType.LIMIT and order.price:
            required = order.price * order.quantity
            available = account.available_cash()
            if available < required:
                return RiskResult(
                    False,
                    f'Insufficient funds: need {required:.2f}, have {available:.2f}',
                )
    else:  # SELL
        available = account.available_shares(order.ticker)
        if available < order.quantity:
            return RiskResult(
                False,
                f'Insufficient shares of {order.ticker}: '
                f'need {order.quantity}, have {available}',
            )
    return RiskResult(True)


def check_order_value(
    order: Order,
    accounts: tp.Dict[str, Account],
    instruments: tp.Dict[str, Instrument],
    halted: set,
) -> RiskResult:
    """Notional value of a limit order must not exceed MAX_ORDER_VALUE."""
    if order.order_type == OrderType.LIMIT and order.price:
        notional = order.price * order.quantity
        if notional > MAX_ORDER_VALUE:
            return RiskResult(
                False,
                f'Order value {notional:.2f} exceeds limit {MAX_ORDER_VALUE:.2f}',
            )
    return RiskResult(True)


# Ordered policy list — the sequence a reader sees is the sequence that runs.
CHECKS = [
    check_account_exists,
    check_instrument,
    check_market_halt,
    check_order_size,
    check_price_sanity,
    check_funds_or_shares,
    check_order_value,
]
