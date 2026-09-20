---
id: EXC-023
title: Add PACKAGING.md/RELEASING.md/CHANGELOG.md to platform/admin/
project: exchange
depends-on: []
spawned-by: [EXC-022]
impact: low
complexity: low
cost: S
---

# EXC-023 — Add PACKAGING.md/RELEASING.md/CHANGELOG.md to platform/admin/

## Outcome

After this ships, `platform/admin/` carries the same `PACKAGING.md`, `RELEASING.md`, and
`CHANGELOG.md` triple every other `platform/*` installable service package already ships,
closing the one docs gap EXC-022's review found.

## Description

EXC-022 added `platform/admin/` as a new installable package (own `pyproject.toml`, own
Dockerfile, own port) — a peer to `account`, `clearing`, `gateway`, `market_data`,
`matching_engine`, `notifications`, `order_management`, and `risk_engine`. All eight of those
ship a `PACKAGING.md` + `RELEASING.md` + `CHANGELOG.md` triple (the project's review addendum,
`development/review-addendum.md`, names this triple explicitly as part of the shipped docs
tree its step 4a sweep audits); `platform/admin/` shipped none of the three.

Write admin's own triple following the existing pattern verbatim — e.g.
`platform/clearing/PACKAGING.md`/`RELEASING.md`/`CHANGELOG.md` — adapted for admin's own
specifics (no Alembic migration history, unlike every stateful sibling; `admin-vX.Y.Z` tag
convention; `[0.0.1]` changelog entry crediting EXC-022 as the extraction/creation source, the
same way `platform/clearing/CHANGELOG.md`'s `[0.0.1]` entry credits EXC-011).

Not part of EXC-022 itself — the review scoped it out as a small, mechanical, zero-risk
addition better done as its own ticket than folded into that review pass (rules §5, `docs-gap`,
disposition: new ticket).

## Implementation Plan

### 0. Feature branch (mandatory)

Before any change, create a feature branch inside the `exchange` repo (`path = "."`,
`layout = "in-tree"`):

```
git checkout main
git checkout -b feat/EXC-023-admin-packaging-docs
```

Do all work on this branch, committing locally as you go. Publish only per the project's commit
policy (never push or open an MR without explicit user approval): tidy WIP commits into a small
number of atomic commits before presenting them (root-path child default), then present the
suggested commit message; only after approval, keep the tidied history, verify
`git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'` prints
nothing, push, and open the MR — merging is always the human's.

### Prerequisite gate (hard)

None. `depends-on: []`; EXC-022 (`spawned-by:`) is already `6-done/` and merged to `main`
(PR #39, `dc07da8`) — confirmed via `tickets/BOARD.md` and this repo's own `git log`.

### Confirmed design decisions (do not deviate without asking)

1. **Model the triple on `platform/gateway/`'s, not `platform/clearing/`'s.** `platform/admin/`
   has no `migrations/` directory and no Alembic history — same as `gateway`, unlike every
   stateful sibling (`account`, `clearing`, `market_data`, `matching_engine`, `notifications`,
   `order_management`, `risk_engine`). `gateway`'s `PACKAGING.md` already omits the Alembic
   sentence that the stateful siblings' carry; admin's should match that omission verbatim
   rather than clearing's fuller version.
2. **`CHANGELOG.md`'s `[0.0.1]` entry says "Added", not "Extracted".** Every existing sibling's
   entry reads "Extracted from `services/<name>/`..." because each was pulled out of a
   pre-EXC-005 `services/` package. `platform/admin/` has no `services/admin/` predecessor — it
   was built new by EXC-022 — so the entry must instead read something like "Added
   `platform/admin/` as a new installable package: read-only ops dashboard (Datastar/SSE) over
   the exchange's services (EXC-022)."
3. **Tag convention is `admin-vX.Y.Z`**, matching every sibling's `<service>-vX.Y.Z`.
4. **`pyproject.toml`'s `version = "0.0.1"`** (`platform/admin/pyproject.toml:7`) already matches
   the changelog's `[0.0.1]` — no version bump needed, this ticket only adds the three files.
5. **Also update `development/review-addendum.md`'s step 4a item 2** (the "shipped docs tree"
   definition) to include `admin` and bump its count from eight services / 24 files to nine
   services / 27 files, plus a new `v11` revision-history line recording the change. This was
   not in the ticket's original Description — refinement re-verified the Description against the
   current repo and found this addendum entry would otherwise go stale the moment this ticket
   ships, the same class of miss its own v8–v10 lines document being caught and fixed for.

### Tasks

#### Task 1 — `platform/admin/PACKAGING.md`
Create it, adapting `platform/gateway/PACKAGING.md` verbatim except for the package name
(`admin` instead of `gateway`) and description reference — no Alembic/migrations sentence
(decision 1).

#### Task 2 — `platform/admin/RELEASING.md`
Create it, adapting `platform/gateway/RELEASING.md` verbatim except for the package name and
tag prefix: bump `platform/admin/pyproject.toml`, add a `platform/admin/CHANGELOG.md` entry,
commit, tag `admin-vX.Y.Z` (decision 3), push the tag.

#### Task 3 — `platform/admin/CHANGELOG.md`
Create it in Keep a Changelog format (same preamble as every sibling) with a single
`## [0.0.1] - 2026-09-20` entry under `**Added**` per decision 2.

#### Task 4 — `development/review-addendum.md` step 4a item 2 + revision history
Per decision 5: in the "shipped docs tree" sentence (currently listing `account`, `clearing`,
`gateway`, `market_data`, `matching_engine`, `notifications`, `order_management`,
`risk_engine` — eight services, 24 files), add `admin` to the list and change the count to nine
services, 27 files total. Append a `- **v11** (2026-09-20) — ...` line to the revision history
describing this change, and bump the header's `**Version 10**` to `**Version 11**`.

### Acceptance test

1. `ls platform/admin/PACKAGING.md platform/admin/RELEASING.md platform/admin/CHANGELOG.md` —
   all three exist.
2. `grep -c "Alembic" platform/admin/PACKAGING.md` — prints `0` (decision 1).
3. `grep "Added \`platform/admin/\`" platform/admin/CHANGELOG.md` — matches (decision 2).
4. `grep "admin-v" platform/admin/RELEASING.md` — matches (decision 3).
5. `grep -c "platform/\*/PACKAGING.md" development/review-addendum.md` after the edit still
   resolves to the same sentence, now reading "nine services ... 27 files total" and listing
   `admin`.
6. `just lint` and `just test` — both green (no code changed, but confirms the branch is clean
   and nothing else broke).

### Docs update (mandatory when user-facing)

This ticket's entire deliverable is docs (`PACKAGING.md`/`RELEASING.md`/`CHANGELOG.md`) plus
keeping `development/review-addendum.md`'s shipped-docs-tree definition in sync with them
(Task 4) — no separate registration step beyond Tasks 1–4 themselves.

### Finish (mandatory)

1. Acceptance test green; `just lint` / `just test` clean.
2. Docs updated per Tasks 1–4 above.
3. Write a summary (files touched: the three new `platform/admin/` docs, plus
   `development/review-addendum.md`; nothing deferred).
4. Suggest commit message: `docs(admin): add PACKAGING/RELEASING/CHANGELOG triple (EXC-023)`.
5. Tidy WIP commits into atomic ones (root-path child) before presenting.
6. Commit locally; present for approval; only after approval verify the remote base isn't
   behind, push, and open the MR. Hand back.

## Review

- [x] Reviewer independence settled (step 0): this session began after a `/clear` with no
  memory of authoring the branch — the next-best handoff step 0 names when a spawned
  independent reviewer is unavailable. Audits (steps 2–4a) run directly by this reviewer on
  that basis; none delegated.
- [x] In-tree stale-branch check (step 0a): `pickle doctor` initially warned the checked-out
  branch had the ticket in `3-in-development` while `main` had it in `4-in-review`; rebased
  `feat/EXC-023-admin-packaging-docs` onto `main` and re-ran — `0 error(s), 0 warning(s)`.
- [x] Implementation audit (steps 1, 2): all 4 tasks verified against the actual tree.
  Acceptance test re-run verbatim, all 6 items pass: (1) all three
  `platform/admin/{PACKAGING,RELEASING,CHANGELOG}.md` exist; (2) `grep -c "Alembic"
  platform/admin/PACKAGING.md` → `0`; (3) `grep "Added `platform/admin/`"
  platform/admin/CHANGELOG.md` matches, heading is `**Added**` not `**Changed**` (decision 2);
  (4) `grep "admin-v" platform/admin/RELEASING.md` matches (`admin-vX.Y.Z`, decision 3); (5)
  `development/review-addendum.md` step 4a item 2 now reads "nine services ... admin ... 27
  files total"; (6) `just lint` clean, `just check` clean (`ruff check` + `ruff format
  --check`, 148 files formatted), `just test` → 90 passed. `platform/admin/pyproject.toml`
  version unchanged at `0.0.1` (decision 4, no bump needed). `git diff main...HEAD --stat`
  shows exactly the 4 files the plan names, nothing else touched.
- [x] Quality audit (step 3): docs-only change, no code; new files match the `gateway` template
  (diffed line-for-line) with only package name / tag prefix / changelog heading substituted
  per decisions 1–3.
- [x] Consistency audit (step 4): no contradictions found between the new triple and its
  `gateway` model, or between the addendum edit and the actual file count (27 files, 9
  services, confirmed by `find platform -maxdepth 2 -name '{PACKAGING,RELEASING,CHANGELOG}.md'`).
  `development/design.md`'s pre-existing note that `platform/admin/` is "absent from the
  [service] table" is a known, self-documented gap unrelated to this ticket's scope (packaging
  docs, not the architecture table) — left as-is.
- [x] Documentation audit (step 4a): coverage — the ticket's own deliverable is the docs; no
  gap. Whole-tree sweep — re-read `development/design.md`, `README.md`,
  `platform/base/README.md` and the full 27-file `platform/*/{PACKAGING,RELEASING,CHANGELOG}.md`
  set; addendum's revision history and version header both correctly bumped to v11. No docs
  build configured for this project (addendum step 1) — n/a.
- [ ] Docs-readability pass (step 4b, optional): no docs-readability reviewer available in this
  environment — conscious skip.
- [x] Findings recorded (step 5): none. See table and disposition summary below.
- [x] Ticket moved to `tickets/6-done/` (step 6).
- [x] Other references / governing documents (step 7): `development/review-addendum.md` was
  itself Task 4 of this ticket's own plan (header, step 4a item 2, revision history) — already
  reconciled by the branch under review, verified above. No other ticket or doc references
  EXC-023 by id.
- [x] Remaining-tickets impact sweep (step 8): `grep -rl "EXC-023" tickets/1-to-do
  tickets/2-ready` — no hits. No dependent tickets to patch.
- [x] Summary + commit message & MR attributes presented for approval; overarching bookkeeping
  committed per policy; remote-base-not-behind check applies at push time (step 9).

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|

No findings — the branch matches its Implementation Plan exactly, including the two
non-obvious decisions (no-Alembic omission, "Added" not "Extracted" wording) that are the
easiest parts of this kind of ticket to get wrong.

disposition summary: 0 findings.

cost: estimated S, actual S.

## History

- 2026-09-19 — created (TO DO). source: pickle ticket new
- 2026-09-20 — TO DO → READY: plan complete
- 2026-09-20 — READY → IN DEVELOPMENT: picked up
- 2026-09-20 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-09-20 — IN REVIEW → DONE: no findings; acceptance green
