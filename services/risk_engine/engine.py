"""
services/risk_engine/engine.py

Performs pre-trade risk checks on every order before it enters the book.
Account state is cached in-memory for fast checks (no DB round-trip).
The check() entry point is async; individual check methods are synchronous.

If any check fails, the order is rejected with a reason.
"""

from __future__ import annotations

import logging
import typing as tp
from dataclasses import dataclass

from shared.models.domain import Account, Instrument, Order, OrderType, Side

logger = logging.getLogger(__name__)

# Default limits — in a real system these are per-account config
MAX_ORDER_VALUE = 1_000_000.0  # max notional per single order
MAX_POSITION_CONCENTRATION = 0.50  # max 50% of portfolio in one stock
MIN_CASH_BUFFER = 0.0  # no naked positions


@dataclass
class RiskResult:
    passed: bool
    reason: tp.Optional[str] = None


class RiskEngine:
    """
    Holds a local cache of account state so checks are fast (no DB round-trip).
    State is updated via direct method calls: register_account/register_instrument
    at startup, and update_reserved_cash/update_reserved_shares on each order.
    """

    def __init__(self) -> None:
        self._accounts: tp.Dict[str, Account] = {}
        self._instruments: tp.Dict[str, Instrument] = {}
        self._halted_tickers: set = set()

    # ------------------------------------------------------------------
    # State management (called by event handlers)
    # ------------------------------------------------------------------

    def register_account(self, account: Account) -> None:
        self._accounts[account.account_id] = account

    def register_instrument(self, instrument: Instrument) -> None:
        self._instruments[instrument.ticker] = instrument

    def halt_ticker(self, ticker: str) -> None:
        self._halted_tickers.add(ticker)
        logger.warning('Trading halted for %s', ticker)

    def resume_ticker(self, ticker: str) -> None:
        self._halted_tickers.discard(ticker)
        logger.info('Trading resumed for %s', ticker)

    # ------------------------------------------------------------------
    # Main check entry point
    # ------------------------------------------------------------------

    async def check(self, order: Order) -> RiskResult:
        checks = [
            self._check_account_exists,
            self._check_instrument,
            self._check_market_halt,
            self._check_order_size,
            self._check_price_sanity,
            self._check_funds_or_shares,
            self._check_order_value,
        ]
        for check in checks:
            result = check(order)
            if not result.passed:
                logger.info(
                    'Order %s rejected by %s: %s',
                    order.order_id,
                    check.__name__,
                    result.reason,
                )
                return result
        return RiskResult(passed=True)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_account_exists(self, order: Order) -> RiskResult:
        if order.account_id not in self._accounts:
            return RiskResult(False, f'Unknown account: {order.account_id}')
        return RiskResult(True)

    def _check_instrument(self, order: Order) -> RiskResult:
        instrument = self._instruments.get(order.ticker)
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
                f'Quantity {order.quantity} exceeds '
                f'max order size {instrument.max_order_size}',
            )
        return RiskResult(True)

    def _check_market_halt(self, order: Order) -> RiskResult:
        if order.ticker in self._halted_tickers:
            return RiskResult(False, f'Trading halted for {order.ticker}')
        return RiskResult(True)

    def _check_order_size(self, order: Order) -> RiskResult:
        if order.quantity <= 0:
            return RiskResult(False, 'Order quantity must be positive')
        return RiskResult(True)

    def _check_price_sanity(self, order: Order) -> RiskResult:
        if order.order_type == OrderType.LIMIT:
            if order.price is None or order.price <= 0:
                return RiskResult(False, 'Limit order must have a positive price')
            instrument = self._instruments.get(order.ticker)
            if instrument and instrument.last_price:
                ratio = order.price / instrument.last_price
                if ratio > 3.0 or ratio < 0.1:
                    return RiskResult(
                        False,
                        f'Price {order.price:.2f} is too far from last price '
                        f'{instrument.last_price:.2f} (possible fat-finger)',
                    )
        return RiskResult(True)

    def _check_funds_or_shares(self, order: Order) -> RiskResult:
        account = self._accounts[order.account_id]

        if order.side == Side.BUY:
            if order.order_type == OrderType.LIMIT and order.price:
                required = order.price * order.quantity
                available = account.available_cash()
                if available < required:
                    return RiskResult(
                        False,
                        f'Insufficient funds: need {required:.2f},'
                        f' have {available:.2f}',
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

    def _check_order_value(self, order: Order) -> RiskResult:
        if order.order_type == OrderType.LIMIT and order.price:
            notional = order.price * order.quantity
            if notional > MAX_ORDER_VALUE:
                return RiskResult(
                    False,
                    f'Order value {notional:.2f} exceeds limit {MAX_ORDER_VALUE:.2f}',
                )
        return RiskResult(True)
