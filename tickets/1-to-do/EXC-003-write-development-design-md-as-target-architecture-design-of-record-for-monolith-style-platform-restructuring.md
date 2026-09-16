---
id: EXC-003
title: Write development/design.md as target-architecture design of record for monolith-style platform/ restructuring
project: exchange
depends-on: []
spawned-by: []
impact: high
complexity: medium
cost: M
---

# EXC-003 — Write development/design.md as target-architecture design of record for monolith-style platform/ restructuring

## Outcome

After this ships, `development/design.md` is the single design of record for exchange's target
architecture — a `uv` workspace of independently-versioned service packages under `platform/`,
mirroring a reference project — and `CLAUDE.md` is reduced to the pickle marker plus a pointer to
it, the same shape the reference project uses (short README-style pointer, one deep design doc).
Every later migration ticket (platform/base extraction, per-service package moves, Alembic,
Docker, CI, versioning) is written against decisions this document pins down, not invented ad hoc
per ticket.

## Description

exchange currently ships as one flat repo: a single root `pyproject.toml` (`setuptools`, one
version `0.1.0`, `services*`/`shared*`/`clients*` all one install), one shared `Dockerfile` with
`CMD` overridden per service in compose, no migration history (`shared/platform/db/tables.py:25`
issues `CREATE SCHEMA IF NOT EXISTS` and tables are created at boot), and one flat
`.github/workflows/ci.yaml`. `CLAUDE.md` carries the real project conventions and is auto-loaded
by Claude Code every session; `AGENTS.md` currently holds only the pickle marker (no project
content of its own yet).

The target, decided in conversation (2026-09-16), full parity with the reference project
(`~/Projects/private/monolith`):

1. **Workspace.** Convert to a `uv` workspace. Each service becomes its own installable package
   under `platform/<service-name>/` (own `pyproject.toml`, hatchling, `src/` layout, own version,
   starting at `0.0.1` each per the reference project's convention), depending on a shared
   `platform/base/` package (the `shared/` extraction — config, DB engine, HTTP client,
   request context, and the new Repository/UoW base classes from EXC-001, if that lands first).
   Services already never import each other directly (HTTP-only, per `CLAUDE.md`'s existing
   convention) — cross-service Python imports do not need to be invented, only removed from the
   shared install and pointed at `platform/base` instead.
2. **Migrations.** Add Alembic to each of the 6 stateful services, one independent history per
   service, version table scoped to that service's own Postgres schema (schema-per-service
   already exists in code — `services/*/tables.py` already pass `schema=...` — only the migration
   history itself is missing). A `<service>-migrate` one-shot compose container per stateful
   service, gating that service's startup, replacing the current create-on-boot bootstrap.
3. **Docker/compose.** One Dockerfile per service package (two-stage: `uv`-based builder,
   distroless runtime, non-root), replacing the single shared `infra/docker/Dockerfile`.
4. **justfile/CI.** Root `justfile` using `mod` imports for per-service recipes, each service
   package carrying its own `justfile`; one reusable GitHub Actions workflow parameterized per
   package, called by a thin per-service workflow file, path-filtered so a service's CI only runs
   when that service (or `platform/base`, or the workspace lockfile) changes.
5. **Versioning/release.** Per-service independent SemVer, own `CHANGELOG.md` (Keep a Changelog
   format) and release tags (`<service>-vX.Y.Z`) per service, each service carrying its own
   `PACKAGING.md` (why `src/`-layout + implicit namespace package, if applicable) and
   `RELEASING.md` (the manual release procedure). This supersedes — do not also wire up — the
   existing unused single-repo `[tool.semantic_release]` block in the current root
   `pyproject.toml`; note in this doc that it should be removed once each service has its own
   versioning story, and record which ticket removes it.
6. **Docs.** `CLAUDE.md` is emptied to the pickle marker plus a one-line pointer to
   `development/design.md` (literal parity with the reference project, which carries no
   CLAUDE.md/AGENTS.md content of its own at all). `AGENTS.md` is unaffected (still marker-only).
   `docs/architecture.md` and `docs/lob_concepts_review.md` fold into `design.md` — decide in this
   ticket's Implementation Plan whether they become sections of `design.md` or stay separate and
   are merely linked from it (the reference project's `design.md` is a single prose document, no
   sub-files).

This ticket's own deliverable is **only the document** (plus the `CLAUDE.md` edit) — no code
moves. It should be concrete enough that EXC-004 onward (`platform/base` extraction, one ticket
per service migrating into `platform/<name>/`, `clients/` import updates, Docker/compose rewrite,
Alembic, justfile/CI restructuring, per-service versioning) can each be filed and refined by
reading this document alone, without re-litigating any of the six decisions above. File those as
separate tickets once this one is done — do not fold them into this one's scope.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
