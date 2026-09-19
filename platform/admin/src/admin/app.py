"""
Admin service -- read-only ops dashboard. Serves the Datastar/SSE frontend
over a FastAPI app (every other exchange service is FastAPI; only the
frontend technology -- Datastar, Jinja2 fragment templates, hand-encoded
SSE -- is ported from monolith's aiohttp-based admin, not its backend
framework).

Environment variables:
- `DATABASE_URL`: PostgreSQL connection string (required) -- same shared
  `exchange:exchange` role every other service uses; admin issues SELECT
  only (read-only is a code convention, not a DB restriction).
- `GATEWAY_URL`, `MARKET_DATA_URL`, `RISK_ENGINE_URL`, `MATCHING_ENGINE_URL`,
  `NOTIFICATIONS_URL`: the five instrumented services' base URLs, for their
  `GET /metrics` endpoints (default: standard port assignment).
- `PORT`: HTTP port (default: 8008).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from base.db.connection import get_engine
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from admin import metrics, remote_metrics, render
from admin.datastar import patch_elements, patch_signals

TICK_SECONDS = 2
HISTORY_LEN = 30
STAGES = ('submitted', 'executed', 'filled')

_GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:8000')
_MARKET_DATA_URL = os.getenv('MARKET_DATA_URL', 'http://localhost:8005')
_RISK_ENGINE_URL = os.getenv('RISK_ENGINE_URL', 'http://localhost:8002')
_MATCHING_ENGINE_URL = os.getenv('MATCHING_ENGINE_URL', 'http://localhost:8003')
_NOTIFICATIONS_URL = os.getenv('NOTIFICATIONS_URL', 'http://localhost:8007')

templates = Jinja2Templates(directory='templates')


@dataclass
class _AppState:
    http: httpx.AsyncClient | None = None


_state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state.http = httpx.AsyncClient(timeout=5.0)
    try:
        yield
    finally:
        await _state.http.aclose()


app = FastAPI(title='Admin', version='0.1.0', lifespan=lifespan)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


@app.get('/')
async def index(request: Request):
    return templates.TemplateResponse(request=request, name='index.html', context={})


@app.get('/events')
async def events(request: Request) -> StreamingResponse:
    return StreamingResponse(
        _tick(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache'},
    )


def _fmt(value: object, template: str) -> str:
    return template.format(value) if value is not None else '—'


async def _tick():  # noqa: C901
    """
    Datastar SSE feed: every 2s, query current exchange state plus the five
    instrumented services' `/metrics`, and push one patch-signals event
    (Overview stat numbers) plus one patch-elements event per fragment
    (3 sparklines, chart, ticker bars, trade tape, 8 service cards).

    # ponytail: per-connection in-memory history, each open tab re-queries
    independently -- move to a shared broadcaster + DB-backed history if
    this ever needs many concurrent viewers or a longer look-back.
    """
    history: dict[str, list[float]] = {stage: [] for stage in STAGES}
    previous: metrics.FunnelTotals | None = None
    prev_trades_recorded = 0
    prev_cash_reserved = 0.0
    db = get_engine()

    with contextlib.suppress(asyncio.CancelledError, ConnectionResetError):
        while True:
            async with db.connect() as conn:
                totals = await metrics.funnel_totals(conn)
                current_backlog = await metrics.backlog(conn)
                latency = await metrics.fill_latency_ms(conn)
                reject_rate = await metrics.reject_rate(conn)
                oldest = await metrics.oldest_resting_age_seconds(conn)
                volume = await metrics.volume_by_ticker(conn)
                tape = await metrics.trade_tape(conn)
                oms_stats, oms_up = await _try_stats(
                    metrics.order_management_stats(conn),
                    {'open_orders': 0, 'outbox_backlog': 0},
                )
                clearing_stat, clearing_up = await _try_stats(
                    metrics.clearing_stats(conn),
                    {'trades_recorded': prev_trades_recorded, 'settlement': 'T+0'},
                )
                acct_stats, acct_up = await _try_stats(
                    metrics.account_stats(conn),
                    {'accounts': 0, 'cash_reserved': prev_cash_reserved},
                )
                notif_db, _ = await _try_stats(
                    metrics.notifications_db_stats(conn), {'events_per_sec': 0.0}
                )

            gw, md, risk, match, notif = await asyncio.gather(
                remote_metrics.get_gateway_metrics(_state.http, _GATEWAY_URL),
                remote_metrics.get_market_data_metrics(_state.http, _MARKET_DATA_URL),
                remote_metrics.get_risk_engine_metrics(_state.http, _RISK_ENGINE_URL),
                remote_metrics.get_matching_engine_metrics(
                    _state.http, _MATCHING_ENGINE_URL
                ),
                remote_metrics.get_notifications_metrics(
                    _state.http, _NOTIFICATIONS_URL
                ),
            )

            rates: dict[str, float] = {}
            for stage in STAGES:
                total = totals[stage]
                prev = previous[stage] if previous else total
                rate = max(0.0, (total - prev) / TICK_SECONDS)
                rates[stage] = rate
                buf = history[stage]
                buf.append(rate)
                del buf[:-HISTORY_LEN]
            previous = totals

            trades_recorded = clearing_stat['trades_recorded']
            writes_per_sec = max(
                0.0, (trades_recorded - prev_trades_recorded) / TICK_SECONDS
            )
            prev_trades_recorded = trades_recorded

            cash_reserved = acct_stats['cash_reserved']
            updates_per_sec = abs(cash_reserved - prev_cash_reserved) / TICK_SECONDS
            prev_cash_reserved = cash_reserved

            signals = {
                'submittedTotal': totals['submitted'],
                'executedTotal': totals['executed'],
                'filledTotal': totals['filled'],
                'submittedRate': round(rates['submitted'], 1),
                'executedRate': round(rates['executed'], 1),
                'filledRate': round(rates['filled'], 1),
                'backlog': current_backlog,
                'fillLatencyP50': round(latency['p50'])
                if latency['p50'] is not None
                else None,
                'fillLatencyP95': round(latency['p95'])
                if latency['p95'] is not None
                else None,
                'rejectRate': round(reject_rate * 100, 2),
                'oldestRestingSeconds': round(oldest) if oldest is not None else 0,
                'clock': datetime.now(timezone.utc).strftime('%H:%M:%S'),
            }
            yield patch_signals(signals).encode()

            for stage in STAGES:
                yield patch_elements(
                    render.spark(
                        history[stage], render.STAGE_COLORS[stage], f'spark-{stage}'
                    )
                ).encode()
            yield patch_elements(render.chart(history)).encode()
            yield patch_elements(render.ticker_bars(volume)).encode()
            yield patch_elements(render.feed_rows(tape)).encode()

            for fragment in _service_cards(
                gw=gw,
                md=md,
                risk=risk,
                match=match,
                notif=notif,
                notif_db=notif_db,
                oms_stats=oms_stats,
                oms_up=oms_up,
                clearing_stat=clearing_stat,
                clearing_up=clearing_up,
                writes_per_sec=writes_per_sec,
                acct_stats=acct_stats,
                acct_up=acct_up,
                updates_per_sec=updates_per_sec,
                submitted_rate=rates['submitted'],
                reject_rate=reject_rate,
            ):
                yield patch_elements(fragment).encode()

            await asyncio.sleep(TICK_SECONDS)


async def _try_stats(coro, fallback: dict) -> tuple[dict, bool]:
    try:
        return await coro, True
    except Exception:
        return fallback, False


def _service_cards(  # noqa: PLR0913
    *,
    gw: dict | None,
    md: dict | None,
    risk: dict | None,
    match: dict | None,
    notif: dict | None,
    notif_db: dict,
    oms_stats: dict,
    oms_up: bool,
    clearing_stat: dict,
    clearing_up: bool,
    writes_per_sec: float,
    acct_stats: dict,
    acct_up: bool,
    updates_per_sec: float,
    submitted_rate: float,
    reject_rate: float,
) -> list[str]:
    return [
        render.service_card(
            'svc-gateway',
            'Gateway',
            8000,
            'Entry point · auth · request routing · stateless',
            gw is not None,
            [
                ('Requests/s', _fmt(gw and gw['requests_per_sec'], '{:.1f}')),
                (
                    'Latency p50/p95',
                    f'{gw["latency_p50_ms"]}/{gw["latency_p95_ms"]}ms'
                    if gw and gw['latency_p50_ms'] is not None
                    else '—',
                ),
                ('Error rate', _fmt(gw and gw['error_rate'] * 100, '{:.2f}%')),
            ],
            'No database — routes to OMS, Market Data, Risk Engine, Notifications.',
        ),
        render.service_card(
            'svc-order-management',
            'Order Management',
            8001,
            'Order lifecycle & persistence · stateful',
            oms_up,
            [
                ('Open orders', f'{oms_stats["open_orders"]:,}'),
                ('Submitted/s', f'{submitted_rate:.1f}'),
                ('Outbox backlog', f'{oms_stats["outbox_backlog"]:,}'),
            ],
            'Outbox relay → Notifications (OrderAccepted / Rejected / Cancelled).',
        ),
        render.service_card(
            'svc-risk-engine',
            'Risk Engine',
            8002,
            'Pre-trade checks · account cache · stateful',
            risk is not None,
            [
                ('Cached accounts', _fmt(risk and risk['cached_accounts'], '{}')),
                ('Checks/s', _fmt(risk and risk['checks_per_sec'], '{:.1f}')),
                ('Reject rate', f'{reject_rate * 100:.2f}%'),
            ],
            'Reservation state is in-memory only — not durable across a restart.',
            warn=True,
        ),
        render.service_card(
            'svc-matching-engine',
            'Matching Engine',
            8003,
            'Order book · price-time matching · stateful',
            match is not None,
            [
                ('Active books', _fmt(match and match['active_books'], '{}')),
                ('Resting orders', _fmt(match and match['resting_orders'], '{:,}')),
                ('Trades/s', f'{writes_per_sec:.1f}'),
            ],
            'Order book is in-memory only — outbox relays trades downstream.',
            warn=True,
        ),
        render.service_card(
            'svc-clearing',
            'Clearing',
            8004,
            'Post-trade audit ledger · stateful',
            clearing_up,
            [
                ('Trades recorded', f'{clearing_stat["trades_recorded"]:,}'),
                ('Writes/s', f'{writes_per_sec:.1f}'),
                ('Settlement', clearing_stat['settlement']),
            ],
            'Audit ledger only — cash/positions are owned by Account, not Clearing.',
        ),
        render.service_card(
            'svc-market-data',
            'Market Data',
            8005,
            'Quotes · depth · trade feed · stateless',
            md is not None,
            [
                ('Tickers tracked', _fmt(md and md['tickers_tracked'], '{}')),
                ('Quote req/s', _fmt(md and md['quote_requests_per_sec'], '{:.1f}')),
                ('Cache', 'in-mem'),
            ],
            'Quote/trade history not persisted — lost on restart.',
            warn=True,
        ),
        render.service_card(
            'svc-account',
            'Account',
            8006,
            'Cash, positions & reservations · stateful',
            acct_up,
            [
                ('Accounts', f'{acct_stats["accounts"]:,}'),
                ('Cash reserved', f'${acct_stats["cash_reserved"]:,.0f}'),
                ('Updates/s', f'{updates_per_sec:.1f}'),
            ],
            'Pushes AccountUpdated to Risk Engine on every mutation (sync + outbox).',
        ),
        render.service_card(
            'svc-notifications',
            'Notifications',
            8007,
            'Per-account event feed · stateful',
            notif is not None,
            [
                ('WS clients', _fmt(notif and notif['ws_clients'], '{}')),
                ('Events/s', f'{notif_db["events_per_sec"]:.1f}'),
                (
                    'Backfill req/s',
                    _fmt(notif and notif['backfill_requests_per_sec'], '{:.1f}'),
                ),
            ],
            'WebSocket push, with HTTP backfill for missed events.',
        ),
    ]


app.mount('/static', StaticFiles(directory='static'), name='static')
