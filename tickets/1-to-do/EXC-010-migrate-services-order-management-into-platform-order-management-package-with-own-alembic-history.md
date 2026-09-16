---
id: EXC-010
title: Migrate services/order_management into platform/order_management package with own Alembic history
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-010 — Migrate services/order_management into platform/order_management package with own Alembic history

## Outcome

After this ships, `platform/order_management/` is its own installable package (own
`pyproject.toml`, version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on
`platform/base/`, with its own two-stage Dockerfile and its own independent Alembic migration
history gating its startup — instead of a subtree of the single flat install sharing the
create-on-boot bootstrap.

## Description

`EXC-003 decisions 1, 2, 3, 5`. `order_management` is stateful (`DATABASE_URL`, schema-per-service
already in code) and one of the two files already over the 200-line guideline
(`services/order_management/service.py`, `app.py` — pre-existing overage, per
`development/review-addendum.md` step 3 item 3; do not grow them further during this move). Scope:
move `services/order_management/` to `platform/order_management/src/order_management/`, give it
its own `pyproject.toml` (hatchling, `src/` layout, depends on `platform/base/`), own two-stage
Dockerfile, own versioning artifacts starting at `0.0.1`, and its own Alembic migration history
scoped to its Postgres schema, replacing its share of the create-on-boot bootstrap with an
`order_management-migrate` one-shot compose container gating startup. Depends on EXC-004
(`platform/base/` must exist first).

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
