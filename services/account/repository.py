"""Repository for Account persistence in the Account service."""

from __future__ import annotations

import typing as tp

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from services.account.tables import accounts as accounts_t
from services.account.tables import positions as positions_t
from services.account.tables import reserved_shares as reserved_shares_t
from shared.domain.models import Account


class AccountRepository:
    """Handles persistence of Account state (cash, positions, reservations)."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, account: Account) -> None:
        """Upsert account in its own transaction."""
        async with self._engine.begin() as conn:
            await self._save(conn, account)

    async def save_with_conn(self, conn, account: Account) -> None:
        """Upsert account using an existing transaction connection."""
        await self._save(conn, account)

    async def _save(self, conn, account: Account) -> None:
        await conn.execute(
            pg_insert(accounts_t)
            .values(
                account_id=account.account_id,
                name=account.name,
                cash_balance=account.cash_balance,
                reserved_cash=account.reserved_cash,
                created_at=account.created_at,
            )
            .on_conflict_do_update(
                index_elements=['account_id'],
                set_=dict(
                    name=account.name,
                    cash_balance=account.cash_balance,
                    reserved_cash=account.reserved_cash,
                ),
            )
        )
        await conn.execute(
            delete(positions_t).where(positions_t.c.account_id == account.account_id)
        )
        pos_rows = [
            {'account_id': account.account_id, 'ticker': t, 'quantity': q}
            for t, q in account.positions.items()
            if q != 0
        ]
        if pos_rows:
            await conn.execute(insert(positions_t), pos_rows)

        await conn.execute(
            delete(reserved_shares_t).where(
                reserved_shares_t.c.account_id == account.account_id
            )
        )
        res_rows = [
            {'account_id': account.account_id, 'ticker': t, 'quantity': q}
            for t, q in account.reserved_shares.items()
            if q != 0
        ]
        if res_rows:
            await conn.execute(insert(reserved_shares_t), res_rows)

    async def load_all(self) -> tp.List[Account]:
        """Load all accounts with their positions and reservations."""
        async with self._engine.connect() as conn:
            acc_rows = (await conn.execute(select(accounts_t))).mappings().all()
            pos_rows = (await conn.execute(select(positions_t))).mappings().all()
            res_rows = (await conn.execute(select(reserved_shares_t))).mappings().all()

        positions: tp.Dict[str, dict] = {}
        reserved: tp.Dict[str, dict] = {}
        for r in pos_rows:
            positions.setdefault(r['account_id'], {})[r['ticker']] = int(r['quantity'])
        for r in res_rows:
            reserved.setdefault(r['account_id'], {})[r['ticker']] = int(r['quantity'])

        result = []
        for r in acc_rows:
            acct = Account(
                account_id=r['account_id'],
                name=r['name'],
                cash_balance=float(r['cash_balance']),
                reserved_cash=float(r['reserved_cash']),
                created_at=r['created_at'],
            )
            acct.positions = positions.get(r['account_id'], {})
            acct.reserved_shares = reserved.get(r['account_id'], {})
            result.append(acct)
        return result
