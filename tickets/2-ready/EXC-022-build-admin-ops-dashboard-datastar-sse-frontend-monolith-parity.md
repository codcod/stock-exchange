---
id: EXC-022
title: Build admin ops dashboard (Datastar/SSE frontend, monolith-parity)
project: exchange
depends-on: []
spawned-by: []
impact: medium
complexity: high
cost: L
---

# EXC-022 — Build admin ops dashboard (Datastar/SSE frontend, monolith-parity)

## Outcome

After this ships, opening a new `platform/admin/` service in a browser shows a live, auto-
updating read-only ops console for the exchange — order-flow funnel, key metrics, throughput
chart, per-ticker volume, trade tape, and per-service detail cards — matching the approved
mockup's layout, with no polling from the browser (server pushes updates over one SSE
connection).

## Description

Follows the mockup approved in chat:
https://claude.ai/artifact/3pGrStBJuEZ2wWKt2rkjHC (two views — **Overview**: order-flow funnel
[Submitted / Trades executed / Orders filled] with rate + sparkline each, a metric row [open
backlog, fill latency p50/p95, reject rate, oldest resting order], a throughput chart, a
volume-by-ticker panel, and a trade tape; **Services**: one card per running service
[Gateway, Order Management, Risk Engine, Matching Engine, Clearing, Market Data, Account,
Notifications] with port, stateless/stateful tag, status pill, 3 key stats, and a caption of
known behavior/caveats from `development/design.md`). The layout, copy, palette (dark
trading-console theme, tokens defined in the mockup's `:root`), and tab structure are locked by
that approval — this ticket is the real implementation behind it, not a redesign.

**Frontend stack — exact parity with `~/Projects/monolith/platform/admin/`:**
- Datastar for reactivity: vendor `static/datastar.js` (matching monolith's pinned version),
  no other JS framework, no build step.
- Server-rendered Jinja2 fragment templates (`templates/index.html` + `templates/fragments/*`
  for the pieces that get patched: sparklines, chart, ticker bars, feed rows, service cards).
- A single `/events` SSE endpoint per page view that ticks on an interval, querying current
  state and pushing one `datastar-patch-signals` event (stat numbers) plus one
  `datastar-patch-elements` event per non-trivial fragment — port monolith's
  `src/stelo/admin/datastar.py` (`patch_elements`/`patch_signals`, hand-encoded wire format,
  no `datastar-py` dependency) essentially verbatim.
- Per-connection in-memory history for sparklines/chart (monolith's own documented
  simplification — `# ponytail: per-connection in-memory history... move to a shared
  broadcaster + DB-backed history if this ever needs many concurrent viewers or a longer
  look-back`) — same tradeoff applies here, carry the same comment forward.

**What does NOT change: the backend framework.** Monolith's admin uses aiohttp because its
sibling services (inbox/traffic/dispatcher) are aiohttp too. Every exchange service is FastAPI
(`development/design.md`'s own convention). FastAPI already supports `Jinja2Templates` and
`StreamingResponse` for SSE natively, so this ticket builds `platform/admin/` as a FastAPI
service — matching its own siblings — and only ports the frontend technology (Datastar +
templates + the SSE encoder), not aiohttp.

**Ownership pattern**, mirroring monolith's admin module: own installable package
`platform/admin/` (own `pyproject.toml`, depends on `platform/base`), own port (8008, next
free), **no schema/migrations of its own** — read-only. Read-only queries hit other services'
schemas directly via SQLAlchemy Core. *Correction during refinement:* there is **no existing
precedent** for this in the codebase — every current service only ever queries its own schema
(verified: no service imports or references another service's table object or schema-qualified
SQL). The technique is still sound — one shared Postgres instance, every service already uses
the identical `postgresql+asyncpg://exchange:exchange@postgres:5432/exchange` `DATABASE_URL`
(`infra/docker/compose.services.yml`), and `base.db.connection.get_engine()` applies no schema
restriction — admin is simply the first service to read outside its own schema. It follows
monolith admin's own convention for this (`src/stelo/admin/adapters/read_model.py`): redeclare
each foreign table's columns locally with lightweight `sa.table(...)` column refs, rather than
adding a workspace dependency on the five owning packages.

Admin reuses the existing `exchange:exchange` role/`DATABASE_URL` rather than a new restricted
Postgres role — matching every other service (there's no per-service-role precedent either) and
keeping this ticket to `platform/admin/` plus the five small instrumentation additions below.
Read-only is enforced by code discipline (admin issues `SELECT` only), not the database.

**Data sources per panel** (mapped during refinement — several of the mockup's Services-view
stats turned out not to be persisted anywhere, DB or otherwise, since they describe live
in-process state of stateless/cache-only services):

| Panel field | Source |
|---|---|
| Overview: funnel totals/rates/sparklines (Submitted/Executed/Filled), backlog, fill latency p50/p95, reject rate, oldest resting order, throughput chart, trade tape | `order_management.orders` + `clearing.trades`, admin's own DB (see Task breakdown) |
| Overview: volume by ticker (buy/sell split) | `SUM(quantity)` from `order_management.orders` grouped by `ticker, side` in the trailing window — this is *order flow* by side, not matched-trade volume (a trade is one buy+one sell at the same quantity, so it carries no buy/sell split of its own) |
| Services: Order Management (open orders, submitted/s, outbox backlog), Clearing (trades recorded, writes/s, settlement), Account (accounts, cash reserved, updates/s) | Direct DB reads — `order_management.orders`/`outbox`, `clearing.trades`, `account.accounts`/`reserved_shares` |
| Services: Notifications "Events/s" | `notifications.notifications.created_at`, DB-derivable |
| Services: Gateway (requests/s, latency p50/p95, error rate) | **Not persisted anywhere.** Gateway is stateless with no metrics store. Requires new in-process instrumentation + a `GET /metrics` endpoint (Task, below) |
| Services: Risk Engine (cached accounts, checks/s) | **Not persisted.** `risk_engine`'s schema holds only `instruments`; the account cache and check counter are in-memory. Requires instrumentation |
| Services: Matching Engine (active books, resting orders) | **Not persisted as such** — the live order book is in-memory; `matching_engine`'s schema holds only the outbox. Requires a `GET /metrics` endpoint reading that in-memory state directly (no new counter needed, just exposing what already exists) |
| Services: Market Data ("quote req/s") | **Not tracked.** Requires a request counter + `GET /metrics`. ("Tickers tracked" and "Cache: in-mem" are cheap — the former is `len()` of existing in-memory state, the latter a static label) |
| Services: Notifications ("WS clients", "backfill req/s") | WS clients is `len()` of the existing in-memory `_subscribers` dict (no new counter); backfill req/s needs a counter. Both exposed via `GET /metrics` |

This widens the ticket beyond `platform/admin/` alone: gateway, market_data, risk_engine,
matching_engine, and notifications each get a small in-process counter (where one doesn't
already exist as live state) and a `GET /metrics` JSON endpoint — decided during refinement in
preference to shipping the Services view with fabricated or blank numbers for a third of its
cells. All five stay read-only from admin's side; admin only ever calls their existing/new HTTP
endpoints or its own DB connection, never writes.

Soft coupling: none. This ticket is independent of EXC-021 (Event-Driven Architecture
patterns) — the admin panel reads existing tables directly, it does not depend on any EDA
change landing first.

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd .   # exchange is the root-path child (layout = in-tree)
git checkout main
git checkout -b feat/EXC-022-admin-ops-dashboard
```

WIP commits encouraged; tidy into atomic commits before presenting (root-path child, rules §0).
No push / no MR without explicit user approval.

### Prerequisite gate (hard)

None. `depends-on: []`; independent of EXC-021 (see Description). Working tree clean before
starting.

### Confirmed design decisions (do not deviate without asking)

1. **Backend framework is FastAPI, not aiohttp.** Every exchange service is FastAPI
   (`development/design.md`); only the frontend technology (Datastar, Jinja2 fragment
   templates, hand-encoded SSE) is ported from monolith's aiohttp-based admin, not its web
   framework.
2. **Own installable package, no schema/migrations.** `platform/admin/` — own
   `pyproject.toml` depending on `base`, port 8008, stateless, no Alembic history, no
   `migrations/` directory.
3. **Reuse the existing `exchange:exchange` `DATABASE_URL`.** No new Postgres role. Read-only
   is a code convention (admin issues `SELECT` only) — confirmed with the user during
   refinement, matching the fact that every other service already shares this one role.
4. **Cross-schema reads use monolith's `read_model.py` convention.** Redeclare each foreign
   table's needed columns locally with `sa.table(...)` (see monolith
   `src/stelo/admin/adapters/read_model.py`) rather than adding a workspace dependency on
   `order_management`/`matching_engine`/`clearing`/`account`/`risk_engine`.
5. **SSE encoder uses stdlib `json`, not `orjson`.** Monolith's `datastar.py` uses `orjson`;
   exchange has no `orjson` dependency anywhere and this hot path (a handful of small JSON
   payloads every 2s per connection) doesn't need it — stdlib `json.dumps` in the same two
   functions (`patch_signals`/`patch_elements`), same wire format. No new dependency.
6. **One `/events` SSE connection per browser tab, feeding both views.** The mockup's two
   sections (`#view-overview`, `#view-services`) are both always present in the DOM; the tab
   click only toggles which is `hidden`. So the server pushes both views' `datastar-patch-*`
   events on every tick over the one connection, and the client-side tab switch is a pure
   Datastar signal (no second connection, no page reload).
7. **Per-connection in-memory history for sparklines/chart**, monolith's own documented
   simplification, carried forward verbatim with the same `# ponytail:` comment (Description).
8. **Instrumentation additions to the five other services are minimal and additive**: a new
   `GET /metrics` route on each, plus a request/rate counter only where no live in-memory state
   already answers the question (see Description's data-source table). No existing route,
   response shape, or behavior changes. Each new counter is `# ponytail:`-commented as
   in-memory/per-process (resets on restart, not meaningful with multiple replicas) — the same
   ceiling this codebase already accepts for admin's own sparkline history.

### Tasks

#### Task 1 — Shared rate-counter helper (`platform/base`)
Add `platform/base/src/base/metrics.py`: a small `RateCounter` class over
`collections.deque` — `record(value: float = 1.0)` appends `(timestamp, value)`,
`rate_last(seconds: float) -> float` sums values with `timestamp` in the trailing window and
divides by `seconds`, `percentiles_last(seconds, pcts)` returns percentiles over the same
window (used for gateway request latency). Pure stdlib (`collections`, `time`, `statistics`),
no new dependency. `# ponytail: in-memory per-process counter, resets on restart and isn't
shared across replicas — move to a real metrics backend (e.g. Prometheus) if this needs to
survive restarts or aggregate across instances`. One `test_metrics.py` (assert-based,
`platform/base/src/base/tests/test_metrics.py`) covering record/rate_last/percentiles_last.

#### Task 2 — Gateway instrumentation
`platform/gateway/src/gateway/app.py`: add an `@app.middleware("http")` that wraps every
request with a `RateCounter` (module-level singleton) recording `(latency_ms, status_code)`.
New route `GET /metrics` → `{"requests_per_sec": ..., "latency_p50_ms": ..., "latency_p95_ms":
..., "error_rate": ...}` computed over the trailing 60s (`error_rate` = fraction of recorded
requests with `status_code >= 500`, over the same window `/health` is excluded from the
counter so the dashboard's own or infra's health polling doesn't skew it).

#### Task 3 — Market Data instrumentation
`platform/market_data/src/market_data/app.py`: increment a `RateCounter` in the `GET
/quotes/{ticker}` handler. New route `GET /metrics` → `{"tickers_tracked": len(self._quotes)
[via the service object], "quote_requests_per_sec": ...}` (60s window).

#### Task 4 — Risk Engine instrumentation
`platform/risk_engine/src/risk_engine/app.py`: increment a `RateCounter` where the pre-trade
check handler runs. New route `GET /metrics` → `{"cached_accounts": <len of the in-memory
account cache>, "checks_per_sec": ...}` (60s window).

#### Task 5 — Matching Engine instrumentation
`platform/matching_engine/src/matching_engine/app.py`: new route `GET /metrics` →
`{"active_books": <number of order books currently held>, "resting_orders": <sum of resting
orders across those books>}`, reading the engine's existing in-memory state directly — no new
counter needed here.

#### Task 6 — Notifications instrumentation
`platform/notifications/src/notifications/app.py`: increment a `RateCounter` in the `GET
/notifications/{account_id}` (backfill) handler. New route `GET /metrics` →
`{"ws_clients": sum(len(v) for v in _subscribers.values()), "backfill_requests_per_sec":
...}`.

#### Task 7 — Scaffold `platform/admin/`
- `platform/admin/pyproject.toml`: `name = "admin"`, `dependencies = ["base", "fastapi>=0.111",
  "uvicorn[standard]>=0.29", "jinja2>=3.1"]`, `[tool.hatch.build.targets.wheel] packages =
  ["src/admin"]` (mirror `platform/account/pyproject.toml`).
- `platform/admin/Dockerfile`: copy `platform/account/Dockerfile` and adapt (package name
  `admin`, port `8008`, **no** `migrations`/`alembic.ini` copy — admin has neither).
- `platform/admin/src/admin/__init__.py`, `__main__.py` (mirror `platform/account/__main__.py`,
  default `PORT=8008`).
- Register the new package: add `"platform/admin"` to `[tool.uv.workspace] members` and `admin
  = { workspace = true }` to `[tool.uv.sources]` in the root `pyproject.toml`.
- `infra/docker/compose.services.yml`: new `admin` service (build context `../..`, dockerfile
  `platform/admin/Dockerfile`, command `["-m", "admin"]`, env `PORT: "8008"`,
  `DATABASE_URL` (same value as every other service), `GATEWAY_URL: http://gateway:8000`,
  `MARKET_DATA_URL: http://market-data:8005`, `RISK_ENGINE_URL: http://risk-engine:8002`,
  `MATCHING_ENGINE_URL: http://matching-engine:8003`, `NOTIFICATIONS_URL:
  http://notifications:8007`, port `8008:8008`, healthcheck against `/health` mirroring
  `market-data`'s, `depends_on` on `postgres` being up (no `-migrate` dependency — admin has no
  migration).

#### Task 8 — `read_model.py`
`platform/admin/src/admin/read_model.py`: `sa.table(...)` column refs (Confirmed decision 4)
for `order_management.orders` (order_id, account_id, ticker, side, quantity, price, status,
filled_quantity, created_at, updated_at), `clearing.trades` (trade_id, ticker, buy_order_id,
sell_order_id, quantity, price, executed_at), `account.accounts` (account_id, cash_balance,
reserved_cash), `account.reserved_shares` (account_id, ticker, quantity),
`notifications.notifications` (notification_id, created_at). (`risk_engine.instruments` isn't
needed by any panel — omit it.)

#### Task 9 — `metrics.py` (Overview panel queries)
`platform/admin/src/admin/metrics.py`, functions taking an `AsyncConnection` from
`base.db.connection.get_engine()`:
- `funnel_totals(conn)` — `COUNT(*)` from `orders` (submitted total), `COUNT(*)` from `trades`
  (executed total), `COUNT(*) WHERE status = 'FILLED'` from `orders` (filled total). Rates are
  computed admin-side between ticks (same technique as monolith's `stage_totals` + previous-tick
  delta), not a second query.
- `backlog(conn)` — `COUNT(*) FROM orders WHERE status IN ('OPEN', 'PARTIALLY_FILLED')`.
- `fill_latency_ms(conn)` — `percentile_cont(0.5/0.95) WITHIN GROUP (ORDER BY
  extract(epoch from (updated_at - created_at)) * 1000)` over the most recent 500 `status =
  'FILLED'` orders.
- `reject_rate(conn)` — `COUNT(*) WHERE status = 'REJECTED'` / `COUNT(*)` over the most recent
  500 orders.
- `oldest_resting_age_seconds(conn)` — `extract(epoch from (now() - min(created_at)))  WHERE
  status IN ('OPEN', 'PARTIALLY_FILLED')`.
- `volume_by_ticker(conn, window_seconds=60)` — `SUM(quantity) GROUP BY ticker, side FROM
  orders WHERE created_at > now() - interval` (Description's data-source table), pivoted to
  `{ticker: {"buy": qty, "sell": qty}}`.
- `trade_tape(conn, limit=20)` — recent activity feed: `SELECT ... FROM trades JOIN orders ON
  orders.order_id = COALESCE(trades.sell_order_id, trades.buy_order_id) ORDER BY executed_at
  DESC LIMIT :limit` for FILLED/PARTIAL rows (status from the joined order,
  side/qty/price/ticker from the trade), `UNION ALL` with `SELECT ... FROM orders WHERE status
  = 'REJECTED' ORDER BY updated_at DESC LIMIT :limit` for REJECTED rows; merge-sort the two by
  timestamp in Python and take the newest `limit`. Side shown is the joined order's own `side`
  column (the order whose fill/rejection this row reports), not an inferred aggressor side.

Service-card queries in the same module:
- `order_management_stats(conn)` — open orders (`backlog` query reused), submitted/s
  (admin-side rate over `funnel_totals`), outbox backlog `COUNT(*) FROM
  order_management.outbox WHERE published_at IS NULL` (add this table's column ref to
  `read_model.py` alongside `orders`).
- `clearing_stats(conn)` — trades recorded (`COUNT(*) FROM trades`), writes/s (rate over the
  same total), `settlement = "T+0"` (static label, matches mockup).
- `account_stats(conn)` — `COUNT(*) FROM accounts`, `SUM(reserved_cash) FROM accounts`,
  updates/s (rate of `accounts` rows... no `updated_at` column exists on `accounts` — use
  `SUM(reserved_cash)` sampled tick-over-tick delta as the "updates/s" proxy instead of a row
  count, since there's no timestamp column to query directly).
- `notifications_db_stats(conn)` — `events_per_sec` from `COUNT(*) FROM notifications.notifications
  WHERE created_at > now() - interval '60 seconds'` / 60.

`remote_metrics.py` — one `httpx.AsyncClient` (reuse pattern from
`base.clients.risk_engine`/similar), five `async def get_gateway_metrics() -> dict | None`
style functions calling each service's new `GET /metrics` (Tasks 2–6), returning `None` on
timeout/connection error (treated as "service down" by the card renderer, not a crash — the
existing `GET /health` per card still drives the UP/DOWN pill; `/metrics` failure only blanks
that card's three stat values).

#### Task 10 — `datastar.py`
`platform/admin/src/admin/datastar.py`: `patch_signals(signals: dict) -> str` and
`patch_elements(html, *, selector=None, mode=None) -> str`, ported from monolith's
`src/stelo/admin/datastar.py` (Confirmed decision 5: stdlib `json.dumps` in place of
`orjson.dumps`, otherwise identical wire format — verified against the vendored
`static/datastar.js`, same version as monolith, Task 13).

#### Task 11 — `render.py` + templates
`platform/admin/src/admin/render.py`: Jinja2 environment over `templates/fragments/`
(`autoescape=True`, `trim_blocks=True`, `lstrip_blocks=True`, mirroring monolith's
`render.py`). Fragment builders: `spark(values, color, elem_id)` and `chart(history)` ported
near-verbatim from monolith's (same SVG-coordinate math, `orjson.dumps` → `json.dumps`);
new `ticker_bars(volume_by_ticker)`, `feed_rows(trade_tape)`, and `service_card(name, port,
role_line, status, stats, note)` built to the mockup's exact markup/classes (read from the
mockup's HTML during refinement — `.hero-card`, `.metric-card`, `.ticker-row`, `table.feed`,
`.service-card` structure and class names, `:root` CSS tokens).

Templates (`platform/admin/templates/`):
- `base.html` — `<head>` with the mockup's `:root` CSS tokens and `Sora`/`IBM Plex Mono`
  Google Fonts links, `extra_head`/`content` blocks (mirror monolith `base.html`).
- `index.html` — extends `base.html`; topbar, `<nav class="tabs">` with `data-view="overview"`/
  `"services"` buttons wired to a Datastar signal (`$activeView`, default `"overview"`) that
  toggles each `<section>`'s visibility via `data-show`, `initial data-signals` for every
  metric ($receivedTotal-style names from the mockup's own `data-role` attributes, adapted to
  Datastar's `$signal`/`data-text` bindings), the two `<section id="view-overview">`/`<section
  id="view-services" data-show="$activeView == 'services'">` bodies with the mockup's markup,
  `body_init` wired to `data-on-load="@get('/events', {retryMaxCount: 100})"` (monolith
  convention).
- `templates/fragments/spark.html`, `chart.html`, `ticker_bars.html`, `feed_rows.html`,
  `service_card.html` — one small template per fragment builder above, each fragment's root
  tag carrying the `id` Datastar's default merge matches on.

#### Task 12 — `app.py` (FastAPI app + `/events` SSE route)
`platform/admin/src/admin/app.py`:
- `GET /health` → `{"status": "ok"}`.
- `GET /` → `Jinja2Templates` render of `index.html`.
- `GET /events` → `StreamingResponse(media_type="text/event-stream")`. Loop every 2 seconds
  (`TICK_SECONDS = 2`, matching monolith): open a `get_engine().connect()`, run the Task 9
  queries, call the Task 9 `remote_metrics` functions concurrently (`asyncio.gather`), maintain
  per-connection `history: dict[str, list[float]]` for the three funnel series
  (`HISTORY_LEN = 30`, 60s window — `# ponytail:` per-connection in-memory history, same
  comment as monolith and Description, move to a shared broadcaster + DB-backed history if this
  ever needs many concurrent viewers or a longer look-back), yield one `patch_signals(...)`
  (all numeric/text signals for both views) followed by one `patch_elements(...)` per fragment
  (3 sparklines, chart, ticker bars, trade tape rows, 8 service cards) each tick. Suppress
  `asyncio.CancelledError`/client-disconnect on loop exit (mirrors monolith's
  `contextlib.suppress`).
- FastAPI `app.mount("/static", StaticFiles(directory="static"))`.
- Env vars: `DATABASE_URL` (required), `GATEWAY_URL`/`MARKET_DATA_URL`/`RISK_ENGINE_URL`/
  `MATCHING_ENGINE_URL`/`NOTIFICATIONS_URL` (defaults matching the standard port assignment,
  same convention as `account/app.py`'s `RISK_ENGINE_URL`), `PORT` (default 8008).

#### Task 13 — Vendor `static/datastar.js`
Copy `~/Projects/monolith/platform/admin/static/datastar.js` to
`platform/admin/static/datastar.js` verbatim (same pinned version — Confirmed decision 1 only
swaps the backend framework, not this asset).

#### Task 14 — Self-checks
- `platform/base/src/base/tests/test_metrics.py` (Task 1, assert-based `RateCounter` checks).
- `platform/admin/src/admin/tests/test_render.py` — assert-based checks that `spark`/`chart`/
  `ticker_bars`/`feed_rows`/`service_card` produce the expected root-element `id` and don't
  raise on empty input (mirrors monolith's `tests/unit/test_render.py` intent).
- `platform/admin/src/admin/tests/test_datastar.py` — asserts `patch_signals`/`patch_elements`
  wire format (event/data line shape) matches what `static/datastar.js` expects.

### Acceptance test

1. `just services-build` — builds `admin` and the five modified images clean.
2. `just lint` and `just test` — clean, including the new `test_metrics.py`/`test_render.py`/
   `test_datastar.py`.
3. `just infra-up && just services-up` (or equivalent for a dev loop already running the
   stack), then run the existing traffic generator (`clients/simulator`, per
   `development/design.md`'s "Running the project") for at least 60 seconds so the funnel,
   throughput, and trade-tape panels have live data to render.
4. Open `http://localhost:8008/` in a browser: Overview tab shows the funnel cards, metric
   row, throughput chart, volume-by-ticker panel, and trade tape all updating without a page
   reload or any polling visible in the browser's Network tab (one open `/events`
   `EventSource`/fetch-stream connection, no other periodic requests).
5. Click the Services tab: 8 cards render (Gateway, Order Management, Risk Engine, Matching
   Engine, Clearing, Market Data, Account, Notifications), each with port, stateless/stateful
   tag, a green UP status pill (from `/health`), 3 live stats, and its caption — confirm every
   stat is a real, changing number (not a static placeholder) except the two static labels
   (`Cache: in-mem`, `Settlement: T+0`).
6. `curl http://localhost:8008/metrics` is **not** expected to exist (admin exposes no
   `/metrics` of its own, unlike the five instrumented services) — confirm `curl
   http://localhost:8000/metrics`, `:8002/metrics`, `:8003/metrics`, `:8005/metrics`,
   `:8007/metrics` each return the fields Tasks 2–6 specify.
7. Stop one service (e.g. `docker compose -f infra/docker/compose.services.yml stop
   market-data`) and confirm its Services card degrades to a DOWN status pill without crashing
   the `/events` stream for the rest of the page.

### Docs update (mandatory when user-facing)

`development/design.md`:
- "Architecture overview" code block: add a `platform/admin/` line alongside the other
  `platform/` entries, describing it as the read-only ops dashboard (own installable package,
  no migrations).
- "Service responsibilities" table / the port-assignment prose right after it: add `admin` at
  port 8008 to the authoritative service list (the table itself is already stale per prior
  History — follow that section's existing correction rather than re-adding to the stale
  table).
- Note the five `/metrics` additions (Tasks 2–6) inline next to each service's existing
  description, one clause each, so a future reader doesn't have to find this ticket to learn
  they exist.

### Finish (mandatory)

1. Acceptance test green; `just services-build`, `just lint`, `just test` clean.
2. `development/design.md` updated per Docs update above.
3. Write a summary: files touched (per Task above), decisions made (Confirmed design decisions
   1–8), anything deferred (e.g. a real Postgres read-only role, a shared metrics backend —
   both flagged `# ponytail:` in the relevant files).
4. Suggested commit message: `feat(admin): add read-only ops dashboard with Datastar/SSE
   (EXC-022)` — body notes the five companion `/metrics` instrumentation additions.
5. Tidy WIP commits into atomic ones (root-path child) before presenting.
6. Commit locally on the ticket branch; no push/MR without user approval. Verify
   `origin/main...HEAD` carries no `tickets/` path before pushing, once approved. Hand back.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-19 — created (TO DO). source: chat: user approved a mockup
  (https://claude.ai/artifact/3pGrStBJuEZ2wWKt2rkjHC) of a read-only admin ops dashboard
  modeled on monolith's platform/admin/, then asked to file this ticket to build it with the
  same frontend stack and that exact layout.
- 2026-09-19 — TO DO → READY: plan complete
