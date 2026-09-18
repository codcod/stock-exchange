---
id: EXC-013
title: Update clients/ imports for platform/ package layout
project: exchange
depends-on: [EXC-005, EXC-006, EXC-007, EXC-008, EXC-009, EXC-010, EXC-011, EXC-012]
spawned-by: []
impact: low
complexity: low
cost: S
---

# EXC-013 — Update clients/ imports for platform/ package layout

## Outcome

After this ships, `clients/simulator/` and `clients/tui/` are confirmed clean against the fully
migrated `platform/` layout, and a CI-run test guards that: a future `services.*`/`shared.*`
import under `clients/` fails the build instead of sitting unnoticed.

## Description

`clients/` talks to services over HTTP only (per `development/design.md`'s service-boundary
note), so this is expected to be a small grep-and-fix pass rather than a real port: confirm
neither `clients/simulator/main.py` nor `clients/tui/{api.py,config.py,models.py}` imports
anything from `services.*` or the old `shared.platform.*`/`shared.domain.*` paths that moved
during EXC-004–EXC-012, and fix whatever does. Depends on every service migration ticket
(EXC-005–EXC-012) being done, since only then are the old paths actually gone and the check
meaningful.

**Re-verified at refinement (2026-09-18):** `EXC-005`–`EXC-012` are all in `6-done/` and
merged, so ran the check now — `grep -rn "services\.\|shared\." clients/` returns nothing.
`clients/` is already clean; there is no import to fix. Rather than close this as a no-op,
the scope becomes a regression guard: add a small test that fails CI if a future change
reintroduces a `services.*`/`shared.*` import under `clients/`, instead of that surfacing
silently the way EXC-016's compose bug did for four tickets. (User decision, 2026-09-18.)

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-013-update-clients-imports-for-platform-package-layout
```

`exchange` is the root-path child (`path = "."`) — tidy WIP commits into atomic ones before
presenting.

### Prerequisite gate (hard)

`EXC-005`–`EXC-012` are all in `6-done/` with a `merged` History line (re-verified at
refinement, 2026-09-18).

### Confirmed design decisions (do not deviate without asking)

1. **No import fixes are needed** — the migration already left `clients/` clean (re-verified
   at refinement, see Description). This ticket adds a regression guard test, not a repair.
2. **`pyproject.toml`'s `[tool.pytest.ini_options] testpaths`** is currently
   `["services", "platform"]` — stale (`services` no longer holds real source, only a leftover
   tracked `__init__.py` and gitignored `__pycache__`) and missing `clients`, so the new guard
   test wouldn't be discovered by a bare `pytest` invocation. Fix `testpaths` to
   `["clients", "platform"]` as part of this ticket — it's the change that makes the new test's
   presence actually matter, not a drive-by unrelated to the ticket.

### Tasks

#### Task 1 — Add the regression guard test
Create `clients/tests/__init__.py` (empty) and `clients/tests/test_no_stale_imports.py`:
```python
import re
from pathlib import Path

STALE = re.compile(r"^\s*(from|import)\s+(services|shared)(\.|\s)")


def test_no_stale_service_or_shared_imports():
    offenders = []
    for path in Path(__file__).parent.parent.rglob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if STALE.match(line):
                offenders.append(f"{path}:{lineno}: {line.strip()}")
    assert not offenders, "stale services./shared. import(s):\n" + "\n".join(offenders)
```

#### Task 2 — Fix `testpaths`
`pyproject.toml`, `[tool.pytest.ini_options]`:
```
testpaths = ["clients", "platform"]
```

### Acceptance test

- `uv run pytest` (no path argument, relying on `testpaths`) discovers and passes
  `clients/tests/test_no_stale_imports.py`.
- Temporarily add `import services.account` to a scratch file under `clients/`, rerun the test,
  confirm it fails naming that file:line, then revert — do not commit the broken state.
- `just lint` / `just test` stay green.

### Docs update (mandatory when user-facing)

No user-facing surface — internal test/config only.

### Finish (mandatory)

1. Acceptance test green; `just lint`/`just test` clean.
2. No docs to update (see above).
3. Write a summary: files added, the `testpaths` fix, anything deferred.
4. Suggest a Conventional Commit message, e.g.:
   ```
   test(clients): guard against stale services./shared. imports (EXC-013)
   ```
5. Tidy WIP commits into atomic ones (root-path child).
6. Commit locally; do not push or open an MR without user approval. Verify
   `git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'` prints
   nothing before pushing. Present the commit message for approval, then push and open the
   merge request — merging is always the human's.

## Review

**Reviewer independence (step 0):** not delegated — the reviewing agent had no hand in this
branch (fresh session), so it is already independent; ran the audits directly.

**In-tree stale-branch check (step 0a):** `pickle doctor` initially warned the checked-out
branch had the ticket in `3-in-development` vs `main`'s `4-in-review`, plus a payload-version
drift (0.18.0 vs 0.19.0). Rebased `feat/EXC-013-…` onto `main`; `pickle doctor` then reported
0 errors, 0 warnings.

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | blocking | test-gap | — | New file `clients/tests/test_no_stale_imports.py` is not ruff-formatted; `ruff format --check .` (run via `just check`) fails on it. CI (`.github/workflows/ci.yaml:30`) runs `ruff format --check .`, so this branch would land a red PR. The ticket's own acceptance test lists only `just lint`/`just test`, omitting `just check`/`fmt-check` — the exact gap `development/review-addendum.md` step 2 item 3 warns about. | `just check` → `Would reformat: clients/tests/test_no_stale_imports.py`; `just lint`/`just test` alone stay green | Run `uv run ruff format clients/tests/test_no_stale_imports.py`, re-run `just check`, commit as the rework fix. |

Implementation audit (step 2): both tasks present exactly as planned (guard test at
`clients/tests/test_no_stale_imports.py`, `testpaths` fixed to `["clients", "platform"]`).
Acceptance test re-run: `uv run pytest` discovers and passes the new test (67 passed);
temporarily injected `import services.account` into a scratch file under `clients/simulator/`
and confirmed the test fails naming that file:line, then reverted (working tree clean
afterward). `just lint` and `just services-build` green. `just check` fails per F1.

Quality audit (step 3): no async-discipline, line-count, or type-hint issues — the added file
is a 13-line sync test script. Addendum's outbox-map and stateful/stateless items don't apply
(no service code touched).

Consistency audit (step 4 / 4a): no stale-xrefs found; `development/design.md`'s "intentionally
simplified" list and "Detailed architecture" section are unaffected (no data-flow change). No
user-facing docs surface, matching the ticket's own Docs update section. `services/` (removed
from `testpaths`) confirmed to hold no real test files (`git ls-files`/`find` show only a
tracked `__init__.py` and gitignored `__pycache__`), so nothing is lost by dropping it.

Impact sweep (step 8): `tickets/2-ready/EXC-015-…` depends on EXC-013 but only for its
prerequisite gate; its own scope (`[tool.setuptools.packages.find]` dropping `services*`) is
unaffected by this ticket's `testpaths` change. No assumption invalidated.

disposition summary: 1 blocking (F1, routed to rework), 0 non-blocking.

cost: estimated S, actual S

### Rework fix record — round 1 (commit a33a02a)

Note: the branch was tidied into one atomic commit before publish (§1's tidy fallback) —
`a33a02a` no longer resolves; the equivalent change is folded into the merged
`e5efc41`/`6e05679` (see History).

Fixed F1: ran `uv run ruff format clients/tests/test_no_stale_imports.py` (single-quote
project convention, `pyproject.toml`'s `[tool.ruff.format] quote-style = "single"`). `just
check` (lint + fmt-check), `just services-build`, and `uv run pytest` (67 passed) all green
afterward.

**Scoped re-review (round 1):** read the fix diff (`git show a33a02a`) — a pure quote-style
change (double → single quotes throughout the file), no semantic change, no new defects. Rebased
onto `main`; `pickle doctor` clean (0 errors, 0 warnings). Re-ran `just check` (lint + fmt-check
both pass), `uv run pytest` (67 passed), `just services-build` (green). No new findings. F1
resolved.

Final disposition summary: 1 blocking (F1, fixed in rework round 1), 0 non-blocking.

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-18 — TO DO → READY: plan complete
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
- 2026-09-18 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-09-18 — IN REVIEW → REWORK: F1 blocking: new test file fails ruff format --check
- 2026-09-18 — REWORK → IN REVIEW: F1 fixed
- 2026-09-18 — IN REVIEW → DONE: F1 fixed, scoped re-review clean
- 2026-09-18 — MERGED: PR #30, commit 6e05679
