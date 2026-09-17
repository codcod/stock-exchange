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
4. **The corrected service count was not propagated.** EXC-016 fixed "Six service containers" →
   "Eight …" at `design.md:383` but left `infra/docker/compose.services.yml:1`
   (`# Application services — all eight microservices.`, while the file holds nine blocks) and
   `README.md:12` (`# Start Postgres + all six microservices`, against `design.md:48`'s
   "eight"). README's is the most visible wrong number in the repo. (F7, `docs-gap`.)
5. **`development/design.md:100-112`** — the "Detailed architecture" banner declares its own
   section "not re-audited … historical background, not a current source of truth", yet
   `### Infrastructure` — where EXC-016 wrote new authoritative prose, and where a reader is
   sent for the compose layout — is a subsection of it. Either carve `### Infrastructure` out
   above the banner or exempt it in the banner text. (`spec-unclear`.)
6. **`development/review-addendum.md:89-92`** — claims `development/design.md` is "the entire
   shipped docs tree". It is not: `README.md`, `platform/base/README.md` and
   `platform/{account,gateway,market_data}/PACKAGING.md` also ship, added by EXC-005/006/007
   after the addendum's v2. This stale claim is *why* finding 4's `README.md:12` slipped past
   the docs sweep, so fixing it is worth more than the line itself. Bump the addendum to v4.
   (`stale-xref`.)

Deliberately excluded: `design.md:382`'s "Postgres 17" (the image is `postgres:18-alpine`) and
the `postgres-data` volume path both belong to **EXC-017**, which owns `compose.infra.yml`.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-17 — created (TO DO). source: review: EXC-016's review findings F4, F5, F6, F7 and two
  governing-document observations, batched by theme (documentation accuracy). Promoted over
  noting because finding 6 explains a gap in the review procedure itself, not just a wrong
  number.
