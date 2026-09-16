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

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
