---
id: EXC-016
title: Fix compose.services.yml depends_on referencing undefined postgres service
project: exchange
depends-on: []
spawned-by: [EXC-004]
impact: medium
complexity: low
cost: S
---

# EXC-016 — Fix compose.services.yml depends_on referencing undefined postgres service

## Outcome

After this ships, `just services-build` (the `exchange` child's configured build command) succeeds
instead of failing with `service "<name>" depends on undefined service "postgres": invalid compose
project` — currently every service in `infra/docker/compose.services.yml` declares `depends_on:
postgres`, but `postgres` is only defined in the separate `infra/docker/compose.infra.yml`, which
`docker-compose -f infra/docker/compose.services.yml build` never sees.

## Description

Found during EXC-004's review (validate ticket EXC-004): `just services-build` fails outright, on
`main` and independent of EXC-004's changes (reproduced by checking out the parent commit and
re-running it) — a pre-existing bug, not something EXC-004 introduced or is in scope to fix.
`compose.services.yml`'s own header comment says it "Requires the 'exchange' network created by
compose.infra.yml", i.e. it's designed to run against an already-up `postgres` at runtime via the
shared external `exchange` network — but `depends_on` is validated against services defined in the
same compose invocation, so declaring it without ever merging in `compose.infra.yml` (or defining a
stub/external `postgres` entry) makes the project invalid for `build` (and any other one-file
invocation), not just `up`. Fix options to weigh: merge both compose files in the `services-build`/
`services-up`/etc. `just` recipes (`docker-compose -f compose.infra.yml -f compose.services.yml
...`), so `postgres` resolves from the merged project; or drop the `depends_on: postgres` entries
from `compose.services.yml` entirely, since the actual cross-stack dependency is already carried
by the external `exchange` network, not by compose's own startup ordering. This blocks every
future ticket's `just services-build` acceptance step, not only EXC-004's.

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-016-fix-compose-services-yml-depends-on-postgres
```

Work and commit locally per the project's commit policy (`exchange` is a root-path child —
tidy WIP commits into atomic ones before presenting; no push/MR without explicit user
approval).

### Prerequisite gate (hard)

None. `depends-on: []`.

### Confirmed design decisions (do not deviate without asking)

1. **Drop the `postgres:` entry from every `depends_on:` map in
   `infra/docker/compose.services.yml`, rather than merging `compose.infra.yml` into the
   `services-*` `just` recipes.** Both of the Description's options would make
   `services-build` valid; the deciding reason is semantic, not validity. Merging is
   mechanically easy (`{{ stack }}` already exists at `justfile:6`, and every `services-*`
   recipe is a one-token swap), but it would change what those recipes *mean*: `services-down`
   would also stop Postgres, and `services-up` would no longer be services-only. Dropping the
   dangling `postgres:` entries keeps each recipe's scope intact and makes the file valid on
   its own for every one-file invocation (`build`, `up`, `down`, `logs`, `redeploy`), which
   matches the file's own stated design — its header comment "Requires the 'exchange' network
   created by compose.infra.yml": the cross-stack coupling is the shared external Docker
   network, not compose's `depends_on` startup ordering, which cannot span two compose files.

   **Convention for future work (this is why the fix must not regress):** a `<svc>-migrate`
   one-shot container genuinely *does* need to wait for Postgres. That ordering belongs in the
   `justfile` (infra brought up with `--wait` before services), **never** in a
   `depends_on: postgres` entry inside `compose.services.yml`. EXC-008/009/010/011/012 each
   plan a `<svc>_migrate` container on EXC-007's precedent and would otherwise reintroduce the
   exact dangling reference this ticket removes.

2. **The "wait until Postgres is healthy" gate is preserved in the `justfile`, not dropped.**
   The original plan accepted losing it on the premise that "its own healthcheck already gates
   `infra-up`". That premise is false: `infra-up` (`justfile:44-46`) is a plain
   `{{ infra }} up -d` with **no `--wait`** (`grep -- '--wait' justfile` matches nothing), so
   it returns when the container *starts*, not when it is healthy. Worse, `just up`
   (`justfile:95-97`) invokes the **merged** `{{ stack }}`, where `depends_on: postgres` today
   resolves and does real work — dropping it unreplaced would let `account-migrate` run
   `alembic upgrade head` against a not-yet-ready Postgres, exit non-zero, and so leave
   `account` (gated on `service_completed_successfully`) and then `gateway` never starting.
   `just up` is the documented one-command entry point (`README.md:12-13`,
   `development/design.md:47-48`, `compose.services.yml:4`). The fix is therefore two
   `justfile` edits alongside the compose change (Task 2), which preserve the ordering on every
   path instead of accepting a regression.

3. **Every other `depends_on:` entry in this file is untouched** — only the `postgres:`
   sub-key is removed from each map; a service that also waits on another service in this same
   file (`risk-engine` → `account`; `order-management` → `risk-engine`, `account`,
   `notifications`; `matching-engine` → `order-management`) keeps that entry. Where `postgres`
   was the *only* key, the whole `depends_on:` block is removed (an empty `depends_on: {}`
   would be equivalent but noisier). **`account` is explicitly left alone**: it waits on
   `account-migrate: condition: service_completed_successfully`, which is load-bearing and has
   nothing to do with this bug.

### Tasks

#### Task 1 — Edit `infra/docker/compose.services.yml`
In each service block, remove just the `postgres:` sub-entry from `depends_on:` (dropping the
whole `depends_on:` key when `postgres` was its only entry). Six maps carry it:
- `account-migrate`: `depends_on:` (only `postgres`) → remove the whole block. *(Added by
  EXC-007 after this ticket was first written; it is the block the error message actually
  names.)*
- `clearing`: same → remove the whole block.
- `notifications`: same → remove the whole block.
- `risk-engine`: `depends_on: {postgres, account}` → keep only `account: condition:
  service_healthy`.
- `order-management`: `depends_on: {postgres, risk-engine, account, notifications}` → drop
  `postgres`, keep the other three.
- `matching-engine`: `depends_on: {postgres, order-management}` → drop `postgres`, keep
  `order-management`.
- `account`, `market-data` and `gateway` have no `postgres` entry — untouched.

#### Task 2 — Preserve the Postgres-health ordering in `justfile`
- `infra-up`: `{{ infra }} up -d` → `{{ infra }} up -d --wait`, so the recipe returns only
  once Postgres passes its healthcheck (`compose.infra.yml:26-30`).
- `up`: replace the single merged `{{ stack }} up -d --build` with `just infra-up` followed by
  `{{ services }} up -d --build`, so infra is healthy before any service (notably
  `account-migrate`) starts. Reusing `infra-up` also reuses its network-create guard, so the
  duplicated `docker network inspect` line in `up` goes away.

### Acceptance test

From the repo root, on `feat/EXC-016-fix-compose-services-yml-depends-on-postgres`:
```
docker compose -f infra/docker/compose.services.yml config >/dev/null
docker compose -f infra/docker/compose.infra.yml -f infra/docker/compose.services.yml config >/dev/null
just services-build
just --evaluate >/dev/null && just --dry-run up
```
Expect: both `config` invocations exit 0 with no "depends on undefined service" error (the
one-file case is the failure this ticket exists to fix; the merged case proves the fix did not
break it), `just services-build` exits 0, and `just --dry-run up` shows infra brought up with
`--wait` before the services. Assert exit status, not an image count. Also run `just lint` and
`just test` to confirm this config-only change doesn't touch anything they cover (expected:
unaffected, still green).

### Docs update (mandatory when user-facing)

`development/design.md:382-386` documents the exact behaviour being removed and is already
stale on two further counts. Rewrite it:
- `:382` — "Six service containers; all depend only on Postgres health" → the file now holds
  nine service blocks (eight long-running services plus the `account-migrate` one-shot), and
  they no longer declare a Postgres dependency.
- `:386` — drop the claim that "All six service containers share a single
  `depends_on: postgres: condition: service_healthy` — no inter-service dependency ordering is
  enforced by docker-compose". Inter-service `depends_on` does exist now (`risk-engine`,
  `order-management`, `matching-engine`, `gateway`, `account`); Postgres ordering is enforced
  by `just infra-up --wait` instead.
- Leave `:382`'s "Postgres 17" (actually `postgres:18-alpine`) and the `postgres-data` volume
  path alone unless the line is being rewritten anyway — the volume path is a separate bug
  filed as its own ticket.

### Finish (mandatory)

1. Acceptance test green (`just services-build` succeeds); `just lint`/`just test` unaffected.
2. `development/design.md:382-386` updated per the docs step.
3. Write a summary: which `depends_on: postgres` entries were removed, the `justfile` edits
   that preserve the health ordering, and why — referencing the design decisions above.
4. Suggested commit message:
   ```
   fix: drop dangling postgres depends_on from compose.services.yml (EXC-016)

   compose.services.yml declared depends_on: postgres in six service
   blocks, but postgres is only defined in the separate
   compose.infra.yml, making any one-file invocation (build, up, down,
   logs) an invalid compose project. The cross-stack dependency is
   already carried by the shared external `exchange` network, not by
   compose's own startup ordering.

   The Postgres-health ordering that entry provided on the merged
   `just up` path is preserved in the justfile instead: infra-up now
   passes --wait, and up brings infra up before the services rather
   than starting both from one merged project.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-016 in-review --reason "acceptance green"` and hand back.

## Review

<!-- empty until IN REVIEW -->
## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — TO DO → READY: plan complete
- 2026-09-17 — plan amended inline: applicability gate found Task 1 stale, Decision 2's premise
  false, and the docs claim wrong (see Notes)
- 2026-09-17 — READY → IN DEVELOPMENT: picked up
- 2026-09-17 — IN DEVELOPMENT → IN REVIEW: acceptance green (fdf80f3); publish pending approval
- 2026-09-17 — published: branch pushed, MR opened (PR #23, fdf80f3); awaiting human merge
