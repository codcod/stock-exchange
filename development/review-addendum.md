# Review addendum — exchange project-specific rules

**Version 3** · written 2026-09-16 against `main` at `31e5603` (pickle install; no tickets
filed yet), updated same day by EXC-003 (docs/architecture.md → development/design.md) and on
2026-09-17 by EXC-007's review.

Applies **on top of** the brine review protocol
(`.agents/skills/brine/resources/review-protocol.md`), keyed to that procedure's step numbers.
It never replaces it.

There is no overarching addendum layer: exchange is a single child-project at `path = "."`
under `layout = "in-tree"`, so the board and the code share one repository and one addendum
covers both surfaces. If a second child is ever registered, the bookkeeping rules move up to a
top-level `review_addendum` and the rest stays here.

**This file does not restate `CLAUDE.md`.** Its "Development conventions" and "When modifying a
service" sections are the source of truth for the conventions themselves. What this file adds is
the *audit procedure*: which of those conventions have no mechanical enforcement, and where they
are already soft-violated.

## Step 1 — Load context (additions)

Configured commands: `just services-build`, `just test`, `just lint`. There is no configured
docs command — `development/design.md` is hand-maintained prose, not a built doc site, so step
4a's "build the docs" sub-step has nothing to run.

Governing documents for this project: `CLAUDE.md` (a pointer only, since EXC-003) and
`development/design.md` (design of record — architecture, conventions, and its "What's
intentionally simplified" section — see step 4a). There is no `PLAN.md` or `CHANGELOG.md` in
this repo; do not look for them.

## Step 2 — Implementation audit (additions)

`CLAUDE.md`'s "When modifying a service" checklist is the per-service acceptance test. The one
step most likely to be silently skipped:

1. **A new event needs both outbox maps, in the *emitting* service.** Each `outbox_relay.py`
   (`services/{account,matching_engine,order_management}/outbox_relay.py`) carries an
   `EVENT_DESTINATIONS` dict (event type → list of downstream services) and an
   `ENDPOINT_FOR_EVENT_TYPE` dict (destination → URL path). Wiring only one of the two still
   passes local unit tests — they mock the HTTP call — and only fails at runtime when the relay
   polls and finds no endpoint for a destination it was told to fan out to. Grep both dicts in the
   emitting service's file whenever a ticket adds or renames an event.
2. **The consumer side is a separate, unaudited contract.** `EVENT_DESTINATIONS` names a
   downstream service by string; nothing type-checks that the named service actually exposes the
   `/events/...` route `ENDPOINT_FOR_EVENT_TYPE` points at. Confirm the destination service's
   `app.py` defines that route.
3. **An acceptance test that stops at `just lint` does not cover CI.** `.github/workflows/ci.yaml`
   runs `ruff check .` **and** `ruff format --check .`; `just lint` is only the first of the two.
   A ticket whose acceptance test lists `just lint` without `just check` (or `just fmt-check`) can
   go green locally and still land a red PR — generated files are the usual culprit, since
   scaffolders such as `alembic revision` do not emit ruff-formatted output. Run `just check`
   during the implementation audit, not only at step 9, and class a plan that omits it `test-gap`.
4. **Stateful/stateless is a hard split, not a convention.** `risk_engine`, `order_management`,
   `matching_engine`, `clearing`, `account`, `notifications` require `DATABASE_URL`; `gateway` and
   `market_data` do not. A ticket that adds persistence to `gateway` or `market_data` is
   contradicting this split — flag it at step 4, `class: design` (or `plan-wrong` if a ticket's
   own confirmed decision asserted otherwise).

## Step 3 — Quality audit (additions)

1. **Lint is real signal, not just formatting.** `just lint` runs `ruff check .` with `PL`
   (pylint) and `C90` (complexity) selected, not only `E`/`F`. Do not wave through a lint failure
   as "just style" — a `PLR09xx` or `C901` hit is a structural finding.
2. **Type hints are unchecked.** `import typing as tp` is a house convention (`CLAUDE.md`), but
   nothing in `just lint` or `just test` runs mypy/pyright. A wrong or missing annotation is
   `class: design`, never blocking on its own.
3. **The 200-line-per-file guideline is already soft-violated** in four files that predate this
   addendum: `services/order_management/service.py` (205), `services/order_management/app.py`
   (204), `services/matching_engine/order_book.py` (246), `platform/account/src/account/app.py` (199). Do not
   file the existing overage as a finding. Flag only a branch that grows one of these further, or
   that adds a new file starting over 200 lines.
4. **Async discipline is a correctness axis here, not style.** Every service module is
   `async def` (FastAPI + asyncpg). A blocking call inside a service — a bare `httpx.Client`
   instead of `httpx.AsyncClient`, a synchronous DB driver call, `time.sleep` — stalls the whole
   process's event loop for every account, not just the caller: `class: correctness`. The client
   side inverts this: `clients/tui/` is synchronous by convention, so blocking I/O there must run
   via `@work(thread=True)`; a bare coroutine calling blocking I/O on the TUI's event loop freezes
   the UI and is the same `correctness` class from the other direction.

## Step 4 / 4a — Consistency & documentation audit (additions)

1. **`development/design.md`'s "What's intentionally simplified" section is a list of accepted
   limitations** (no market-data WebSocket, at-least-once outbox delivery with no consumer-side
   dedup, non-durable risk reservations, in-memory-only market data, etc.), not a backlog. Do not
   file any of them as a finding on their own. A ticket that touches one of these areas without
   updating or removing its entry is `stale-xref`; a ticket whose design assumes a listed
   limitation doesn't exist is `plan-wrong`.
2. **Whole-tree docs sweep is small and exact here** — `development/design.md` is the entire
   shipped docs tree (`docs/architecture.md` and `docs/lob_concepts_review.md` were folded into
   it and deleted by EXC-003). Read it in full rather than spot-checking; there is no docs build
   to catch what a skim misses (step 1).
3. **`platform/gateway/` has no test directory**, unlike every other service (each has its own
   `tests/`). This is a pre-existing gap, not itself a finding — but a ticket that changes gateway
   routing, auth, or rate-limiting without adding a test alongside is `test-gap`, not something to
   wave through because "gateway has no tests anyway." Gateway is the entry point; untested changes
   there are the highest-blast-radius kind in this repo.

## Step 7 — Governing documents (additions)

`development/design.md`'s "When modifying a service" step 6 — *update this document's "Detailed
architecture" section if the data flow changed* — is this project's own reconciliation rule. A
branch that changes which service emits, consumes, or relays an event without updating that
section's diagram/prose has broken this project's own convention: file it as `stale-xref` per
step 7, same disposition path as any other governing-document drift.

## Step 9 — Finish (additions)

Run `just check` (`lint` + `fmt-check`) before presenting the commit for approval — it is the
one-shot local gate and the closest thing this repo has to a CI dry run.

## Revision history

- **v1** (2026-09-16) — Written at pickle install time, before any ticket exists. Grounded
  against the actual tree (outbox maps, line-count guideline violations, gateway's missing
  `tests/`, ruff's lint selection) rather than restated from `CLAUDE.md` prose.
- **v2** (2026-09-16) — EXC-003 folded `docs/architecture.md` and `docs/lob_concepts_review.md`
  into `development/design.md` and deleted the originals; every governing-document reference
  above moved from `docs/architecture.md` to `development/design.md`.
- **v3** (2026-09-17) — EXC-007's review added step 2 item 3 (an acceptance test listing only
  `just lint` misses CI's `ruff format --check`, which a scaffolded Alembic revision fails) after
  the branch under review landed an unformatted generated migration, and repointed step 3 item 3's
  line-count entry from `services/account/app.py` (201) to `platform/account/src/account/app.py`
  (199).
