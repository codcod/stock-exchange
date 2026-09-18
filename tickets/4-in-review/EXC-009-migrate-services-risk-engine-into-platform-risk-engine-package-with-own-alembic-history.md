---
id: EXC-009
title: Migrate services/risk_engine into platform/risk_engine package with own Alembic history
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-009 — Migrate services/risk_engine into platform/risk_engine package with own Alembic history

## Outcome

After this ships, `platform/risk_engine/` is its own installable package (own `pyproject.toml`,
version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on `platform/base/`, with
its own two-stage Dockerfile and its own independent Alembic migration history gating its startup
— instead of a subtree of the single flat install sharing the create-on-boot bootstrap.

## Description

`EXC-003 decisions 1, 2, 3, 5`. `risk_engine` is stateful (`DATABASE_URL`, schema-per-service
already in code). Scope: move `services/risk_engine/` to `platform/risk_engine/src/risk_engine/`,
give it its own `pyproject.toml` (hatchling, `src/` layout, depends on `platform/base/`), own
two-stage Dockerfile, own versioning artifacts starting at `0.0.1`, and its own Alembic migration
history scoped to its Postgres schema, replacing its share of the create-on-boot bootstrap with a
`risk_engine-migrate` one-shot compose container gating startup. Depends on EXC-004
(`platform/base/` must exist first).

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-009-migrate-services-risk-engine-into-platform-risk-engine-package-with-own-alembic-history
```

Work and commit locally per the project's commit policy (`exchange` is a root-path child —
tidy WIP commits into atomic ones before presenting; no push/MR without explicit user
approval).

### Prerequisite gate (hard)

EXC-004 must be `6-done/` and merged. It is: `PR #19`, `bb4e5cd`, merged to `main`
(`tickets/BOARD.md` DONE table). `platform/base/` exists with package name `base`, and already
carries `platform/base/src/base/db/migrations.py` (added by EXC-007) — the shared async
`run_migrations_online(target_metadata)` helper. This ticket reuses it **unchanged**.

### Confirmed design decisions (do not deviate without asking)

1. **`platform/risk_engine/`'s importable package name is `risk_engine`, flat** —
   `platform/risk_engine/src/risk_engine/{__init__.py,__main__.py,app.py,checks.py,engine.py,
   repository.py,tables.py,tests/}`, matching every other `platform/<service>/` package.
2. **`alembic` stays a transitive dependency via `platform/base`** — no direct entry in
   `platform/risk_engine/pyproject.toml`.
3. **Own two-stage Dockerfile**, same shape as EXC-005–EXC-008's, plus `alembic.ini` and
   `migrations/` copied into the runtime stage. `ENTRYPOINT` stays plain `python`.
4. **A new `risk-engine-migrate` one-shot compose service — with no `depends_on: postgres`
   entry**, per the EXC-016 convention (verify against the current `account-migrate` block,
   which already carries no `depends_on:` — merged after EXC-007's plan was written). The
   Postgres-health gate is `just infra-up --wait`, not a compose `depends_on`.
   `risk-engine`'s own `depends_on` **keeps** its existing `account: condition: service_healthy`
   entry (it warms an account cache on boot — unrelated to migrations) and **adds**
   `risk-engine-migrate: condition: service_completed_successfully` alongside it.
5. **`risk_engine/tables.py`'s `MetaData` is schema-qualified**: `metadata = MetaData()` →
   `metadata = MetaData(schema='risk_engine')`.
6. **`risk_engine/tables.py`'s `ensure_tables()` wrapper is deleted**, along with its import,
   and `app.py`'s lifespan drops the `await ensure_tables(db)` call. `order_management`,
   `clearing`, `notifications` still call the shared `base.db.tables.ensure_tables()` until
   EXC-010–EXC-012 land.
7. **The initial migration is handwritten**: one revision doing `CREATE SCHEMA IF NOT EXISTS
   risk_engine` plus creating the single `instruments` table verbatim from `tables.py`.
8. **A genuine cross-service Python import breaks the moment this ticket lands, regardless of
   whether EXC-010 has landed yet: `services/order_management/tests/test_service.py:16` has
   `from services.risk_engine.engine import RiskResult`** (a fake-double type import, not an
   HTTP call). This ticket's own Task 3 import-rewrite is scoped to
   `platform/risk_engine/src` and would never touch a file outside that tree, so it must be
   fixed as its own task here — repoint that one line to `from risk_engine.engine import
   RiskResult` (flat; `risk_engine` becomes a root workspace dependency in Task 4, so the flat
   import resolves whether or not `order_management` itself has moved to `platform/` yet).
   This is the same class of miss as EXC-007's F2 finding (a sibling consumer of a moved
   module, caught only at review time) — fixing it in-plan here instead. If EXC-010 has
   *already* landed by the time this ticket is implemented, the file will be at
   `platform/order_management/src/order_management/tests/test_service.py` instead — locate it
   with `grep -rl "services\.risk_engine" services platform` rather than assuming the path.
9. **`just services-build` is now expected to pass outright** (EXC-016 merged) — treat any
   failure as a real regression.
10. **Every sibling `platform/*/Dockerfile` needs a `COPY platform/risk_engine/pyproject.toml
    ./platform/risk_engine/pyproject.toml` stub** — discover the current list with
    `ls platform/*/Dockerfile | grep -v platform/risk_engine/Dockerfile` at implementation
    time, not a hardcoded list (EXC-008/EXC-010–EXC-012 carry no `depends-on:` on each other, so
    landing order is not fixed).
11. **Also fix `justfile`'s `run-risk` recipe** (currently `uv run python -m
    services.risk_engine`) to `uv run python -m risk_engine`.
12. **`justfile`/CI restructuring (design decision 4) is out of scope** — EXC-014.

### Tasks

#### Task 1 — Move the source tree
```
mkdir -p platform/risk_engine/src
git mv services/risk_engine platform/risk_engine/src/risk_engine
```

#### Task 2 — Scaffold `platform/risk_engine/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "risk_engine"
version = "0.0.1"
description = "Risk Engine — pre-trade checks against instrument and account limits"
requires-python = ">=3.11"
dependencies = [
    "base",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
]

[tool.uv.sources]
base = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/risk_engine"]
```

#### Task 3 — Rewrite internal imports
```
grep -rl 'services\.risk_engine' platform/risk_engine/src \
  | xargs sed -i '' -e 's/services\.risk_engine/risk_engine/g'
```
Covers `__main__.py`, `app.py`, `checks.py`, `engine.py`, `repository.py`,
`tests/test_engine.py`. Verify: `grep -rn "services\.risk_engine" platform/risk_engine/src` —
expect no output.

#### Task 4 — Fix the cross-service test import (decision 8)
```
grep -rl 'services\.risk_engine' services platform --include='*.py'
```
Repoint the one match (`.../order_management/tests/test_service.py`)'s `from
services.risk_engine.engine import RiskResult` → `from risk_engine.engine import RiskResult`.
Verify: the same grep now returns nothing outside this ticket's own moved tree.

#### Task 5 — Update the root workspace and sibling Dockerfiles
In root `pyproject.toml`:
- `[tool.uv.workspace].members`: add `"platform/risk_engine"`.
- `[project.dependencies]`: add `"risk_engine"`, and `[tool.uv.sources]`: add
  `risk_engine = { workspace = true }` — this is also what makes Task 4's flat `risk_engine`
  import resolve.
- `[tool.coverage.run].source`: add `"platform/risk_engine/src"`.

For every file matched by `ls platform/*/Dockerfile | grep -v platform/risk_engine/Dockerfile`
(decision 10): add `COPY platform/risk_engine/pyproject.toml
./platform/risk_engine/pyproject.toml` in its builder stage.

#### Task 6 — `risk_engine/tables.py` and `app.py`: schema-qualify, drop create-on-boot
- `metadata = MetaData()` → `metadata = MetaData(schema='risk_engine')`.
- Delete the `ensure_tables()` function and its import.
- In `platform/risk_engine/src/risk_engine/app.py`'s lifespan: delete the (post-Task-3-rewrite)
  `from risk_engine.tables import ensure_tables` import and the `await ensure_tables(db)` call.

#### Task 7 — Scaffold Alembic under `platform/risk_engine/`
```
cd platform/risk_engine
alembic init -t generic migrations
```
Then replace `migrations/env.py` (same shape as EXC-007/EXC-008's, importing
`from risk_engine.tables import metadata as target_metadata` and
`from base.db.migrations import run_migrations_online`) and comment out `alembic.ini`'s default
`sqlalchemy.url` line with a note that `env.py` sources the DSN from `DATABASE_URL`.

#### Task 8 — Write the initial migration
```
alembic revision -m "create risk_engine schema"
```
Edit the generated `migrations/versions/<rev>_create_risk_engine_schema.py`:
```python
def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS risk_engine')
    op.create_table(
        'instruments',
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('lot_size', sa.Integer(), nullable=False),
        sa.Column('max_order_size', sa.Integer(), nullable=False),
        sa.Column('is_tradeable', sa.Boolean(), nullable=False),
        sa.Column('last_price', sa.Numeric(18, 6), nullable=True),
        sa.PrimaryKeyConstraint('ticker'),
        schema='risk_engine',
    )


def downgrade() -> None:
    op.drop_table('instruments', schema='risk_engine')
```

#### Task 9 — Write `platform/risk_engine/Dockerfile` (two-stage + Alembic files)
Same shape as `platform/account/Dockerfile`; builder installs `--package risk_engine`; runtime
copies `src/risk_engine` → `./risk_engine`, `migrations/`, `alembic.ini`; sibling `COPY
.../pyproject.toml` lines for every other current workspace member. `EXPOSE 8002`.
`CMD ["-m", "risk_engine"]`.

#### Task 10 — Wire compose: repoint `risk-engine`, add `risk-engine-migrate`
In `infra/docker/compose.services.yml`, `risk-engine` service block:
- `build.dockerfile`: `infra/docker/Dockerfile` → `platform/risk_engine/Dockerfile`.
- `command`: `python -m services.risk_engine` → `python -m risk_engine`.
- `depends_on`: **keep** `account: condition: service_healthy` and **add**
  `risk-engine-migrate: condition: service_completed_successfully`.

Add a new `risk-engine-migrate` service block (no `depends_on:`):
```yaml
  risk-engine-migrate:
    build:
      context: ../..
      dockerfile: platform/risk_engine/Dockerfile
    command: ["-m", "alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: postgresql+asyncpg://exchange:exchange@postgres:5432/exchange
```

#### Task 11 — Fix `justfile`'s `run-risk` recipe
`uv run python -m services.risk_engine` → `uv run python -m risk_engine` (decision 11).

#### Task 12 — Versioning artifacts
Create `platform/risk_engine/CHANGELOG.md`, `PACKAGING.md`, `RELEASING.md` — same shape as
`platform/account/`'s three files.

### Acceptance test

From the repo root, on
`feat/EXC-009-migrate-services-risk-engine-into-platform-risk-engine-package-with-own-alembic-history`:
```
cd platform/risk_engine && alembic history && cd -
# expect: one revision, "create risk_engine schema" (<base> -> <rev> (head))

uv sync --extra dev
uv run python -c "import risk_engine.app, risk_engine.checks, risk_engine.engine, risk_engine.repository"
just check
just test
for df in platform/*/Dockerfile; do
  pkg=$(basename "$(dirname "$df")")
  docker build -f "$df" -t "exchange-${pkg//_/-}:test" .
done
just services-build
grep -rn "services\.risk_engine" services scripts platform clients infra --include='*.py' --include='*.yml'
test ! -d services/risk_engine
```
Then a real migration run:
```
docker-compose -f infra/docker/compose.infra.yml up -d postgres
DATABASE_URL=postgresql+asyncpg://exchange:exchange@localhost:5432/exchange \
  uv run --project platform/risk_engine alembic -c platform/risk_engine/alembic.ini upgrade head
psql postgresql://exchange:exchange@localhost:5432/exchange -c "\dt risk_engine.*"
```
Expect: `alembic history` one revision; imports clean, **including** the fixed cross-service
import at `.../order_management/tests/test_service.py` (run `just test` from repo root so
`order_management`'s tests collect and confirm it resolves — do not treat this file's tests as
out of scope just because they live in a sibling service); `just check` clean; `just test`
passes with no drop in collected count; every `platform/*/Dockerfile` builds; `just
services-build` succeeds; the `grep` prints nothing; `services/risk_engine` gone; live `alembic
upgrade head` creates `risk_engine` schema with `instruments` + `risk_engine.alembic_version`.

### Docs update (mandatory when user-facing)

- `README.md`: in the "Project Structure" tree, replace the `services/risk_engine` line with
  `platform/risk_engine/`.
- `development/design.md`: fix stale references picked up by `grep -n
  "services/risk_engine\|services\.risk_engine" development/design.md` — currently line 19
  (`services/risk_engine   → pre-trade checks ...`).

### Finish (mandatory)

1. Acceptance test green; `just check`/`just test` clean; every `platform/*/Dockerfile` builds;
   `just services-build` passes; a live `alembic upgrade head` creates the `risk_engine` schema
   and its `instruments` table; the `order_management` test-suite cross-import fix (decision 8)
   verified resolving.
2. Docs updated per above.
3. Write a summary: files moved, imports rewritten (including the cross-service fix outside the
   moved tree), Alembic scaffold + initial migration, `tables.py` schema-qualified and
   `ensure_tables()`/its call removed, new Dockerfile + `risk-engine-migrate` compose wiring (no
   `depends_on: postgres`), sibling-Dockerfile stub updates, `justfile`'s `run-risk` fix,
   versioning docs.
4. Suggested commit message:
   ```
   feat: migrate services/risk_engine into platform/risk_engine package with own Alembic history (EXC-009)

   Move risk_engine to its own installable platform/risk_engine package
   with a two-stage Dockerfile, its own Alembic migration history gating
   startup via a new risk-engine-migrate one-shot container, and updated
   compose and workspace wiring. Also repoints order_management's test
   double import, which named services.risk_engine directly.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-009 in-review --reason "acceptance green"` and hand back.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-17 — TO DO → READY: plan complete
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
- 2026-09-18 — IN DEVELOPMENT → IN REVIEW: acceptance green
