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

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-17 — created (TO DO). source: review: EXC-001's review found `SqlAlchemyUnitOfWork`'s
  own commit/rollback state machine has no direct test coverage (test-gap, promoted to a new
  ticket rather than noted, since it is small, clearly scoped, and shared infra more services
  will build on).
