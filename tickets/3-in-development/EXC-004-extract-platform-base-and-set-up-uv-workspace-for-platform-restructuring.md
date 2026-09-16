---
id: EXC-004
title: Extract platform/base and set up uv workspace for platform/ restructuring
project: exchange
depends-on: []
spawned-by: []
impact: high
complexity: medium
cost: M
---

# EXC-004 — Extract platform/base and set up uv workspace for platform/ restructuring

## Outcome

After this ships, the repo root is a `uv` workspace, `platform/base/` is its own installable
package (`base`) holding shared config, DB engine, HTTP client, request context, and cross-service
domain models/events/API schemas, and every service module (`services/*`, `scripts/*`) imports
that package directly (`base.db`, `base.domain.models`, …) instead of the old `shared.*` paths —
the dependency every later `platform/<service>/` package (EXC-005–EXC-012) declares in turn.

## Description

`EXC-003 decision 1`: the workspace becomes a `uv` workspace with `platform/<service>/` packages
plus one shared `platform/base/` package. This ticket is the foundational step — no *service*
code moves into `platform/<name>/` yet (that's EXC-005 through EXC-012, one per service; all six
already carry `depends-on: [EXC-004]`).

Scope: convert root `pyproject.toml` to a `uv` workspace (`[tool.uv.workspace]`), create
`platform/base/` as an installable package (own `pyproject.toml`, hatchling, `src/` layout,
package name **`base`** — flat, no project-prefix namespace, matching the layout EXC-005–EXC-009
already committed to: `platform/<service>/src/<service>/`), and move
`shared/platform/{db,http_client.py,request_context.py,clients/}` **and**
`shared/domain/{models.py,events.py,api_schemas.py}` into it as `base.{db,http_client,
request_context,clients,domain}`. Unlike the original draft of this ticket, every import of
`shared.platform.*`/`shared.domain.*` across the repo (~40 files: `services/*`, `scripts/seed.py`,
plus the moved modules' own internal cross-imports) is rewritten to `base.*` **in this ticket** —
there is no compatibility shim and no deferred rewrite; `shared/` is deleted once the move is
verified. The existing shared `infra/docker/Dockerfile` (single `pip install -e .` for every
service image) must keep building once the root package depends on a workspace member — decision
3's per-service two-stage Dockerfiles are still a later, per-service concern (EXC-005–EXC-012,
removed from root only in EXC-015), so this ticket makes the minimal fix (switch that install step
to `uv sync`) rather than restructuring Docker.

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-004-extract-platform-base-uv-workspace
```

Work and commit locally per the project's commit policy (`exchange` is a root-path child —
tidy WIP commits into atomic ones before presenting; no push/MR without explicit user approval).

### Prerequisite gate (hard)

None. `depends-on: []` — this ticket has no hard prerequisites. Soft note: EXC-001 (Repository/
Unit-of-Work base classes) is still in `1-to-do/` and not a dependency; if it lands and merges
before this ticket is picked up, its base classes fold into `platform/base/` too per EXC-003
decision 1 and should be added as an extra source file in Task 3 below. If it hasn't landed,
`platform/base/` ships without them — a later ticket adds them.

### Confirmed design decisions (do not deviate without asking)

1. **`platform/base/`'s importable package name is `base`, flat — not `exchange.base` or any
   other project-prefixed namespace.** Layout: `platform/base/src/base/{db/,http_client.py,
   request_context.py,clients/,domain/}`. This matches the flat `platform/<service>/src/
   <service>/` convention EXC-005–EXC-009 already committed to (e.g. `platform/gateway/src/
   gateway/`) — a project-prefixed namespace (the reference monolith's `stelo.base` pattern) was
   considered and rejected specifically to stay consistent with those already-filed tickets.
2. **`shared/domain/{models.py,events.py,api_schemas.py}` folds into `platform/base/` as
   `base.domain.{models,events,api_schemas}`**, alongside the config/DB/HTTP-client/
   request-context code decision 1's wording named explicitly. Confirmed with the user during
   refinement — EXC-003 decision 1 didn't name domain/ explicitly, but the HTTP clients moving
   into `base.clients` already depend on it, and no other package owns it.
3. **No compatibility shim for the old `shared.platform.*`/`shared.domain.*` import paths.**
   Every call site is rewritten to `base.*` in this ticket (Task 4), not deferred to
   EXC-005–EXC-012. Confirmed with the user — the ticket's original draft assumed services would
   keep importing old paths until their own migration ticket, which is inconsistent with
   physically moving the files; rewriting now is the smaller, non-contradictory diff.
4. **`platform/base/`'s `pyproject.toml` declares its own direct runtime dependencies**
   (`sqlalchemy[asyncio]`, `asyncpg`, `httpx`, `pydantic`) independently of the root
   `pyproject.toml`, which keeps its own copies of `sqlalchemy`/`asyncpg`/`httpx` because
   `services/*` still import them directly today. This duplication is normal in a `uv` workspace
   (one lockfile resolves both) and is *not* cleaned up here — EXC-015 ("remove dead root-level
   … aggregate pyproject deps") is the ticket that trims the root list once every service has
   moved out.
5. **The shared `infra/docker/Dockerfile` is patched, not replaced.** Swap its
   `pip install -e .` step for `uv sync --frozen --no-dev` plus `ENV PATH="/app/.venv/bin:
   $PATH"`, so `CMD`/compose `command: python -m services.<name>` keep working unchanged. Losing
   the old `COPY pyproject.toml` → install → `COPY . .` layer-caching split is accepted (noted
   inline as a `ponytail:` comment) — decision 3's real per-service two-stage Dockerfiles
   (EXC-005–EXC-012) make this file dead code anyway (removed by EXC-015).

### Tasks

#### Task 1 — Convert the root to a `uv` workspace
In `pyproject.toml`:
- Add `[tool.uv.workspace]` with `members = ["platform/base"]`.
- Add `"base"` to `[project].dependencies`.
- Add `[tool.uv.sources]` with `base = { workspace = true }`.
- In `[tool.setuptools.packages.find].include`, drop `"shared*"` (keep `"services*"`,
  `"clients*"`).
- In `[tool.coverage.run].source`, replace `"shared"` with `"platform/base/src"`.

#### Task 2 — Scaffold `platform/base/`
Create `platform/base/pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "base"
version = "0.0.1"
description = "Shared config, DB engine, HTTP client, request context, and cross-service domain types for exchange services"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "httpx>=0.27",
    "pydantic>=2.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/base"]
```
Create empty `platform/base/src/base/__init__.py`, `platform/base/src/base/clients/__init__.py`,
`platform/base/src/base/domain/__init__.py`, `platform/base/src/base/db/__init__.py` (the last
three replace the ones moved in Task 3 if `git mv` doesn't carry them — check before creating
duplicates).

#### Task 3 — Move the source files
```
git mv shared/platform/db/connection.py platform/base/src/base/db/connection.py
git mv shared/platform/db/tables.py platform/base/src/base/db/tables.py
git mv shared/platform/http_client.py platform/base/src/base/http_client.py
git mv shared/platform/request_context.py platform/base/src/base/request_context.py
git mv shared/platform/clients/*.py platform/base/src/base/clients/
git mv shared/domain/models.py platform/base/src/base/domain/models.py
git mv shared/domain/events.py platform/base/src/base/domain/events.py
git mv shared/domain/api_schemas.py platform/base/src/base/domain/api_schemas.py
git rm -r shared/
```
(`shared/` also holds `shared/README.md` and empty `shared/__init__.py`/`shared/platform/
__init__.py`/`shared/domain/__init__.py`/`shared/platform/clients/__init__.py`/`shared/platform/
db/__init__.py` — all removed with it; `shared/README.md`'s content is carried forward in Task 7.)

#### Task 4 — Rewrite every import
Across the whole repo (`services/`, `scripts/`, and the files just moved into
`platform/base/src/base/`), replace:
- `shared.platform.` → `base.`
- `shared.domain.` → `base.domain.`

e.g.:
```
grep -rl 'shared\.platform\.\|shared\.domain\.' --include='*.py' services scripts platform \
  | xargs sed -i '' -e 's/shared\.platform\./base./g' -e 's/shared\.domain\./base.domain./g'
```
Verify with `grep -rn "shared\." services scripts platform --include='*.py'` — expect no output.

#### Task 5 — Regenerate the lockfile
```
uv lock
```
Commit the updated `uv.lock`.

#### Task 6 — Fix `infra/docker/Dockerfile`
Replace:
```
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir -e .

COPY . .
```
with:
```
RUN pip install --no-cache-dir uv

COPY . .
# ponytail: whole-repo COPY before install drops the old dep-layer cache split;
# restore it (or drop this file) once EXC-005..012 give each service its own Dockerfile (EXC-015).
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
```
`CMD`/compose `command:` lines stay unchanged.

#### Task 7 — Docs
- `README.md`: in the "Project Structure" tree, replace the `shared/` block with a `platform/
  base/` block describing what it now holds (config/DB/HTTP-client/request-context/clients/
  domain types), reusing `shared/README.md`'s table content.
- Create `platform/base/README.md` from `shared/README.md`'s content, updated for the new
  `base.*` module paths (drop the "What lives next to each service" table — unchanged, still
  true, but arguably belongs in `development/design.md` instead; leave it out of scope here if it
  doesn't fit cleanly, note-and-close rather than expanding this ticket).
- `development/design.md`: update the "current, authoritative" prose (not the frozen EXC-003
  decision list) — line ~65 (`shared/db/` → `platform/base/src/base/`), line ~68
  (`shared/domain/models.py` → `platform/base/src/base/domain/models.py`), line ~82
  (`shared/domain/` → `platform/base/`), and extend the "Detailed architecture" stale-paths
  disclaimer blockquote (~lines 91–100) to note the further move from `shared/platform/`/
  `shared/domain/` to `platform/base/`. Leave the numbered EXC-003 decision list (lines 592–626)
  untouched — it's a dated historical record, not a live reference.

### Acceptance test

From the repo root:
```
uv sync --extra dev
uv run python -c "import base.db, base.http_client, base.request_context, base.clients.account, base.domain.models, base.domain.events, base.domain.api_schemas"
just lint
just test
just services-build
grep -rn "shared\." services scripts platform --include='*.py'   # expect no output
test ! -d shared                                                  # expect shared/ gone
```
All must succeed/print nothing, as noted.

### Docs update (mandatory when user-facing)

See Task 7 above: `README.md` project-structure tree, new `platform/base/README.md`, and
`development/design.md`'s live "Development conventions"/"When modifying a service" prose and
the "Detailed architecture" stale-paths disclaimer.

### Finish (mandatory)

1. Acceptance test green; `just lint`/`just test`/`just services-build` clean.
2. Docs updated per Task 7.
3. Write a summary: files moved, every call site rewritten, `uv.lock` regenerated, Dockerfile
   patched, docs updated; note the EXC-001 conditional (Task/Prerequisite gate above) as
   deferred if EXC-001 hadn't landed yet.
4. Suggested commit message:
   ```
   feat: extract platform/base and set up uv workspace (EXC-004)

   Convert the root to a uv workspace, move shared/platform/* and
   shared/domain/* into the new platform/base package (base.*), and
   rewrite every import accordingly.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before pushing).
   `pickle ticket move EXC-004 in-review --reason "acceptance green"` and hand back.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — TO DO → READY: plan complete
- 2026-09-16 — READY → IN DEVELOPMENT: picked up
