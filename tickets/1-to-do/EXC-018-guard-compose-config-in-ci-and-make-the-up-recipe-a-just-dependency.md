---
id: EXC-018
title: Guard compose config in CI and make the up recipe a just dependency
project: exchange
depends-on: []
spawned-by: [EXC-016]
impact: high
complexity: low
cost: S
---

# EXC-018 — Guard compose config in CI and make the up recipe a just dependency

## Outcome

After this ships, a dangling `depends_on` reference in either compose file fails in CI instead
of reaching `main`, and `just --dry-run up` shows the Postgres `--wait` gate it actually
performs. EXC-016 fixed one such reference by hand after it had silently blocked the configured
build command (`just services-build`) for four consecutive tickets; nothing currently stops the
next one.

## Description

Batched from two non-blocking findings of EXC-016's review (F3, F1).

**1. No mechanical guard against the bug EXC-016 just fixed (F3, `test-gap`).**
`.github/workflows/ci.yaml` declares only a `lint` job (line 9) and a `test` job (line 32) —
it never runs `docker compose config`, so an invalid compose project reaches `main` freely.
That is exactly what happened: `depends_on: postgres` referencing a service defined only in
`compose.infra.yml` made every one-file invocation of `compose.services.yml` an invalid
project, and EXC-004, EXC-005, EXC-006 and EXC-007 each recorded "`services-build` failure
unchanged" while it sat there. EXC-016's Decision 1 recorded a convention in prose — future
`<svc>-migrate` containers put their Postgres ordering in the `justfile`, never in
`depends_on: postgres` — but that prose is about to be archived in `6-done/`, and
`tickets/1-to-do/EXC-008`, `EXC-009`, `EXC-010`, `EXC-011` and `EXC-012` each plan a
`<svc>_migrate` one-shot compose container "gating startup" without citing it. Suggested fix: a
`compose-check` recipe running `docker compose -f infra/docker/compose.services.yml config -q`
**and** the merged two-file form, wired into CI as its own step or job. Also worth patching the
five queued tickets to cite the convention — EXC-016's review noted the omission but the ticket
had already concluded.

**2. `up` invokes `just infra-up` as a shell command rather than a recipe dependency (F1,
`test-gap`).** EXC-016's Task 2 rewrote `up` (`justfile:95-97`) as a body that shells out to
`just infra-up`. It is functionally correct — a nested `just` runs with the justfile's directory
as cwd and propagates a non-zero exit, so a failed `infra-up` does abort before services start —
but it is not idiomatic `just`, and it made EXC-016's own acceptance criterion unfalsifiable:
the ticket expected `just --dry-run up` to "show infra brought up with `--wait` before the
services", and `--dry-run` prints only the `just infra-up` line, never the `--wait` flag:

```
$ just --dry-run up
just infra-up
docker-compose -f infra/docker/compose.services.yml up -d --build
```

Declaring it as `up: infra-up` with only `{{ services }} up -d --build` in the body fixes the
idiom and makes the gate visible to `--dry-run` in one line.

Soft coupling: EXC-014 ("Restructure justfile and CI into per-service mod-imported recipes")
will rewrite both surfaces this ticket touches. Whichever lands second should absorb the other;
worth checking at refinement rather than encoding as a hard dependency.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-17 — created (TO DO). source: review: EXC-016's review findings F3 and F1, batched by
  theme (compose/justfile robustness). Promoted over noting because the missing CI guard let a
  build-breaking config error sit on `main` across four tickets, and five queued tickets plan the
  same container shape that caused it.
