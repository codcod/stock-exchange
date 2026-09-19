---
id: EXC-023
title: Add PACKAGING.md/RELEASING.md/CHANGELOG.md to platform/admin/
project: exchange
depends-on: []
spawned-by: [EXC-022]
impact: low
complexity: low
cost: S
---

# EXC-023 — Add PACKAGING.md/RELEASING.md/CHANGELOG.md to platform/admin/

## Outcome

After this ships, `platform/admin/` carries the same `PACKAGING.md`, `RELEASING.md`, and
`CHANGELOG.md` triple every other `platform/*` installable service package already ships,
closing the one docs gap EXC-022's review found.

## Description

EXC-022 added `platform/admin/` as a new installable package (own `pyproject.toml`, own
Dockerfile, own port) — a peer to `account`, `clearing`, `gateway`, `market_data`,
`matching_engine`, `notifications`, `order_management`, and `risk_engine`. All eight of those
ship a `PACKAGING.md` + `RELEASING.md` + `CHANGELOG.md` triple (the project's review addendum,
`development/review-addendum.md`, names this triple explicitly as part of the shipped docs
tree its step 4a sweep audits); `platform/admin/` shipped none of the three.

Write admin's own triple following the existing pattern verbatim — e.g.
`platform/clearing/PACKAGING.md`/`RELEASING.md`/`CHANGELOG.md` — adapted for admin's own
specifics (no Alembic migration history, unlike every stateful sibling; `admin-vX.Y.Z` tag
convention; `[0.0.1]` changelog entry crediting EXC-022 as the extraction/creation source, the
same way `platform/clearing/CHANGELOG.md`'s `[0.0.1]` entry credits EXC-011).

Not part of EXC-022 itself — the review scoped it out as a small, mechanical, zero-risk
addition better done as its own ticket than folded into that review pass (rules §5, `docs-gap`,
disposition: new ticket).

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-19 — created (TO DO). source: pickle ticket new
