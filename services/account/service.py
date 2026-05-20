"""
Account service — the authoritative source of truth for all account state.

Owns cash balances, share positions, and reservations. Settling a trade
means applying debits/credits here. Every mutation emits an AccountUpdated
event via the transactional outbox so downstream subscribers (Risk Engine)
stay current.
"""

from __future__ import annotations

import json
import logging
import typing as tp
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from services.account.outbox_repo import write_outbox_rows
from services.account.tables import processed_events as processed_events_t
from shared.domain.events import AccountUpdated, TradeExecuted
from shared.domain.models import Account

if tp.TYPE_CHECKING:
    from services.account.repository import AccountRepository

logger = logging.getLogger(__name__)


class AccountService:
    """
    Manages account identity, cash, positions, and reservations.

    All mutations write to the database and enqueue an AccountUpdated event
    in the same transaction so the Risk Engine cache stays coherent.
    """

    def __init__(self, account_repo: 'AccountRepository', engine: AsyncEngine) -> None:
        self._accounts: tp.Dict[str, Account] = {}
        self._repo = account_repo
        self._engine = engine

    # ------------------------------------------------------------------
    # Account registration
    # ------------------------------------------------------------------

    async def register_account(self, account: Account) -> Account:
        """Persist a new account and populate the in-memory cache."""
        self._accounts[account.account_id] = account
        async with self._engine.begin() as conn:
            await self._repo.save_with_conn(conn, account)
            await _enqueue_account_updated(conn, account)
        return account

    def list_accounts(self) -> tp.List[Account]:
        return list(self._accounts.values())

    def get_account(self, account_id: str) -> tp.Optional[Account]:
        return self._accounts.get(account_id)

    # ------------------------------------------------------------------
    # Reservation management
    # ------------------------------------------------------------------

    async def reserve_cash(self, account_id: str, delta: float) -> tp.Optional[Account]:
        """Increase (positive delta) or release (negative delta) a cash reservation."""
        account = self._accounts.get(account_id)
        if account is None:
            return None
        account.reserved_cash = max(0.0, account.reserved_cash + delta)
        async with self._engine.begin() as conn:
            await self._repo.save_with_conn(conn, account)
            await _enqueue_account_updated(conn, account)
        return account

    async def reserve_shares(
        self, account_id: str, ticker: str, delta: int
    ) -> tp.Optional[Account]:
        """Increase or release a share reservation for a specific ticker."""
        account = self._accounts.get(account_id)
        if account is None:
            return None
        current = account.reserved_shares.get(ticker, 0)
        account.reserved_shares[ticker] = max(0, current + delta)
        async with self._engine.begin() as conn:
            await self._repo.save_with_conn(conn, account)
            await _enqueue_account_updated(conn, account)
        return account

    # ------------------------------------------------------------------
    # Trade settlement
    # ------------------------------------------------------------------

    async def apply_settlement(
        self, event: TradeExecuted
    ) -> tp.Tuple[tp.Optional[Account], tp.Optional[Account]]:
        """
        Apply post-trade debits and credits for buyer and seller.

        Idempotent: re-delivery of the same event_id is a no-op, guarded by
        the processed_events table within the same transaction.
        """
        async with self._engine.begin() as conn:
            already_done = await conn.scalar(
                select(processed_events_t.c.event_id).where(
                    processed_events_t.c.event_id == event.event_id
                )
            )
            if already_done:
                return None, None

            buyer = self._accounts.get(event.buyer_account_id)
            seller = self._accounts.get(event.seller_account_id)
            trade_value = event.price * event.quantity

            if buyer:
                buyer.cash_balance -= trade_value
                buyer.positions[event.ticker] = (
                    buyer.positions.get(event.ticker, 0) + event.quantity
                )
                buyer.reserved_cash = max(0.0, buyer.reserved_cash - trade_value)
                logger.info(
                    'Settled BUY %s: %s +%d shares, -%.2f cash',
                    buyer.account_id,
                    event.ticker,
                    event.quantity,
                    trade_value,
                )
                await self._repo.save_with_conn(conn, buyer)
                await _enqueue_account_updated(conn, buyer)

            if seller:
                seller.cash_balance += trade_value
                seller.positions[event.ticker] = max(
                    0, seller.positions.get(event.ticker, 0) - event.quantity
                )
                reserved = seller.reserved_shares.get(event.ticker, 0)
                seller.reserved_shares[event.ticker] = max(0, reserved - event.quantity)
                logger.info(
                    'Settled SELL %s: %s -%d shares, +%.2f cash',
                    seller.account_id,
                    event.ticker,
                    event.quantity,
                    trade_value,
                )
                await self._repo.save_with_conn(conn, seller)
                await _enqueue_account_updated(conn, seller)

            await conn.execute(
                insert(processed_events_t).values(event_id=event.event_id)
            )

        return buyer, seller


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _make_account_updated(account: Account) -> AccountUpdated:
    return AccountUpdated(
        account_id=account.account_id,
        name=account.name,
        cash_balance=account.cash_balance,
        reserved_cash=account.reserved_cash,
        positions=dict(account.positions),
        reserved_shares=dict(account.reserved_shares),
    )


async def _enqueue_account_updated(conn, account: Account) -> None:
    event = _make_account_updated(account)
    now = datetime.now(timezone.utc)
    await write_outbox_rows(
        conn,
        [
            {
                'event_id': event.event_id,
                'event_type': 'AccountUpdated',
                'destination': 'risk_engine',
                'payload': json.dumps(asdict(event), default=str),
                'created_at': now,
                'published_at': None,
            }
        ],
    )
