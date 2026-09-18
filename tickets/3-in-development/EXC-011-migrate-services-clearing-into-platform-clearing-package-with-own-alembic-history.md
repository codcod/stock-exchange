---
id: EXC-011
title: Migrate services/clearing into platform/clearing package with own Alembic history
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-011 — Migrate services/clearing into platform/clearing package with own Alembic history

## Outcome

After this ships, `platform/clearing/` is its own installable package (own `pyproject.toml`,
version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on `platform/base/`, with
its own two-stage Dockerfile and its own independent Alembic migration history gating its startup
— instead of a subtree of the single flat install sharing the create-on-boot bootstrap.

## Description

`EXC-003 decisions 1, 2, 3, 5`. `clearing` is stateful (`DATABASE_URL`, schema-per-service already
in code). Scope: move `services/clearing/` to `platform/clearing/src/clearing/`, give it its own
`pyproject.toml` (hatchling, `src/` layout, depends on `platform/base/`), own two-stage Dockerfile,
own versioning artifacts starting at `0.0.1`, and its own Alembic migration history scoped to its
Postgres schema, replacing its share of the create-on-boot bootstrap with a `clearing-migrate`
one-shot compose container gating startup. Depends on EXC-004 (`platform/base/` must exist
first).

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-011-migrate-services-clearing-into-platform-clearing-package-with-own-alembic-history
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

1. **`platform/clearing/`'s importable package name is `clearing`, flat** —
   `platform/clearing/src/clearing/{__init__.py,__main__.py,app.py,repository.py,service.py,
   tables.py,tests/}`, matching every other `platform/<service>/` package.
2. **`alembic` stays a transitive dependency via `platform/base`** — no direct entry in
   `platform/clearing/pyproject.toml`.
3. **Own two-stage Dockerfile**, same shape as EXC-005–EXC-010's. `ENTRYPOINT` stays plain
   `python`.
4. **A new `clearing-migrate` one-shot compose service — with no `depends_on: postgres`
   entry**, per the EXC-016 convention. `clearing` currently has no `depends_on:` block at all
   (Tier 2, no service dependencies) — this ticket **adds** one: `clearing-migrate: condition:
   service_completed_successfully`.
5. **`clearing/tables.py`'s `MetaData` is schema-qualified**: `metadata = MetaData()` →
   `metadata = MetaData(schema='clearing')`.
6. **`clearing/tables.py`'s `ensure_tables()` wrapper is deleted**, along with its import, and
   `app.py`'s lifespan drops the `await ensure_tables(db)` call. `notifications` still calls the
   shared `base.db.tables.ensure_tables()` until EXC-012 lands.
7. **The initial migration is handwritten**: one revision doing `CREATE SCHEMA IF NOT EXISTS
   clearing` plus creating the single `trades` table verbatim from `tables.py`.
8. **`services/clearing/tests/test_service.py`'s module docstring already points at
   `platform/account/src/account/tests/`** (repointed by EXC-007's review, F5) — leave it as is,
   it needs no further change from this move.
9. **`just services-build` is now expected to pass outright** (EXC-016 merged).
10. **Every sibling `platform/*/Dockerfile` needs a `COPY platform/clearing/pyproject.toml
    ./platform/clearing/pyproject.toml` stub** — discover the current list with
    `ls platform/*/Dockerfile | grep -v platform/clearing/Dockerfile` at implementation time.
11. **Also fix `justfile`'s `run-clearing` recipe** (currently `uv run python -m
    services.clearing`) to `uv run python -m clearing`.
12. **`justfile`/CI restructuring (design decision 4) is out of scope** — EXC-014.

### Tasks

#### Task 1 — Move the source tree
```
mkdir -p platform/clearing/src
git mv services/clearing platform/clearing/src/clearing
```

#### Task 2 — Scaffold `platform/clearing/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "clearing"
version = "0.0.1"
description = "Clearing — post-trade trade-record keeper (audit ledger only)"
requires-python = ">=3.11"
dependencies = [
    "base",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
]

[tool.uv.sources]
base = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/clearing"]
```

#### Task 3 — Rewrite internal imports
```
grep -rl 'services\.clearing' platform/clearing/src \
  | xargs sed -i '' -e 's/services\.clearing/clearing/g'
```
Covers `__main__.py`, `app.py`, `repository.py`, `service.py`, `tests/test_service.py`. Verify:
`grep -rn "services\.clearing" platform/clearing/src` — expect no output. Also run `grep -rn
"services\.clearing" services scripts platform clients infra --include='*.py' --include='*.yml'`
(repo-wide) to catch any sibling consumer — none is known to exist, but confirm.

#### Task 4 — Update the root workspace and sibling Dockerfiles
In root `pyproject.toml`:
- `[tool.uv.workspace].members`: add `"platform/clearing"`.
- `[project.dependencies]`: add `"clearing"`, and `[tool.uv.sources]`: add
  `clearing = { workspace = true }`.
- `[tool.coverage.run].source`: add `"platform/clearing/src"`.

For every file matched by `ls platform/*/Dockerfile | grep -v platform/clearing/Dockerfile`
(decision 10): add `COPY platform/clearing/pyproject.toml ./platform/clearing/pyproject.toml`
in its builder stage.

#### Task 5 — `clearing/tables.py` and `app.py`: schema-qualify, drop create-on-boot
- `metadata = MetaData()` → `metadata = MetaData(schema='clearing')`.
- Delete the `ensure_tables()` function and its import.
- In `platform/clearing/src/clearing/app.py`'s lifespan: delete the (post-Task-3-rewrite) `from
  clearing.tables import ensure_tables` import and the `await ensure_tables(db)` call.

#### Task 6 — Scaffold Alembic under `platform/clearing/`
```
cd platform/clearing
alembic init -t generic migrations
```
Then replace `migrations/env.py` (same shape as EXC-007–010's, importing `from clearing.tables
import metadata as target_metadata` and `from base.db.migrations import
run_migrations_online`) and comment out `alembic.ini`'s default `sqlalchemy.url` line.

#### Task 7 — Write the initial migration
```
alembic revision -m "create clearing schema"
```
Edit the generated `migrations/versions/<rev>_create_clearing_schema.py`:
```python
def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS clearing')
    op.create_table(
        'trades',
        sa.Column('trade_id', sa.String(), nullable=False),
        sa.Column('ticker', sa.String(), nullable=False),
        sa.Column('buy_order_id', sa.String(), nullable=False),
        sa.Column('sell_order_id', sa.String(), nullable=False),
        sa.Column('buyer_account_id', sa.String(), nullable=False),
        sa.Column('seller_account_id', sa.String(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(18, 6), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('trade_id'),
        schema='clearing',
    )


def downgrade() -> None:
    op.drop_table('trades', schema='clearing')
```

#### Task 8 — Write `platform/clearing/Dockerfile` (two-stage + Alembic files)
Same shape as `platform/account/Dockerfile`; builder installs `--package clearing`; runtime
copies `src/clearing` → `./clearing`, `migrations/`, `alembic.ini`; sibling `COPY
.../pyproject.toml` lines for every other current workspace member. `EXPOSE 8004`.
`CMD ["-m", "clearing"]`.

#### Task 9 — Wire compose: repoint `clearing`, add `clearing-migrate`
In `infra/docker/compose.services.yml`, `clearing` service block:
- `build.dockerfile`: `infra/docker/Dockerfile` → `platform/clearing/Dockerfile`.
- `command`: `python -m services.clearing` → `python -m clearing`.
- `depends_on`: **add** (block did not exist before) `clearing-migrate: condition:
  service_completed_successfully`.

Add a new `clearing-migrate` service block (no `depends_on:`):
```yaml
  clearing-migrate:
    build:
      context: ../..
      dockerfile: platform/clearing/Dockerfile
    command: ["-m", "alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: postgresql+asyncpg://exchange:exchange@postgres:5432/exchange
```

#### Task 10 — Fix `justfile`'s `run-clearing` recipe
`uv run python -m services.clearing` → `uv run python -m clearing` (decision 11).

#### Task 11 — Versioning artifacts
Create `platform/clearing/CHANGELOG.md`, `PACKAGING.md`, `RELEASING.md` — same shape as
`platform/account/`'s three files.

### Acceptance test

From the repo root, on
`feat/EXC-011-migrate-services-clearing-into-platform-clearing-package-with-own-alembic-history`:
```
cd platform/clearing && alembic history && cd -
# expect: one revision, "create clearing schema" (<base> -> <rev> (head))

uv sync --extra dev
uv run python -c "import clearing.app, clearing.repository, clearing.service"
just check
just test
for df in platform/*/Dockerfile; do
  pkg=$(basename "$(dirname "$df")")
  docker build -f "$df" -t "exchange-${pkg//_/-}:test" .
done
just services-build
grep -rn "services\.clearing" services scripts platform clients infra --include='*.py' --include='*.yml'
test ! -d services/clearing
```
Then a real migration run:
```
docker-compose -f infra/docker/compose.infra.yml up -d postgres
DATABASE_URL=postgresql+asyncpg://exchange:exchange@localhost:5432/exchange \
  uv run --project platform/clearing alembic -c platform/clearing/alembic.ini upgrade head
psql postgresql://exchange:exchange@localhost:5432/exchange -c "\dt clearing.*"
```
Expect: `alembic history` one revision; imports clean; `just check` clean; `just test` passes
with no drop in collected count; every `platform/*/Dockerfile` builds; `just services-build`
succeeds; the `grep` prints nothing; `services/clearing` gone; live `alembic upgrade head`
creates `clearing` schema with `trades` + `clearing.alembic_version`.

### Docs update (mandatory when user-facing)

- `README.md`: in the "Project Structure" tree, replace the `services/clearing` line with
  `platform/clearing/`.
- `development/design.md`: fix stale references picked up by `grep -n
  "services/clearing\|services\.clearing" development/design.md` — currently line 22
  (`services/clearing      → post-trade trade-record keeper ...`).

### Finish (mandatory)

1. Acceptance test green; `just check`/`just test` clean; every `platform/*/Dockerfile` builds;
   `just services-build` passes; a live `alembic upgrade head` creates the `clearing` schema and
   its `trades` table.
2. Docs updated per above.
3. Write a summary: files moved, imports rewritten, Alembic scaffold + initial migration,
   `tables.py` schema-qualified and `ensure_tables()`/its call removed, new Dockerfile +
   `clearing-migrate` compose wiring (no `depends_on: postgres`), sibling-Dockerfile stub
   updates, `justfile`'s `run-clearing` fix, versioning docs.
4. Suggested commit message:
   ```
   feat: migrate services/clearing into platform/clearing package with own Alembic history (EXC-011)

   Move clearing to its own installable platform/clearing package with
   a two-stage Dockerfile, its own Alembic migration history gating
   startup via a new clearing-migrate one-shot container, and updated
   compose and workspace wiring.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-011 in-review --reason "acceptance green"` and hand back.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-17 — TO DO → READY: plan complete
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
