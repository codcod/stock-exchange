"""
In-memory pre-trade risk engine.

Account and instrument state are cached at startup and updated on every
account change, enabling fast validation without database round-trips.
The full ordered policy is visible in `checks.CHECKS`.
"""

from __future__ import annotations

import logging
import typing as tp
from dataclasses import dataclass

from shared.domain.models import Account, Instrument, Order

logger = logging.getLogger(__name__)


@dataclass
class RiskResult:
    """The result of a single risk check."""

    passed: bool
    reason: tp.Optional[str] = None


class RiskEngine:
    """
    A fast, in-memory engine for pre-trade risk checks.

    The engine maintains a local cache of account and instrument state,
    which is populated at startup and updated on every trade. This allows
    for rapid validation of incoming orders without database round-trips.
    """

    def __init__(self) -> None:
        self._accounts: tp.Dict[str, Account] = {}
        self._instruments: tp.Dict[str, Instrument] = {}
        self._halted_tickers: set = set()

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def register_account(self, account: Account) -> None:
        """Add or update an account in the local cache."""
        self._accounts[account.account_id] = account

    def register_instrument(self, instrument: Instrument) -> None:
        """Add or update an instrument in the local cache."""
        self._instruments[instrument.ticker] = instrument

    def halt_ticker(self, ticker: str) -> None:
        """Temporarily halt trading for a specific ticker."""
        self._halted_tickers.add(ticker)
        logger.warning('Trading halted for %s', ticker)

    def resume_ticker(self, ticker: str) -> None:
        """Resume trading for a halted ticker."""
        self._halted_tickers.discard(ticker)
        logger.info('Trading resumed for %s', ticker)

    # ------------------------------------------------------------------
    # Main check entry point
    # ------------------------------------------------------------------

    async def check(self, order: Order) -> RiskResult:
        """
        Run all pre-trade risk checks for a new order.

        Imports CHECKS lazily to avoid the circular import that would arise
        from checks.py importing RiskResult from this module at load time.
        """
        from services.risk_engine.checks import CHECKS

        for check_fn in CHECKS:
            result = check_fn(
                order, self._accounts, self._instruments, self._halted_tickers
            )
            if not result.passed:
                logger.info(
                    'Order %s rejected by %s: %s',
                    order.order_id,
                    check_fn.__name__,
                    result.reason,
                )
                return result
        return RiskResult(passed=True)
