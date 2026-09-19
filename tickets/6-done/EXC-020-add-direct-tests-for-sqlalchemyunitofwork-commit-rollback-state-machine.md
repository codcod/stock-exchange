---
id: EXC-020
title: Add direct tests for SqlAlchemyUnitOfWork commit/rollback state machine
project: exchange
depends-on: []
spawned-by: [EXC-001]
impact: low
complexity: low
cost: S
---

# EXC-020 — Add direct tests for SqlAlchemyUnitOfWork commit/rollback state machine

## Outcome

After this ships, `platform/base/src/base/unit_of_work.py`'s own commit/rollback state
machine — the "a forgotten `commit()` rolls back instead of silently doing nothing"
guarantee that EXC-001 was built to provide — has a direct test asserting it, instead of
being exercised only indirectly through `Fake*UnitOfWork` doubles that bypass
`SqlAlchemyUnitOfWork` entirely.

## Description

EXC-001 added `AbstractUnitOfWork`/`SqlAlchemyUnitOfWork` to `platform/base/` and migrated
`account`/`order_management` onto it, but `platform/base/` has no `tests/` directory and
neither service's tests instantiate the real `SqlAlchemyUnitOfWork` — both use
`Fake*UnitOfWork(AbstractUnitOfWork)` doubles (per EXC-001 decision 8) whose `commit`/
`rollback` just flip a flag. That is deliberate and correct for service-level tests, but it
means the actual state machine in `SqlAlchemyUnitOfWork.__aexit__`/`commit`/`rollback` — the
`_committed` flag that makes `rollback()` a no-op after a real `commit()`, and the
unconditional-rollback-on-exit behaviour itself — has never been exercised by any test in the
repo.

No real database is needed to close this gap: a fake `AsyncEngine`/`AsyncConnection`/
`AsyncTransaction` triple (recording whether `.commit()`/`.rollback()` was called) is enough to
drive `SqlAlchemyUnitOfWork` through its real `__aenter__`/`commit`/`__aexit__` path and assert:
normal exit after `commit()` does not roll back; exit without `commit()` (falling off the end of
the block, or an exception) does roll back; and `rollback()` is never called twice. A new
`platform/base/src/base/tests/test_unit_of_work.py` is the natural home, matching every other
module's own `tests/` convention.

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd .
git checkout main
git checkout -b feat/EXC-020-uow-state-machine-tests
```

Root-path child (`path = "."`): tidy WIP commits into atomic ones before presenting; the user
chooses squash vs. keeping tidied history at approval.

### Prerequisite gate (hard)

None — no `depends-on:`, clean pickup.

### Confirmed design decisions (do not deviate without asking)

1. **No real database.** Drive `SqlAlchemyUnitOfWork` with hand-rolled fake
   `AsyncEngine`/`AsyncConnection`/`AsyncTransaction` doubles that record whether `.commit()`/
   `.rollback()` was called, matching the fake-double style already used in every service's own
   `tests/` (e.g. `platform/account/src/account/tests/test_service.py`'s `_FakeConn`) rather than
   introducing a mocking library or a real Postgres fixture.
2. **New `tests/` package, not a bare test file.** `platform/base/src/base/tests/` gets an
   `__init__.py` alongside `test_unit_of_work.py`, matching the package convention every other
   service's `tests/` directory uses (they are packages, not implicit namespace dirs).
3. **Rely on the workspace's existing pytest-asyncio config.** Root `pyproject.toml`'s
   `[tool.pytest.ini_options]` already sets `asyncio_mode = "auto"`; no per-file marker or
   `platform/base/pyproject.toml` change is needed for `async def test_*` functions to run.

### Tasks

#### Task 1 — Add the `tests/` package
Create `platform/base/src/base/tests/__init__.py` (empty), mirroring every service's own
`tests/` package.

#### Task 2 — Write the fake engine/connection/transaction triple
In `platform/base/src/base/tests/test_unit_of_work.py`, define minimal fakes standing in for
`AsyncEngine`, `AsyncConnection`, and `AsyncTransaction`:
- `FakeTransaction`: records `committed: bool` and `rollback_calls: int` on `.commit()` /
  `.rollback()`.
- `FakeConnection`: `.begin()` returns a `FakeTransaction`; `.close()` records it was called.
- `FakeEngine`: `.connect()` returns a `FakeConnection`.

#### Task 3 — Test: commit then normal exit does not roll back
`async with SqlAlchemyUnitOfWork(FakeEngine()) as uow: await uow.commit()` — after the block
exits, assert the transaction's `rollback_calls == 0` and `committed is True`, and the
connection's `.close()` was called.

#### Task 4 — Test: exit without commit rolls back (falls off the end of the block)
Same setup, but do not call `uow.commit()` inside the block. After exit, assert
`rollback_calls == 1` and `committed is False`.

#### Task 5 — Test: exit via exception rolls back
```python
with pytest.raises(ValueError):
    async with SqlAlchemyUnitOfWork(FakeEngine()) as uow:
        raise ValueError("boom")
```
Assert `rollback_calls == 1` on the transaction — `__aexit__` rolls back even when the body
raised.

#### Task 6 — Test: rollback is never called twice
Directly exercise the `_committed` guard: enter the context, call `await uow.commit()`, then
call `await uow.rollback()` explicitly (simulating a caller that commits and then also hits the
`__aexit__` unconditional rollback). Assert the fake transaction's `rollback_calls == 0` — the
`_committed` flag in `SqlAlchemyUnitOfWork.rollback()` (`unit_of_work.py`, the `if not
self._committed:` guard) must have short-circuited it.

### Acceptance test

`just test` (root) — or the package-scoped `cd platform/base && uv run --package base pytest .`
— collects and passes the four new tests in
`platform/base/src/base/tests/test_unit_of_work.py`, with no other test in the repo affected.
`just lint` clean.

### Docs update (mandatory when user-facing)

No user-facing surface — this adds test coverage only, no behaviour or public API change.

### Finish (mandatory)

1. Acceptance test green; `just lint` clean.
2. Write a summary: the new file, the four cases covered, and confirm no existing test's
   `Fake*UnitOfWork` doubles needed to change.
3. Suggested commit message:
   ```
   test(base): add direct tests for SqlAlchemyUnitOfWork commit/rollback state machine (EXC-020)

   Exercises the real __aenter__/commit/__aexit__ path via fake AsyncEngine/
   AsyncConnection/AsyncTransaction doubles: commit-then-exit doesn't roll back,
   exit without commit (falling off the end, or an exception) does, and rollback
   is never called twice.
   ```
4. Root-path child: tidy WIP commits into atomic ones before presenting.
5. Commit locally on the ticket branch; do not push or open an MR without user approval.
   `pickle ticket move EXC-020 in-review --reason "acceptance green"` and hand back.

## Review

- [x] Reviewer independence settled (step 0): the orchestrating reviewer authored this branch
  in this session, so audits (steps 2–4a) were **delegated** to a fresh sub-agent, briefed
  adversarially with no memory of writing the code; findings re-verified by hand before
  recording.
- [x] In-tree stale-branch check (step 0a): branch was stale (`pickle doctor` warned it held
  the ticket at "3-in-development" while `main` had "4-in-review"); rebased onto `main`,
  re-ran `pickle doctor` — clean.
- [x] Implementation audit — acceptance test re-run (`just test`: 71 passed, all 4 new tests
  green); all 6 tasks done in the named files; all 3 confirmed design decisions honoured (fake
  triple matches `_FakeConn` style, `tests/` is a package with `__init__.py`, no per-file
  asyncio marker added).
- [x] Quality audit — `just lint` clean (no `PLR09xx`/`C901` hits); `just check` clean (`ruff
  format --check .`: 135 files already formatted, no drift). Tests exercise the real
  `__aenter__`/`commit`/`__aexit__` path, not tautological.
- [x] Consistency audit — new test file's naming/style/imports match sibling test files (e.g.
  `platform/account/src/account/tests/test_service.py`); no duplicated fake-double logic
  elsewhere in the repo; fakes' method signatures match exactly what `unit_of_work.py` calls.
- [x] Documentation audit — ticket's "no user-facing surface" claim verified true: branch
  touches zero production files; no shipped doc (`README.md`, `platform/base/README.md`, any
  `PACKAGING.md`) references `UnitOfWork`; `development/design.md`'s "What's intentionally
  simplified" section lists nothing related to the commit/rollback mechanism.
- [ ] Docs-readability pass — n/a, no `.adoc`/`.md` files changed by this branch.

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | non-blocking | test-gap | note and close | `SqlAlchemyUnitOfWork.rollback()`'s `_committed` guard only prevents a rollback *after* a real commit; it does not guard against `rollback()` being called twice while still uncommitted (e.g. an explicit `rollback()` followed by `__aexit__`'s own unconditional rollback) — that path fires `transaction.rollback()` twice and is untested. Not a plan deviation: Task 6 only specified the commit-then-rollback case, which the new test covers correctly. | `platform/base/src/base/unit_of_work.py:65-70`; no caller in the repo currently calls `rollback()` explicitly before exiting the block, so this is latent, not exercised in production | Note and close — no current caller hits it; revisit with a guard (`_committed or _rolled_back`) and a test if a future service calls `rollback()` explicitly inside the block. |

Disposition summary: 1 finding (F1), non-blocking, disposition **note and close**. No tickets spawned.

cost: estimated S, actual S

## History

- 2026-09-17 — created (TO DO). source: review: EXC-001's review found `SqlAlchemyUnitOfWork`'s
  own commit/rollback state machine has no direct test coverage (test-gap, promoted to a new
  ticket rather than noted, since it is small, clearly scoped, and shared infra more services
  will build on).
- 2026-09-18 — refined: re-verified Description against current `unit_of_work.py` (unchanged
  since filing); added the Implementation Plan.
- 2026-09-18 — TO DO → READY: plan complete
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
- 2026-09-18 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-09-18 — IN REVIEW → DONE: reviewed: 1 non-blocking finding (F1, test-gap), disposition note-and-close
- 2026-09-18 — EXC-020 PR #36 opened
- 2026-09-18 — merged to main (PR #36, f6dc2af)
