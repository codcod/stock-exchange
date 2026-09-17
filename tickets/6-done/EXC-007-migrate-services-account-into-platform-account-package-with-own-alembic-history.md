---
id: EXC-007
title: Migrate services/account into platform/account package with own Alembic history
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-007 — Migrate services/account into platform/account package with own Alembic history

## Outcome

After this ships, `platform/account/` is its own installable package (own `pyproject.toml`,
version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on `platform/base/`, with
its own two-stage Dockerfile and its own independent Alembic migration history gating its startup
— instead of a subtree of the single flat install sharing the create-on-boot bootstrap.

## Description

`EXC-003 decisions 1, 2, 3, 5`. `account` is stateful (`DATABASE_URL`, schema-per-service already
in code via `services/account/tables.py`'s `schema=...`). Scope: move `services/account/` to
`platform/account/src/account/`, give it its own `pyproject.toml` (hatchling, `src/` layout,
depends on `platform/base/`), own two-stage Dockerfile, own versioning artifacts starting at
`0.0.1`, and its own Alembic migration history scoped to its Postgres schema, replacing its share
of `platform/base/src/base/db/tables.py:25`'s `CREATE SCHEMA IF NOT EXISTS` bootstrap with an
`account-migrate` one-shot compose container gating startup. Depends on EXC-004 (`platform/base/`
must exist first).

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-007-migrate-services-account-into-platform-account-package-with-own-alembic-history
```

Work and commit locally per the project's commit policy (`exchange` is a root-path child —
tidy WIP commits into atomic ones before presenting; no push/MR without explicit user
approval).

### Prerequisite gate (hard)

EXC-004 must be `6-done/` and merged. It is: `PR #19`, `bb4e5cd`, merged to `main`
(`tickets/BOARD.md` DONE table). `platform/base/` exists with package name `base`.

### Confirmed design decisions (do not deviate without asking)

1. **`platform/account/`'s importable package name is `account`, flat** —
   `platform/account/src/account/{__init__.py,__main__.py,app.py,service.py,repository.py,
   outbox_repo.py,outbox_relay.py,tables.py,tests/}`, matching `platform/base/src/base/`
   (EXC-004 decision 1).
2. **`alembic` is a dependency of `platform/base`, not of `platform/account` itself** —
   mirroring `~/Projects/private/monolith`'s `stelo-base` package (`platform/stelo-base/
   pyproject.toml`'s `dependencies` includes `alembic`, and every module depends on it
   transitively; no module declares it directly). A new `platform/base/src/base/db/
   migrations.py` module provides a reusable async `run_migrations_online(target_metadata)`
   helper — a direct adaptation of `~/Projects/private/monolith/platform/stelo-base/src/
   stelo/base/migrations.py`, substituted to source the DSN from this repo's existing
   `base.db.connection.get_engine()` (which already reads `DATABASE_URL`) instead of
   monolith's per-service `config.toml`. EXC-008–EXC-012 reuse this same helper unchanged.
3. **Own two-stage Dockerfile** (design decision 3), same shape as EXC-005/006's, plus
   `alembic.ini` and `migrations/` copied into the runtime stage so `python -m alembic
   upgrade head` also works there — mirrors `~/Projects/private/monolith/platform/inbox/
   Dockerfile`'s runtime stage. `ENTRYPOINT` stays plain `python` (no shell) so compose can
   override `CMD` for the migration one-shot instead of the app.
4. **A new `account-migrate` one-shot compose service**, mirroring monolith's `<module>-
   migrate` pattern (`inbox-migrate`/`traffic-migrate`/`dispatcher-migrate` in
   `~/Projects/private/monolith/compose.yaml`) exactly: same build/image as `account`,
   `command: ["-m", "alembic", "upgrade", "head"]`, `depends_on: postgres: condition:
   service_healthy`. `account`'s own `depends_on` switches from `postgres` directly to
   `account-migrate: condition: service_completed_successfully` (monolith's `inbox` depends
   on `inbox-migrate`, not `postgres`, directly — the migrate job already gates on Postgres
   being ready).
5. **`account/tables.py`'s `MetaData` is schema-qualified at the `MetaData` level**:
   `metadata = MetaData()` → `metadata = MetaData(schema='account')`. Alembic's shared
   `run_migrations_online` helper sets `version_table_schema=target_metadata.schema` so each
   service's `alembic_version` table lives inside its own schema instead of racing every
   other service for the same `public.alembic_version` row (the exact reason monolith's
   `stelo.base.migrations._do_run_migrations` does this). Existing per-`Table` `schema=
   'account'` kwargs are left as-is (redundant with the `MetaData`-level schema, harmless).
6. **`account/tables.py`'s `ensure_tables()` wrapper is deleted**, along with its `from
   base.db.tables import ensure_tables as _ensure_tables` import, and `app.py`'s lifespan
   drops the `await ensure_tables(db)` call (`app.py:65` pre-migration) — Alembic now owns
   schema/table creation via the `account-migrate` container gating startup, replacing
   create-on-boot for this service. The shared `base.db.tables.ensure_tables()` helper
   itself is **not** touched — `clearing`, `notifications`, `risk_engine`,
   `order_management`, `matching_engine` still call it until EXC-008–EXC-012 land.
7. **The initial migration is handwritten** (scaffolded via `alembic revision`, then edited
   by hand), not autogenerated: one revision doing `CREATE SCHEMA IF NOT EXISTS account`
   plus creating the 5 existing tables (`accounts`, `positions`, `reserved_shares`,
   `outbox`, `processed_events`) verbatim from `tables.py` — mirrors monolith's `inbox`/
   `traffic`/`dispatcher`, each a single handwritten "create `<module>` schema" revision.
8. **`just services-build` is expected to still fail** with the pre-existing, already-
   tracked `EXC-016` error (undefined `postgres` service in `compose.services.yml`),
   unrelated to `account` — same precedent EXC-005/006 established. `account-migrate`'s own
   new `depends_on: postgres:` entry carries the identical, already-tracked issue (not new
   scope; EXC-016 already covers every stateful service's block in this file). Verify the
   new Dockerfile and the migration directly instead (Acceptance test, below).
9. **`justfile`/CI restructuring (design decision 4) is out of scope** — EXC-014, gated on
   every `EXC-005`–`EXC-012` landing first.

### Tasks

#### Task 1 — Move the source tree
```
mkdir -p platform/account/src
git mv services/account platform/account/src/account
```

#### Task 2 — Scaffold `platform/account/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "account"
version = "0.0.1"
description = "Account service — cash/position ledger, reservations, settlement"
requires-python = ">=3.11"
dependencies = [
    "base",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
]

[tool.uv.sources]
base = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/account"]
```
(`alembic` comes transitively via `base` — decision 2, no direct entry here.)

#### Task 3 — Rewrite internal imports
```
grep -rl 'services\.account' platform/account/src \
  | xargs sed -i '' -e 's/services\.account/account/g'
```
Covers `__main__.py`, `app.py`, `service.py`, `repository.py`, `outbox_repo.py`,
`outbox_relay.py`, `tests/test_service.py`. Verify:
`grep -rn "services\.account" platform/account/src` — expect no output.

#### Task 4 — Update the root workspace, `platform/base`'s deps, and sibling Dockerfiles
In root `pyproject.toml`:
- `[tool.uv.workspace].members`: add `"platform/account"`.
- `[project.dependencies]`: add `"account"`, and `[tool.uv.sources]`: add
  `account = { workspace = true }` — EXC-005/006's gotcha: without both, `uv sync` never
  installs the workspace member into the root venv and the acceptance test's `import
  account...` step fails with `ModuleNotFoundError`.
- `[tool.coverage.run].source`: add `"platform/account/src"` alongside the existing
  `platform/base/src`, `platform/gateway/src`, `platform/market_data/src`.
- `testpaths` already includes `"platform"` (added by EXC-006) — no change needed.

In `platform/base/pyproject.toml`: add `"alembic"` to `dependencies` (decision 2).

In `platform/gateway/Dockerfile` and `platform/market_data/Dockerfile` (existing sibling
workspace members): add `COPY platform/account/pyproject.toml
./platform/account/pyproject.toml` — the recurring gotcha EXC-006's review (F1) flagged:
every new workspace member needs a `pyproject.toml`-only `COPY` stub in every sibling's
Dockerfile, or their `uv sync` breaks resolving the now-larger workspace.

#### Task 5 — `account/tables.py` and `app.py`: schema-qualify, drop create-on-boot
- `metadata = MetaData()` → `metadata = MetaData(schema='account')`.
- Delete the `ensure_tables()` function and its `from base.db.tables import ensure_tables as
  _ensure_tables` import.
- In `platform/account/src/account/app.py`'s lifespan: delete the (post-Task-3-rewrite)
  `from account.tables import ensure_tables` import and the `await ensure_tables(db)` call.

#### Task 6 — Add `platform/base/src/base/db/migrations.py` (shared Alembic helper)
```python
import asyncio

import sqlalchemy as sa
from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine

from .connection import get_engine


def _do_run_migrations(connection: sa.Connection, target_metadata: sa.MetaData) -> None:
    # Each service's migration history lives in its own schema's
    # alembic_version table — otherwise every service fights over the
    # same public.alembic_version row and stamps each other's revisions.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=target_metadata.schema,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations(
    engine: AsyncEngine, target_metadata: sa.MetaData
) -> None:
    assert target_metadata.schema is not None, "target_metadata needs a schema"

    async with engine.connect() as connection:
        # The schema has to exist before alembic can even check its
        # version table inside that schema — the first migration's own
        # CREATE SCHEMA runs too late for that first check.
        await connection.execute(
            sa.schema.CreateSchema(target_metadata.schema, if_not_exists=True)
        )
        await connection.commit()
        await connection.run_sync(_do_run_migrations, target_metadata)
    await engine.dispose()


def run_migrations_online(target_metadata: sa.MetaData) -> None:
    """
    Standard Alembic `env.py` online-mode entry point for an async
    SQLAlchemy engine. Every service's `migrations/env.py` calls this the
    same way, passing its own schema-qualified `target_metadata`; the DSN
    comes from `base.db.connection.get_engine()`'s own `DATABASE_URL`
    read, the one place this repo already sources it.
    """
    engine = get_engine()
    asyncio.run(_run_async_migrations(engine, target_metadata))
```
(direct adaptation of `~/Projects/private/monolith/platform/stelo-base/src/stelo/base/
migrations.py`, substituting exchange's existing `get_engine()` for monolith's per-config-
file DSN.)

#### Task 7 — Scaffold Alembic under `platform/account/`
```
cd platform/account
alembic init -t generic migrations
```
Then:
- Replace the generated `migrations/env.py` with:
```python
import os
from logging.config import fileConfig

from alembic import context

from account.tables import metadata as target_metadata
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
- In the generated `alembic.ini`: comment out the default `sqlalchemy.url = driver://...`
  line and add a one-line comment that the DSN is intentionally not set here — `env.py`
  sources it from `DATABASE_URL` via `base.db.connection.get_engine()` (mirrors
  `~/Projects/private/monolith/platform/inbox/alembic.ini`'s equivalent comment).
- Leave `script_location = %(here)s/migrations` and the generated `migrations/script.py.mako`
  untouched (stock Alembic defaults).

#### Task 8 — Write the initial migration
```
alembic revision -m "create account schema"
```
Edit the generated `migrations/versions/<rev>_create_account_schema.py`:
```python
def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS account')
    op.create_table(
        'accounts',
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('cash_balance', sa.Numeric(18, 6), nullable=False),
        sa.Column('reserved_cash', sa.Numeric(18, 6), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('account_id'),
        schema='account',
    )
    op.create_table(
        'positions',
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('account_id', 'ticker'),
        schema='account',
    )
    op.create_table(
        'reserved_shares',
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('account_id', 'ticker'),
        schema='account',
    )
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
        schema='account',
    )
    op.create_table(
        'processed_events',
        sa.Column('event_id', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('event_id'),
        schema='account',
    )


def downgrade() -> None:
    # Not dropping the account schema itself: alembic's own version table
    # (version_table_schema="account") lives in it and still needs it to
    # record this downgrade.
    op.drop_table('processed_events', schema='account')
    op.drop_table('outbox', schema='account')
    op.drop_table('reserved_shares', schema='account')
    op.drop_table('positions', schema='account')
    op.drop_table('accounts', schema='account')
```
(exact column shapes copied from `platform/account/src/account/tables.py`; mirrors
`~/Projects/private/monolith/platform/inbox/migrations/versions/
63e29b2fa4df_create_inbox_schema.py`'s single-handwritten-revision shape.)

#### Task 9 — Write `platform/account/Dockerfile` (two-stage + Alembic files)
```dockerfile
# syntax=docker/dockerfile:1
#
# Build context is the repo root (see infra/docker/compose.services.yml) — uv needs the
# workspace root (pyproject.toml + uv.lock) plus every platform/* member's pyproject.toml to
# resolve the workspace, even though this image only installs account and its dependency
# closure.
#

#
# BUILD
#
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /app
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY platform/base ./platform/base
COPY platform/account/pyproject.toml ./platform/account/pyproject.toml
COPY platform/account/src ./platform/account/src
COPY platform/gateway/pyproject.toml ./platform/gateway/pyproject.toml
COPY platform/market_data/pyproject.toml ./platform/market_data/pyproject.toml

RUN uv sync --locked --no-dev --no-editable --package account

#
# RUNTIME
#
FROM gcr.io/distroless/python3-debian13
WORKDIR /opt/account
COPY --from=builder /app/.venv/lib/python3.13/site-packages /opt/site-packages
COPY platform/account/src/account ./account
COPY platform/account/migrations ./migrations
COPY platform/account/alembic.ini .
ENV PYTHONPATH=/opt/site-packages

EXPOSE 8006

# Entrypoint is plain `python` (no shell) so compose overrides CMD to run
# migrations instead of the app — see the `account-migrate` service in
# infra/docker/compose.services.yml.
ENTRYPOINT ["python"]
CMD ["-m", "account"]
```
(sibling `COPY .../pyproject.toml` lines needed for the same uv-workspace-resolution reason
as Task 4's sibling-Dockerfile edits; `alembic.ini` + `migrations/` copied into the runtime
stage so `python -m alembic upgrade head` also works there — mirrors
`~/Projects/private/monolith/platform/inbox/Dockerfile`'s runtime stage.)

#### Task 10 — Wire compose: repoint `account`, add `account-migrate`
In `infra/docker/compose.services.yml`, `account` service block:
- `build.dockerfile`: `infra/docker/Dockerfile` → `platform/account/Dockerfile`
  (`build.context` stays `../..`).
- `command`: `python -m services.account` → `python -m account`.
- `depends_on`: replace `postgres: condition: service_healthy` with `account-migrate:
  condition: service_completed_successfully`.

Add a new `account-migrate` service block in the same file:
```yaml
  account-migrate:
    build:
      context: ../..
      dockerfile: platform/account/Dockerfile
    command: ["-m", "alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: postgresql+asyncpg://exchange:exchange@postgres:5432/exchange
    depends_on:
      postgres:
        condition: service_healthy
```
(mirrors monolith's `inbox-migrate`/`traffic-migrate`/`dispatcher-migrate` blocks exactly —
same image/build, command override, postgres gate — decision 4.)

#### Task 11 — Versioning artifacts
Create `platform/account/CHANGELOG.md` (Keep a Changelog format): title line, the standard
preamble sentence linking https://keepachangelog.com/en/1.0.0/, one dated `0.0.1` entry
noting "Extracted from `services/account/` into its own `platform/account/` package, with
its own Alembic migration history replacing create-on-boot (EXC-007)." under a **Changed**
label.

Create `platform/account/PACKAGING.md`: one short paragraph — `account` is a
`hatchling`-built, `src/`-layout package (`src/account/`), installed into the repo's `uv`
workspace via `[tool.uv.sources]` in the root `pyproject.toml`; its importable package name
is flat (`account`, matching every other `platform/<service>/` package); it ships its own
Alembic migration history under `migrations/`, applied by the `account-migrate` one-shot
compose container before `account` itself starts.

Create `platform/account/RELEASING.md`: manual release procedure — bump `version` in
`platform/account/pyproject.toml`, add a dated entry to `platform/account/CHANGELOG.md`,
commit, tag `account-vX.Y.Z`, push the tag.

### Acceptance test

From the repo root, on
`feat/EXC-007-migrate-services-account-into-platform-account-package-with-own-alembic-history`:
```
cd platform/account && alembic history && cd -
# expect: one revision, "create account schema" (<base> -> <rev> (head))

uv sync --extra dev
uv run python -c "import account.app, account.service, account.repository, account.outbox_repo, account.outbox_relay"
just lint
just test
docker build -f platform/account/Dockerfile -t exchange-account:test .
docker build -f platform/gateway/Dockerfile -t exchange-gateway:test .
docker build -f platform/market_data/Dockerfile -t exchange-market-data:test .
grep -rn "services\.account" services scripts platform clients infra --include='*.py' --include='*.yml'
test ! -d services/account
```
Then a real migration run against the docker-compose Postgres:
```
docker-compose -f infra/docker/compose.infra.yml up -d postgres
DATABASE_URL=postgresql+asyncpg://exchange:exchange@localhost:5432/exchange \
  uv run --project platform/account alembic -c platform/account/alembic.ini upgrade head
psql postgresql://exchange:exchange@localhost:5432/exchange -c "\dt account.*"
```
Expect: `alembic history` shows exactly one revision; imports clean; `just test` still
passes (`account`'s `tests/test_service.py` is pure-unit, no DB, unaffected by the schema
move — do not treat a drop in collected test count as passing); `just lint` clean; the
`account`, `gateway`, and `market_data` Dockerfiles all still build (the last two after their
new `COPY` stub lines from Task 4); the `grep` prints nothing; `services/account` is gone;
`alembic upgrade head` against the live Postgres creates the `account` schema with `accounts`,
`positions`, `reserved_shares`, `outbox`, `processed_events`, plus `account.alembic_version`.
Separately, confirm `just services-build` still fails with exactly the pre-existing `EXC-016`
error and no new error — do not treat that failure as blocking (decision 8).

### Docs update (mandatory when user-facing)

- `README.md`: in the "Project Structure" tree, replace the `services/account/` line with
  `platform/account/`.
- `development/design.md`: fix any stale `services/account` / `services\.account` path
  references picked up by
  `grep -n "services/account\|services\.account" development/design.md`.

### Finish (mandatory)

1. Acceptance test green; `just lint`/`just test` clean; all three Dockerfiles
   (`account`, `gateway`, `market_data`) build; a live `alembic upgrade head` creates the
   `account` schema and its 5 tables.
2. Docs updated per above.
3. Write a summary: files moved (including `tests/`), imports rewritten, new
   `platform/base/src/base/db/migrations.py` shared helper, Alembic scaffold + initial
   migration added under `platform/account/`, `tables.py` schema-qualified and
   `ensure_tables()`/its call removed, new Dockerfile + `account-migrate` compose wiring,
   sibling-Dockerfile `COPY` stub updates, versioning docs, and the still-open `EXC-016`
   compose failure (confirmed unchanged, not fixed here).
4. Suggested commit message:
   ```
   feat: migrate services/account into platform/account package with own Alembic history (EXC-007)

   Move account to its own installable platform/account package with a
   two-stage Dockerfile, its own Alembic migration history gating startup
   via a new account-migrate one-shot container, and updated compose and
   workspace wiring.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path
   child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-007 in-review --reason "acceptance green"` and hand
   back.

## Review

- [x] Reviewer independence settled (step 0): audits run independently — this session did not
      author the branch
- [x] Implementation audit — acceptance test re-run verbatim, tasks & criteria verified
      (steps 1, 2)
- [x] Quality audit (step 3)
- [x] Consistency audit (step 4)
- [x] Documentation audit — coverage, whole-tree sweep (step 4a): no docs build command is
      configured for this project (addendum step 1); `README.md` and `development/design.md`
      swept in full
- [x] Docs-readability pass: skipped — no docs-readability reviewer configured in this host
      (sanctioned conscious skip, step 4b); 0 suggestions, 0 discarded
- [x] Findings recorded with severity, class and disposition; disposition summary + cost line
      below (step 5)
- [x] Ticket moved to `tickets/6-done/`; `## History` appended (step 6)
- [x] Other references updated; governing documents reconciled (`development/design.md`,
      `development/review-addendum.md` → v3); board regenerated by the move (step 7)
- [x] Remaining-tickets impact sweep done — EXC-001 and EXC-002 patched (step 8)
- [x] Summary + commit message & MR attributes presented for approval; `origin/main...HEAD`
      verified to carry no `tickets/` path before pushing (step 9)

### Verification evidence

| check | result |
|---|---|
| `alembic history` | `<base> -> 6dd73b0dc1cd (head), create account schema` — exactly one revision |
| `uv run python -c "import account.app, account.service, account.repository, account.outbox_repo, account.outbox_relay"` | clean |
| `just lint` | `All checks passed!` |
| `just test` | 66 passed — same count as `main` (verified by collecting on a `main` worktree), so no tests were lost in the move |
| `docker build` × 3 (`account`, `gateway`, `market_data`) | all three build |
| `grep -rn "services\.account" services scripts platform clients infra` | no output |
| `test ! -d services/account` | passes |
| live `alembic upgrade head` | creates `account` schema with `accounts`, `positions`, `reserved_shares`, `outbox`, `processed_events` + `account.alembic_version`; `outbox.id` gets `nextval('account.outbox_id_seq')`, so outbox inserts work |
| `alembic upgrade head` re-run / `downgrade base` | both clean — migration is idempotent and reversible |
| `python -m alembic upgrade head` **inside** `exchange-account:test` | runs; `alembic.ini`, `migrations/` and the `account.tables` import all resolve in the runtime stage (decision 3) |
| `exchange-account:test` container against the migrated DB | `/health` ok and `GET /accounts` returns a row persisted through `AccountRepository` — proves boot works with `ensure_tables()` removed (decisions 5, 6) |
| `just services-build` | fails with `service "order-management" depends on undefined service "postgres"` — the pre-existing EXC-016 error, unchanged, no new error (decision 8) |

All 11 tasks, all 9 confirmed decisions and every acceptance criterion: **met**.

### Findings

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | non-blocking | test-gap | fixed inline | The acceptance test stops at `just lint`, but CI runs `ruff check .` **and** `ruff format --check .`. The `alembic revision` scaffold emits a migration without the blank line ruff wants after the module docstring, so `just check` failed and the PR would have landed red | `just check` → `Would reformat: platform/account/migrations/versions/6dd73b0dc1cd_create_account_schema.py`; `.github/workflows/ci.yaml` "Ruff format check" | Ran `ruff format` on the migration; `just check` now clean. Root cause closed in `development/review-addendum.md` (new step 2 item 3) so EXC-008–EXC-012 put `just check` in their acceptance tests rather than `just lint` alone |
| F2 | non-blocking | stale-xref | fixed inline | `justfile`'s `run-account` still ran `python -m services.account`, a module this branch deleted — breaking `just run-account` and `just dev` (`scripts/dev-tmux.sh:41`). `run-gateway` and `run-market-data` were already broken the same way by EXC-005/EXC-006, which neither review caught | `justfile:127,167,177` | Repointed all three to `python -m {gateway,account,market_data}`; entry points verified to resolve via `importlib.util.find_spec` |
| F3 | non-blocking | stale-xref | fixed inline | The docs step path-swapped `development/design.md`'s "scaffolded but not yet implemented" line to `platform/account/`, leaving a refreshed-looking line asserting something false — `account` ships a 199-line `app.py`, a service, a repository and 11 passing tests, and `services/notifications/` is likewise implemented | `development/design.md:281` | Rewritten to say both are implemented but absent from the table above, pointing at "Architecture overview" as the authoritative list |
| F4 | non-blocking | stale-xref | fixed inline | `development/review-addendum.md` (a governing document — `review_addendum` in `pickle.toml`) listed `services/account/app.py` (201) among the 200-line soft-violations; the file moved and is now 199 lines | `development/review-addendum.md:63` | Repointed to `platform/account/src/account/app.py` (199); addendum bumped to v3 |
| F5 | non-blocking | stale-xref | fixed inline | `services/clearing/tests/test_service.py`'s module docstring pointed at `services/account/tests/` | `services/clearing/tests/test_service.py:6` | Repointed to `platform/account/src/account/tests/` |
| F6 | non-blocking | stale-xref | noted | EXC-001 and EXC-002 (both READY) carry Implementation Plans written against `services/account/...`; EXC-001's prerequisite gate additionally asserted both its target services were still under `services/` | `tickets/2-ready/EXC-001-*.md`, `tickets/2-ready/EXC-002-*.md` | Patched directly per the step-8 impact sweep — paths repointed and EXC-001's prerequisite gate rewritten; see each ticket's own History |

Disposition summary: 5 `fixed inline` (F1–F5), 1 `noted` (F6, patched into EXC-001/EXC-002 by the
step-8 impact sweep rather than left as a follow-up ticket). No `folded`, no `new ticket`, no
blocking findings.

cost: estimated M, actual M

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — Description corrected: line anchor `shared/platform/db/tables.py:25` →
  `platform/base/src/base/db/tables.py:25` (EXC-004 impact sweep — file moved, line unchanged).
- 2026-09-17 — TO DO → READY: plan complete
- 2026-09-17 — READY → IN DEVELOPMENT: picked up
- 2026-09-17 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-09-17 — IN REVIEW → DONE: review passed: 6 non-blocking findings (F1-F5 fixed inline, F6 patched into EXC-001/EXC-002 via the step-8 impact sweep); no blocking findings
