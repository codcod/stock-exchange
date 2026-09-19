---
id: EXC-022
title: Build admin ops dashboard (Datastar/SSE frontend, monolith-parity)
project: exchange
depends-on: []
spawned-by: []
impact: medium
complexity: medium-high
cost: M-L
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
schemas directly via SQLAlchemy Core, following the precedent already in this codebase (the
matching engine already reads `order_management.orders` directly — cross-schema, same-Postgres
read, not an HTTP call): `order_management.orders`, `matching_engine.outbox`,
`clearing.trades`, `account.accounts`/`positions`, `risk_engine.instruments`. Stateless, like
`gateway`/`market_data` — but with a read-only `DATABASE_URL` instead of none.

Soft coupling: none. This ticket is independent of EXC-021 (Event-Driven Architecture
patterns) — the admin panel reads existing tables directly, it does not depend on any EDA
change landing first.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-19 — created (TO DO). source: chat: user approved a mockup
  (https://claude.ai/artifact/3pGrStBJuEZ2wWKt2rkjHC) of a read-only admin ops dashboard
  modeled on monolith's platform/admin/, then asked to file this ticket to build it with the
  same frontend stack and that exact layout.
