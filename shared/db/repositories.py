"""
shared/db/repositories.py

SQLAlchemy Core repository classes — one per domain entity.
No ORM; all queries use Core expression language.
"""

from __future__ import annotations

import typing as tp
from datetime import datetime, timezone

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from shared.db.tables import accounts as accounts_t
from shared.db.tables import instruments as instruments_t
from shared.db.tables import orders as orders_t
from shared.db.tables import outbox as outbox_t
from shared.db.tables import positions as positions_t
from shared.db.tables import reserved_shares as reserved_shares_t
from shared.db.tables import trades as trades_t
from shared.models.domain import (
    Account,
    Instrument,
    Order,
    OrderStatus,
    OrderType,
    Side,
    Trade,
)


def _f(val) -> tp.Optional[float]:
    return float(val) if val is not None else None


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


class OrderRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, order: Order) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                insert(orders_t).values(
                    order_id=order.order_id,
                    account_id=order.account_id,
                    ticker=order.ticker,
                    side=order.side.value,
                    order_type=order.order_type.value,
                    quantity=order.quantity,
                    price=order.price,
                    status=order.status.value,
                    filled_quantity=order.filled_quantity,
                    average_fill_price=order.average_fill_price,
                    reject_reason=order.reject_reason,
                    created_at=order.created_at,
                    updated_at=order.updated_at,
                )
            )

    async def update(self, order: Order) -> None:
        order.updated_at = datetime.now(timezone.utc)
        async with self._engine.begin() as conn:
            await conn.execute(
                update(orders_t)
                .where(orders_t.c.order_id == order.order_id)
                .values(
                    status=order.status.value,
                    filled_quantity=order.filled_quantity,
                    average_fill_price=order.average_fill_price,
                    reject_reason=order.reject_reason,
                    updated_at=order.updated_at,
                )
            )

    async def load_all(self) -> tp.List[Order]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(orders_t))).mappings().all()
        return [_row_to_order(r) for r in rows]


def _row_to_order(r) -> Order:
    order = Order(
        account_id=r['account_id'],
        ticker=r['ticker'],
        side=Side(r['side']),
        order_type=OrderType(r['order_type']),
        quantity=int(r['quantity']),
        price=_f(r['price']),
        order_id=r['order_id'],
        status=OrderStatus(r['status']),
        filled_quantity=int(r['filled_quantity']),
        average_fill_price=_f(r['average_fill_price']),
        reject_reason=r['reject_reason'],
        created_at=r['created_at'],
        updated_at=r['updated_at'],
    )
    return order


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------


class AccountRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, account: Account) -> None:
        async with self._engine.begin() as conn:
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
                delete(positions_t).where(
                    positions_t.c.account_id == account.account_id
                )
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


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------


class InstrumentRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, instrument: Instrument) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                pg_insert(instruments_t)
                .values(
                    ticker=instrument.ticker,
                    name=instrument.name,
                    lot_size=instrument.lot_size,
                    max_order_size=instrument.max_order_size,
                    is_tradeable=instrument.is_tradeable,
                    last_price=instrument.last_price,
                )
                .on_conflict_do_update(
                    index_elements=['ticker'],
                    set_=dict(
                        name=instrument.name,
                        lot_size=instrument.lot_size,
                        max_order_size=instrument.max_order_size,
                        is_tradeable=instrument.is_tradeable,
                        last_price=instrument.last_price,
                    ),
                )
            )

    async def update_last_price(self, ticker: str, last_price: float) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                update(instruments_t)
                .where(instruments_t.c.ticker == ticker)
                .values(last_price=last_price)
            )

    async def load_all(self) -> tp.List[Instrument]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(instruments_t))).mappings().all()
        return [
            Instrument(
                ticker=r['ticker'],
                name=r['name'],
                lot_size=int(r['lot_size']),
                max_order_size=int(r['max_order_size']),
                is_tradeable=bool(r['is_tradeable']),
                last_price=_f(r['last_price']),
            )
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


class TradeRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, trade: Trade) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                insert(trades_t).values(
                    trade_id=trade.trade_id,
                    ticker=trade.ticker,
                    buy_order_id=trade.buy_order_id,
                    sell_order_id=trade.sell_order_id,
                    buyer_account_id=trade.buyer_account_id,
                    seller_account_id=trade.seller_account_id,
                    quantity=trade.quantity,
                    price=trade.price,
                    executed_at=trade.executed_at,
                )
            )


# ---------------------------------------------------------------------------
# Outbox
# ---------------------------------------------------------------------------


async def write_outbox_rows(conn, rows: tp.List[dict]) -> None:
    """Insert outbox rows into an already-open connection/transaction."""
    if rows:
        await conn.execute(insert(outbox_t), rows)


class OutboxRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def fetch_unpublished(self) -> tp.List[dict]:
        async with self._engine.connect() as conn:
            result = await conn.execute(
                select(outbox_t)
                .where(outbox_t.c.published_at.is_(None))
                .order_by(outbox_t.c.id)
            )
            return [dict(row) for row in result.mappings().all()]

    async def mark_published(self, row_id: int) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                update(outbox_t)
                .where(outbox_t.c.id == row_id)
                .values(published_at=datetime.now(timezone.utc))
            )
