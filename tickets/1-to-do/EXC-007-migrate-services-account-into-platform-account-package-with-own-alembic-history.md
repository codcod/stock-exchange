---
id: EXC-007
title: Migrate services/account into platform/account package with own Alembic history
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-007 — Migrate services/account into platform/account package with own Alembic history

## Outcome

After this ships, `platform/account/` is its own installable package (own `pyproject.toml`,
version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on `platform/base/`, with
its own two-stage Dockerfile and its own independent Alembic migration history gating its startup
— instead of a subtree of the single flat install sharing the create-on-boot bootstrap.

## Description

`EXC-003 decisions 1, 2, 3, 5`. `account` is stateful (`DATABASE_URL`, schema-per-service already
in code via `services/account/tables.py`'s `schema=...`). Scope: move `services/account/` to
`platform/account/src/account/`, give it its own `pyproject.toml` (hatchling, `src/` layout,
depends on `platform/base/`), own two-stage Dockerfile, own versioning artifacts starting at
`0.0.1`, and its own Alembic migration history scoped to its Postgres schema, replacing its share
of `shared/platform/db/tables.py:25`'s `CREATE SCHEMA IF NOT EXISTS` bootstrap with an
`account-migrate` one-shot compose container gating startup. Depends on EXC-004 (`platform/base/`
must exist first).

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
