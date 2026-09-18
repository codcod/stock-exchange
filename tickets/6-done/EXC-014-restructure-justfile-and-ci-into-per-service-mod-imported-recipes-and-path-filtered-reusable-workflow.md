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

**Reviewer independence (step 0):** the reviewing agent authored this branch in this same
session, so the audits (steps 2–4a) were delegated to an independent sub-agent (fresh, no
memory of writing the code, briefed adversarially). Its findings were re-verified by hand before
recording, per step 0's "delegation buys independence, not accuracy."

**In-tree stale-branch check (step 0a):** `pickle doctor` run before auditing — 0 errors, 0
warnings, no stale-ticket-branch warning.

**Implementation audit (step 2):** acceptance test re-run verbatim — `just --list` shows all
nine mod groups; `just <name> test`/`just <name> lint` green for all nine; `just lint-repo` and
`just test-repo` green; `.github/workflows/ci.yaml` absent, `service-ci.yml` + 9
`ci-<service>.yml` + `ci-repo.yml` present (11 files); each `ci-<service>.yml`'s `paths:` block
matches the spec. `just services-build`, `just test` (67 passed), `just lint` all green,
unaffected by the mod imports. Every task in the Implementation Plan is done, in the files it
names.

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | blocking | test-gap | — | The old `.github/workflows/ci.yaml` lint job ran both `ruff check .` and `ruff format --check .`. The new CI surface this ticket ships (`service-ci.yml`'s lint job, called by all 9 `ci-<service>.yml`, plus `ci-repo.yml`'s lint job) runs only `ruff check .` / `ruff check clients scripts` via the per-service `lint` recipes and the new `lint-repo` recipe — `ruff format --check` is invoked nowhere in CI anymore. This is exactly the failure mode `development/review-addendum.md` step 2 item 3 was written to prevent (after EXC-007 landed unformatted generated code that passed `just lint` but would have failed CI's format check): a PR with a pure formatting violation now goes green on every one of the 9 per-service workflows and on `ci-repo.yml`, and is only caught if a human happens to run `just check` locally, which nothing in CI enforces. | Repo-wide grep for `ruff format` under `.github/workflows/`, `platform/*/justfile`, and the new `lint-repo` recipe returns zero hits (only the pre-existing, now CI-orphaned root `justfile` `fmt-check`/`check` recipes still reference it). Empirical repro (independent reviewer): appended a formatting violation to `platform/account/src/account/__init__.py`; `just account lint` (the exact command `service-ci.yml`'s lint job runs) passed with "All checks passed!" while `uv run ruff format --check platform/account/src/account/__init__.py` failed with "Would reformat"; edit reverted, working tree confirmed clean. | Add a `ruff format --check .` step to every per-service `lint` recipe (9 files) and to the new `lint-repo` recipe, so `service-ci.yml`'s and `ci-repo.yml`'s lint jobs enforce formatting the same way the old `ci.yaml` did — restoring parity rather than adding a new mechanism. |

Disposition summary: 1 blocking (F1, test-gap) — ticket moves to `5-rework/` for a scoped fix on
the same branch; no non-blocking findings.

### Rework fix record — round 1 (commit f2bb446)

Added `uv run ruff format --check .` as a second line in each of the 9 per-service `lint`
recipes (`platform/<name>/justfile`) and `uv run ruff format --check clients scripts` as a
second line in the root `justfile`'s `lint-repo` recipe — restoring the same `ruff check` +
`ruff format --check` pairing the old `ci.yaml` lint job ran, via the exact commands
`service-ci.yml` and `ci-repo.yml` already call. No workflow YAML changes needed since both
call into `just <name> lint` / `just lint-repo`.

Re-ran the acceptance test after the fix: `just <name> lint` green (including the new format
check) for all 9 services, `just lint-repo` green, `just test-repo` green (1 passed), `just
services-build` green, `just test` green (67 passed), `just lint` green.

Branch tip noted before this round's fix commit (per rules §1, and after rebasing the branch
onto main at pickup to clear a stale-ticket-status warning): `f861ba2`. Diff for the scoped
re-review: `git diff f861ba2..f2bb446`.

cost: estimated M, actual M

### Scoped re-review — round 2

**Reviewer independence (step 0):** this session has no memory of authoring the branch (fresh
session) — direct audit, no delegation needed.

**In-tree stale-branch check (step 0a):** `pickle doctor` at pickup reported the branch's ticket
copy stale (`this branch has it in "5-rework" but main has it in "4-in-review"`); rebased onto
`main`, re-ran `pickle doctor` — 0 errors, 0 warnings.

**Scope (step 1):** F1's fix and the diff that closed it, `git diff f861ba2..f2bb446` (read above,
in the round-1 fix record), plus a fresh read of that diff's replacement text for new defects.

**Implementation audit (step 2):** F1 verified fixed — `just <name> lint` now runs
`ruff format --check .` after `ruff check .` for all 9 services (confirmed by output, not just
recipe text), `just lint-repo` likewise for `clients scripts`. Re-ran the full acceptance test:
`just --list` still shows the nine mod groups; all 9 `just <name> lint`/`test` green; `just
lint-repo`/`test-repo` green; `just services-build` green; `just test` green (67 passed); `just
lint` green. Round-1 diff introduces no new files, only one new line per justfile — nothing else
to verify against the plan's tasks.

**Consistency / governing-doc audit (steps 4, 7):** `development/review-addendum.md` step 2 item
3 named `.github/workflows/ci.yaml` as the workflow enforcing `ruff format --check` — a governing
document this ticket's Task 6 (delete `ci.yaml`) made false: the enforcing workflows are now
`ci-<service>.yml`/`service-ci.yml` and `ci-repo.yml`. No behaviour change, prose only, within
this review's reach (same repo, branch already checked out) — fixed inline in
`development/review-addendum.md` (F2 below).

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F2 | non-blocking | stale-xref | fixed inline | `development/review-addendum.md` step 2 item 3 named `.github/workflows/ci.yaml` as the workflow that runs `ruff format --check`; this ticket deletes that file (Task 6), making the reference stale. | `development/review-addendum.md:49` before the fix; `.github/workflows/ci.yaml` absent from the tree, `ci-<service>.yml`/`service-ci.yml`/`ci-repo.yml` present and running `ruff format --check` (round-1 fix, verified above). | Reworded to name the current workflows instead of the deleted file — done, this round. |

Round-2 disposition summary: 0 blocking; 1 non-blocking (F2, stale-xref, fixed inline).

cost: estimated M, actual M (unchanged by round 2 — a one-file doc reword)

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-18 — TO DO → READY: plan complete
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
- 2026-09-18 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-09-18 — IN REVIEW → REWORK: F1 blocking: ruff format --check dropped from CI
- 2026-09-18 — REWORK → IN REVIEW: findings fixed
- 2026-09-18 — IN REVIEW → DONE: F1 fixed and verified; F2 (stale-xref) fixed inline; round-2 re-review clean
