---
id: EXC-004
title: Extract platform/base and set up uv workspace for platform/ restructuring
project: exchange
depends-on: []
spawned-by: []
impact: high
complexity: medium
cost: M
---

# EXC-004 — Extract platform/base and set up uv workspace for platform/ restructuring

## Outcome

After this ships, the repo root is a `uv` workspace, and `platform/base/` is its own installable
package holding shared config, DB engine, HTTP client, request context, and any Repository/UoW
base classes (EXC-001, if landed) — the dependency every later `platform/<service>/` package
declares instead of importing loose top-level `shared/` modules.

## Description

`EXC-003 decision 1`: the workspace becomes a `uv` workspace with `platform/<service>/` packages
plus one shared `platform/base/` package. This ticket is the foundational step — no service moves
yet (that's EXC-005 through EXC-012, one per service).

Scope: convert root `pyproject.toml` to a `uv` workspace (`[tool.uv.workspace]`), create
`platform/base/` as an installable package (own `pyproject.toml`, hatchling, `src/` layout) and
move `shared/platform/{db,http_client.py,request_context.py,clients/}` into it. Decide, during
refinement, where `shared/domain/{models.py,events.py,api_schemas.py}` land — these are also
cross-service but decision 1's wording only names config/DB/HTTP-client/request-context/UoW
explicitly, so this needs an explicit confirmed-decision entry rather than assuming they fold into
`platform/base/` too. No service code moves into `platform/<name>/` in this ticket; every
service still imports the old `shared.platform.*` paths until its own migration ticket lands
(EXC-005–EXC-012 each depend on this one).

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
