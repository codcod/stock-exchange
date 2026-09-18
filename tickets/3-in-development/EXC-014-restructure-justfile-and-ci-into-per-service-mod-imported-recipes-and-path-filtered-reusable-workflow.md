---
id: EXC-014
title: Restructure justfile and CI into per-service mod-imported recipes and path-filtered reusable workflow
project: exchange
depends-on: [EXC-005, EXC-006, EXC-007, EXC-008, EXC-009, EXC-010, EXC-011, EXC-012]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-014 — Restructure justfile and CI into per-service mod-imported recipes and path-filtered reusable workflow

## Outcome

After this ships, the root `justfile` only `mod`-imports each `platform/<service>/justfile`, and
CI is one reusable GitHub Actions workflow called by a thin per-service workflow file, path-
filtered so a service's CI only runs when that service (or `platform/base`, or the workspace
lockfile) changes — instead of one flat `justfile` and one `.github/workflows/ci.yaml` running
everything on every push.

## Description

`EXC-003 decision 4`. Scope: give each `platform/<service>/` its own `justfile` (build/test/lint
recipes scoped to that package), have the root `justfile` `mod`-import all of them, and replace
`.github/workflows/ci.yaml` with one reusable workflow plus a thin per-service caller workflow,
path-filtered on `platform/<service>/**`, `platform/base/**`, and the workspace lockfile. Depends
on every service migration ticket (EXC-005–EXC-012) — there is nothing to path-filter or `mod`-
import until each service package and its own justfile exist. **Re-verified at refinement
(2026-09-18): all eight dependencies (EXC-005–EXC-012) are in `6-done/` and merged**, so the
nine `platform/` packages this ticket splits across (the eight services plus `platform/base`)
all exist.

**`clients/` and `scripts/` are not `platform/<service>` packages** and this restructuring would
otherwise leave them uncovered by any path-filtered workflow. Decided at refinement: they keep
one always-on, non-path-filtered CI job/workflow (`ci-repo.yml` below) alongside the nine
path-filtered per-service ones, rather than folding into `gateway`'s workflow. (User decision,
2026-09-18.)

Soft coupling, both against the single `.github/workflows/ci.yaml` this ticket replaces:
EXC-002 ("Add static type-checking (ty) to lint pipeline and CI", `2-ready/`) adds a `ty`
step to the current `lint` job and explicitly documents this ticket as its own out-of-scope
follow-up; EXC-018 ("Guard compose config in CI…", `1-to-do/`) adds a `compose-check` step to
the same job and rewrites the `justfile`'s `up` recipe. Whichever of EXC-002/EXC-018/EXC-014
lands last must carry forward whatever the earlier ones already added to `ci.yaml`'s `lint`
job (the `ty` step, the `compose-check` step) into this ticket's reusable workflow, rather than
reverting to the two-step version this ticket's plan was written against.

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-014-restructure-justfile-and-ci-into-per-service-mod-imported-recipes-and-path-filtered-reusable-workflow
```

`exchange` is the root-path child (`path = "."`) — tidy WIP commits into atomic ones before
presenting.

### Prerequisite gate (hard)

`EXC-005` through `EXC-012` are all in `6-done/` with a `merged` History line (verified at
refinement, 2026-09-18) — all nine `platform/` packages (`base` plus the eight services) exist.
Re-confirm at pickup that `ci.yaml`'s `lint` job still matches what this plan assumes (see the
soft-coupling note in the Description) — if EXC-002 or EXC-018 have landed in the meantime,
carry their added steps into the new reusable workflow instead of this plan's two-step version.

### Confirmed design decisions (do not deviate without asking)

1. **Nine per-service `justfile`s**, one at `platform/<name>/justfile` for each of `base`,
   `gateway`, `market_data`, `account`, `matching_engine`, `risk_engine`, `order_management`,
   `clearing`, `notifications` — each with `build`/`test`/`lint` recipes scoped to that package
   only.
2. **Root `justfile` `mod`-imports all nine** (`just` 1.58, in use here, supports `mod name
   'path'`; confirmed no existing `mod` statements to collide with). The existing
   `infra`/`services`/`stack`/`lifecycle`/`qa` groups in the root `justfile` are untouched —
   they're cross-cutting (Docker Compose lifecycle, docs, workspace-wide `install`), not
   per-service.
3. **`clients/` and `scripts/` keep one always-on, non-path-filtered `ci-repo.yml`** (per the
   Description's refinement decision) instead of folding into any single service's workflow.
4. **CI becomes one reusable workflow (`workflow_call`) plus ten thin callers**: nine
   path-filtered per-service callers (`ci-<service>.yml`, one per package in decision 1) and one
   always-on `ci-repo.yml` for `clients/`/`scripts/`. `.github/workflows/ci.yaml` is deleted.
5. **Path filters**: each `ci-<service>.yml` triggers on `platform/<service>/**`,
   `platform/base/**`, and `uv.lock` — a `platform/base` change or a lockfile bump can affect
   every service, so every caller watches both regardless of which service it's for.

### Tasks

#### Task 1 — Per-service `justfile`s
For each `<name>` in `base`, `gateway`, `market_data`, `account`, `matching_engine`,
`risk_engine`, `order_management`, `clearing`, `notifications`, create
`platform/<name>/justfile`:
```
[group('qa')]
build:
    uv build --package <name>

[group('qa')]
test:
    uv run --package <name> pytest platform/<name>

[group('qa')]
lint:
    uv run ruff check platform/<name>
```
(Explicit path arguments to `pytest`/`ruff` rather than relying on `just`'s submodule cwd
behaviour, so the recipe's meaning doesn't depend on which directory `just` happens to run it
from.)

#### Task 2 — Root `justfile` mod-imports
Near the top of `justfile` (after the `set dotenv-load` line), add:
```
mod base 'platform/base'
mod gateway 'platform/gateway'
mod market_data 'platform/market_data'
mod account 'platform/account'
mod matching_engine 'platform/matching_engine'
mod risk_engine 'platform/risk_engine'
mod order_management 'platform/order_management'
mod clearing 'platform/clearing'
mod notifications 'platform/notifications'
```
Callable as `just account test`, `just gateway lint`, etc. Add two new root recipes scoping
the existing repo-wide `test`/`lint` down to what's *not* covered by a per-service justfile:
```
[group('qa')]
lint-repo:
    uv run ruff check clients scripts

[group('qa')]
test-repo:
    uv run --extra dev python -m pytest clients
```
Leave the existing workspace-wide `test`/`lint`/`check` recipes as they are — they still work
as an "everything" convenience for local use; only CI stops calling them directly.

#### Task 3 — Reusable CI workflow
Create `.github/workflows/service-ci.yml`:
```yaml
name: Service CI

on:
  workflow_call:
    inputs:
      service:
        required: true
        type: string

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
      - uses: extractions/setup-just@v3
      - run: uv sync --extra dev
      - run: just "${{ inputs.service }}" lint

  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.13", "3.14"]
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
      - uses: extractions/setup-just@v3
      - uses: actions/setup-python@v7
        with:
          python-version: ${{ matrix.python-version }}
      - run: uv sync --extra dev
      - run: just "${{ inputs.service }}" test
```
Carry forward the `ty`/`compose-check` steps here if EXC-002/EXC-018 landed first (Prerequisite
gate note above); otherwise this ticket's own scope stops at lint+test.

#### Task 4 — Thin per-service caller workflows
For each of the nine names in decision 1, create `.github/workflows/ci-<service>.yml`:
```yaml
name: CI (<service>)

on:
  push:
    branches: [main]
    paths: ["platform/<service>/**", "platform/base/**", "uv.lock"]
  pull_request:
    paths: ["platform/<service>/**", "platform/base/**", "uv.lock"]

jobs:
  ci:
    uses: ./.github/workflows/service-ci.yml
    with:
      service: <service>
```
(9 files: `ci-base.yml`, `ci-gateway.yml`, `ci-market_data.yml`, `ci-account.yml`,
`ci-matching_engine.yml`, `ci-risk_engine.yml`, `ci-order_management.yml`, `ci-clearing.yml`,
`ci-notifications.yml`.)

#### Task 5 — Repo-wide caller workflow
Create `.github/workflows/ci-repo.yml` (no `paths:` filter — always runs on push/PR to keep
`clients/`/`scripts/` covered):
```yaml
name: CI (repo)

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
      - uses: extractions/setup-just@v3
      - run: uv sync --extra dev
      - run: just lint-repo

  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.13", "3.14"]
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
      - uses: extractions/setup-just@v3
      - uses: actions/setup-python@v7
        with:
          python-version: ${{ matrix.python-version }}
      - run: uv sync --extra dev
      - run: just test-repo
```

#### Task 6 — Delete the old workflow
`rm .github/workflows/ci.yaml`. Re-grep for any other reference to that filename
(`development/review-addendum.md` and several `6-done/`/`2-ready/` tickets mention it
historically — those are fine as-is, they describe what existed when written; only a *live*
pointer would need fixing, and none was found at refinement).

### Acceptance test

- `just --list` shows the nine `mod`-imported groups (`just account test`, `just account lint`,
  etc.) alongside the existing root recipes.
- `just <name> test` and `just <name> lint` succeed for each of the nine names.
- `just lint-repo` and `just test-repo` succeed.
- `.github/workflows/ci.yaml` no longer exists; `service-ci.yml` + the nine `ci-<service>.yml`
  + `ci-repo.yml` do (11 files total).
- Inspect each `ci-<service>.yml`'s rendered `paths:` blocks and confirm they name that
  service's own directory, `platform/base/**`, and `uv.lock` — a full GitHub Actions dry run of
  path-filtered triggering isn't available locally, so this is a manual read-back rather than
  an executed check.

### Docs update (mandatory when user-facing)

`development/design.md` decision 4 already describes this target shape in prose (no wording
change needed — this ticket fulfills it, doesn't redescribe it). No other docs name
`.github/workflows/ci.yaml` as a live pointer (checked at refinement).

### Finish (mandatory)

1. Acceptance test green.
2. No docs wording change needed (see above).
3. Write a summary: files added/removed, the repo-wide-job decision, anything deferred (e.g.
   carrying forward EXC-002/EXC-018's steps if they landed first).
4. Suggest a Conventional Commit message, e.g.:
   ```
   refactor(ci): split justfile and CI into per-service mod-imported recipes (EXC-014)
   ```
5. Tidy WIP commits into atomic ones (root-path child).
6. Commit locally; do not push or open an MR without user approval. Verify
   `git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'` prints
   nothing before pushing. Present the commit message for approval, then push and open the
   merge request — merging is always the human's.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-18 — TO DO → READY: plan complete
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
