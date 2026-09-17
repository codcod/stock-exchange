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
   `services-*` `just` recipes.** The Description's two options were weighed: merging compose
   files only fixes `services-build`, leaving `services-up`/`services-down`/`services-logs`/
   `service-logs`/`redeploy` — every other recipe that invokes `compose.services.yml` alone —
   equally invalid for the same reason (`depends_on: postgres` referencing a service this file
   never defines breaks *any* one-file invocation, not just `build`). Dropping the dangling
   `postgres:` entries is the one fix that makes the file valid on its own for every recipe
   that uses it alone, and it matches the file's own stated design (its header comment: "Requires
   the 'exchange' network created by compose.infra.yml" — the cross-stack coupling is the
   shared external Docker network, not compose's own `depends_on` startup ordering, which
   cannot span two separate compose projects/files).
2. **Losing the "wait until postgres is healthy" gate is accepted.** In the documented
   sequence (`just infra-up` before `just services-up`/`services-build`), Postgres is already
   up (and its own healthcheck already gates `infra-up` — see `compose.infra.yml`) by the time
   `compose.services.yml` is invoked, so there is no real ordering loss, only the removal of an
   already-broken (uncheckable across files) promise.
3. **Every other `depends_on:` entry in this file is untouched** — only the `postgres:`
   sub-key is removed from each map; a service that also waits on another service in this same
   file (`risk-engine` → `account`; `order-management` → `risk-engine`, `account`,
   `notifications`; `matching-engine` → `order-management`) keeps that entry. Where `postgres`
   was the *only* key, the whole `depends_on:` block is removed (an empty `depends_on: {}`
   would be equivalent but noisier).

### Tasks

#### Task 1 — Edit `infra/docker/compose.services.yml`
In each service block, remove just the `postgres:` sub-entry from `depends_on:` (dropping the
whole `depends_on:` key when `postgres` was its only entry):
- `account`: `depends_on:` (only `postgres`) → remove the whole block.
- `clearing`: same → remove the whole block.
- `notifications`: same → remove the whole block.
- `risk-engine`: `depends_on: {postgres, account}` → keep only `account: condition:
  service_healthy`.
- `order-management`: `depends_on: {postgres, risk-engine, account, notifications}` → drop
  `postgres`, keep the other three.
- `matching-engine`: `depends_on: {postgres, order-management}` → drop `postgres`, keep
  `order-management`.
- `market-data` and `gateway` already have no `postgres` entry — untouched.

### Acceptance test

From the repo root, on `feat/EXC-016-fix-compose-services-yml-depends-on-postgres`:
```
docker compose -f infra/docker/compose.services.yml config >/dev/null
just services-build
```
Expect: `config` prints no "depends on undefined service" error and `just services-build`
succeeds (all eight images build) — the failure this ticket exists to fix is gone. Also run
`just lint` and `just test` to confirm this compose-only change doesn't touch anything they
cover (expected: unaffected, still green).

### Docs update (mandatory when user-facing)

No user-facing surface — this is an infra config fix with no docs describing the old (broken)
behavior to update.

### Finish (mandatory)

1. Acceptance test green (`just services-build` succeeds); `just lint`/`just test` unaffected.
2. No docs to update.
3. Write a summary: which `depends_on: postgres` entries were removed and why, referencing the
   design decision above.
4. Suggested commit message:
   ```
   fix: drop dangling postgres depends_on from compose.services.yml (EXC-016)

   compose.services.yml declared depends_on: postgres in six service
   blocks, but postgres is only defined in the separate
   compose.infra.yml, making any one-file invocation (build, up, down,
   logs) an invalid compose project. The cross-stack dependency is
   already carried by the shared external `exchange` network, not by
   compose's own startup ordering.
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
