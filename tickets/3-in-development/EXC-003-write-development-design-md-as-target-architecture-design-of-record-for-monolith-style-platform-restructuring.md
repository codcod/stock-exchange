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

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — TO DO → READY
- 2026-09-16 — READY → IN DEVELOPMENT
