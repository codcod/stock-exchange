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

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-18 — TO DO → READY: plan complete
