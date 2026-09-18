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

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-017-fix-postgres-data-volume-mounted-at-a-path-that-is-not-pg18-pgdata
```

`exchange` is the root-path child (`path = "."`) — tidy WIP commits into atomic ones before
presenting.

### Prerequisite gate (hard)

None.

### Confirmed design decisions (do not deviate without asking)

1. **Volume-mount fix: option (a) — repoint the mount to the image's own `PGDATA`.** Change
   `postgres-data:/var/lib/postgresql/docker` to `postgres-data:/var/lib/postgresql/18/docker`
   in `infra/docker/compose.infra.yml:25`. Chosen over mounting the parent directory (option b)
   or setting `PGDATA` explicitly (option c) for the smallest diff; the tradeoff — the path must
   be revisited on the next Postgres major-version bump — is accepted since nothing currently
   plans one. (User decision, 2026-09-18.)
2. **Healthcheck fix folded in (EXC-016 review finding F9):** add `-h 127.0.0.1` so
   `pg_isready` probes TCP instead of the unix socket the entrypoint's temporary `initdb` server
   serves, and add `start_period: 10s`.
3. **`development/design.md:382`'s "Postgres 17" is corrected to "Postgres 18"** in the same
   change, since it's the same file this ticket is already touching for the volume/healthcheck
   fix.

### Tasks

#### Task 1 — Fix the volume mount path
`infra/docker/compose.infra.yml:25`:
```
    volumes:
      - postgres-data:/var/lib/postgresql/18/docker
```

#### Task 2 — Fix the healthcheck
`infra/docker/compose.infra.yml:26-30`:
```
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U exchange"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s
```

#### Task 3 — Fix the stale version reference
`development/design.md:382`: replace "Postgres 17" with "Postgres 18".

### Acceptance test

- Data survives a recreate: `docker compose -f infra/docker/compose.infra.yml down` (no `-v`),
  `just infra-up`, use `just db-shell` to `INSERT` a row into an existing table (e.g. one the
  `account-migrate` Alembic history already created), `docker compose -f
  infra/docker/compose.infra.yml up -d --force-recreate postgres`, then `just db-shell` again
  and confirm the row is still there. Before the fix this loses the row; after, it doesn't.
- `docker compose -f infra/docker/compose.infra.yml down -v && just infra-up` succeeds (fresh
  volume, first-time `initdb` path) and `just infra-up`'s own `--wait` returns healthy only once
  `just db-shell -c "select 1"` (or equivalent) actually connects over TCP — confirms the
  healthcheck fix didn't just move the false-positive window rather than close it.
- `just lint` / `just test` unaffected (no code paths touch this).

### Docs update (mandatory when user-facing)

`development/design.md:382` corrected as Task 3 — the only doc reference to this file's
Postgres version.

### Finish (mandatory)

1. Both acceptance tests green.
2. Docs updated (Task 3).
3. Write a summary: files touched, which volume-mount option was chosen and why, anything
   deferred (e.g. the next major-version bump will need this path revisited again).
4. Suggest a Conventional Commit message, e.g.:
   ```
   fix(infra): fix postgres data volume path and healthcheck TCP probe (EXC-017)
   ```
5. Tidy WIP commits into atomic ones (root-path child).
6. Commit locally; do not push or open an MR without user approval. Verify
   `git fetch origin main && git diff --name-only origin/main...HEAD | grep '^tickets/'` prints
   nothing before pushing. Present the commit message for approval, then push and open the
   merge request — merging is always the human's.

## Review

- [x] Reviewer independence settled (step 0): implementer authored the branch this session, so
  audits (steps 2-4a) were delegated to a freshly spawned, independent sub-agent with no memory
  of writing the code, briefed adversarially. Every delegated claim (diff contents, grep results,
  acceptance-test output) was re-verified by hand before recording here.
- [x] In-tree stale-branch check (step 0a): `pickle doctor` initially warned the branch's ticket
  copy was stale (had it in `3-in-development`, `main` already had `4-in-review`); rebased onto
  `main`, re-ran clean (0 errors, 0 warnings).
- [x] Implementation audit (step 2) — all three tasks verified against `git diff main...HEAD`:
  volume mount now `postgres-data:/var/lib/postgresql/18/docker` (Task 1), healthcheck now
  `pg_isready -h 127.0.0.1 -U exchange` with `start_period: 10s` (Task 2), `development/design.md`
  now reads "Postgres 18" (Task 3). Both acceptance tests re-run verbatim: fresh-volume
  (`down -v && just infra-up`) reached `Healthy` in ~5.8s with health-log entries confirming a
  genuine TCP accept, not the unix-socket false positive; recreate test (insert probe row →
  `down` (no `-v`) → `infra-up` → row still present) confirms persistence. `just lint`,
  `just test` (67 passed), and `just check` (ruff + `ruff format --check`, addendum step 9) all
  green. All three confirmed design decisions honored.
- [x] Quality audit (step 3) — straight two-line compose edit + one doc-string fix; no new
  security/edge-case surface; `start_period: 10s` doesn't mask real failures (`retries: 10` ×
  `interval: 5s` still bounds total wait).
- [x] Consistency audit (step 4) — repo-wide grep for the old mount path, the old healthcheck
  (`pg_isready -U` without `-h`), and "Postgres 17"/`postgres:17`: no remaining live-config or
  docs hits outside `tickets/` (historical ticket prose correctly preserved as-is).
- [x] Documentation audit (step 4a) — `development/design.md` is the entire shipped docs tree
  per the addendum; read in full, only the one corrected line referenced this file's Postgres
  version.
- [ ] Docs-readability pass (step 4b) — conscious skip: the only prose change is a single-word
  version-number swap, not a readability-relevant edit.
- [x] Findings recorded below; disposition summary + cost line present (step 5).
- [x] Ticket moved to `tickets/6-done/` (step 6b) — zero findings, nothing to disposition.
- [x] Other references / governing documents reconciled (step 7) — `development/design.md`
  already corrected as Task 3.
- [x] Remaining-tickets impact sweep (step 8) — `tickets/1-to-do/EXC-019-...md` referenced this
  ticket's `design.md:382` fix in its own "Deliberately excluded" scope note, in present tense as
  still-pending. Now stale since this ticket fixed that line; corrected in place (History line
  added to EXC-019).
- [x] Summary + commit message & MR attributes presented for approval; overarching bookkeeping
  committed per policy; next-ticket suggestion given (step 9).

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| — | — | — | — | no findings from steps 2-4a | independent audit + hand re-verification, both clean | — |

Disposition summary: 0 findings, nothing to disposition.

cost: estimated S, actual S

## History

- 2026-09-17 — created (TO DO). source: review: surfaced as a non-blocking finding by EXC-016's
  applicability gate, which audited `infra/docker/` while confirming EXC-016's plan was still
  worth executing. Promoted to its own ticket rather than noted-and-closed because it is an
  independently schedulable data-persistence bug in a different file
  (`compose.infra.yml`) with a different fix and its own behavioural acceptance test — it
  shares nothing with EXC-016's `depends_on` change beyond the directory.
- 2026-09-17 — folded in EXC-016 review finding F9 (postgres healthcheck lacks `-h` and
  `start_period`); same file, same acceptance test
- 2026-09-18 — TO DO → READY: plan complete
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
- 2026-09-18 — IN DEVELOPMENT → IN REVIEW: acceptance green
- 2026-09-18 — IN REVIEW → DONE: review: 0 findings
