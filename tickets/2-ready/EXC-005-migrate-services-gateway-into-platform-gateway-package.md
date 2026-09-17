---
id: EXC-005
title: Migrate services/gateway into platform/gateway package
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-005 — Migrate services/gateway into platform/gateway package

## Outcome

After this ships, `platform/gateway/` is its own installable package (own `pyproject.toml`,
version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on `platform/base/`, with
its own two-stage Dockerfile — instead of a subtree of the single flat install.

## Description

`EXC-003 decisions 1, 3, 5`. `gateway` is stateless (no `DATABASE_URL`, per
`development/review-addendum.md` step 2 item 3) — no Alembic history applies here. Scope: move
`services/gateway/` to `platform/gateway/src/gateway/`, give it its own `pyproject.toml`
(hatchling, `src/` layout, depends on `platform/base/`), own two-stage Dockerfile replacing its
slice of the shared `infra/docker/Dockerfile`, and own versioning artifacts starting at `0.0.1`.
`gateway` has no `tests/` directory today (pre-existing gap, review-addendum step 4a item 3) —
this migration doesn't need to add one, but must not lose test coverage it doesn't have.
Depends on EXC-004 (`platform/base/` must exist first).

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-005-migrate-services-gateway-into-platform-gateway-package
```

Work and commit locally per the project's commit policy (`exchange` is a root-path child —
tidy WIP commits into atomic ones before presenting; no push/MR without explicit user
approval).

### Prerequisite gate (hard)

EXC-004 must be `6-done/` and merged. It is: `PR #19`, `bb4e5cd`, merged to `main`
(`tickets/BOARD.md` DONE table). `platform/base/` exists with package name `base`.

### Confirmed design decisions (do not deviate without asking)

1. **`platform/gateway/`'s importable package name is `gateway`, flat** —
   `platform/gateway/src/gateway/{__init__.py,__main__.py,app.py,auth.py,dependencies.py,
   schemas.py,routes/}`, matching `platform/base/src/base/` (EXC-004 decision 1).
2. **No Alembic migration history for `gateway`.** `gateway` is stateless — no
   `DATABASE_URL` — per `development/review-addendum.md` step 2 item 3 (design decision 2
   applies only to the 6 stateful services).
3. **`gateway` has no `tests/` directory today** (pre-existing gap,
   `development/review-addendum.md` step 4a item 3). This migration must not lose coverage it
   doesn't have, but does not add tests as part of the move.
4. **Own two-stage Dockerfile** (design decision 3), modelled on the reference monorepo's
   `~/Projects/private/monolith/platform/traffic/Dockerfile` (the closest analog — also a
   stateless HTTP-facing service): `uv`-based builder stage
   (`ghcr.io/astral-sh/uv:python3.13-bookworm-slim`) building only the `gateway` package
   (`uv sync --locked --no-dev --no-editable --package gateway`), copying every workspace
   member's `pyproject.toml` (uv needs the whole workspace to resolve) but only `gateway`'s
   `src/`; runtime stage `gcr.io/distroless/python3-debian13` (non-root by default, no
   shell), copying just the builder's `site-packages` plus `gateway`'s own source, running as
   `ENTRYPOINT ["python"]` / `CMD ["-m", "gateway"]`. `python3.13` (not the root's `3.14`) is
   deliberate — distroless has no `3.14` runtime image yet, exactly as the reference project's
   own Dockerfile comment notes; `platform/gateway/pyproject.toml` still declares
   `requires-python = ">=3.11"` to match `platform/base/`'s existing constraint, not a tight
   pin — the builder image is what fixes the concrete interpreter.
5. **Own versioning artifacts** (design decision 5): `CHANGELOG.md` (Keep a Changelog),
   `PACKAGING.md`, `RELEASING.md`, starting at version `0.0.1`. The reference monorepo does not
   yet have these per-package (only at its repo root), so there is no example to mirror —
   write minimal, project-specific versions; do not over-build them.
6. **`justfile`/CI restructuring (design decision 4) is out of scope** — that's EXC-014, which
   depends on every `EXC-005`–`EXC-012` migration landing first. This ticket keeps using the
   root `justfile`/`just services-build` for lint/test/build.
7. **`infra/docker/compose.services.yml`'s `gateway` service block switches to the new
   Dockerfile and module path**; the shared `infra/docker/Dockerfile`'s stale default `CMD`
   (still `python -m services.gateway`, now a dead path) is repointed at a service that still
   lives there, so it stays truthful for whichever service build omits an explicit `command:`
   override — no other behaviour of that shared file changes (it keeps building every
   not-yet-migrated service; EXC-015 removes it once all of EXC-005–EXC-012 land).
8. **`just services-build` is expected to still fail** with the pre-existing, already-tracked
   `EXC-016` error (`service "<name>" depends on undefined service "postgres"`) — reproduced on
   `main` before this branch, unrelated to `gateway`. Do not attempt to fix it here; verify via
   a direct `docker build` of the new Dockerfile instead (Acceptance test, below).

### Tasks

#### Task 1 — Move the source tree
```
mkdir -p platform/gateway/src
git mv services/gateway platform/gateway/src/gateway
```

#### Task 2 — Scaffold `platform/gateway/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "gateway"
version = "0.0.1"
description = "Public HTTP entry point for the exchange"
requires-python = ">=3.11"
dependencies = [
    "base",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "httpx>=0.27",
]

[tool.uv.sources]
base = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/gateway"]
```

#### Task 3 — Rewrite internal imports
Inside the moved tree, replace `services.gateway` with `gateway` (self-referential imports
only — `base.*` imports are already correct and untouched):
```
grep -rl 'services\.gateway' platform/gateway/src \
  | xargs sed -i '' -e 's/services\.gateway/gateway/g'
```
This covers `app.py` (`from services.gateway import dependencies`, `from services.gateway.routes
import ...`), `routes/{accounts,instruments,market_data,orders}.py` (`from services.gateway.auth
import ...`, `from services.gateway.dependencies import ...`, `from services.gateway.schemas
import ...`), and `__main__.py`'s `uvicorn.run('services.gateway.app:app', ...)` →
`uvicorn.run('gateway.app:app', ...)`. Verify: `grep -rn "services\.gateway" platform/gateway/src`
— expect no output.

#### Task 4 — Update the root workspace and the shared Dockerfile
In root `pyproject.toml`:
- `[tool.uv.workspace].members`: add `"platform/gateway"`.
- `[tool.coverage.run].source`: add `"platform/gateway/src"` alongside `"platform/base/src"`.

In `infra/docker/Dockerfile`, change the default `CMD` from `["python", "-m",
"services.gateway"]` to `["python", "-m", "services.account"]` (still-present, arbitrary
placeholder — every real invocation overrides it via compose `command:` anyway).

#### Task 5 — Write `platform/gateway/Dockerfile` (two-stage)
```dockerfile
# syntax=docker/dockerfile:1
#
# Build context is the repo root (see infra/docker/compose.services.yml) — uv needs the
# workspace root (pyproject.toml + uv.lock) plus every platform/* member's pyproject.toml to
# resolve the workspace, even though this image only installs gateway and its dependency
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
COPY platform/gateway/pyproject.toml ./platform/gateway/pyproject.toml
COPY platform/gateway/src ./platform/gateway/src

# --no-editable: the workspace member installs as a regular wheel, so the final stage can run
# off a copied site-packages dir instead of needing /app/platform around at runtime.
RUN uv sync --locked --no-dev --no-editable --package gateway

#
# RUNTIME
#
# distroless debian13 ships Python 3.13 (3.14 has no distroless build yet) with no
# shell/package manager — smallest, lowest attack surface, non-root by default. Only the
# venv's site-packages are copied over, so no shell is needed to activate it; PYTHONPATH does
# the same job.
FROM gcr.io/distroless/python3-debian13
WORKDIR /opt/gateway
COPY --from=builder /app/.venv/lib/python3.13/site-packages /opt/site-packages
COPY platform/gateway/src/gateway ./gateway
ENV PYTHONPATH=/opt/site-packages

EXPOSE 8000

ENTRYPOINT ["python"]
CMD ["-m", "gateway"]
```

#### Task 6 — Wire the new Dockerfile into compose
In `infra/docker/compose.services.yml`, `gateway` service block:
- `build.dockerfile`: `infra/docker/Dockerfile` → `platform/gateway/Dockerfile` (`build.context`
  stays `../..` — the Dockerfile still needs the full workspace).
- `command`: `python -m services.gateway` → `python -m gateway`.

#### Task 7 — Versioning artifacts
Create `platform/gateway/CHANGELOG.md`, Keep a Changelog format: title line, the standard
preamble sentence linking https://keepachangelog.com/en/1.0.0/, then one dated `0.0.1` entry
noting "Extracted from `services/gateway/` into its own `platform/gateway/` package (EXC-005)."
under a **Changed** label (bold text, not a nested markdown heading, so the ticket file's own
`### `-heading scan can't mistake it for a section of this plan).

Create `platform/gateway/PACKAGING.md`: one short paragraph — `gateway` is a `hatchling`-built,
`src/`-layout package (`src/gateway/`), installed into the repo's `uv` workspace via
`[tool.uv.sources]` in the root `pyproject.toml`; its importable package name is flat
(`gateway`, not a project-prefixed namespace) to match every other `platform/<service>/`
package (`platform/base/` and its EXC-005–EXC-012 siblings).

Create `platform/gateway/RELEASING.md`: manual release procedure (no automation yet) — bump
`version` in `platform/gateway/pyproject.toml`, add a dated entry to
`platform/gateway/CHANGELOG.md`, commit, tag `gateway-vX.Y.Z`, push the tag.

### Acceptance test

From the repo root, on `feat/EXC-005-migrate-services-gateway-into-platform-gateway-package`:
```
uv sync --extra dev
uv run python -c "import gateway.app, gateway.auth, gateway.dependencies, gateway.schemas, \
  gateway.routes.accounts, gateway.routes.instruments, gateway.routes.market_data, gateway.routes.orders"
just lint
just test
docker build -f platform/gateway/Dockerfile -t exchange-gateway:test .
grep -rn "services\.gateway" services scripts platform clients infra --include='*.py' --include='*.yml'
test ! -d services/gateway
```
Expect: imports clean; `just lint`/`just test` pass unchanged (gateway had no tests to lose);
the `docker build` succeeds (proves the two-stage Dockerfile independently of the known
`EXC-016` compose bug); the `grep` prints nothing; `services/gateway` is gone. Separately,
confirm `just services-build` still fails with exactly the pre-existing `EXC-016` error
(undefined `postgres` service) and no *new* error — do not treat that failure as blocking.

### Docs update (mandatory when user-facing)

- `README.md`: in the "Project Structure" tree, replace the `services/gateway/` line with
  `platform/gateway/` and a one-line description, mirroring how EXC-004 added `platform/base/`.
- `development/design.md`: fix any stale `services/gateway` / `shared/platform/` path
  references picked up by `grep -n "services/gateway\|services\.gateway" development/design.md`.

### Finish (mandatory)

1. Acceptance test green; `just lint`/`just test` clean; `docker build` of the new Dockerfile
   succeeds.
2. Docs updated per above.
3. Write a summary: files moved, imports rewritten, new Dockerfile + versioning docs added,
   compose + shared-Dockerfile updates, and the still-open `EXC-016` compose failure (confirmed
   unchanged, not fixed here).
4. Suggested commit message:
   ```
   feat: migrate services/gateway into platform/gateway package (EXC-005)

   Move gateway to its own installable platform/gateway package with a
   two-stage Dockerfile, own versioning docs, and updated compose wiring.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-005 in-review --reason "acceptance green"` and hand back.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — TO DO → READY: plan complete
