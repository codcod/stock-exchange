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

### 0. Feature branch (mandatory)

```
cd .
git checkout main
git checkout -b feat/EXC-003-write-development-design-md-as-target-architecture-design-of-record-for-monolith-style-platform-restructuring
```

Local WIP commits on this branch are fine. Do not push or open a merge request without
explicit user approval (`pickle.toml`: `exchange` is `child_publish_gated`). Since this is
`layout = "in-tree"` at `path = "."`, before pushing verify the remote base is not behind:
`git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'` must
print nothing (or push `origin main` first).

### Prerequisite gate (hard)

None. EXC-001 and EXC-002 are unrelated backlog items — this ticket does not depend on either.

### Confirmed design decisions (do not deviate without asking)

1. **Workspace becomes a `uv` workspace with `platform/<service>/` packages plus one shared
   `platform/base/` package**, mirroring `~/Projects/private/monolith`. Services already
   communicate HTTP-only, so no cross-service imports need rewriting — only the current single
   install needs splitting.
2. **Each of the 6 stateful services gets its own independent Alembic migration history**,
   scoped to its already-existing Postgres schema (`schema=...` in `services/*/tables.py`),
   replacing the `CREATE SCHEMA IF NOT EXISTS` / create-on-boot logic in
   `shared/platform/db/tables.py:25`.
3. **Each service package gets its own two-stage Dockerfile** (`uv`-based builder, distroless
   runtime, non-root), replacing the single shared `infra/docker/Dockerfile`.
4. **Root `justfile` moves to `mod`-imported per-service recipes; CI becomes one reusable
   GitHub Actions workflow called per-service, path-filtered** on that service (or
   `platform/base`, or the workspace lockfile) changing.
5. **Each service versions independently** — own SemVer starting at `0.0.1`, own
   `CHANGELOG.md` (Keep a Changelog), `PACKAGING.md`, `RELEASING.md`, tags `<service>-vX.Y.Z`.
   The existing unused single-repo `[tool.semantic_release]` block in root `pyproject.toml` is
   removed once per-service versioning actually lands — not by this ticket, but the future
   versioning ticket (filed after this one, once `platform/` package names exist to version).
6. **`CLAUDE.md` is emptied to the pickle marker block plus a one-line pointer to
   `development/design.md`** (literal parity with the reference project, which carries no
   CLAUDE.md/AGENTS.md content of its own). `AGENTS.md` is unaffected — already marker-only.
7. **`docs/architecture.md` and `docs/lob_concepts_review.md` fold into `development/design.md`
   as sections, then both files are deleted.** Monolith parity is a single prose design doc, not
   a doc tree with sub-files. `development/review-addendum.md`'s references to
   `docs/architecture.md` (steps 1, 4/4a, 7) are updated to point at `development/design.md`
   instead, and its revision history gets a new entry recording the move.
8. **This ticket's own deliverable is documentation only**: `development/design.md`, the
   `CLAUDE.md` edit, the two doc deletions, and the `review-addendum.md` cross-reference fix.
   No `platform/`, Alembic, Docker, justfile, or versioning code changes happen here — those are
   EXC-004 onward, filed once this ticket reaches `6-done/`, each free to cite these decisions as
   `EXC-003 decision N`.

### Tasks

#### Task 1 — Write `development/design.md`

Create `development/design.md` by merging, in this order:

1. `CLAUDE.md`'s current non-marker content verbatim as sections (everything above the
   `<!-- pickle:begin -->` line): *What this is*, *Architecture overview*, *Key domain
   concepts*, *Running the project*, *Development conventions*, *Account and Risk Engine
   freshness*, *When modifying a service*.
2. The full content of `docs/architecture.md` (331 lines), folded in as one or more sections —
   keep its "What's intentionally simplified" subsection intact and under that name, since
   `development/review-addendum.md` step 4/4a treats it as an accepted-limitations list, not a
   backlog, by that exact heading.
3. The full content of `docs/lob_concepts_review.md` (179 lines), folded in as its own section
   (e.g. "Limit order book concepts").
4. A new closing section, "Target architecture: `platform/` restructuring", stating decisions
   1–8 above verbatim (numbered the same way, so a later ticket's `EXC-003 decision N` citation
   resolves against this document, not just this ticket file).

Resolve any heading-level collisions between the three merged sources by demoting the merged
docs' internal headings one level (so they nest under the new top-level sections) rather than
renaming or dropping content.

#### Task 2 — Empty `CLAUDE.md` to a pointer

Replace `CLAUDE.md`'s content from the top through (but not including) the
`<!-- pickle:begin -->` line with:

```
# Stock Exchange — Project Context

See [`development/design.md`](development/design.md) for architecture, domain concepts, and
development conventions.
```

Leave everything from `<!-- pickle:begin -->` through `<!-- pickle:end -->` byte-for-byte
untouched — it is pickle-owned and re-rendered by `pickle upgrade`; hand-editing it is what
`pickle doctor` flags as drift.

#### Task 3 — Retire `docs/architecture.md` and `docs/lob_concepts_review.md`

1. `git rm docs/architecture.md docs/lob_concepts_review.md` once their content is confirmed
   folded into `development/design.md` (Task 1).
2. Edit `development/review-addendum.md`: replace its `docs/architecture.md` references in
   step 1 ("Governing documents"), step 4/4a (items 1 and 2), and step 7 with
   `development/design.md`. Add a `## Revision history` entry ("v2 — moved governing doc
   reference from docs/architecture.md to development/design.md, EXC-003").

### Acceptance test

1. `grep -rn "docs/architecture.md\|docs/lob_concepts_review.md" --include="*.md" . | grep -v '^\./tickets/'`
   prints nothing (both files are gone and every non-ticket cross-reference is updated; ticket
   history text is immutable and may still mention the old paths).
2. `development/design.md` exists and, read top to bottom, contains every section named in
   Task 1 (spot-check: "What's intentionally simplified" and "Target architecture: `platform/`
   restructuring" are both present).
3. `pickle doctor` reports 0 errors / 0 warnings (proves the pickle marker block in `CLAUDE.md`
   was not touched).
4. `just lint` and `just test` are unaffected (no code changed) — run both anyway to confirm a
   docs-only branch didn't break anything incidental.

### Docs update (mandatory when user-facing)

This ticket's product *is* documentation: `development/design.md` is created as the new design
of record; `CLAUDE.md` is reduced to a pointer at it; `docs/architecture.md` and
`docs/lob_concepts_review.md` are deleted; `development/review-addendum.md` is updated to cite
`development/design.md` instead of the retired `docs/architecture.md`.

### Finish (mandatory)

1. Acceptance test green (above).
2. Docs updated and registered (Task 1–3, all under Docs update).
3. Write a summary: files created/edited/deleted, and confirm no `platform/`/Docker/justfile/
   versioning code was touched (out of scope, per decision 8).
4. Suggested commit message:

   ```
   docs: consolidate CLAUDE.md and docs/ into development/design.md (EXC-003)

   Replace docs/architecture.md, docs/lob_concepts_review.md, and CLAUDE.md's
   project-context content with a single development/design.md, matching the
   reference project's one-doc-of-record pattern. CLAUDE.md keeps only the
   pickle marker plus a pointer.
   ```

5. Tidy up before presenting: this is a root-path child (`path = "."`) — interactive-rebase WIP
   commits into a small number of atomic commits before presenting.
6. Commit locally on the ticket branch; do not push or open a merge request without user
   approval. Verify the remote-base check from step 0 before pushing. Hand back to the user.

## Review

- [x] Reviewer independence settled (step 0): **delegated**. This session authored the branch, so
  steps 2–4a were delegated to a freshly-spawned, adversarially-briefed independent agent
  (no memory of writing the code); every one of its findings was re-verified by hand before
  entering the table below (per step 0's "delegation buys independence, not accuracy").
- [x] Implementation audit — acceptance test re-run, tasks & criteria verified (steps 1, 2)
- [x] Quality audit (step 3)
- [x] Consistency audit (step 4)
- [x] Documentation audit — coverage, whole-tree sweep, docs build clean (step 4a)
- [x] Docs-readability pass — conscious skip: no docs-readability reviewer configured in this host
- [x] Findings recorded with severity, class, disposition; disposition summary + cost line (step 5)
- [x] Ticket moved (step 6)
- [x] Other references updated; governing documents reconciled (step 7)
- [x] Remaining-tickets impact sweep done (step 8)
- [x] Summary + commit message presented for approval (step 9)

**Implementation audit.** All 3 Tasks and all 8 confirmed design decisions verified met, in the
files/paths named. Acceptance test re-run verbatim, all 4 items pass:
1. `command grep -rln "docs/architecture.md\|docs/lob_concepts_review.md" --include="*.md" . | command grep -v '^\./tickets/'` → only `./development/design.md` and `./development/review-addendum.md` (both intentional, explanatory mentions of the retirement).
2. `development/design.md` contains every planned section (spot-checked "What's intentionally simplified" and "Target architecture: platform/ restructuring").
3. `pickle doctor` → 0 errors / 0 warnings.
4. `just lint` → all checks passed. `just test` → 66 passed.

(Note: the plan's own acceptance-test grep, run with a shell alias that strips the `./` prefix,
can falsely appear to leak a `tickets/` hit — confirmed a local shell artifact, not a repo defect,
using real `grep`/`command grep`.)

**Findings:**

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | non-blocking | stale-xref | fixed inline | `README.md`'s Project Structure tree still listed the deleted `docs/architecture.md` and described `CLAUDE.md` as "contains project context" — both made false by this branch's own deletion/edit. Missed by the plan's own acceptance-test grep because the tree splits `docs/` and `architecture.md` across two lines, past a single-line regex. | `README.md:63-67` (pre-fix) | Fixed inline: replaced the `docs/`/`CLAUDE.md` lines with the actual `development/design.md` + pointer-`CLAUDE.md` shape. Commit `1f49785`. |
| F2 | non-blocking | design | noted | `pyproject.toml:51`'s `exclude = ["docs/**/*.py"]` was already a no-op before this branch (`docs/` never held `.py` files) and is now doubly dead since `docs/` no longer exists at all — pre-existing, not caused by this branch. | `pyproject.toml:51` | Leave as noted; a future lint/config-cleanup pass can drop it. |
| F3 | non-blocking | docs-gap | fixed inline | The folded "Detailed architecture" section's staleness disclaimer named only the account/notifications gap, not the also-pre-existing `shared/` → `shared/platform/` path rename baked into the same folded content (e.g. `shared/service_clients.py`, `shared/db/connection.py` no longer exist) — a reader trusting the disclaimer's completeness would still be misled. The underlying path staleness itself predates this ticket (already wrong in `main:docs/architecture.md`) and is out of this ticket's fold-verbatim scope, so only the disclaimer's own incompleteness — authored by this branch — was in scope to fix. | `development/design.md:91-96` (pre-fix) | Fixed inline: broadened the disclaimer to also name the `shared/` → `shared/platform/` rename and point at the real paths. Commit `1f49785`. |

Disposition summary: 3 findings, 0 blocking. 2 `fixed inline` (F1, F3), 1 `noted` (F2).

cost: estimated M, actual M

**Step 7 — governing documents.** `development/design.md` and `CLAUDE.md` are themselves this
ticket's product, already reconciled by Task 1/2. `development/review-addendum.md` was
reconciled by Task 3 (verified: all 4 named spots + revision history + version banner, diff-
checked). No other governing document in this repo references the retired paths.

**Step 8 — impact sweep.** Checked `tickets/1-to-do/` (EXC-001, EXC-002) and `tickets/2-ready/`
(none) for `depends-on:`/Description references to EXC-003: neither EXC-001 nor EXC-002
references it. No assumption invalidated; no patch needed.

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — TO DO → READY
- 2026-09-16 — READY → IN DEVELOPMENT
- 2026-09-16 — IN DEVELOPMENT → IN REVIEW
- 2026-09-16 — IN REVIEW → DONE: review clean; 3 non-blocking findings, 2 fixed inline, 1 noted
