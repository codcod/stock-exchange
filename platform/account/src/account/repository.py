"""Repository for Account persistence in the Account service."""

from __future__ import annotations

import typing as tp

from base.domain.models import Account
from base.repository import AbstractRepository
from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from account.tables import accounts as accounts_t
from account.tables import positions as positions_t
from account.tables import reserved_shares as reserved_shares_t


class AccountRepository(AbstractRepository[Account]):
    """Handles persistence of Account state (cash, positions, reservations)."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, item: Account) -> None:
        """Upsert account using this repository's connection."""
        conn = self._connection
        await conn.execute(
            pg_insert(accounts_t)
            .values(
                account_id=item.account_id,
                name=item.name,
                cash_balance=item.cash_balance,
                reserved_cash=item.reserved_cash,
                created_at=item.created_at,
            )
            .on_conflict_do_update(
                index_elements=['account_id'],
                set_=dict(
                    name=item.name,
                    cash_balance=item.cash_balance,
                    reserved_cash=item.reserved_cash,
                ),
            )
        )
        await conn.execute(
            delete(positions_t).where(positions_t.c.account_id == item.account_id)
        )
        pos_rows = [
            {'account_id': item.account_id, 'ticker': t, 'quantity': q}
            for t, q in item.positions.items()
            if q != 0
        ]
        if pos_rows:
            await conn.execute(insert(positions_t), pos_rows)

        await conn.execute(
            delete(reserved_shares_t).where(
                reserved_shares_t.c.account_id == item.account_id
            )
        )
        res_rows = [
            {'account_id': item.account_id, 'ticker': t, 'quantity': q}
            for t, q in item.reserved_shares.items()
            if q != 0
        ]
        if res_rows:
            await conn.execute(insert(reserved_shares_t), res_rows)

    async def get(self, id: str) -> Account | None:
        """Fetch a single account with its positions and reservations."""
        conn = self._connection
        acc_row = (
            await conn.execute(select(accounts_t).where(accounts_t.c.account_id == id))
        ).mappings().first()
        if acc_row is None:
            return None
        pos_rows = (
            await conn.execute(
                select(positions_t).where(positions_t.c.account_id == id)
            )
        ).mappings().all()
        res_rows = (
            await conn.execute(
                select(reserved_shares_t).where(reserved_shares_t.c.account_id == id)
            )
        ).mappings().all()

        account = Account(
            account_id=acc_row['account_id'],
            name=acc_row['name'],
            cash_balance=float(acc_row['cash_balance']),
            reserved_cash=float(acc_row['reserved_cash']),
            created_at=acc_row['created_at'],
        )
        account.positions = {r['ticker']: int(r['quantity']) for r in pos_rows}
        account.reserved_shares = {r['ticker']: int(r['quantity']) for r in res_rows}
        return account


async def load_all_accounts(engine: AsyncEngine) -> tp.List[Account]:
    """Load all accounts with their positions and reservations (startup hydration)."""
    async with engine.connect() as conn:
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
