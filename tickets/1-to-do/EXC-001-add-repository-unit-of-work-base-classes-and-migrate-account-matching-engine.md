---
id: EXC-001
title: Add Repository/Unit-of-Work base classes and migrate account + matching_engine
project: exchange
depends-on: []
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-001 — Add Repository/Unit-of-Work base classes and migrate account + matching_engine

## Outcome

After this ships, a developer touching `account` or `matching_engine` writes transactional
persistence code against one shared `AbstractUnitOfWork`/`AbstractRepository` pair instead of
each service hand-rolling its own commit/rollback split, and a forgotten `commit()` rolls back
safely by default instead of silently doing nothing.

## Description

Every stateful service currently manages its own transactions ad hoc. `services/account/repository.py`
is the clearest example: `AccountRepository.save()` opens its own `engine.begin()` transaction,
while `save_with_conn()` takes a borrowed connection for callers that need to join an existing
transaction — the same split, hand-written per repository, with no shared base class and no
guaranteed rollback-on-forgotten-commit.

This mirrors a pattern already proven in a reference project
(`~/Projects/private/monolith`, `stelo-base/src/stelo/base/unit_of_work.py`): an
`AbstractUnitOfWork` ABC as an async context manager whose `__aexit__` always calls `rollback()`
(so a forgotten `commit()` is safe-by-default, not a silent no-op), and an `AbstractRepository[T]`
port with just `add`/`get`. Each service subclasses the UoW purely to attach its own concrete
repository in `__aenter__` — no generic SQLAlchemy repository is shared, since each service's row
shape differs.

Scope for this ticket: add `AbstractRepository`/`AbstractUnitOfWork` (plus a
`SqlAlchemyUnitOfWork` base) to `platform/base/`, then migrate `services/account/` and
`services/matching_engine/` — the two services with the most multi-table transactional writes —
to use them. Other services (`order_management`, `risk_engine`, `clearing`, `notifications`) are
explicitly out of scope here; migrate them in a follow-up once this pattern has proven itself on
two real services.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — Description corrected: target path `shared/platform/` → `platform/base/`
  (EXC-004 impact sweep — `shared/` no longer exists post-EXC-004).
