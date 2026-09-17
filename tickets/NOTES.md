# Notes

Hand-written planning notes live here — triage records, parked-ticket notes,
cross-ticket decisions, dependency rationale. `BOARD.md` is generated from the
ticket files (run `pickle board sync`), so nothing hand-written survives there.

## EXC-016 — applicability gate and implementation notes (2026-09-17)

EXC-016's pickup gate (an independent sub-agent audit, per the brine procedure step 3) returned
three blocking findings, each re-confirmed by hand before the plan was amended inline:

1. **Task 1's service list was stale.** EXC-007 had since added the `account-migrate` one-shot
   container — which is the block `docker compose config` actually names — and moved `account`
   onto `depends_on: account-migrate: condition: service_completed_successfully`. The plan as
   written would have deleted that load-bearing gate and missed the offending entry entirely.
2. **Decision 2's premise was false.** It accepted losing the Postgres-health gate because
   "its own healthcheck already gates `infra-up`". It did not: `infra-up` was a plain
   `up -d` with no `--wait`, and `just up` invoked the *merged* `{{ stack }}`, where
   `depends_on: postgres` still did real work. Dropping it unreplaced would have let
   `account-migrate` race Postgres, fail `alembic upgrade head`, and leave `account` and
   `gateway` never starting. Replaced with Task 2, two `justfile` edits.
3. **"No docs to update" was false** — `development/design.md:382-386` described exactly the
   behaviour being removed (and was already stale on two further counts).

Non-blocking findings, all dispositioned inline except the last: the `<svc>-migrate` convention
is now recorded in Decision 1 so EXC-008/009/010/011/012 do not reintroduce the dangling
reference; Decision 1's rationale was corrected (the real objection to merging the compose files
is semantic — `services-down` would stop Postgres — not validity); the acceptance test now
asserts exit status instead of an image count. The `postgres-data` volume being mounted at
`/var/lib/postgresql/docker` while `postgres:18-alpine` declares
`PGDATA=/var/lib/postgresql/18/docker` was promoted to **EXC-017**.

Implemented as one atomic commit `fdf80f3`. Six `postgres:` entries removed from
`compose.services.yml`: `account-migrate`, `clearing` and `notifications` lost the whole
now-empty `depends_on:` key; `risk-engine`, `order-management` and `matching-engine` kept their
inter-service entries; `account`, `market-data` and `gateway` untouched. `{{ stack }}` remains
in use by `down`/`fresh-stack`/`logs`/`ps`, where merged semantics are wanted and `postgres`
resolves. Acceptance: both the one-file and merged `docker compose config` exit 0, `just
services-build` exits 0 building all nine images, `just lint` exits 0, `just test` 66 passed.

Deliberately **not** done, since it would deviate from the confirmed decisions: no mechanical
guard (a `just compose-check` recipe or CI step running `docker compose -f
compose.services.yml config`) was added. Decision 1 records the convention in prose only, so
nothing yet *fails* if a future migrate container reintroduces `depends_on: postgres`.
