---
id: EXC-015
title: Remove dead root-level tooling after platform/ split (root Dockerfile, semantic_release block, aggregate pyproject deps)
project: exchange
depends-on: [EXC-005, EXC-006, EXC-007, EXC-008, EXC-009, EXC-010, EXC-011, EXC-012, EXC-013, EXC-014]
spawned-by: []
impact: low
complexity: low
cost: S
---

# EXC-015 — Remove dead root-level tooling after platform/ split (root Dockerfile, semantic_release block, aggregate pyproject deps)

## Outcome

After this ships, the root of the repo carries no tooling superseded by the `platform/` split:
no root `infra/docker/Dockerfile`, no `[tool.semantic_release]` block in the root
`pyproject.toml`, and `[tool.setuptools.packages.find]` names only the packages still actually
built from the root (`clients*`) — the dead `services*` entry for packages that now live under
`platform/` is gone.

## Description

`EXC-003 decision 5` names the root `pyproject.toml`'s `[tool.semantic_release]` block (already
unused before the split, doubly dead after — see EXC-003's review finding F2) as superseded once
each service has its own versioning story; this ticket is that removal — decision 5's larger
scope (per-service SemVer/CHANGELOG/RELEASING.md) is explicitly tracked elsewhere per
`development/design.md:626`, not here. Scope: delete the root `infra/docker/Dockerfile` (each
service now has its own, EXC-005–EXC-012), remove `[tool.semantic_release*]` from root
`pyproject.toml`, and trim the `[tool.setuptools.packages.find]` aggregate config. Depends on
every migration and restructuring ticket (EXC-005–EXC-014) — this is the final cleanup pass,
only safe once nothing at the root still needs what it removes.

**Re-verified at refinement (2026-09-18), narrowing the third item:** `[tool.setuptools.
packages.find]`'s `include = ["services*", "clients*"]` is only half-dead — `services*` has no
real source left (`services/` on disk holds just a stray tracked `__init__.py` and gitignored
`__pycache__`, confirmed via `git ls-files services/`), but `clients*` is still a live,
imported package (`clients/simulator/`, `clients/tui/`) and must **not** be dropped. The fix is
`include = ["clients*"]`, not deleting the whole config. `infra/docker/Dockerfile` is confirmed
unreferenced by any compose file or workflow already (grepped at refinement) — its removal is
a clean deletion, no follow-on edits elsewhere.

**Depends on EXC-013 and EXC-014, both still in `1-to-do/` as of this refinement** (not yet
`6-done/`) — this ticket can move to `2-ready/` now (the READY gate only requires a complete
plan, not satisfied dependencies), but cannot enter `3-in-development/` until both are done and
merged. Whoever picks this up next must check that first.

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-015-remove-dead-root-level-tooling-after-platform-split
```

`exchange` is the root-path child (`path = "."`) — tidy WIP commits into atomic ones before
presenting.

### Prerequisite gate (hard)

`EXC-013` and `EXC-014` must both be in `6-done/` and merged before this ticket enters
`3-in-development/` — as of this refinement (2026-09-18) both are still in `1-to-do/`. **Stop
and check the board before picking this up**; do not start work if either is unmet.

### Confirmed design decisions (do not deviate without asking)

1. **`[tool.setuptools.packages.find]` keeps `clients*`, drops only `services*`** — `clients/`
   is still a live, imported package; only the `services*` entry is dead (re-verified at
   refinement, see Description).
2. **`services/__init__.py`** (the last tracked file under `services/`, now unreferenced once
   `services*` is dropped from `packages.find`) is deleted along with the directory.
3. **`infra/docker/Dockerfile`** is deleted outright — confirmed unreferenced by any compose
   file or CI workflow at refinement; re-confirm at pickup in case EXC-014 (CI restructuring)
   introduced a new reference in the meantime.

### Tasks

#### Task 1 — Remove the root Dockerfile
`git rm infra/docker/Dockerfile`. Re-grep first (`grep -rn "infra/docker/Dockerfile"
--exclude-dir=.git --exclude-dir=tickets .`) in case something changed since refinement.

#### Task 2 — Remove the semantic_release config
Delete `[tool.semantic_release]` and every `[tool.semantic_release.*]` subsection from
`pyproject.toml` (re-locate at pickup — EXC-014 may have shifted line numbers by then).

#### Task 3 — Trim `packages.find` and remove the dead `services/` tree
`pyproject.toml`:
```
[tool.setuptools.packages.find]
where = ["."]
include = ["clients*"]
```
`git rm services/__init__.py` (or `git rm -r services/` if anything else has landed under it
by pickup time — re-check with `git ls-files services/` first).

**Amended at pickup (2026-09-18, applicability audit finding):** `[tool.coverage.run]`'s
`source` list also names the bare `services` directory (`source = ["services",
"platform/base/src", ...]`) — not caught by the acceptance test's `services\*` grep since that
pattern only matches the literal `services*` glob, not the bare word. Drop `"services"` from
that `source` list in the same edit pass, since the file is already open.

### Acceptance test

- `uv sync --extra dev` succeeds after the `pyproject.toml` edits.
- `git ls-files services/` returns nothing; `git grep -n "semantic_release\|services\*\|\"services\""
  pyproject.toml` returns nothing.
- The child's configured build/test/lint commands (`just services-build`, `just test`, `just
  lint`, or their post-EXC-014 per-service equivalents) stay green — confirms nothing still
  depended on the removed root Dockerfile or the `services*` package-find entry.

### Docs update (mandatory when user-facing)

No wording change needed — `development/design.md` decision 5 already narrates this removal
as future work ("removed once each service has its own versioning story"); this ticket
fulfills that, it doesn't need to restate it.

### Finish (mandatory)

1. Acceptance test green.
2. No docs wording change needed (see above).
3. Write a summary: files/config removed, anything deferred.
4. Suggest a Conventional Commit message, e.g.:
   ```
   chore: remove dead root-level tooling after platform/ split (EXC-015)
   ```
5. Tidy WIP commits into atomic ones (root-path child).
6. Commit locally; do not push or open an MR without user approval. Verify
   `git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'` prints
   nothing before pushing. Present the commit message for approval, then push and open the
   merge request — merging is always the human's.

## Review

- [x] Reviewer independence settled (step 0): no hand in this branch this session — independent, audits run directly (no delegation needed)
- [x] In-tree stale-branch check (step 0a): `pickle doctor` found the branch stale (ticket copy still `3-in-development` vs main's `4-in-review`); rebased `feat/EXC-015-...` onto `main` (4295268), re-ran `pickle doctor` — clean
- [x] Implementation audit — acceptance test re-run, tasks & criteria verified (steps 1, 2)
- [x] Quality audit (step 3) — config-only deletion, no logic to assess for idiom/tests/error-handling
- [x] Consistency audit (step 4) — repo-wide grep for dangling references
- [x] Documentation audit (step 4a) — project has no configured docs-build command (n/a); no user-facing docs coverage needed per the ticket's own "Docs update" section
- [x] Docs-readability pass (step 4b) — conscious skip: no docs-readability reviewer available in this session
- [x] Findings recorded with severity, class, disposition; disposition summary + cost line present (step 5)
- [x] Ticket moved (step 6)
- [x] Other references updated; governing documents reconciled (step 7)
- [x] Remaining-tickets impact sweep done (step 8) — no ticket in `1-to-do/`/`2-ready/` lists EXC-015 in `depends-on:` or Description
- [x] Summary + commit message & MR attributes presented for approval (step 9)

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | non-blocking | stale-xref | fixed inline | `development/design.md` decision 5 said the `[tool.semantic_release]` block would be removed once each service has its own versioning story (tracked by a future ticket) — EXC-015 removed it now, ahead of and independent from that future ticket, making the sentence misattribute the removal | `development/design.md:624-626` (pre-fix) | reworded to credit EXC-015 for the removal, leaving the per-service versioning story itself tracked by the future ticket — fixed on the feature branch, commit `1ee6c77` |

Disposition summary: 1 finding — 1 fixed inline (F1). No blocking findings.

cost: estimated S, actual S

**Acceptance test (re-run verbatim):**
- `uv sync --extra dev` → succeeded (`Resolved 58 packages`, `Checked 47 packages`).
- `git ls-files services/` → empty (pass).
- `git grep -n 'semantic_release\|services\*\|"services"' pyproject.toml` → no match (pass).
- `just lint` → `All checks passed!`
- `just services-build` → all 14 images built.
- `just test` → `67 passed`.

**Implementation audit:** all three plan tasks verified against the diff (`git diff
fd0fd56..HEAD`): Dockerfile removed, `[tool.semantic_release*]` fully removed,
`packages.find` trimmed to `include = ["clients*"]`, `services/__init__.py` and the
`[tool.coverage.run]` bare `"services"` entry both removed exactly as the amended plan
specified. `clients.simulator`/`clients.tui` re-verified importable after the trim.

**Reviewer independence:** this session did not author the branch (the code commit
predates this session — confirmed via `git log`); audits ran directly, no delegation
needed.

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-18 — TO DO → READY: plan complete
- 2026-09-18 — plan amended inline: applicability audit at pickup found `[tool.coverage.run]`
  source list also names bare `services`, missed by the acceptance test's grep pattern;
  folded a fix into Task 3 and widened the grep. Dependency gate re-verified independently
  (git ancestry) — EXC-013/EXC-014 both merged to main; prerequisite is satisfied.
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
- 2026-09-18 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-09-18 — IN REVIEW → DONE: acceptance green; 1 non-blocking finding (F1, stale-xref) fixed inline in design.md on feature branch
- 2026-09-18 — MERGED: PR #32, `01e9a28`
