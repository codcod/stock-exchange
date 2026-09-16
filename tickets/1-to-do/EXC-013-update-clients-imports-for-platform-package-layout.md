---
id: EXC-013
title: Update clients/ imports for platform/ package layout
project: exchange
depends-on: [EXC-005, EXC-006, EXC-007, EXC-008, EXC-009, EXC-010, EXC-011, EXC-012]
spawned-by: []
impact: low
complexity: low
cost: S
---

# EXC-013 — Update clients/ imports for platform/ package layout

## Outcome

After this ships, `clients/simulator/` and `clients/tui/` run unmodified against the fully
migrated `platform/` layout — no import still resolves against a deleted `services/*` or
`shared.platform.*` path.

## Description

`clients/` talks to services over HTTP only (per `development/design.md`'s service-boundary
note), so this is expected to be a small grep-and-fix pass rather than a real port: confirm
neither `clients/simulator/main.py` nor `clients/tui/{api.py,config.py,models.py}` imports
anything from `services.*` or the old `shared.platform.*`/`shared.domain.*` paths that moved
during EXC-004–EXC-012, and fix whatever does. Depends on every service migration ticket
(EXC-005–EXC-012) being done, since only then are the old paths actually gone and the check
meaningful.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
