---
id: EXC-002
title: Add static type-checking (ty) to lint pipeline and CI
project: exchange
depends-on: []
spawned-by: []
impact: medium
complexity: low
cost: M
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

`ty` is already a dev dependency (`[dependency-groups].dev` in root `pyproject.toml`,
`ty>=0.0.37`) but unconfigured and unwired — it proved mature enough for this codebase; the
mypy fallback isn't needed. Discovery during refinement (`uv run ty check services platform
clients --exclude "**/tests/**"`, with the `tui` extra installed — see decision 1 below) found
**39 real diagnostics** across 12 files, all in three concrete, mechanical patterns (no
SQLAlchemy Core `Table`/`Column` issues surfaced); see the Confirmed design decisions and
Tasks below. This collapses the cost range to a single value.

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-002-add-static-type-checking-ty-to-lint-pipeline-and-ci
```

Work and commit locally per the project's commit policy (`exchange` is a root-path child —
tidy WIP commits into atomic ones before presenting; no push/MR without explicit user
approval).

### Prerequisite gate (hard)

None. `depends-on: []`.

### Confirmed design decisions (do not deviate without asking)

1. **`ty` needs the `tui` extra installed to check `clients/tui/` without false positives.**
   `uv sync --extra dev` alone leaves `textual`/`rich` uninstalled (they're behind
   `[project.optional-dependencies].tui`), which makes `ty` report 45 spurious
   `unresolved-import` diagnostics for every `textual`/`rich` import in `clients/tui/`. Both
   `just install` and the CI lint job must sync `--extra dev --extra tui` from now on.
2. **No `[tool.ty...]` pyproject config section** — the reference monorepo's own
   `[tool.ty.environment]` only tunes cross-module import *resolution* roots for its per-module
   `ty check src` invocations (each module's own `justfile`); it does not configure test
   exclusion (that's `[tool.pyright]` there, unused here). Since `exchange` has one root
   `justfile` (decision 4/EXC-014 hasn't split it yet) and services keep `tests/` *nested
   inside* the service directory (not a sibling of a `src/` root), the simplest correct
   scoping is a CLI `--exclude` glob on a single invocation covering all three top-level trees:
   `uv run ty check services platform clients --exclude "**/tests/**"`. Confirmed working
   during discovery (excludes `platform/market_data/src/market_data/tests/` and every other `tests/` dir with
   zero config).
3. **Fix pattern A — Optional module-level service singleton, unguarded in route handlers**
   (29 of the 39 diagnostics, 6 files: `platform/{account,market_data}/src/*/app.py` and
   `services/{clearing,notifications,order_management,risk_engine}/app.py`). Each service's `_AppState` dataclass holds its
   dependency as `tp.Optional[X] = None`, populated once in the `lifespan` startup hook, then
   read unguarded (`_state.svc.foo(...)`) in every route handler — `ty` can't see across that
   boundary, and it's a real (if practically-always-false) crash risk if a handler ever ran
   before/after the lifespan window. Fix: add one small module-level narrowing accessor per
   optional field, and call it instead of the raw attribute at every read site — e.g. in
   `platform/account/src/account/app.py`:
   ```python
   def _svc() -> AccountService:
       assert _state.svc is not None, 'service not initialized'
       return _state.svc

   def _risk() -> RiskEngineClient:
       assert _state.risk is not None, 'risk client not initialized'
       return _state.risk
   ```
   then replace `_state.svc.` → `_svc().` and `_state.risk.` → `_risk().` at each call site.
   Same pattern, one accessor per optional field, in the other five files.
4. **Fix pattern B — `db: object = None` hides the real engine type** (2 files:
   `services/order_management/app.py`, `services/matching_engine/app.py`). `object` was used
   as a placeholder type for the lazily-created SQLAlchemy engine; `base.db.connection.
   get_engine() -> AsyncEngine` is the real type. Fix: retype the field
   `tp.Optional[AsyncEngine] = None` (`from sqlalchemy.ext.asyncio import AsyncEngine`) and add
   a `_db() -> AsyncEngine` accessor identical in shape to pattern A's, used at every
   `_state.db` read site (including the `.begin()` call this pattern was masking).
5. **Fix pattern C — a genuine `Optional[float]` reaching numeric code**
   (`services/matching_engine/order_book.py`, 3 diagnostics). Two are pre-existing, already
   individually justified with a stale `# type: ignore[operator]` comment (mypy/pyright
   syntax, which `ty` does not honor — hence still flagged); the invariant they document is
   real (`incoming.price` is only read after a `MARKET`-order early-return, so it's always
   `LIMIT` there and never `None`) — rewrite both to `# ty: ignore[unsupported-operator]` to
   restate the same already-accepted suppression in `ty`'s own syntax, not to silence a new
   finding. The third (`_rest`, line ~229) has no existing suppression; its docstring already
   says "Insert a *limit* order" and both call sites (`add_order` guards `order_type ==
   OrderType.LIMIT`; `restore_order` only ever restores previously-resting — hence
   previously-LIMIT — orders) confirm `order.price` is never `None` there — add `assert
   order.price is not None  # only LIMIT orders reach _rest (see call sites)` at the top of
   `_rest`, not another ignore comment (an assert documents *why*; a bare ignore doesn't).
6. **Fix pattern D — `clients/tui/` widgets accessed through an under-specified type**
   (2 files, 6 diagnostics). `clients/tui/app.py:296,303`:
   `self.screen.query_one('TabbedContent')` returns a bare `Widget` (no `expect_type` given);
   pass the class so `ty` (and Textual itself, which validates the match at runtime) know the
   real type: `self.screen.query_one('TabbedContent', TabbedContent).active = ...` (needs
   `from textual.widgets import TabbedContent`, not yet imported there).
   `clients/tui/widgets/order_entry.py:110,113,116,123`: `self.app` on a `Widget` is typed as
   Textual's generic `App[Unknown]`, which has no `post_status` — that method only exists on
   this project's `ExchangeApp` subclass. Add a `TYPE_CHECKING`-guarded import (avoids a
   circular import with `clients/tui/app.py`, which imports this widget) and a small typed
   accessor:
   ```python
   if tp.TYPE_CHECKING:
       from clients.tui.app import ExchangeApp

   ...
   def _app(self) -> 'ExchangeApp':
       return tp.cast('ExchangeApp', self.app)
   ```
   then replace the four `self.app.post_status(...)` call sites with `self._app().post_status(...)`.
7. **`ty` is wired into the root `just lint` recipe (unaffected — EXC-014 kept the
   workspace-wide `lint`/`test`/`check` recipes as a local "everything" convenience) and into
   `ci-repo.yml`'s `lint` job, not a per-service split** (patched 2026-09-18 impact sweep: EXC-014
   landed first and deleted `.github/workflows/ci.yaml`, this decision's original CI target;
   `ty check` is one whole-tree invocation across `services`/`platform`/`clients`, not a
   per-service one, and `ci-repo.yml` is the only surviving workflow with no path filter — it
   runs on every push/PR the same way `ci.yaml` used to, so it is where a repo-wide check
   belongs. Same reasoning EXC-018's compose-check guard uses for the same reason.)

### Tasks

#### Task 1 — Wire `ty` into the lint pipeline
- `justfile`: change `install:` to `uv sync --extra dev --extra tui` (decision 1); add a `ty`
  invocation to the `lint:` recipe, after the existing `ruff check .`:
  ```
  uv run ty check services platform clients --exclude "**/tests/**"
  ```
- `.github/workflows/ci-repo.yml`, `lint` job: change the "Install dependencies" step to
  `uv sync --extra dev --extra tui`; add a "Type check" step after "Lint" (`just lint-repo`) —
  or after whatever step EXC-018/other tickets have since added there:
  ```yaml
        - name: Type check
          run: uv run ty check services platform clients --exclude "**/tests/**"
  ```

#### Task 2 — Fix pattern A: `platform/account/src/account/app.py`
Add `_svc()`/`_risk()` accessors (decision 3); replace the 7 flagged call sites (`register_account`
×2, `list_accounts`, `get_account`, `reserve_cash`, `reserve_shares`, `apply_settlement`).

#### Task 3 — Fix pattern A: `clearing`, `market_data`, `notifications` app.py
One `_svc()` accessor per file (decision 3); replace the flagged call sites: `clearing` (1,
`on_trade_executed`), `market_data` (5: `all_tickers`, `get_quote`, `get_trade_history`,
`on_market_data_update`, `on_trade_executed`), `notifications` (7: `list_for_account` + 6×`add`).

#### Task 4 — Fix patterns A + B: `order_management`, `matching_engine` app.py
`order_management/app.py`: `_svc()` accessor (7 call sites: `submit_order`,
`get_open_orders`, `get_order` ×2, `cancel_order`, `get_orders_for_account`,
`on_order_filled`) plus `_db()` accessor per decision 4 (retype `db`, fix the `.begin()` call
site). `matching_engine/app.py`: `_db()` accessor per decision 4 only (no `svc` field here;
just the one `.begin()` call site).

#### Task 5 — Fix pattern A: `risk_engine/app.py`
`_instrument_repo()` accessor (decision 3); replace the 1 flagged call site (`save`).

#### Task 6 — Fix pattern C: `services/matching_engine/order_book.py`
Per decision 5: rewrite the two `# type: ignore[operator]` comments (lines ~130, ~137) to
`# ty: ignore[unsupported-operator]`; add the `assert order.price is not None` guard at the
top of `_rest` (line ~217).

#### Task 7 — Fix pattern D: `clients/tui/`
Per decision 6: `app.py` — import `TabbedContent`, pass it as `query_one`'s `expect_type` at
both call sites. `widgets/order_entry.py` — add the `TYPE_CHECKING` import + `_app()` cast
helper, replace the 4 `self.app.post_status(...)` call sites.

### Acceptance test

From the repo root, on `feat/EXC-002-add-static-type-checking-ty-to-lint-pipeline-and-ci`:
```
uv sync --extra dev --extra tui
just lint
just test
just services-build
```
Expect: `just lint` now runs `ruff check .` *and* `ty check services platform clients --exclude
"**/tests/**"`, both clean (`ty` prints "All checks passed!"/0 diagnostics); `just test` still
green (no runtime behaviour changed — every fix is either a narrowing accessor, a retype, an
ignore-comment rewrite, or an assert on an invariant already true); `just services-build`'s
outcome is unaffected by this ticket (still whatever EXC-016 leaves it at — do not treat that
as this ticket's concern). Separately confirm `ci-repo.yml`'s `lint` job would pass by running
the same commands its steps now use:
`uv sync --extra dev --extra tui`, `uv run ruff check clients scripts`,
`uv run ruff format --check clients scripts`,
`uv run ty check services platform clients --exclude "**/tests/**"`.

### Docs update (mandatory when user-facing)

No user-facing surface — internal lint tooling. `development/review-addendum.md` step 3 item 2
("a wrong or missing annotation is `class: design`, never blocking on its own") is now
partially superseded (a *caught* violation is a lint failure, hence blocking by `just lint`
itself) — leave that addendum line as-is (it's about annotations `ty`'s configured rule set
doesn't happen to catch, which can still exist) rather than rewriting it as part of this
ticket; note the nuance in the summary instead.

### Finish (mandatory)

1. Acceptance test green: `just lint` (ruff + ty) and `just test` clean.
2. No docs to update (see above).
3. Write a summary: the three fix patterns and their file counts, the `tui` extra fix, and the
   CI/justfile wiring.
4. Suggested commit message:
   ```
   feat: add ty static type-checking to lint pipeline and CI (EXC-002)

   Wire `ty check` into `just lint` and CI, scoped to services/,
   platform/, and clients/ excluding tests/. Fix the 39 real violations
   this surfaced: unguarded Optional service singletons, an untyped
   `db: object` placeholder, two stale mypy-style ignore comments, and
   two Textual widgets accessed through an under-specified type.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-002 in-review --reason "acceptance green"` and hand back.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — Description corrected: scope `shared/` → `platform/` (EXC-004 impact sweep —
  `shared/` no longer exists post-EXC-004).
- 2026-09-16 — TO DO → READY: plan complete
- 2026-09-17 — plan paths repointed from `services/account/` to `platform/account/src/account/`
  (and `services/market_data/tests/` to `platform/market_data/src/market_data/tests/`) — EXC-007
  impact sweep; no scope change.
- 2026-09-18 — plan amended: EXC-014's review impact sweep patched decision 7 and Task 1's CI
  wiring to target `ci-repo.yml`'s `lint` job instead of the now-deleted `ci.yaml`; root `just
  lint` wiring unaffected.
