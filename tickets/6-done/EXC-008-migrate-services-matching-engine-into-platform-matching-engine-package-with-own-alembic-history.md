---
id: EXC-008
title: Migrate services/matching_engine into platform/matching_engine package with own Alembic history
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-008 — Migrate services/matching_engine into platform/matching_engine package with own Alembic history

## Outcome

After this ships, `platform/matching_engine/` is its own installable package (own
`pyproject.toml`, version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on
`platform/base/`, with its own two-stage Dockerfile and its own independent Alembic migration
history gating its startup — instead of a subtree of the single flat install sharing the
create-on-boot bootstrap.

## Description

`EXC-003 decisions 1, 2, 3, 5`. `matching_engine` is stateful (`DATABASE_URL`, schema-per-service
already in code). It also owns the outbox event relay (`services/matching_engine/outbox_relay.py`)
— its `EVENT_DESTINATIONS`/`ENDPOINT_FOR_EVENT_TYPE` maps and any `shared.platform.clients.*`
imports must keep resolving after the move (`platform/base/` per EXC-004). Scope: move
`services/matching_engine/` to `platform/matching_engine/src/matching_engine/`, give it its own
`pyproject.toml` (hatchling, `src/` layout, depends on `platform/base/`), own two-stage Dockerfile,
own versioning artifacts starting at `0.0.1`, and its own Alembic migration history scoped to its
Postgres schema, replacing its share of the create-on-boot bootstrap with a
`matching_engine-migrate` one-shot compose container gating startup. Depends on EXC-004
(`platform/base/` must exist first).

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-008-migrate-services-matching-engine-into-platform-matching-engine-package-with-own-alembic-history
```

Work and commit locally per the project's commit policy (`exchange` is a root-path child —
tidy WIP commits into atomic ones before presenting; no push/MR without explicit user
approval).

### Prerequisite gate (hard)

EXC-004 must be `6-done/` and merged. It is: `PR #19`, `bb4e5cd`, merged to `main`
(`tickets/BOARD.md` DONE table). `platform/base/` exists with package name `base`, and already
carries `platform/base/src/base/db/migrations.py` (added by EXC-007) — the shared async
`run_migrations_online(target_metadata)` helper. This ticket reuses it **unchanged**; no new
copy, no edits.

### Confirmed design decisions (do not deviate without asking)

1. **`platform/matching_engine/`'s importable package name is `matching_engine`, flat** —
   `platform/matching_engine/src/matching_engine/{__init__.py,__main__.py,app.py,matching.py,
   order_book.py,outbox_relay.py,outbox_repo.py,tables.py,tests/}`, matching every other
   `platform/<service>/` package (EXC-004 decision 1).
2. **`alembic` stays a transitive dependency via `platform/base`** (already added there by
   EXC-007) — no direct `alembic` entry in `platform/matching_engine/pyproject.toml`.
3. **Own two-stage Dockerfile**, same shape as EXC-005–EXC-007's, plus `alembic.ini` and
   `migrations/` copied into the runtime stage so `python -m alembic upgrade head` also works
   there. `ENTRYPOINT` stays plain `python` so compose can override `CMD` for the migration
   one-shot.
4. **A new `matching-engine-migrate` one-shot compose service — with no `depends_on: postgres`
   entry.** EXC-016 (merged, PR #23) established the repo-wide convention that the
   Postgres-health gate belongs to `just infra-up --wait` (and `just up`'s ordering of
   `infra-up` before `services up`), never to a `depends_on: postgres` entry inside
   `compose.services.yml` — that entry is what EXC-016 removed everywhere, including from
   `account-migrate`. Verify `infra/docker/compose.services.yml`'s current `account-migrate`
   block before writing this one: it has no `depends_on:` key at all. Mirror that, not
   EXC-007's original text (written before EXC-016 landed).
   `matching-engine`'s own `depends_on` **keeps** its existing `order-management: condition:
   service_healthy` entry (startup hydration of open orders — unrelated to migrations) and
   **adds** `matching-engine-migrate: condition: service_completed_successfully` alongside it.
5. **`matching_engine/tables.py`'s `MetaData` is schema-qualified**: `metadata = MetaData()` →
   `metadata = MetaData(schema='matching_engine')`. The shared `run_migrations_online` helper
   already sets `version_table_schema=target_metadata.schema` (EXC-007 decision 5) — no change
   needed there.
6. **`matching_engine/tables.py`'s `ensure_tables()` wrapper is deleted**, along with its
   `from base.db.tables import ensure_tables as _ensure_tables` import, and `app.py`'s lifespan
   drops the `await ensure_tables(_state.db)` call — Alembic now owns schema/table creation via
   the `matching-engine-migrate` container. The shared `base.db.tables.ensure_tables()` helper
   is **not** touched — `risk_engine`, `order_management`, `clearing`, `notifications` still
   call it until EXC-009–EXC-012 land.
7. **The initial migration is handwritten**, not autogenerated: one revision doing `CREATE
   SCHEMA IF NOT EXISTS matching_engine` plus creating the single `outbox` table verbatim from
   `tables.py` (matching_engine persists no order-book state itself — it hydrates from
   `order_management` over HTTP on startup — so `outbox` is the only table).
8. **`EVENT_DESTINATIONS`/`DESTINATION_URLS`/`ENDPOINT_FOR_EVENT_TYPE` in `outbox_relay.py` are
   left untouched.** Their string values (`'clearing'`, `'order_management'`, `'market_data'`,
   `'account'`, `'notifications'`) are HTTP routing keys resolved against compose service
   *names* and env-var URLs, not Python import paths — Task 3's `services\.matching_engine` →
   `matching_engine` rewrite must not touch them.
9. **`just services-build` is now expected to pass outright** — EXC-016 (merged) removed the
   dangling `depends_on: postgres` that made it fail unconditionally; treat any failure here as
   a real regression, not the old pre-existing EXC-016 error.
10. **Every sibling `platform/*/Dockerfile` needs a new `COPY platform/matching_engine/
    pyproject.toml ./platform/matching_engine/pyproject.toml` stub** (uv resolves the whole
    workspace). **Discover the current sibling list at implementation time** —
    `ls platform/*/Dockerfile | grep -v platform/matching_engine/Dockerfile` — rather than
    hardcoding today's three (`gateway`, `market_data`, `account`): EXC-009–EXC-012 have no
    `depends-on:` on each other, so this ticket may land before or after any of them, and a
    hardcoded list would go stale exactly the way EXC-007's F2/F5 findings did.
11. **Also fix `justfile`'s `run-matching` recipe** (currently `uv run python -m
    services.matching_engine`, which this branch deletes) to `uv run python -m matching_engine`
    — EXC-007's review (F2) found `run-gateway`/`run-account`/`run-market-data` all broken this
    same way and only caught it at review time; fixing it in-plan here avoids repeating that.
12. **`justfile`/CI restructuring (design decision 4) is out of scope** — EXC-014, gated on
    every `EXC-005`–`EXC-012` landing first.

### Tasks

#### Task 1 — Move the source tree
```
mkdir -p platform/matching_engine/src
git mv services/matching_engine platform/matching_engine/src/matching_engine
```

#### Task 2 — Scaffold `platform/matching_engine/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "matching_engine"
version = "0.0.1"
description = "Matching Engine — order book, price-time priority matching, trade outbox"
requires-python = ">=3.11"
dependencies = [
    "base",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
]

[tool.uv.sources]
base = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/matching_engine"]
```

#### Task 3 — Rewrite internal imports
```
grep -rl 'services\.matching_engine' platform/matching_engine/src \
  | xargs sed -i '' -e 's/services\.matching_engine/matching_engine/g'
```
Covers `__main__.py`, `app.py`, `matching.py`, `order_book.py`, `outbox_relay.py`,
`outbox_repo.py`, `tests/test_engine.py`. Verify: `grep -rn "services\.matching_engine"
platform/matching_engine/src` — expect no output. Also run `grep -rn "services\.matching_engine"
services scripts platform clients infra --include='*.py' --include='*.yml'` (repo-wide, not just
the moved tree) to catch any sibling consumer this move breaks — expect no output (none is known
to exist; this is the same class of miss that broke `justfile`'s `run-*` recipes in EXC-005/006/007).

#### Task 4 — Update the root workspace and sibling Dockerfiles
In root `pyproject.toml`:
- `[tool.uv.workspace].members`: add `"platform/matching_engine"`.
- `[project.dependencies]`: add `"matching_engine"`, and `[tool.uv.sources]`: add
  `matching_engine = { workspace = true }`.
- `[tool.coverage.run].source`: add `"platform/matching_engine/src"`.
- `testpaths` already includes `"platform"` — no change needed.

For every file matched by `ls platform/*/Dockerfile | grep -v platform/matching_engine/Dockerfile`
(decision 10): add `COPY platform/matching_engine/pyproject.toml
./platform/matching_engine/pyproject.toml` in its builder stage, alongside the existing sibling
`COPY .../pyproject.toml` lines.

#### Task 5 — `matching_engine/tables.py` and `app.py`: schema-qualify, drop create-on-boot
- `metadata = MetaData()` → `metadata = MetaData(schema='matching_engine')`.
- Delete the `ensure_tables()` function and its `from base.db.tables import ensure_tables as
  _ensure_tables` import.
- In `platform/matching_engine/src/matching_engine/app.py`'s lifespan: delete the
  (post-Task-3-rewrite) `from matching_engine.tables import ensure_tables` import and the
  `await ensure_tables(_state.db)` call.

#### Task 6 — Scaffold Alembic under `platform/matching_engine/`
```
cd platform/matching_engine
alembic init -t generic migrations
```
Then:
- Replace the generated `migrations/env.py` with:
```python
import os
from logging.config import fileConfig

from alembic import context

from matching_engine.tables import metadata as target_metadata
from base.db.migrations import run_migrations_online

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if context.is_offline_mode():
    context.configure(
        url=os.environ['DATABASE_URL'],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        version_table_schema=target_metadata.schema,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online(target_metadata)
```
- In the generated `alembic.ini`: comment out the default `sqlalchemy.url = driver://...` line
  and add a one-line comment that the DSN is intentionally not set here — `env.py` sources it
  from `DATABASE_URL` via `base.db.connection.get_engine()`.
- Leave `script_location` and the generated `migrations/script.py.mako` untouched.

#### Task 7 — Write the initial migration
```
alembic revision -m "create matching_engine schema"
```
Edit the generated `migrations/versions/<rev>_create_matching_engine_schema.py`:
```python
def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS matching_engine')
    op.create_table(
        'outbox',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('destination', sa.String(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='matching_engine',
    )


def downgrade() -> None:
    # Not dropping the matching_engine schema itself: alembic's own version
    # table (version_table_schema="matching_engine") lives in it.
    op.drop_table('outbox', schema='matching_engine')
```

#### Task 8 — Write `platform/matching_engine/Dockerfile` (two-stage + Alembic files)
Same shape as `platform/account/Dockerfile` (builder: `uv sync --locked --no-dev --no-editable
--package matching_engine`; runtime: distroless, copies `src/matching_engine` → `./matching_engine`,
`migrations/`, `alembic.ini`), plus the sibling `COPY .../pyproject.toml` lines for every
*other* current workspace member (mirror decision 10's discovery, in reverse — this Dockerfile
needs one `COPY` stub per sibling too). `EXPOSE 8003`. `CMD ["-m", "matching_engine"]`.

#### Task 9 — Wire compose: repoint `matching-engine`, add `matching-engine-migrate`
In `infra/docker/compose.services.yml`, `matching-engine` service block:
- `build.dockerfile`: `infra/docker/Dockerfile` → `platform/matching_engine/Dockerfile`.
- `command`: `python -m services.matching_engine` → `python -m matching_engine`.
- `depends_on`: **keep** `order-management: condition: service_healthy` and **add**
  `matching-engine-migrate: condition: service_completed_successfully`.

Add a new `matching-engine-migrate` service block (no `depends_on:` — decision 4):
```yaml
  matching-engine-migrate:
    build:
      context: ../..
      dockerfile: platform/matching_engine/Dockerfile
    command: ["-m", "alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: postgresql+asyncpg://exchange:exchange@postgres:5432/exchange
```

#### Task 10 — Fix `justfile`'s `run-matching` recipe
`uv run python -m services.matching_engine` → `uv run python -m matching_engine` (decision 11).

#### Task 11 — Versioning artifacts
Create `platform/matching_engine/CHANGELOG.md` (Keep a Changelog format), `PACKAGING.md`
(hatchling, `src/`-layout, flat `matching_engine` import name, own Alembic history applied by
`matching-engine-migrate`), and `RELEASING.md` (bump version, changelog entry, tag
`matching_engine-vX.Y.Z`) — same shape as `platform/account/`'s three files (EXC-007).

### Acceptance test

From the repo root, on
`feat/EXC-008-migrate-services-matching-engine-into-platform-matching-engine-package-with-own-alembic-history`:
```
cd platform/matching_engine && alembic history && cd -
# expect: one revision, "create matching_engine schema" (<base> -> <rev> (head))

uv sync --extra dev
uv run python -c "import matching_engine.app, matching_engine.matching, matching_engine.order_book, matching_engine.outbox_repo, matching_engine.outbox_relay"
just check
just test
for df in platform/*/Dockerfile; do
  pkg=$(basename "$(dirname "$df")")
  docker build -f "$df" -t "exchange-${pkg//_/-}:test" .
done
just services-build
grep -rn "services\.matching_engine" services scripts platform clients infra --include='*.py' --include='*.yml'
test ! -d services/matching_engine
```
Then a real migration run against the docker-compose Postgres:
```
docker-compose -f infra/docker/compose.infra.yml up -d postgres
DATABASE_URL=postgresql+asyncpg://exchange:exchange@localhost:5432/exchange \
  uv run --project platform/matching_engine alembic -c platform/matching_engine/alembic.ini upgrade head
psql postgresql://exchange:exchange@localhost:5432/exchange -c "\dt matching_engine.*"
```
Expect: `alembic history` shows exactly one revision; imports clean; `just check` (lint +
fmt-check — not just `just lint`, per `development/review-addendum.md` step 2 item 3) clean;
`just test` passes with no drop in collected test count vs `main`; every `platform/*/Dockerfile`
builds, including the ones edited by Task 4's sibling stubs; `just services-build` now succeeds
outright (decision 9); the `grep` prints nothing; `services/matching_engine` is gone; `alembic
upgrade head` creates the `matching_engine` schema with `outbox` plus
`matching_engine.alembic_version`.

### Docs update (mandatory when user-facing)

- `README.md`: in the "Project Structure" tree, replace the `services/matching_engine` line
  with `platform/matching_engine/`.
- `development/design.md`: fix stale `services/matching_engine` / `services\.matching_engine`
  references picked up by `grep -n "services/matching_engine\|services\.matching_engine"
  development/design.md` — currently lines 21 (`services/matching_engine  → order book + ...`),
  362 (`### Outbox event relay (`services/matching_engine/`)`), and 447 (which also names a
  nonexistent `services/matching_engine/engine.py` — the class is in `order_book.py`; correct
  the filename too while repointing the path, since Task touches this exact line anyway).
- `development/review-addendum.md` step 3 item 3: repoint `services/matching_engine/
  order_book.py (246)` to `platform/matching_engine/src/matching_engine/order_book.py (246)` —
  line count unchanged, path stale after the move. Bump the revision history with a new entry.

### Finish (mandatory)

1. Acceptance test green; `just check`/`just test` clean; every `platform/*/Dockerfile` builds;
   `just services-build` passes; a live `alembic upgrade head` creates the `matching_engine`
   schema and its `outbox` table.
2. Docs updated per above (`README.md`, `development/design.md`, `development/review-addendum.md`).
3. Write a summary: files moved (including `tests/`), imports rewritten, Alembic scaffold +
   initial migration added, `tables.py` schema-qualified and `ensure_tables()`/its call removed,
   new Dockerfile + `matching-engine-migrate` compose wiring (no `depends_on: postgres`, per the
   EXC-016 convention), sibling-Dockerfile `COPY` stub updates, `justfile`'s `run-matching`
   fix, versioning docs.
4. Suggested commit message:
   ```
   feat: migrate services/matching_engine into platform/matching_engine package with own Alembic history (EXC-008)

   Move matching_engine to its own installable platform/matching_engine
   package with a two-stage Dockerfile, its own Alembic migration history
   gating startup via a new matching-engine-migrate one-shot container,
   and updated compose and workspace wiring.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-008 in-review --reason "acceptance green"` and hand back.

## Review

- [x] Reviewer independence settled (step 0): **independent** — this reviewing session has no
  hand in the `feat/EXC-008-...` branch (fresh session, first action was this review); no
  delegation needed.
- [x] Implementation audit — acceptance test re-run, tasks & criteria verified (steps 1, 2)
- [x] Quality audit (step 3)
- [x] Consistency audit (step 4)
- [x] Documentation audit — coverage, whole-tree sweep; no docs build configured for this
  project (step 4a)
- [x] Docs-readability pass — **conscious skip**: no docs-readability reviewer configured in
  this host session (step 4b)
- [x] Findings recorded with severity, class, disposition; disposition summary + cost line (step 5)
- [x] Ticket moved (step 6)
- [x] Other references updated; governing documents reconciled (step 7)
- [x] Remaining-tickets impact sweep done (step 8)
- [x] Summary + commit message & MR attributes presented for approval (step 9)

**Implementation audit.** Re-ran the full acceptance test on
`feat/EXC-008-migrate-services-matching-engine-into-platform-matching-engine-package-with-own-alembic-history`
(commit `7a4cff7`, plus a review fixup `16126f7` — see F1 below):
- `alembic history` (via `uv run --project platform/matching_engine`): exactly one revision,
  `<base> -> eb6552474e2f (head), create matching_engine schema`. Met.
- `uv sync --extra dev` + import check
  (`matching_engine.app/.matching/.order_book/.outbox_repo/.outbox_relay`): clean, no output. Met.
- `just check` (ruff check + ruff format --check): both clean. Met.
- `just test`: 66 passed, including the moved `matching_engine` suite (10 tests) at its new
  path; no drop vs. the pre-move suite. Met.
- `platform/*/Dockerfile` builds (account, gateway, market_data, matching_engine): all build
  clean. Met.
- `just services-build`: succeeds outright (decision 9) — all 10 images built. Met.
- Repo-wide `grep -rn "services\.matching_engine" services scripts platform clients infra
  --include='*.py' --include='*.yml'`: no output. `services/matching_engine` directory: gone.
  Met.
- Live migration: started an isolated Postgres 18 container, ran
  `alembic -c platform/matching_engine/alembic.ini upgrade head` against it with `DATABASE_URL`
  pointed at it — `matching_engine.outbox` and `matching_engine.alembic_version` both created
  (`\dt matching_engine.*`). Met.
- All 12 confirmed design decisions verified against the diff: package name/layout (1), `alembic`
  transitive-only (2), Dockerfile shape + migration files copied (3), `matching-engine-migrate`
  compose block has no `depends_on: postgres`, mirrors `account-migrate` (4), `tables.py`
  schema-qualified (5), `ensure_tables()` and its call deleted from `tables.py`/`app.py` (6),
  initial migration handwritten, matches the plan's SQL verbatim (7), `EVENT_DESTINATIONS` /
  `DESTINATION_URLS` / `ENDPOINT_FOR_EVENT_TYPE` untouched (8), `just services-build` green (9),
  all three sibling Dockerfiles (`account`, `gateway`, `market_data`) got the new `COPY` stub (10),
  `justfile`'s `run-matching` fixed (11), no `justfile`/CI restructuring attempted (12).

**Quality audit.** Code is idiomatic and matches the sibling `platform/account`/`platform/gateway`
shape. Test coverage unchanged (file moved verbatim, only import paths rewritten). No blocking
call introduced. `EVENT_DESTINATIONS`/`ENDPOINT_FOR_EVENT_TYPE` both wired for the three event
types (addendum step 2 item 1) — this branch didn't add or rename an event, so the check is
moot, but verified anyway. No new file exceeds 200 lines; `order_book.py` (246, pre-existing
overage) was moved, not grown.

**Consistency audit.** Searched project-wide for `services.matching_engine` / `services/
matching_engine` (see grep above, and doc grep below) — one stale reference found (F1).
`outbox_relay.py`'s destination strings correctly left as HTTP routing keys, not import paths.

**Documentation audit.** `README.md` and `development/design.md` updated per the plan
(`services/matching_engine` line removed from the tree, `platform/matching_engine/` entry
added with correct description; the outbox-relay section header and the Limit Order Book table's
`order_book.py` path both repointed; the stale `engine.py` filename corrected to
`order_book.py`). Whole-tree grep for `matching_engine`/`matching-engine` across
`development/design.md`, `README.md`, `development/review-addendum.md` found one item this branch
missed (F1) and one pre-existing item unrelated to this branch (F2). No docs build is configured
for this project (addendum step 1).

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | non-blocking | stale-xref | fixed inline | `development/review-addendum.md` step 2 item 1's outbox-maps parenthetical still said `services/matching_engine/outbox_relay.py`, made false by this branch's move to `platform/matching_engine/` | `development/review-addendum.md:38` (pre-fix) | repointed to `platform/matching_engine/src/matching_engine/outbox_relay.py` |
| F2 | non-blocking | stale-xref | noted | Same parenthetical's `services/account/outbox_relay.py` entry is also stale (account moved to `platform/account/` in EXC-007) — pre-existing, not this branch's causation, so left as-is per the inline-fix bar | `development/review-addendum.md:38` | a future ticket/review repoints it when next touching this file; too small on its own to promote |

Disposition summary: 1 fixed inline (F1), 1 noted (F2). No findings folded or spawned as new
tickets — nothing here clears the promotion test on its own.

cost: estimated M, actual M

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-17 — TO DO → READY: plan complete
- 2026-09-17 — READY → IN DEVELOPMENT: picked up
- 2026-09-17 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-09-17 — IN REVIEW → DONE: review clean — 1 fixed inline (F1), 1 noted (F2), no blocking findings
