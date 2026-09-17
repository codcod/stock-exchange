---
id: EXC-017
title: Fix postgres-data volume mounted at a path that is not PG18 PGDATA
project: exchange
depends-on: []
spawned-by: [EXC-016]
impact: medium
complexity: low
cost: S
---

# EXC-017 — Fix postgres-data volume mounted at a path that is not PG18 PGDATA

## Outcome

After this ships, local Postgres data survives a container recreate: `just infra-down && just
infra-up` (or any `docker compose up --force-recreate`) comes back with the same database
instead of an empty one. Today the named `postgres-data` volume is mounted at a path the
server never writes to, so every recreate silently starts from scratch and the accumulated
accounts, orders and trades of a dev session are lost.

## Description

Found during EXC-016's applicability gate (an independent audit of `infra/docker/`, not
something EXC-016 introduced or is in scope to fix). `infra/docker/compose.infra.yml:25`
mounts the named volume as `postgres-data:/var/lib/postgresql/docker`, but the `postgres:18-alpine`
image (`compose.infra.yml:17`) declares `PGDATA=/var/lib/postgresql/18/docker` — verified with
`docker image inspect postgres:18-alpine --format '{{range .Config.Env}}{{println .}}{{end}}'`.
The paths do not match, so the named volume holds nothing the server writes, and the real data
directory lands in the image's own declared volume — a fresh anonymous volume on every
recreate. The mount path looks like it was carried over from a pre-18 image layout, where
`PGDATA` sat directly under `/var/lib/postgresql`; the 18 images moved it under a
major-version directory.

Fix options to weigh during refinement: (a) point the mount at the image's `PGDATA`
(`postgres-data:/var/lib/postgresql/18/docker`) — smallest change, but the path has to be
revisited on every major-version bump; (b) mount the parent (`postgres-data:/var/lib/postgresql`)
so the version directory lives inside the volume and a bump needs no compose edit — but a
major-version bump then finds an old-version data directory in place, which the image refuses
to start against, so the upgrade becomes explicit rather than silent (arguably the safer
failure); (c) set `PGDATA` explicitly in `environment:` and mount to match, making the
coupling local and visible. Whichever is chosen, the acceptance test should be behavioural —
write a row, recreate the container, read it back — and not merely that the path strings agree.

**Second item, folded in from EXC-016's review (finding F9, `design`).** The same file's
healthcheck (`compose.infra.yml:26-30`) is `pg_isready -U exchange` with `interval: 5s`,
`retries: 10` and **no `start_period`**. With no `-h`, `pg_isready` probes the local unix
socket, which the official Postgres entrypoint serves during first-time `initdb` using a
temporary server started with `listen_addresses=''`. So on a fresh volume the healthcheck can
report healthy before the database accepts TCP connections. This is pre-existing and not a
regression — the identical healthcheck previously backed `compose.services.yml`'s
`depends_on: postgres: condition: service_healthy` — but EXC-016 moved the gate into
`just infra-up --wait` and `development/design.md:386` now asserts "Postgres is healthy before
any service starts" as a positive guarantee, so the healthcheck's precision started mattering
more. Cheap fix, natural to land with the volume change since both touch this file:
`test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U exchange"]` and/or `start_period: 10s`. Note
this was reasoned from the Postgres image's entrypoint behaviour and `docker compose up --help`,
not reproduced — a runtime check belongs in this ticket's acceptance test.

Note also that `development/design.md:382` still describes this file as "Postgres 17" while
the image is `postgres:18-alpine`; the docs step should correct that line. EXC-016 deliberately
left it alone to keep its own diff scoped.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-17 — created (TO DO). source: review: surfaced as a non-blocking finding by EXC-016's
  applicability gate, which audited `infra/docker/` while confirming EXC-016's plan was still
  worth executing. Promoted to its own ticket rather than noted-and-closed because it is an
  independently schedulable data-persistence bug in a different file
  (`compose.infra.yml`) with a different fix and its own behavioural acceptance test — it
  shares nothing with EXC-016's `depends_on` change beyond the directory.
- 2026-09-17 — folded in EXC-016 review finding F9 (postgres healthcheck lacks `-h` and
  `start_period`); same file, same acceptance test
