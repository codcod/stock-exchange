---
id: EXC-002
title: Add static type-checking (ty) to lint pipeline and CI
project: exchange
depends-on: []
spawned-by: []
impact: medium
complexity: low
cost: S-M
---

# EXC-002 — Add static type-checking (ty) to lint pipeline and CI

## Outcome

After this ships, `just lint` (and CI) fails when a service's type hints are wrong or missing,
instead of the `import typing as tp` convention (`CLAUDE.md`) being enforced only by code review.

## Description

`CLAUDE.md` mandates `import typing as tp` (`tp.Optional`, `tp.List`, …) across the codebase, but
nothing mechanically checks it — `just lint` only runs `ruff check .`, which has no type-checking
rules enabled, and there is no mypy/pyright config anywhere in the repo. `development/review-addendum.md`
already flags this as an unenforced convention (step 3, item 2): "a wrong or missing annotation is
`class: design`, never blocking on its own" — precisely because nothing catches it today.

A reference project (`~/Projects/private/monolith`) uses `ty` (Astral's type checker, same
toolchain family as `ruff`) scoped to each module's `src/` only — never `tests/`, since test
doubles/fakes are loose by design and shouldn't be forced to type-check against real classes
(`root pyproject.toml`'s `[tool.ty.environment] root = [...]`).

Scope for this ticket: add `ty` (or evaluate mypy if `ty` proves too immature for this codebase's
patterns — e.g. SQLAlchemy Core's dynamic `Table`/`Column` typing) to `pyproject.toml`, wire it
into `just lint`, scoped to `services/*/`, `platform/`, and `clients/` but excluding every `tests/`
directory. Fix whatever violations turn up across the eight services — expect the fix-existing-
violations pass to be the larger, harder-to-estimate part of this ticket, which is why cost is
graded as a range rather than a single value pending that discovery.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — Description corrected: scope `shared/` → `platform/` (EXC-004 impact sweep —
  `shared/` no longer exists post-EXC-004).
