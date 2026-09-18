---
id: EXC-012
title: Migrate services/notifications into platform/notifications package with own Alembic history
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-012 — Migrate services/notifications into platform/notifications package with own Alembic history

## Outcome

After this ships, `platform/notifications/` is its own installable package (own `pyproject.toml`,
version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on `platform/base/`, with
its own two-stage Dockerfile and its own independent Alembic migration history gating its startup
— instead of a subtree of the single flat install sharing the create-on-boot bootstrap.

## Description

`EXC-003 decisions 1, 2, 3, 5`. `notifications` is stateful (`DATABASE_URL`, schema-per-service
already in code) — per a prior memory, this service and `account` were fully implemented, not
scaffolded, so this migration is a real code move, not a stub relocation. Scope: move
`services/notifications/` to `platform/notifications/src/notifications/`, give it its own
`pyproject.toml` (hatchling, `src/` layout, depends on `platform/base/`), own two-stage Dockerfile,
own versioning artifacts starting at `0.0.1`, and its own Alembic migration history scoped to its
Postgres schema, replacing its share of the create-on-boot bootstrap with a
`notifications-migrate` one-shot compose container gating startup. Depends on EXC-004
(`platform/base/` must exist first).

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-012-migrate-services-notifications-into-platform-notifications-package-with-own-alembic-history
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

1. **`platform/notifications/`'s importable package name is `notifications`, flat** —
   `platform/notifications/src/notifications/{__init__.py,__main__.py,app.py,repository.py,
   service.py,tables.py,tests/}`, matching every other `platform/<service>/` package.
2. **`alembic` stays a transitive dependency via `platform/base`** — no direct entry in
   `platform/notifications/pyproject.toml`.
3. **Own two-stage Dockerfile**, same shape as EXC-005–EXC-011's. `ENTRYPOINT` stays plain
   `python`.
4. **A new `notifications-migrate` one-shot compose service — with no `depends_on: postgres`
   entry**, per the EXC-016 convention. `notifications` currently has no `depends_on:` block at
   all (Tier 2, no service dependencies) — this ticket **adds** one:
   `notifications-migrate: condition: service_completed_successfully`.
5. **`notifications/tables.py`'s `MetaData` is schema-qualified**: `metadata = MetaData()` →
   `metadata = MetaData(schema='notifications')`.
6. **`notifications/tables.py`'s `ensure_tables()` wrapper is deleted**, along with its import,
   and `app.py`'s lifespan drops the `await ensure_tables(db)` call. This is the last of the six
   stateful services on create-on-boot — after this ticket, the shared
   `base.db.tables.ensure_tables()` helper has no remaining callers (leave the helper itself in
   place; removing dead code is out of scope here, tracked by EXC-015).
7. **The initial migration is handwritten**: one revision doing `CREATE SCHEMA IF NOT EXISTS
   notifications` plus creating the single `notifications` table verbatim from `tables.py`.
8. **`development/design.md:281` already correctly asserts `services/notifications/` ships full
   behaviour, not a stub** (per a prior finding — EXC-007's review, F3) — this ticket's Docs
   step only needs the path prefix repointed to `platform/`, not the "implemented" claim
   itself, which stays true and unrelated to this move.
9. **`just services-build` is now expected to pass outright** (EXC-016 merged).
10. **Every sibling `platform/*/Dockerfile` needs a `COPY platform/notifications/pyproject.toml
    ./platform/notifications/pyproject.toml` stub** — discover the current list with
    `ls platform/*/Dockerfile | grep -v platform/notifications/Dockerfile` at implementation
    time.
11. **Also fix `justfile`'s `run-notifications` recipe** (currently `uv run python -m
    services.notifications`) to `uv run python -m notifications`.
12. **`justfile`/CI restructuring (design decision 4) is out of scope** — EXC-014.

### Tasks

#### Task 1 — Move the source tree
```
mkdir -p platform/notifications/src
git mv services/notifications platform/notifications/src/notifications
```

#### Task 2 — Scaffold `platform/notifications/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "notifications"
version = "0.0.1"
description = "Notifications — per-account event feed; WebSocket push + HTTP backfill"
requires-python = ">=3.11"
dependencies = [
    "base",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
]

[tool.uv.sources]
base = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/notifications"]
```

#### Task 3 — Rewrite internal imports
```
grep -rl 'services\.notifications' platform/notifications/src \
  | xargs sed -i '' -e 's/services\.notifications/notifications/g'
```
Covers `__main__.py`, `app.py`, `repository.py`, `service.py`, `tests/test_service.py`. Verify:
`grep -rn "services\.notifications" platform/notifications/src` — expect no output. Also run
`grep -rn "services\.notifications" services scripts platform clients infra --include='*.py'
--include='*.yml'` (repo-wide) to catch any sibling consumer — none is known to exist, but
confirm.

#### Task 4 — Update the root workspace and sibling Dockerfiles
In root `pyproject.toml`:
- `[tool.uv.workspace].members`: add `"platform/notifications"`.
- `[project.dependencies]`: add `"notifications"`, and `[tool.uv.sources]`: add
  `notifications = { workspace = true }`.
- `[tool.coverage.run].source`: add `"platform/notifications/src"`.

For every file matched by `ls platform/*/Dockerfile | grep -v platform/notifications/Dockerfile`
(decision 10): add `COPY platform/notifications/pyproject.toml
./platform/notifications/pyproject.toml` in its builder stage.

#### Task 5 — `notifications/tables.py` and `app.py`: schema-qualify, drop create-on-boot
- `metadata = MetaData()` → `metadata = MetaData(schema='notifications')`.
- Delete the `ensure_tables()` function and its import.
- In `platform/notifications/src/notifications/app.py`'s lifespan: delete the
  (post-Task-3-rewrite) `from notifications.tables import ensure_tables` import and the `await
  ensure_tables(db)` call.

#### Task 6 — Scaffold Alembic under `platform/notifications/`
```
cd platform/notifications
alembic init -t generic migrations
```
Then replace `migrations/env.py` (same shape as EXC-007–011's, importing `from
notifications.tables import metadata as target_metadata` and `from base.db.migrations import
run_migrations_online`) and comment out `alembic.ini`'s default `sqlalchemy.url` line.

#### Task 7 — Write the initial migration
```
alembic revision -m "create notifications schema"
```
Edit the generated `migrations/versions/<rev>_create_notifications_schema.py`:
```python
def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS notifications')
    op.create_table(
        'notifications',
        sa.Column('notification_id', sa.String(), nullable=False),
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('notification_id'),
        schema='notifications',
    )


def downgrade() -> None:
    op.drop_table('notifications', schema='notifications')
```

#### Task 8 — Write `platform/notifications/Dockerfile` (two-stage + Alembic files)
Same shape as `platform/account/Dockerfile`; builder installs `--package notifications`;
runtime copies `src/notifications` → `./notifications`, `migrations/`, `alembic.ini`; sibling
`COPY .../pyproject.toml` lines for every other current workspace member. `EXPOSE 8007`.
`CMD ["-m", "notifications"]`.

#### Task 9 — Wire compose: repoint `notifications`, add `notifications-migrate`
In `infra/docker/compose.services.yml`, `notifications` service block:
- `build.dockerfile`: `infra/docker/Dockerfile` → `platform/notifications/Dockerfile`.
- `command`: `python -m services.notifications` → `python -m notifications`.
- `depends_on`: **add** (block did not exist before) `notifications-migrate: condition:
  service_completed_successfully`.

Add a new `notifications-migrate` service block (no `depends_on:`):
```yaml
  notifications-migrate:
    build:
      context: ../..
      dockerfile: platform/notifications/Dockerfile
    command: ["-m", "alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: postgresql+asyncpg://exchange:exchange@postgres:5432/exchange
```

#### Task 10 — Fix `justfile`'s `run-notifications` recipe
`uv run python -m services.notifications` → `uv run python -m notifications` (decision 11).

#### Task 11 — Versioning artifacts
Create `platform/notifications/CHANGELOG.md`, `PACKAGING.md`, `RELEASING.md` — same shape as
`platform/account/`'s three files.

### Acceptance test

From the repo root, on
`feat/EXC-012-migrate-services-notifications-into-platform-notifications-package-with-own-alembic-history`:
```
cd platform/notifications && alembic history && cd -
# expect: one revision, "create notifications schema" (<base> -> <rev> (head))

uv sync --extra dev
uv run python -c "import notifications.app, notifications.repository, notifications.service"
just check
just test
for df in platform/*/Dockerfile; do
  pkg=$(basename "$(dirname "$df")")
  docker build -f "$df" -t "exchange-${pkg//_/-}:test" .
done
just services-build
grep -rn "services\.notifications" services scripts platform clients infra --include='*.py' --include='*.yml'
test ! -d services/notifications
```
Then a real migration run:
```
docker-compose -f infra/docker/compose.infra.yml up -d postgres
DATABASE_URL=postgresql+asyncpg://exchange:exchange@localhost:5432/exchange \
  uv run --project platform/notifications alembic -c platform/notifications/alembic.ini upgrade head
psql postgresql://exchange:exchange@localhost:5432/exchange -c "\dt notifications.*"
```
Expect: `alembic history` one revision; imports clean; `just check` clean; `just test` passes
with no drop in collected count; every `platform/*/Dockerfile` builds; `just services-build`
succeeds; the `grep` prints nothing; `services/notifications` gone; live `alembic upgrade head`
creates `notifications` schema with `notifications` + `notifications.alembic_version`.

### Docs update (mandatory when user-facing)

- `README.md`: in the "Project Structure" tree, replace the `services/notifications` line with
  `platform/notifications/`.
- `development/design.md`: fix stale references picked up by `grep -n
  "services/notifications\|services\.notifications" development/design.md` — currently line 23
  (`services/notifications → per-account event feed ...`) and line 281 (path prefix only —
  decision 8).

### Finish (mandatory)

1. Acceptance test green; `just check`/`just test` clean; every `platform/*/Dockerfile` builds;
   `just services-build` passes; a live `alembic upgrade head` creates the `notifications`
   schema and its `notifications` table.
2. Docs updated per above.
3. Write a summary: files moved, imports rewritten, Alembic scaffold + initial migration,
   `tables.py` schema-qualified and `ensure_tables()`/its call removed (last remaining caller of
   the shared helper — note this explicitly), new Dockerfile + `notifications-migrate` compose
   wiring (no `depends_on: postgres`), sibling-Dockerfile stub updates, `justfile`'s
   `run-notifications` fix, versioning docs.
4. Suggested commit message:
   ```
   feat: migrate services/notifications into platform/notifications package with own Alembic history (EXC-012)

   Move notifications to its own installable platform/notifications
   package with a two-stage Dockerfile, its own Alembic migration
   history gating startup via a new notifications-migrate one-shot
   container, and updated compose and workspace wiring. This is the
   last of the six stateful services off the shared create-on-boot
   bootstrap.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-012 in-review --reason "acceptance green"` and hand back.

## Review

**Reviewer independence (step 0):** delegated — the implementing agent authored this branch in
this session, so the audits (steps 2–4a) were run by a fresh, independent sub-agent with no
memory of writing the code, briefed adversarially. Every delegated finding below was re-verified
by hand before being recorded.

**Applicability-gate audit (pre-pickup):**

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| G1 | non-blocking | stale-xref | note-and-close | `development/design.md`'s stale-reference line numbers had drifted to 19/285 (ticket stated 23/281), cosmetic only | ticket Description vs. `development/design.md` at pickup time | none — the Docs step's own `grep -n` finds the lines dynamically, so execution was unaffected |

**Post-implementation review (independent, delegated audit; PR #29 merged as commit `151723e`):**

- Implementation audit: every task and acceptance criterion **met** — acceptance test re-run
  verbatim (alembic history, imports, `just check`, `just lint`, `just test` 66 passed, all 8
  `platform/*/Dockerfile`s build, `just services-build`, grep clean, `services/notifications`
  gone, live `alembic upgrade head` created the schema/table/`alembic_version` on real Postgres).
- Quality audit: idiomatic verbatim move, no gratuitous changes; no security issue introduced by
  the migration itself.
- Consistency audit: Dockerfile diffed line-for-line against `platform/account/Dockerfile`
  (same shape, correct port substitution); port 8007 consistent everywhere referenced; no
  caller/callee drift.
- Documentation audit: `README.md` and `development/design.md` correctly repointed to
  `platform/notifications/`; whole-tree sweep found no stale `services/notifications` /
  `services.notifications` reference outside `platform/notifications/CHANGELOG.md`'s own
  (correct, historical) mention.

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | non-blocking | other | note-and-close | Local `main` checkout was briefly behind `origin/main` at the start of the independent review (an artifact of the review environment, not the branch) | reviewer fast-forwarded to `origin/main` before auditing | none — process note only |
| F2 | non-blocking | correctness | note-and-close | `GET /notifications/{account_id}?since=` has no error handling around `datetime.fromisoformat`, and `/ws/notifications/{account_id}` has no per-account authorization | `platform/notifications/src/notifications/app.py` (`get_notifications`, `ws_notifications`) | pre-existing, carried over verbatim by the move, out of this ticket's scope; worth a follow-up ticket if not already tracked — none filed, since it does not clear the promotion test on its own (a repo-wide auth/validation gap, not specific to this migration) |

Disposition summary: 3 non-blocking (G1, F1, F2), all note-and-close. 0 blocking. 0 spawned.

cost: estimated M, actual M

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-17 — TO DO → READY: plan complete
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
- 2026-09-18 — IN DEVELOPMENT → IN REVIEW: acceptance green
