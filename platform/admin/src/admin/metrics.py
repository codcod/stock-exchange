"""
Overview-panel and service-card queries against the other services' schemas
(via `read_model`). Rates that need a delta between ticks (submitted/s,
writes/s, updates/s) are computed admin-side by the caller from successive
totals — same technique as monolith's `stage_totals` + previous-tick delta —
rather than a second query here.
"""

from __future__ import annotations

import typing as tp
from itertools import chain

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection

from admin.read_model import (
    accounts,
    order_management_outbox,
    orders,
    trades,
)

_RECENT_LIMIT = 500


class FunnelTotals(tp.TypedDict):
    submitted: int
    executed: int
    filled: int


async def funnel_totals(conn: AsyncConnection) -> FunnelTotals:
    submitted = await conn.scalar(sa.select(sa.func.count()).select_from(orders))
    executed = await conn.scalar(sa.select(sa.func.count()).select_from(trades))
    filled = await conn.scalar(
        sa.select(sa.func.count())
        .select_from(orders)
        .where(orders.c.status == 'FILLED')
    )
    return {
        'submitted': submitted or 0,
        'executed': executed or 0,
        'filled': filled or 0,
    }


async def backlog(conn: AsyncConnection) -> int:
    result = await conn.scalar(
        sa.select(sa.func.count())
        .select_from(orders)
        .where(orders.c.status.in_(['OPEN', 'PARTIALLY_FILLED']))
    )
    return result or 0


async def fill_latency_ms(conn: AsyncConnection) -> dict[str, float | None]:
    result = await conn.execute(
        sa.text("""
            SELECT
                percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms),
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
            FROM (
                SELECT
                    extract(epoch FROM (updated_at - created_at)) * 1000 AS latency_ms
                FROM order_management.orders
                WHERE status = 'FILLED'
                ORDER BY updated_at DESC
                LIMIT :limit
            ) recent
        """),
        {'limit': _RECENT_LIMIT},
    )
    p50, p95 = tp.cast(tuple[float | None, float | None], tp.cast(object, result.one()))
    return {'p50': p50, 'p95': p95}


async def reject_rate(conn: AsyncConnection) -> float:
    result = await conn.execute(
        sa.text("""
            SELECT
                count(*) FILTER (WHERE status = 'REJECTED')::float / NULLIF(count(*), 0)
            FROM (
                SELECT status FROM order_management.orders
                ORDER BY updated_at DESC LIMIT :limit
            ) recent
        """),
        {'limit': _RECENT_LIMIT},
    )
    return result.scalar() or 0.0


async def oldest_resting_age_seconds(conn: AsyncConnection) -> float | None:
    result = await conn.execute(
        sa.text("""
            SELECT extract(epoch FROM (now() - min(created_at)))
            FROM order_management.orders
            WHERE status IN ('OPEN', 'PARTIALLY_FILLED')
        """)
    )
    return tp.cast(float | None, result.scalar())


async def volume_by_ticker(
    conn: AsyncConnection, window_seconds: float = 60
) -> dict[str, dict[str, int]]:
    result = await conn.execute(
        sa.text("""
            SELECT ticker, side, SUM(quantity) AS qty
            FROM order_management.orders
            WHERE created_at > now() - make_interval(secs => :window_seconds)
            GROUP BY ticker, side
        """),
        {'window_seconds': window_seconds},
    )
    volume: dict[str, dict[str, int]] = {}
    for row in result:
        side_key = 'buy' if row.side == 'BUY' else 'sell'
        volume.setdefault(row.ticker, {'buy': 0, 'sell': 0})[side_key] = int(row.qty)
    return volume


async def trade_tape(conn: AsyncConnection, limit: int = 20) -> list[dict]:
    """
    Merge fills (trade joined to the order it reports) and rejections
    (order alone), newest first. Side shown is the joined order's own
    `side` — the order whose fill/rejection this row reports — not an
    inferred aggressor side.
    """
    fills = (
        (
            await conn.execute(
                sa.text("""
                SELECT
                    t.ticker, o.side, t.quantity, t.price, o.status, t.executed_at AS ts
                FROM clearing.trades t
                JOIN order_management.orders o
                    ON o.order_id = COALESCE(t.sell_order_id, t.buy_order_id)
                ORDER BY t.executed_at DESC
                LIMIT :limit
            """),
                {'limit': limit},
            )
        )
        .mappings()
        .all()
    )
    rejections = (
        (
            await conn.execute(
                sa.text("""
                SELECT ticker, side, quantity, price, status, updated_at AS ts
                FROM order_management.orders
                WHERE status = 'REJECTED'
                ORDER BY updated_at DESC
                LIMIT :limit
            """),
                {'limit': limit},
            )
        )
        .mappings()
        .all()
    )
    merged = sorted(chain(fills, rejections), key=lambda r: r['ts'], reverse=True)[
        :limit
    ]
    return [
        {
            'ticker': r['ticker'],
            'side': r['side'],
            'quantity': r['quantity'],
            'price': float(r['price']) if r['price'] is not None else None,
            'status': r['status'],
            'at': r['ts'].isoformat(),
        }
        for r in merged
    ]


# ---------------------------------------------------------------------------
# Service-card queries
# ---------------------------------------------------------------------------


async def order_management_stats(conn: AsyncConnection) -> dict:
    open_orders = await backlog(conn)
    outbox_backlog = await conn.scalar(
        sa.select(sa.func.count())
        .select_from(order_management_outbox)
        .where(order_management_outbox.c.published_at.is_(None))
    )
    return {'open_orders': open_orders, 'outbox_backlog': outbox_backlog or 0}


async def clearing_stats(conn: AsyncConnection) -> dict:
    trades_recorded = await conn.scalar(sa.select(sa.func.count()).select_from(trades))
    return {'trades_recorded': trades_recorded or 0, 'settlement': 'T+0'}


async def account_stats(conn: AsyncConnection) -> dict:
    count = await conn.scalar(sa.select(sa.func.count()).select_from(accounts))
    reserved_cash_total = await conn.scalar(
        sa.select(sa.func.sum(accounts.c.reserved_cash))
    )
    return {
        'accounts': count or 0,
        'cash_reserved': float(reserved_cash_total) if reserved_cash_total else 0.0,
    }


async def notifications_db_stats(conn: AsyncConnection) -> dict:
    events_per_sec = await conn.scalar(
        sa.text("""
            SELECT count(*)::float / 60
            FROM notifications.notifications
            WHERE created_at > now() - interval '60 seconds'
        """)
    )
    return {'events_per_sec': round(events_per_sec or 0.0, 1)}
