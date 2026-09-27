---
id: EXC-025
title: Replace base's repository, unit-of-work and migration copies with monobase
project: exchange
depends-on: [EXC-024]
spawned-by: []
impact: medium
complexity: low
cost: S
---

# EXC-025 — Replace base's repository, unit-of-work and migration copies with monobase

## Outcome

After this ships, stock-exchange's services get `AbstractRepository`, the unit-of-work bases and
the Alembic migration runner from the tagged `monobase` release shared with monolith and
porth, instead of from their own copies in `platform/base`.

## Description

`platform/base/src/base/repository.py` and `unit_of_work.py` match monolith's `stelo-base`
line for line, and `db/migrations.py` differs only in taking the DSN from `get_engine()`. The
shared `monobase` library (design:
`umbrella-org/monolith-umbrella/development/monobase/design.md` 1.3, §5; the library was first
shipped as `monolith-base` and renamed) now holds them.

Change: `base` depends on `monobase`, pinned with the tag-archive URL source (design
§4.4, no `git` needed in the Dockerfile builder stage). The imports switch to
`monobase.repository`, `monobase.unit_of_work` and `monobase.migrations`. That
covers `account` and `order_management` unit of work, their repositories, and every
`migrations/env.py`, which now pass the DSN explicitly. `base/repository.py`,
`base/unit_of_work.py` and `base/db/migrations.py` are deleted, along with
`base/tests/test_unit_of_work.py`, which moves to the library. `base.db.connection.get_engine()`
stays as the cached `DATABASE_URL` reader, but builds the engine with `monobase.db.make_engine`.
`base/db/tables.py::ensure_tables` is already unused (the base README says so) and is deleted.
`platform/base/README.md` is updated.

Out of scope: `metrics`, `http_client`, `request_context`, `domain`, `clients` stay in `base`
(design §3.3). The outbox copies wait for monobase's outbox extra (MB-002 on the
monolith-umbrella board).

Prerequisites: EXC-024 (hard, same board). `uv` can't resolve a `>=3.13` dependency from
packages declaring `>=3.11`. Cross-board: `monobase` `v0.1.0` must be tagged
(monolith-umbrella MB-003, which re-cuts it under the new name). pickle can't express that as `depends-on:`, so check it at
pickup.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-27 — created (TO DO). source: chat: consumer migration from monolith-base design.md 1.0 §5
- 2026-09-27 — Description: the library is renamed `monolith-base` → `monobase` (monolith-umbrella design 1.3); the tag gate moves to MB-003. source: chat: user decision.
