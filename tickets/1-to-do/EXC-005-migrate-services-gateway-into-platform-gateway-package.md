---
id: EXC-005
title: Migrate services/gateway into platform/gateway package
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: low
cost: S
---

# EXC-005 — Migrate services/gateway into platform/gateway package

## Outcome

After this ships, `platform/gateway/` is its own installable package (own `pyproject.toml`,
version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on `platform/base/`, with
its own two-stage Dockerfile — instead of a subtree of the single flat install.

## Description

`EXC-003 decisions 1, 3, 5`. `gateway` is stateless (no `DATABASE_URL`, per
`development/review-addendum.md` step 2 item 3) — no Alembic history applies here. Scope: move
`services/gateway/` to `platform/gateway/src/gateway/`, give it its own `pyproject.toml`
(hatchling, `src/` layout, depends on `platform/base/`), own two-stage Dockerfile replacing its
slice of the shared `infra/docker/Dockerfile`, and own versioning artifacts starting at `0.0.1`.
`gateway` has no `tests/` directory today (pre-existing gap, review-addendum step 4a item 3) —
this migration doesn't need to add one, but must not lose test coverage it doesn't have.
Depends on EXC-004 (`platform/base/` must exist first).

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
