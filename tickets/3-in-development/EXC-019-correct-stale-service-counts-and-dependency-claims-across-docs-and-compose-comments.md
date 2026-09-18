---
id: EXC-019
title: Correct stale service counts and dependency claims across docs and compose comments
project: exchange
depends-on: []
spawned-by: [EXC-016]
impact: low
complexity: low
cost: S
---

# EXC-019 — Correct stale service counts and dependency claims across docs and compose comments

## Outcome

After this ships, the repo's own documentation stops contradicting itself about how many
services there are and which of them wait on which. A reader following `README.md` or
`development/design.md` today is told the stack has six microservices in one place and eight in
another, and is told services "wait on the services they call" when three of the four named do
not.

## Description

Batched from five non-blocking documentation findings of EXC-016's review (F4, F5, F6, F7, plus
two governing-document observations). All are factual errors in prose, no behaviour change.
EXC-016's own rewrite of `development/design.md`'s Infrastructure section introduced two of them
and sat next to the rest; they were classified non-blocking because none breaks a golden path.

1. **`infra/docker/compose.services.yml:15`** — the Tier 1 banner comment reads
   `# Tier 1: no service dependencies — only Postgres`. After EXC-016 there is no Postgres
   dependency anywhere in the file, and `account` — a Tier 1 block — *does* have a service
   dependency (`account-migrate`, added by EXC-007). (F4, `stale-xref`.)
2. **`development/design.md:386`** — "`risk-engine`, `order-management`, `matching-engine` and
   `gateway` wait on the services they call" is false for three of the four. `gateway` sets
   `CLEARING_URL`, `RISK_ENGINE_URL` and `NOTIFICATIONS_URL` but its `depends_on` covers only
   order-management, matching-engine, market-data and account. `matching-engine` calls clearing,
   market-data, account and notifications but waits only on order-management.
   `order-management` calls matching-engine but does not wait on it. Suggested wording: they
   wait on *a subset* of the services they call, the rest being covered by application-level
   retry. (F5, `docs-gap`.)
3. **`development/design.md:386`, same paragraph** — it ends "Each container runs
   `python -m services.<name>` (or `python -m <name>` for the `platform/` packages) and is
   reachable on `localhost:800X`", but the paragraph now counts `account-migrate`, which runs
   `alembic upgrade head` and exposes no port. Scope the sentence to the eight long-running
   services. (F6, `docs-gap`.)
4. **The corrected service count was not propagated to `README.md`.** EXC-016 fixed "Six
   service containers" → "Eight …" at `design.md:383`. `README.md:12`
   (`# Start Postgres + all six microservices`) still says six, against `design.md:52`'s
   "eight" — the most visible wrong number in the repo. (F7, `docs-gap`.)
   Re-verified during refinement: `infra/docker/compose.services.yml:1`
   (`# Application services — all eight microservices.`) already reads "eight" and needs no
   change — five more one-shot migrate blocks landed since this finding was filed (EXC-008/009/
   010/011/012), so the file now holds fourteen `services:` blocks, but the comment only ever
   counted the eight long-running microservices, which is still the correct count.
5. **`development/design.md:100-112`** — the "Detailed architecture" banner declares its own
   section "not re-audited … historical background, not a current source of truth", yet
   `### Infrastructure` — where EXC-016 wrote new authoritative prose, and where a reader is
   sent for the compose layout — is a subsection of it. Either carve `### Infrastructure` out
   above the banner or exempt it in the banner text. (`spec-unclear`.)
6. **`development/review-addendum.md:93-96`** — claims `development/design.md` is "the entire
   shipped docs tree". It is not: `README.md`, `platform/base/README.md` and nine
   `platform/*/PACKAGING.md` files also ship, added by EXC-005 through EXC-012 after the
   addendum's v2. This stale claim is *why* finding 4's `README.md:12` slipped past the docs
   sweep, so fixing it is worth more than the line itself. (`stale-xref`.)
   Re-verified during refinement: the addendum's own revision history has moved on to v7 (five
   more revisions landed after this finding was filed, each repointing a stale path elsewhere in
   the document), but its header banner is still stuck reading "**Version 3**" — a second,
   pre-existing desync this ticket's edit will need to close by writing a v8 header, not the
   originally-suggested v4.

Deliberately excluded: `design.md:382`'s "Postgres 17" (the image is `postgres:18-alpine`) and
the `postgres-data` volume path both belonged to **EXC-017**, which owns `compose.infra.yml`.
**EXC-017 has since fixed both** (design.md now reads "Postgres 18"); nothing remains here for
this ticket to do on that front.

## Implementation Plan

### 0. Feature branch (mandatory)

```
cd .
git checkout main
git checkout -b feat/EXC-019-correct-stale-docs-counts
```

Root-path child (`path = "."`): tidy WIP commits into atomic ones before presenting; the user
chooses squash vs. keeping tidied history at approval.

### Prerequisite gate (hard)

None — no `depends-on:`, clean pickup.

### Confirmed design decisions (do not deviate without asking)

1. **Fix finding 5 (design.md's "not re-audited" banner covering `### Infrastructure`) by
   exempting the subsection in the banner's own text, not by moving it out of the
   `## Detailed architecture` span.** Smaller diff, no risk of disturbing the heading anchors
   the sequence/component diagram sections around it rely on.
2. **`infra/docker/compose.services.yml:1` gets no edit.** Re-verified during refinement
   (Description, finding 4): the comment already reads "eight microservices" and is still
   correct — the extra blocks the file has grown since this finding was filed are one-shot
   migrations, not microservices.
3. **The addendum's version bump target is v8, not the v4 originally suggested** (Description,
   finding 6) — its revision history has moved to v7 since this finding was filed, and its
   header banner ("**Version 3**") has been out of sync with that history since v4 landed. This
   ticket's edit writes a header that is accurate through v8, closing that desync as a side
   effect of doing the bump correctly rather than as separate extra scope.

### Tasks

#### Task 1 — Fix the Tier 1 banner comment (finding 1)
`infra/docker/compose.services.yml:15`: change
`# Tier 1: no service dependencies — only Postgres` to
`# Tier 1: no other-service dependencies — only Postgres` (or equivalent wording) so it no
longer contradicts `account`'s `depends_on: account-migrate` two lines below (line 26) or the
removed Postgres `depends_on` this same banner used to describe.

#### Task 2 — Correct the "wait on the services they call" claim (finding 2)
`development/design.md:391` (the `depends_on` paragraph under `### Infrastructure`): reword
"`risk-engine`, `order-management`, `matching-engine` and `gateway` wait on the services they
call" to state they wait on **a subset** of the services they call — `risk-engine` fully covers
its one call (`account`); `order-management` calls `matching-engine` but does not wait on it;
`matching-engine` calls `clearing`, `market-data`, `account` and `notifications` but waits only
on `order-management`; `gateway` calls `clearing`, `risk-engine` and `notifications` via env var
but its `depends_on` covers only `order-management`, `matching-engine`, `market-data` and
`account` — the rest is covered by application-level retry, per the sentence that already
follows.

#### Task 3 — Scope the "each container runs / reachable on localhost" sentence (finding 3)
Same paragraph (`development/design.md:391`), final sentence: scope "Each container runs
`python -m services.<name>` … and is reachable on `localhost:800X`" to the eight long-running
services — it currently reads as if it covers every block, but none of the six one-shot
`*-migrate` blocks (`account-migrate`, `clearing-migrate`, `notifications-migrate`,
`risk-engine-migrate`, `order-management-migrate`, `matching-engine-migrate`) run a long-lived
process or expose a port.

#### Task 4 — Fix README's stale service count (finding 4)
`README.md:12`: change `# Start Postgres + all six microservices` to
`# Start Postgres + all eight microservices`, matching `development/design.md:52`.

#### Task 5 — Exempt `### Infrastructure` from the "historical" banner (finding 5, decision 1)
`development/design.md:97-108` (the blockquote banner opening `## Detailed architecture`): add
a clause exempting `### Infrastructure` (and its content) from the "not re-audited … historical
background" characterization, since EXC-016 rewrote that subsection with current, authoritative
prose. Keep the rest of the banner as-is — the other subsections it covers (C4 diagrams,
sequence diagram, etc.) are still the stale, un-audited fold-in it describes.

#### Task 6 — Fix the addendum's stale "entire shipped docs tree" claim and re-sync its version header (finding 6, decision 3)
`development/review-addendum.md:93-96`: rewrite the claim that `development/design.md` is "the
entire shipped docs tree" to instead list what actually ships: `development/design.md`,
`README.md`, `platform/base/README.md`, and each service's `platform/*/PACKAGING.md` (currently
nine files — `account`, `clearing`, `gateway`, `market_data`, `matching_engine`, `notifications`,
`order_management`, `risk_engine`, plus any added since). Then update the header banner
(`development/review-addendum.md:1-4`, currently `**Version 3** · written 2026-09-16 … updated
same day by EXC-003 … and on 2026-09-17 by EXC-007's review.`) to `**Version 8**`, folding in a
one-clause summary of what v4–v7 already changed (each a stale-path repoint from a service's
`platform/` migration) plus this ticket's own v8 change. Add the matching `- **v8**
(2026-09-18) — …` entry to the `## Revision history` section (after the existing v7 entry) —
this is the same kind of self-referential bookkeeping the ticket's own `## History` follows, but
for this document's own version field.

### Acceptance test

1. `grep -rn "six microservices" README.md development/design.md` → no matches.
2. `grep -n "wait on the services they call" development/design.md` → no matches (reworded).
3. Re-read `development/design.md:97-108` and confirm `### Infrastructure` is explicitly
   exempted from the "historical, not current source of truth" characterization.
4. Re-read `development/review-addendum.md:1-4` and confirm it reads "Version 8" and its claim
   about what ships matches the actual shipped file list (`README.md`, `platform/base/README.md`,
   nine `platform/*/PACKAGING.md` files, `development/design.md`).
5. `just lint` clean (docs-only change, but keep it green).

### Docs update (mandatory when user-facing)

This ticket *is* the docs update — `README.md`, `development/design.md`, and
`development/review-addendum.md` are the deliverable. No further registration needed.

### Finish (mandatory)

1. Acceptance test green.
2. Write a summary: files touched, and call out the two refinement-time corrections (decisions
   2 and 3 above) so the reviewer isn't surprised the diff doesn't match the original finding
   text verbatim.
3. Suggested commit message:
   ```
   docs: correct stale service counts and dependency claims (EXC-019)

   Fixes the Tier 1 banner comment, the "wait on the services they call" and
   container/port claims in design.md's Infrastructure section, README's six-vs-eight
   service count, the "historical" banner wrongly covering the current Infrastructure
   subsection, and the review addendum's stale docs-tree claim (with its version
   header re-synced to v8).
   ```
4. Root-path child: tidy WIP commits into atomic ones before presenting.
5. Commit locally on the ticket branch; do not push or open an MR without user approval.
   `pickle ticket move EXC-019 in-review --reason "acceptance green"` and hand back.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-17 — created (TO DO). source: review: EXC-016's review findings F4, F5, F6, F7 and two
  governing-document observations, batched by theme (documentation accuracy). Promoted over
  noting because finding 6 explains a gap in the review procedure itself, not just a wrong
  number.
- 2026-09-18 — corrected Description's "Deliberately excluded" note (EXC-017's impact sweep,
  step 8): EXC-017 fixed `design.md:382`'s "Postgres 17" and the volume path, so that exclusion
  is now past tense — nothing left for this ticket on that front.
- 2026-09-18 — refined: re-verified Description against the current tree (findings 4 and 6 were
  stale on their own terms — five more `*-migrate` blocks and three more addendum revisions
  landed since filing); corrected both, added the Implementation Plan.
- 2026-09-18 — TO DO → READY: plan complete
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
