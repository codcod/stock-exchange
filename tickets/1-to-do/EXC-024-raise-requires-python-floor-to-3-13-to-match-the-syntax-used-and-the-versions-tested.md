---
id: EXC-024
title: Raise requires-python floor to 3.13 to match the syntax used and the versions tested
project: exchange
depends-on: []
spawned-by: []
impact: low
complexity: low
cost: S
---

# EXC-024 — Raise requires-python floor to 3.13 to match the syntax used and the versions tested

## Outcome

After this ships, installing any exchange package on Python 3.11 or 3.12 is refused up front
by the resolver, instead of succeeding and then failing with a `SyntaxError`/`ImportError` the
first time `base.repository` or `base.unit_of_work` is imported.

## Description

Every `pyproject.toml` in the repo (the root plus all ten `platform/*` members) declares
`requires-python = ">=3.11"`, but the code does not run on 3.11:

- `platform/base/src/base/repository.py` uses PEP 695 generic class syntax
  (`class AbstractRepository[T]`), a `SyntaxError` before 3.12.
- `platform/base/src/base/unit_of_work.py`, `platform/account/src/account/unit_of_work.py` and
  `platform/order_management/src/order_management/unit_of_work.py` use `typing.override`,
  added in 3.12.

Nothing actually runs below 3.13: every service `Dockerfile` builds on
`ghcr.io/astral-sh/uv:python3.13-bookworm-slim`, both CI workflows
(`.github/workflows/ci-repo.yml`, `service-ci.yml`) test a `["3.13", "3.14"]` matrix, and the
local `.venv` is 3.14. `[tool.ruff] target-version = "py312"` in the root `pyproject.toml` is a
third, different number.

Proposed fix: raise the floor to what is built and tested, `requires-python = ">=3.13"` in all
eleven `pyproject.toml` files, set ruff's `target-version = "py313"`, and re-lock `uv.lock`.
No upper bound, since CI already tests 3.14. 3.13 also matches the floor of the monolith's
`stelo-base` and porth's design (§4.6), which matters for a shared base library being
considered across the three projects.

Soft coupling: EXC-002 (add `ty` to lint/CI) type-checks against a Python version; if it lands
first, its configured version should follow this floor.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-27 — created (TO DO). source: chat: declared floor >=3.11 found below the 3.12 syntax in `base` during a cross-repo shared-library review
