---
id: EXC-006
title: Migrate services/market_data into platform/market_data package
project: exchange
depends-on: [EXC-004]
spawned-by: []
impact: medium
complexity: low
cost: S
---

# EXC-006 — Migrate services/market_data into platform/market_data package

## Outcome

After this ships, `platform/market_data/` is its own installable package (own `pyproject.toml`,
version `0.0.1`, `CHANGELOG.md`/`PACKAGING.md`/`RELEASING.md`) depending on `platform/base/`, with
its own two-stage Dockerfile — instead of a subtree of the single flat install.

## Description

`EXC-003 decisions 1, 3, 5`. `market_data` is stateless and in-memory-only (no `DATABASE_URL`,
per `development/review-addendum.md` step 2 item 3) — no Alembic history applies here. Scope: move
`services/market_data/` to `platform/market_data/src/market_data/`, give it its own
`pyproject.toml` (hatchling, `src/` layout, depends on `platform/base/`), own two-stage Dockerfile
replacing its slice of the shared `infra/docker/Dockerfile`, and own versioning artifacts starting
at `0.0.1`. Depends on EXC-004 (`platform/base/` must exist first).

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
