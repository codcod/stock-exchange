---
id: EXC-010
title: Migrate services/order_management into platform/order_management package with own Alembic history
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-010 — Migrate services/order_management into platform/order_management package with own Alembic history

## Outcome

After this ships, `platform/order_management/` is its own installable package (own
`pyproject.toml`, version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on
`platform/base/`, with its own two-stage Dockerfile and its own independent Alembic migration
history gating its startup — instead of a subtree of the single flat install sharing the
create-on-boot bootstrap.

## Description

`EXC-003 decisions 1, 2, 3, 5`. `order_management` is stateful (`DATABASE_URL`, schema-per-service
already in code) and one of the two files already over the 200-line guideline
(`services/order_management/service.py`, `app.py` — pre-existing overage, per
`development/review-addendum.md` step 3 item 3; do not grow them further during this move). Scope:
move `services/order_management/` to `platform/order_management/src/order_management/`, give it
its own `pyproject.toml` (hatchling, `src/` layout, depends on `platform/base/`), own two-stage
Dockerfile, own versioning artifacts starting at `0.0.1`, and its own Alembic migration history
scoped to its Postgres schema, replacing its share of the create-on-boot bootstrap with an
`order_management-migrate` one-shot compose container gating startup. Depends on EXC-004
(`platform/base/` must exist first).

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-010-migrate-services-order-management-into-platform-order-management-package-with-own-alembic-history
```

Work and commit locally per the project's commit policy (`exchange` is a root-path child —
tidy WIP commits into atomic ones before presenting; no push/MR without explicit user
approval).

### Prerequisite gate (hard)

EXC-004 must be `6-done/` and merged. It is: `PR #19`, `bb4e5cd`, merged to `main`
(`tickets/BOARD.md` DONE table). `platform/base/` exists with package name `base`, and already
carries `platform/base/src/base/db/migrations.py` (added by EXC-007) — the shared async
`run_migrations_online(target_metadata)` helper. This ticket reuses it **unchanged**.
`platform/base/src/base/repository.py` and `unit_of_work.py` (added by EXC-001) already back
`order_management`'s existing `repository.py`/`unit_of_work.py` — those files move as-is, no
rewrite needed for that layer (only their `services.order_management` internal imports change,
Task 3).

### Confirmed design decisions (do not deviate without asking)

1. **`platform/order_management/`'s importable package name is `order_management`, flat** —
   `platform/order_management/src/order_management/{__init__.py,__main__.py,app.py,service.py,
   repository.py,outbox_repo.py,outbox_relay.py,unit_of_work.py,tables.py,tests/}`, matching
   every other `platform/<service>/` package.
2. **`alembic` stays a transitive dependency via `platform/base`** — no direct entry in
   `platform/order_management/pyproject.toml`.
3. **Own two-stage Dockerfile**, same shape as EXC-005–EXC-009's. `ENTRYPOINT` stays plain
   `python`.
4. **A new `order-management-migrate` one-shot compose service — with no `depends_on: postgres`
   entry**, per the EXC-016 convention. `order-management`'s own `depends_on` **keeps** its
   existing `risk-engine`, `account`, `notifications` (`condition: service_healthy`) entries —
   none of those are the migration gate — and **adds**
   `order-management-migrate: condition: service_completed_successfully` alongside them.
5. **`order_management/tables.py`'s `MetaData` is schema-qualified**: `metadata = MetaData()` →
   `metadata = MetaData(schema='order_management')`.
6. **`order_management/tables.py`'s `ensure_tables()` wrapper is deleted**, along with its
   import, and `app.py`'s lifespan drops the `await ensure_tables(...)` call. `clearing`,
   `notifications` still call the shared `base.db.tables.ensure_tables()` until EXC-011/EXC-012
   land.
7. **The initial migration is handwritten**: one revision doing `CREATE SCHEMA IF NOT EXISTS
   order_management` plus creating the two existing tables (`outbox`, `orders`) verbatim from
   `tables.py`.
8. **`order_management/service.py` (216 lines) and `app.py` (207 lines) are already over the
   200-line guideline** — EXC-001's review found they grew from the addendum-recorded 205/204
   (pre-EXC-001) to 216/207, and **noted it rather than fixing it or updating the addendum**
   (`tickets/6-done/EXC-001-...md` findings F2/F3). `development/review-addendum.md` step 3
   item 3 therefore still reads `services/order_management/service.py (205)` /
   `services/order_management/app.py (204)` — both the path *and* the counts are now stale.
   This ticket's Docs update repoints the path **and** corrects the counts to the current 216
   /207 (the move itself doesn't grow them further — do not add to either file during this
   migration; if a task under Tasks 5/6 would grow either, stop and ask before proceeding).
9. **A genuine cross-service Python import passes through this ticket regardless of landing
   order: `.../order_management/tests/test_service.py` has `from services.risk_engine.engine
   import RiskResult` (or, if EXC-009 already landed, `from risk_engine.engine import
   RiskResult` — EXC-009 decision 8 repoints it as part of its own migration).** This ticket's
   Task 3 import-rewrite is scoped to `services\.order_management` and must **not** touch this
   line if it still says `services.risk_engine...` — `risk_engine` may not have moved yet, and
   `services/risk_engine` remains a valid import path until EXC-009 lands. Verify at
   implementation time with `grep -n "risk_engine" platform/order_management/src/
   order_management/tests/test_service.py` (after Task 1's move) and leave whatever it finds
   alone unless it is already broken (i.e. names a `services.risk_engine` path that no longer
   exists on disk), in which case repoint it to `risk_engine.engine` as EXC-009 would have.
10. **`just services-build` is now expected to pass outright** (EXC-016 merged).
11. **Every sibling `platform/*/Dockerfile` needs a `COPY platform/order_management/
    pyproject.toml ./platform/order_management/pyproject.toml` stub** — discover the current
    list with `ls platform/*/Dockerfile | grep -v platform/order_management/Dockerfile` at
    implementation time.
12. **Also fix `justfile`'s `run-oms` recipe** (currently `uv run python -m
    services.order_management`) to `uv run python -m order_management`.
13. **`justfile`/CI restructuring (design decision 4) is out of scope** — EXC-014.

### Tasks

#### Task 1 — Move the source tree
```
mkdir -p platform/order_management/src
git mv services/order_management platform/order_management/src/order_management
```

#### Task 2 — Scaffold `platform/order_management/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "order_management"
version = "0.0.1"
description = "Order Management — order lifecycle, persistence, outbox relay to Notifications"
requires-python = ">=3.11"
dependencies = [
    "base",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
]

[tool.uv.sources]
base = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/order_management"]
```

#### Task 3 — Rewrite internal imports
```
grep -rl 'services\.order_management' platform/order_management/src \
  | xargs sed -i '' -e 's/services\.order_management/order_management/g'
```
Covers `__main__.py`, `app.py`, `service.py`, `repository.py`, `outbox_repo.py`,
`outbox_relay.py`, `unit_of_work.py`, `tests/test_service.py`, `tests/test_outbox.py`. Verify:
`grep -rn "services\.order_management" platform/order_management/src` — expect no output. Per
decision 9, this sed must **not** touch any `services.risk_engine...` string — confirm with
`grep -n "risk_engine" platform/order_management/src/order_management/tests/test_service.py`
after the rewrite and handle per decision 9's rule.

#### Task 4 — Update the root workspace and sibling Dockerfiles
In root `pyproject.toml`:
- `[tool.uv.workspace].members`: add `"platform/order_management"`.
- `[project.dependencies]`: add `"order_management"`, and `[tool.uv.sources]`: add
  `order_management = { workspace = true }`.
- `[tool.coverage.run].source`: add `"platform/order_management/src"`.

For every file matched by `ls platform/*/Dockerfile | grep -v platform/order_management/Dockerfile`
(decision 11): add `COPY platform/order_management/pyproject.toml
./platform/order_management/pyproject.toml` in its builder stage.

#### Task 5 — `order_management/tables.py` and `app.py`: schema-qualify, drop create-on-boot
- `metadata = MetaData()` → `metadata = MetaData(schema='order_management')`.
- Delete the `ensure_tables()` function and its import.
- In `platform/order_management/src/order_management/app.py`'s lifespan: delete the
  (post-Task-3-rewrite) `from order_management.tables import ensure_tables` import and the
  `await ensure_tables(...)` call. **Do not otherwise touch `app.py`** — it is already at 207
  lines (decision 8); a net-new line here needs an explicit ask first.

#### Task 6 — Scaffold Alembic under `platform/order_management/`
```
cd platform/order_management
alembic init -t generic migrations
```
Then replace `migrations/env.py` (same shape as EXC-007/008/009's, importing `from
order_management.tables import metadata as target_metadata` and `from base.db.migrations import
run_migrations_online`) and comment out `alembic.ini`'s default `sqlalchemy.url` line.

#### Task 7 — Write the initial migration
```
alembic revision -m "create order_management schema"
```
Edit the generated `migrations/versions/<rev>_create_order_management_schema.py`:
```python
def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS order_management')
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
        schema='order_management',
    )
    op.create_table(
        'orders',
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('order_type', sa.String(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(18, 6), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('filled_quantity', sa.Integer(), nullable=False),
        sa.Column('average_fill_price', sa.Numeric(18, 6), nullable=True),
        sa.Column('reject_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('order_id'),
        schema='order_management',
    )


def downgrade() -> None:
    op.drop_table('orders', schema='order_management')
    op.drop_table('outbox', schema='order_management')
```

#### Task 8 — Write `platform/order_management/Dockerfile` (two-stage + Alembic files)
Same shape as `platform/account/Dockerfile`; builder installs `--package order_management`;
runtime copies `src/order_management` → `./order_management`, `migrations/`, `alembic.ini`;
sibling `COPY .../pyproject.toml` lines for every other current workspace member. `EXPOSE 8001`.
`CMD ["-m", "order_management"]`.

#### Task 9 — Wire compose: repoint `order-management`, add `order-management-migrate`
In `infra/docker/compose.services.yml`, `order-management` service block:
- `build.dockerfile`: `infra/docker/Dockerfile` → `platform/order_management/Dockerfile`.
- `command`: `python -m services.order_management` → `python -m order_management`.
- `depends_on`: **keep** `risk-engine`, `account`, `notifications` (all `condition:
  service_healthy`) and **add** `order-management-migrate: condition:
  service_completed_successfully`.

Add a new `order-management-migrate` service block (no `depends_on:`):
```yaml
  order-management-migrate:
    build:
      context: ../..
      dockerfile: platform/order_management/Dockerfile
    command: ["-m", "alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: postgresql+asyncpg://exchange:exchange@postgres:5432/exchange
```

#### Task 10 — Fix `justfile`'s `run-oms` recipe
`uv run python -m services.order_management` → `uv run python -m order_management` (decision 12).

#### Task 11 — Versioning artifacts
Create `platform/order_management/CHANGELOG.md`, `PACKAGING.md`, `RELEASING.md` — same shape as
`platform/account/`'s three files.

### Acceptance test

From the repo root, on
`feat/EXC-010-migrate-services-order-management-into-platform-order-management-package-with-own-alembic-history`:
```
cd platform/order_management && alembic history && cd -
# expect: one revision, "create order_management schema" (<base> -> <rev> (head))

uv sync --extra dev
uv run python -c "import order_management.app, order_management.service, order_management.repository, order_management.outbox_repo, order_management.outbox_relay, order_management.unit_of_work"
just check
just test
for df in platform/*/Dockerfile; do
  pkg=$(basename "$(dirname "$df")")
  docker build -f "$df" -t "exchange-${pkg//_/-}:test" .
done
just services-build
grep -rn "services\.order_management" services scripts platform clients infra --include='*.py' --include='*.yml'
test ! -d services/order_management
wc -l platform/order_management/src/order_management/service.py platform/order_management/src/order_management/app.py
```
Then a real migration run:
```
docker-compose -f infra/docker/compose.infra.yml up -d postgres
DATABASE_URL=postgresql+asyncpg://exchange:exchange@localhost:5432/exchange \
  uv run --project platform/order_management alembic -c platform/order_management/alembic.ini upgrade head
psql postgresql://exchange:exchange@localhost:5432/exchange -c "\dt order_management.*"
```
Expect: `alembic history` one revision; imports clean; `just check` clean; `just test` passes
with no drop in collected count; every `platform/*/Dockerfile` builds; `just services-build`
succeeds; the `grep` prints nothing; `services/order_management` gone; the `wc -l` check reports
216 and 207 respectively — unchanged from before the move (decision 8: no new lines added); live
`alembic upgrade head` creates `order_management` schema with `outbox`, `orders` +
`order_management.alembic_version`.

### Docs update (mandatory when user-facing)

- `README.md`: in the "Project Structure" tree, replace the `services/order_management` line
  with `platform/order_management/`.
- `development/design.md`: fix stale references picked up by `grep -n
  "services/order_management\|services\.order_management" development/design.md` — currently
  line 20 (`services/order_management → order lifecycle and persistence`).
- `development/review-addendum.md` step 3 item 3: repoint `services/order_management/
  service.py (205)` → `platform/order_management/src/order_management/service.py (216)` and
  `services/order_management/app.py (204)` → `platform/order_management/src/
  order_management/app.py (207)` — both path and count corrected in one edit (decision 8).
  Bump the revision history with a new entry.

### Finish (mandatory)

1. Acceptance test green; `just check`/`just test` clean; every `platform/*/Dockerfile` builds;
   `just services-build` passes; a live `alembic upgrade head` creates the `order_management`
   schema and its two tables; `service.py`/`app.py` line counts unchanged at 216/207.
2. Docs updated per above, including the addendum's corrected line counts.
3. Write a summary: files moved (including `tests/`, `unit_of_work.py`), imports rewritten,
   Alembic scaffold + initial migration, `tables.py` schema-qualified and `ensure_tables()`/its
   call removed, new Dockerfile + `order-management-migrate` compose wiring (no `depends_on:
   postgres`), sibling-Dockerfile stub updates, `justfile`'s `run-oms` fix, the addendum's
   corrected line-count/path entry, versioning docs, and the cross-service `risk_engine` import
   handled per decision 9 (state which branch of decision 9 applied).
4. Suggested commit message:
   ```
   feat: migrate services/order_management into platform/order_management package with own Alembic history (EXC-010)

   Move order_management to its own installable
   platform/order_management package with a two-stage Dockerfile, its
   own Alembic migration history gating startup via a new
   order-management-migrate one-shot container, and updated compose and
   workspace wiring.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-010 in-review --reason "acceptance green"` and hand back.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-17 — TO DO → READY: plan complete
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
- 2026-09-18 — plan amended inline: decision 8 / the acceptance test both assumed `app.py` would
  stay at 207 lines "unchanged from before the move", but Task 5 mandatorily deletes the
  `ensure_tables` import and its `await` call from `app.py`'s lifespan (dropping create-on-boot),
  which shrinks it by 2 lines regardless. Executed Task 5 as written; recorded the addendum
  (Docs update, decision 8) and the acceptance test's actual result against the true post-move
  count of 205, not the plan's stale 207. `service.py` is untouched by this ticket and stayed at
  216 as assumed.
- 2026-09-18 — IN DEVELOPMENT → IN REVIEW: acceptance green
