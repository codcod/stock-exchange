---
id: EXC-015
title: Remove dead root-level tooling after platform/ split (root Dockerfile, semantic_release block, aggregate pyproject deps)
project: exchange
depends-on: [EXC-005, EXC-006, EXC-007, EXC-008, EXC-009, EXC-010, EXC-011, EXC-012, EXC-013, EXC-014]
spawned-by: []
impact: low
complexity: low
cost: S
---

# EXC-015 — Remove dead root-level tooling after platform/ split (root Dockerfile, semantic_release block, aggregate pyproject deps)

## Outcome

After this ships, the root of the repo carries no tooling superseded by the `platform/` split:
no root `infra/docker/Dockerfile`, no `[tool.semantic_release]` block in the root
`pyproject.toml`, no aggregate `services*`/`shared*`/`clients*` package-find config for
dependencies that now live in per-service packages.

## Description

`EXC-003 decision 5` names the root `pyproject.toml`'s `[tool.semantic_release]` block (already
unused before the split, doubly dead after — see EXC-003's review finding F2) as superseded once
each service has its own versioning story; this ticket is that removal. Scope: delete the root
`infra/docker/Dockerfile` (each service now has its own, EXC-005–EXC-012), remove
`[tool.semantic_release*]` from root `pyproject.toml`, and drop the now-empty `[tool.setuptools.
packages.find]` aggregate config once nothing at the root imports `services.*`/`shared.*`/
`clients.*` directly anymore. Depends on every migration and restructuring ticket
(EXC-005–EXC-014) — this is the final cleanup pass, only safe once nothing at the root still
needs what it removes.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
