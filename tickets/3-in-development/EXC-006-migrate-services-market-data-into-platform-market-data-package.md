---
id: EXC-006
title: Migrate services/market_data into platform/market_data package
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: low
cost: M
---

# EXC-006 — Migrate services/market_data into platform/market_data package

## Outcome

After this ships, `platform/market_data/` is its own installable package (own `pyproject.toml`,
version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on `platform/base/`, with
its own two-stage Dockerfile — instead of a subtree of the single flat install.

## Description

`EXC-003 decisions 1, 3, 5`. `market_data` is stateless and in-memory-only (no `DATABASE_URL`,
per `development/review-addendum.md` step 2 item 3) — no Alembic history applies here. Scope: move
`services/market_data/` to `platform/market_data/src/market_data/`, give it its own
`pyproject.toml` (hatchling, `src/` layout, depends on `platform/base/`), own two-stage Dockerfile
replacing its slice of the shared `infra/docker/Dockerfile`, and own versioning artifacts starting
at `0.0.1`. Depends on EXC-004 (`platform/base/` must exist first). Unlike `gateway` (EXC-005),
`market_data` already has a `tests/` directory (`services/market_data/tests/test_service.py`) —
this migration moves it too and must keep it discovered by `just test` (root `pyproject.toml`'s
`testpaths` is currently `["services"]` only). Soft coupling, no hard dependency: this ticket
reuses the two-stage-Dockerfile pattern EXC-005 establishes (same shape, `market_data` in place
of `gateway`) — independently buildable/reviewable even if EXC-005 hasn't merged first.

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-006-migrate-services-market-data-into-platform-market-data-package
```

Work and commit locally per the project's commit policy (`exchange` is a root-path child —
tidy WIP commits into atomic ones before presenting; no push/MR without explicit user
approval).

### Prerequisite gate (hard)

EXC-004 must be `6-done/` and merged. It is: `PR #19`, `bb4e5cd`, merged to `main`
(`tickets/BOARD.md` DONE table). `platform/base/` exists with package name `base`.

### Confirmed design decisions (do not deviate without asking)

1. **`platform/market_data/`'s importable package name is `market_data`, flat** —
   `platform/market_data/src/market_data/{__init__.py,__main__.py,app.py,service.py,tests/}`,
   matching `platform/base/src/base/` (EXC-004 decision 1).
2. **No Alembic migration history for `market_data`.** Stateless, in-memory-only — no
   `DATABASE_URL` — per `development/review-addendum.md` step 2 item 3.
3. **Own two-stage Dockerfile** (design decision 3), same shape as EXC-005's
   `platform/gateway/Dockerfile`: `uv`-based builder
   (`ghcr.io/astral-sh/uv:python3.13-bookworm-slim`, `uv sync --locked --no-dev --no-editable
   --package market_data`), runtime `gcr.io/distroless/python3-debian13`
   (`ENTRYPOINT ["python"]` / `CMD ["-m", "market_data"]`), `python3.13` for the same
   distroless-availability reason EXC-005 documents; `requires-python = ">=3.11"` in
   `platform/market_data/pyproject.toml` (matching `platform/base/`, not a tight pin).
4. **Own versioning artifacts** (design decision 5): `CHANGELOG.md` (Keep a Changelog),
   `PACKAGING.md`, `RELEASING.md`, starting at version `0.0.1` — same minimal shape as
   EXC-005's.
5. **`services/market_data/tests/` moves with the package**, to
   `platform/market_data/src/market_data/tests/` (same relative position it has today,
   directly under the service). Root `pyproject.toml`'s `[tool.pytest.ini_options].testpaths`
   must grow from `["services"]` to `["services", "platform"]` so `just test` still discovers
   it — this is a correctness requirement, not cleanup: skipping it silently drops
   `test_service.py` from every future `just test` run.
6. **`justfile`/CI restructuring (design decision 4) is out of scope** — EXC-014, gated on
   every `EXC-005`–`EXC-012` landing first.
7. **`infra/docker/compose.services.yml`'s `market-data` service block switches to the new
   Dockerfile and module path**; no other service's compose block changes.
8. **`just services-build` is expected to still fail** with the pre-existing, already-tracked
   `EXC-016` error (undefined `postgres` service), unrelated to `market_data`. Verify the new
   Dockerfile with a direct `docker build` instead (Acceptance test, below).

### Tasks

#### Task 1 — Move the source tree
```
mkdir -p platform/market_data/src
git mv services/market_data platform/market_data/src/market_data
```

#### Task 2 — Scaffold `platform/market_data/pyproject.toml`
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "market_data"
version = "0.0.1"
description = "In-memory market data service (quotes, depth, trade tape)"
requires-python = ">=3.11"
dependencies = [
    "base",
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
]

[tool.uv.sources]
base = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/market_data"]
```

#### Task 3 — Rewrite internal imports
```
grep -rl 'services\.market_data' platform/market_data/src \
  | xargs sed -i '' -e 's/services\.market_data/market_data/g'
```
Covers `__main__.py` (`from services.market_data.app import app`), `app.py` (`from
services.market_data.service import MarketDataService`), and `tests/test_service.py` (`from
services.market_data.service import MAX_TRADE_HISTORY, MarketDataService`). Verify:
`grep -rn "services\.market_data" platform/market_data/src` — expect no output.

#### Task 4 — Update the root workspace, pytest config, and the shared Dockerfile
In root `pyproject.toml`:
- `[tool.uv.workspace].members`: add `"platform/market_data"`.
- `[project.dependencies]`: add `"market_data"`, and `[tool.uv.sources]`: add
  `market_data = { workspace = true }` — EXC-005 found that without both, `uv sync` never
  installs the workspace member into the root venv and the acceptance test's `import
  market_data...` step fails with `ModuleNotFoundError`.
- `[tool.pytest.ini_options].testpaths`: `["services"]` → `["services", "platform"]`.
- `[tool.coverage.run].source`: add `"platform/market_data/src"` alongside
  `"platform/base/src"` (and `"platform/gateway/src"` if EXC-005 has already merged; otherwise
  leave that entry for EXC-005 to add).

`infra/docker/Dockerfile`'s default `CMD` needs no further change here (EXC-005 already
repointed it away from a service that's moving out).

#### Task 5 — Write `platform/market_data/Dockerfile` (two-stage)
```dockerfile
# syntax=docker/dockerfile:1
#
# Build context is the repo root (see infra/docker/compose.services.yml) — uv needs the
# workspace root (pyproject.toml + uv.lock) plus every platform/* member's pyproject.toml to
# resolve the workspace, even though this image only installs market_data and its dependency
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
COPY platform/market_data/pyproject.toml ./platform/market_data/pyproject.toml
COPY platform/market_data/src ./platform/market_data/src

RUN uv sync --locked --no-dev --no-editable --package market_data

#
# RUNTIME
#
FROM gcr.io/distroless/python3-debian13
WORKDIR /opt/market_data
COPY --from=builder /app/.venv/lib/python3.13/site-packages /opt/site-packages
COPY platform/market_data/src/market_data ./market_data
ENV PYTHONPATH=/opt/site-packages

EXPOSE 8005

ENTRYPOINT ["python"]
CMD ["-m", "market_data"]
```

#### Task 6 — Wire the new Dockerfile into compose
In `infra/docker/compose.services.yml`, `market-data` service block:
- `build.dockerfile`: `infra/docker/Dockerfile` → `platform/market_data/Dockerfile`
  (`build.context` stays `../..`).
- `command`: `python -m services.market_data` → `python -m market_data`.

#### Task 7 — Versioning artifacts
Create `platform/market_data/CHANGELOG.md` (Keep a Changelog format): title line, the standard
preamble sentence linking https://keepachangelog.com/en/1.0.0/, one dated `0.0.1` entry noting
"Extracted from `services/market_data/` into its own `platform/market_data/` package
(EXC-006)." under a **Changed** label (bold text, not a nested heading).

Create `platform/market_data/PACKAGING.md`: one short paragraph — `market_data` is a
`hatchling`-built, `src/`-layout package (`src/market_data/`), installed into the repo's `uv`
workspace via `[tool.uv.sources]` in the root `pyproject.toml`; its importable package name is
flat (`market_data`, not a project-prefixed namespace) to match every other
`platform/<service>/` package.

Create `platform/market_data/RELEASING.md`: manual release procedure — bump `version` in
`platform/market_data/pyproject.toml`, add a dated entry to
`platform/market_data/CHANGELOG.md`, commit, tag `market_data-vX.Y.Z`, push the tag.

### Acceptance test

From the repo root, on
`feat/EXC-006-migrate-services-market-data-into-platform-market-data-package`:
```
uv sync --extra dev
uv run python -c "import market_data.app, market_data.service"
just lint
just test
docker build -f platform/market_data/Dockerfile -t exchange-market-data:test .
grep -rn "services\.market_data" services scripts platform clients infra --include='*.py' --include='*.yml'
test ! -d services/market_data
```
Expect: imports clean; `just test`'s output still includes `test_service.py`'s cases (now
collected from `platform/market_data/src/market_data/tests/`, confirming the `testpaths`
change worked — do not treat a drop in collected test count as passing); `just lint` clean;
the `docker build` succeeds; the `grep` prints nothing; `services/market_data` is gone.
Separately, confirm `just services-build` still fails with exactly the pre-existing `EXC-016`
error and no new error — do not treat that failure as blocking.

### Docs update (mandatory when user-facing)

- `README.md`: in the "Project Structure" tree, replace the `services/market_data/` line with
  `platform/market_data/`.
- `development/design.md`: fix any stale `services/market_data` / `services\.market_data`
  path references picked up by
  `grep -n "services/market_data\|services\.market_data" development/design.md`.

### Finish (mandatory)

1. Acceptance test green; `just lint`/`just test` clean (including the moved test file);
   `docker build` of the new Dockerfile succeeds.
2. Docs updated per above.
3. Write a summary: files moved (including `tests/`), imports rewritten, `testpaths` updated,
   new Dockerfile + versioning docs added, compose updated, and the still-open `EXC-016`
   compose failure (confirmed unchanged, not fixed here).
4. Suggested commit message:
   ```
   feat: migrate services/market_data into platform/market_data package (EXC-006)

   Move market_data to its own installable platform/market_data package
   with a two-stage Dockerfile, own versioning docs, and updated compose
   and pytest wiring.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-006 in-review --reason "acceptance green"` and hand back.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — TO DO → READY: plan complete
- 2026-09-17 — plan amended inline: EXC-005's review (impact sweep, step 8) found Task 4 here
  had the same root-`pyproject.toml` wiring gap EXC-005 itself hit during implementation —
  missing `[project.dependencies]`/`[tool.uv.sources]` entries for the new workspace member.
  Added both.
- 2026-09-17 — READY → IN DEVELOPMENT: picked up
- 2026-09-17 — plan amended inline: Task 5's Dockerfile, copied verbatim from EXC-005's pattern,
  only worked for a 2-member workspace. With `market_data` added as a 3rd `[tool.uv.workspace]`
  member, `uv sync --locked --package <target>` fails inside either service's Docker build with
  `references a workspace ... but is not a workspace member`, because uv resolves the whole
  workspace declared in root `pyproject.toml`, not just the target package — every member's
  `pyproject.toml` must be present in the build context even though only the target gets
  installed. Fixed by adding a `COPY platform/<sibling>/pyproject.toml
  ./platform/<sibling>/pyproject.toml` line (no `src/`, so no extra install) for the other
  service's Dockerfile in both `platform/market_data/Dockerfile` (added gateway's) and
  `platform/gateway/Dockerfile` (added market_data's, to fix the regression this ticket's own
  workspace-member addition caused there). Verified both `docker build`s green.
