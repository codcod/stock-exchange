---
id: EXC-014
title: Restructure justfile and CI into per-service mod-imported recipes and path-filtered reusable workflow
project: exchange
depends-on: [EXC-005, EXC-006, EXC-007, EXC-008, EXC-009, EXC-010, EXC-011, EXC-012]
spawned-by: []
impact: medium
complexity: medium
cost: M
---

# EXC-014 — Restructure justfile and CI into per-service mod-imported recipes and path-filtered reusable workflow

## Outcome

After this ships, the root `justfile` only `mod`-imports each `platform/<service>/justfile`, and
CI is one reusable GitHub Actions workflow called by a thin per-service workflow file, path-
filtered so a service's CI only runs when that service (or `platform/base`, or the workspace
lockfile) changes — instead of one flat `justfile` and one `.github/workflows/ci.yaml` running
everything on every push.

## Description

`EXC-003 decision 4`. Scope: give each `platform/<service>/` its own `justfile` (build/test/lint
recipes scoped to that package), have the root `justfile` `mod`-import all of them, and replace
`.github/workflows/ci.yaml` with one reusable workflow plus a thin per-service caller workflow,
path-filtered on `platform/<service>/**`, `platform/base/**`, and the workspace lockfile. Depends
on every service migration ticket (EXC-005–EXC-012) — there is nothing to path-filter or `mod`-
import until each service package and its own justfile exist.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
