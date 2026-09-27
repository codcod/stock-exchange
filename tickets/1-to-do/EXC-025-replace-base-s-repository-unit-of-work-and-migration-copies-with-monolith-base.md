---
id: EXC-025
title: Replace base's repository, unit-of-work and migration copies with monolith-base
project: exchange
depends-on: [EXC-024]
spawned-by: []
impact: medium
complexity: low
cost: S
---

# EXC-025 — Replace base's repository, unit-of-work and migration copies with monolith-base

## Outcome

After this ships, stock-exchange's services get `AbstractRepository`, the unit-of-work bases and
the Alembic migration runner from the tagged `monolith-base` release shared with monolith and
porth, instead of from their own copies in `platform/base`.

## Description

`platform/base/src/base/repository.py` and `unit_of_work.py` match monolith's `stelo-base`
line for line, and `db/migrations.py` differs only in taking the DSN from `get_engine()`. The
shared `monolith-base` library (design:
`umbrella-org/monolith-umbrella/development/monolith-base/design.md` 1.0, §5) now holds them.

Change: `base` depends on `monolith-base`, pinned with the tag-archive URL source (design
§4.4, no `git` needed in the Dockerfile builder stage). The imports switch to
`monolith_base.repository`, `monolith_base.unit_of_work` and `monolith_base.migrations`. That
covers `account` and `order_management` unit of work, their repositories, and every
`migrations/env.py`, which now pass the DSN explicitly. `base/repository.py`,
`base/unit_of_work.py` and `base/db/migrations.py` are deleted, along with
`base/tests/test_unit_of_work.py`, which moves to the library. `base.db.connection.get_engine()`
stays as the cached `DATABASE_URL` reader, but builds the engine with `monolith_base.db.make_engine`.
`base/db/tables.py::ensure_tables` is already unused (the base README says so) and is deleted.
`platform/base/README.md` is updated.

Out of scope: `metrics`, `http_client`, `request_context`, `domain`, `clients` stay in `base`
(design §3.3). The outbox copies wait for monolith-base's outbox extra (MB-002 on the
monolith-umbrella board).

Prerequisites: EXC-024 (hard, same board). `uv` can't resolve a `>=3.13` dependency from
packages declaring `>=3.11`. Cross-board: `monolith-base` `v0.1.0` must be tagged
(monolith-umbrella MB-001). pickle can't express that as `depends-on:`, so check it at
pickup.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-27 — created (TO DO). source: chat: consumer migration from monolith-base design.md 1.0 §5
