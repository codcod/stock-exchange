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

Post-merge review: PR #23 was merged (`deddc9a`) before this review ran, so the branch was gone
by review time and the code was audited at `fdf80f3` / `git diff deddc9a^1..deddc9a` (verified
byte-identical on +/- lines). No blocking finding arose, so step 6c's "file it as its own
ticket" route was not needed.

- [x] Reviewer independence settled (step 0): **delegated** — the reviewing agent authored the
      branch in this session, so audits (steps 2-4a) went to a freshly spawned independent
      reviewer briefed adversarially; every returned finding was re-verified by hand before
      entering the table below, and classification, dispositions and the move stayed with the
      orchestrating reviewer
- [x] Implementation audit — acceptance test re-run verbatim, tasks & criteria verified (steps 1, 2)
- [x] Quality audit (step 3)
- [x] Consistency audit (step 4)
- [x] Documentation audit — coverage + whole-tree sweep done; no docs build to run (addendum
      step 1: `development/design.md` is hand-maintained prose, no docs command configured)
- [x] Docs-readability pass — **skipped: no reviewer available.** `opencode` is on PATH but no
      `docs-readability` agent is configured (`grep -c docs-readability ~/.config/opencode/opencode.jsonc`
      → 0), and this host exposes no `docs_readability` tool. Sanctioned conscious skip (step 4b);
      0 suggestions, 0 discarded as fabricated
- [x] Findings recorded with severity, class and disposition; disposition summary + cost line below (step 5)
- [x] Ticket moved to `tickets/6-done/`; `## History` appended (step 6)
- [x] Other references updated; governing documents reconciled (step 7 — see F5/F6 and EXC-019)
- [x] Remaining-tickets impact sweep done (step 8)
- [x] Summary + commit message & MR attributes presented for approval; `origin/main...HEAD`
      verified to carry no `tickets/` path before the push (in-tree, step 9); bookkeeping
      committed with explicit pathspecs

### Findings

| id | severity | class | disposition | description | evidence | suggestion |
|---|---|---|---|---|---|---|
| F1 | non-blocking | test-gap | noted | The acceptance test's `--wait` criterion cannot fail: `just --dry-run up` prints the `just infra-up` line, never the `--wait` flag | `just --dry-run up` → `just infra-up` / `docker-compose -f infra/docker/compose.services.yml up -d --build`; exit 0 | Criterion was unfalsifiable as written; the fix (a recipe dependency) is F1b |
| F1b | non-blocking | design | new ticket → EXC-018 | `up` shells out to `just infra-up` instead of declaring it a recipe dependency — works and propagates failure, but is non-idiomatic and hides the gate from `--dry-run` | `justfile:95-97` | `up: infra-up` with only `{{ services }} up -d --build` in the body |
| F2 | non-blocking | test-gap | noted | Acceptance test lists `just lint` and `just test` but not `just check`, so it does not cover CI's `ruff format --check` (addendum step 2 item 3 mandates this class) | ticket Acceptance test vs `.github/workflows/ci.yaml:26-30` | No damage: `just check` → exit 0, `118 files already formatted`. Class recorded; no code change |
| F3 | non-blocking | test-gap | new ticket → EXC-018 | Nothing mechanically prevents a dangling `depends_on` reaching `main` again, and five queued tickets plan the container shape that caused it | `.github/workflows/ci.yaml` has only `lint` (:9) and `test` (:32), no `docker compose config`; `tickets/1-to-do/EXC-008:32`, EXC-009, EXC-010, EXC-011, EXC-012 plan `<svc>_migrate` containers, none citing EXC-016 | `compose-check` recipe (one-file **and** merged `config -q`) wired into CI; patch the five tickets to cite Decision 1's convention |
| F4 | non-blocking | stale-xref | new ticket → EXC-019 | Tier 1 banner comment made false by this branch: there is no Postgres dependency left in the file, and `account` (Tier 1) does have a service dependency | `infra/docker/compose.services.yml:15` — `# Tier 1: no service dependencies — only Postgres` | Reword to name the `account-migrate` one-shot |
| F5 | non-blocking | docs-gap | new ticket → EXC-019 | This branch's own new prose overstates the waits: 3 of the 4 services named do not wait on services they call | `development/design.md:386` vs `compose.services.yml` — gateway sets CLEARING/RISK_ENGINE/NOTIFICATIONS_URL (:203,205,208) but `depends_on` (:211-219) omits them; matching-engine calls 4 (:174-178), waits on 1 (:187-189); order-management calls matching-engine (:143), waits on it nowhere (:154-160) | Say they wait on a *subset*, the rest covered by application-level retry |
| F6 | non-blocking | docs-gap | new ticket → EXC-019 | Same new paragraph's `python -m` / `localhost:800X` claim is false for `account-migrate`, the container it just added to the count | `development/design.md:383,386` vs `compose.services.yml:22` (`command: ["-m", "alembic", "upgrade", "head"]`, no `ports:`) | Scope the sentence to the eight long-running services |
| F7 | non-blocking | docs-gap | new ticket → EXC-019 | The corrected service count was not propagated to the two other places carrying a stale one | `infra/docker/compose.services.yml:1` "all eight microservices" (nine blocks); `README.md:12` "all six microservices" vs `development/design.md:48` "eight" | One-line fix in each; README's is the most visible |
| F8 | non-blocking | other | noted | Every commit of this ticket carries a `Co-Authored-By: Claude …` trailer and PR #23's body carried a "Generated with Claude Code" line, both forbidden outright by the user's global instructions, which explicitly override the harness default | `git log --format=%B` on `fdf80f3`, `029d38f`, `516f68d`, `13ef7ba`, `e25f426` | PR body corrected via `gh pr edit 23`. The six commit trailers are merged and published; removing them needs a history rewrite, which is not worth it — the actionable part is not repeating it |
| F9 | non-blocking | design | folded → EXC-017 | Postgres healthcheck can report healthy mid-`initdb`, so `--wait` is weaker than the new prose asserts — pre-existing, not a regression | `infra/docker/compose.infra.yml:26-30` — `pg_isready -U exchange`, no `-h`, no `start_period`; the identical check previously backed the removed `depends_on` | `pg_isready -h 127.0.0.1` and/or `start_period: 10s`; EXC-017 already owns this file |
| F10 | non-blocking | stale-xref | fixed inline | This review's own implementation notes named a `fresh-stack` recipe that does not exist | `tickets/NOTES.md` vs `justfile` — no `fresh-stack`; the fourth `{{ stack }}` user is `db-wipe` (`justfile:106-108`), and `fresh` is `clean-all install` (`justfile:40`) | Corrected to `db-wipe` in `tickets/NOTES.md` |

**Disposition summary:** 11 non-blocking findings, 0 blocking — 3 noted (F1, F2, F8), 1 fixed
inline (F10), 1 folded (F9 → EXC-017), 6 new ticket batched into 2 by theme (F1b, F3 → EXC-018
compose/justfile robustness; F4, F5, F6, F7 → EXC-019 documentation accuracy).

```
cost: estimated S, actual S
```

### Verdict

**Implementation audit — all tasks and decisions met.** Task 1 removed exactly six `postgres:`
entries and no others: whole `depends_on:` blocks from `account-migrate`, `clearing` and
`notifications`; the `postgres:` sub-key only from `risk-engine`, `order-management` and
`matching-engine`. `account`, `market-data` and `gateway` are untouched in the diff, and
`account` retains `depends_on: account-migrate: condition: service_completed_successfully`
(`compose.services.yml:43-45`). Every surviving `postgres` string in the file is a `DATABASE_URL`
hostname. Task 2 landed both justfile edits. Decision 3 verified entry by entry.

**Decision 1's rationale survives adversarial testing.** Its deciding reason — that merging the
compose files would make `services-down` also stop Postgres — requires that one-file `down`
today does *not*. Since both files declare `name: exchange`, project-label scoping made that
doubtful; a scratch two-file project sharing one `name:` settled it: `docker compose -f b.yml ps -a`
does list the sibling container, but `docker compose -f b.yml down` removed only its own and
left the sibling running. The rationale holds.

**Decision 2 met on the path it names, partially met as a general guarantee.** `just up` gates on
Postgres health through `infra-up --wait`, and `docker compose up --help` confirms `--wait` means
"wait for services to be running|healthy". Two caveats, both recorded: F1 (the gate is invisible
to the acceptance test) and F9 (the healthcheck itself is imprecise on a fresh volume).

**Nothing regressed; six recipes went from always-broken to working.** Against the pre-change
file (`git show deddc9a^1:infra/docker/compose.services.yml`) every one-file subcommand failed —
`config`, `down --dry-run`, `logs` and `ps` all printed `depends on undefined service "postgres":
invalid compose project` — which also confirms this ticket's claim that the file was invalid for
`build`/`up`/`down`/`logs`. `services-build`, `services-up`, `services-down`, `services-logs`,
`service-logs` and `redeploy` now work. `just up` keeps its health gate; `just db-wipe` inherits
it; `scripts/dev-tmux.sh:40` calls `just infra-up` and silently gained it. `just services-up` and
`just redeploy <svc>` still have no Postgres gate of their own, so run without a prior `infra-up`
they now yield a silent partial stack where they previously yielded a loud invalid-project error
— strictly better than 100% broken, and the precondition is documented at `justfile:68`.

**Commands re-run:** one-file `config` 0 · merged `config` 0 · `just services-build` 0 (nine
images) · `just --evaluate` 0 · `just --dry-run up` 0 · `just lint` 0 · `just test` 0 (66 passed)
· `just check` 0 · `just fmt-check` 0 (118 files already formatted).

**Not observed:** `just up` and `just infra-up` were never executed end-to-end, by the
implementer or the reviewer — port 5432 on this machine is held by an unrelated project and a
leftover `exchange-postgres-1` sits in `Created` state with `Bind for 0.0.0.0:5432 failed`. So
`--wait`'s runtime behaviour and F9's initdb race are reasoned from `docker compose up --help`
and the Postgres image's entrypoint, not demonstrated. F9 carries that caveat into EXC-017.

**Quality audit:** the branch changes six YAML lines, two justfile lines and one doc paragraph and
touches no Python, so the addendum's async-discipline, 200-line, outbox-map and
stateful/stateless checks have nothing to bite on. Stated explicitly rather than padded. No
security surface.

**Step 7 — governing documents:** `development/design.md`'s Infrastructure section was rewritten
by the branch itself; two inaccuracies in that new prose are F5 and F6, reconciled via EXC-019
rather than edited here, since a code/docs fix needs a feature branch and this project is
publish-gated. `development/design.md`'s "What's intentionally simplified" section contains no
entry about compose ordering, so none was owed. The data flow did not change, so the addendum's
step-7 "Detailed architecture" rule is satisfied by the Infrastructure rewrite already made.

**Step 8 — impact sweep:** no ticket lists EXC-016 in `depends-on:`. EXC-008/009/010/011/012 each
plan a `<svc>_migrate` one-shot container and none cites Decision 1's convention — carried into
EXC-018 as an item rather than patched here. EXC-014 will rewrite the `justfile` and CI surfaces
EXC-018 touches; noted as a soft coupling in EXC-018, not a hard dependency.
## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — TO DO → READY: plan complete
- 2026-09-17 — plan amended inline: applicability gate found Task 1 stale, Decision 2's premise
  false, and the docs claim wrong (see Notes)
- 2026-09-17 — READY → IN DEVELOPMENT: picked up
- 2026-09-17 — IN DEVELOPMENT → IN REVIEW: acceptance green (fdf80f3); publish pending approval
- 2026-09-17 — published: branch pushed, MR opened (PR #23, fdf80f3); awaiting human merge
- 2026-09-17 — merged to main (PR #23, deddc9a)
- 2026-09-17 — IN REVIEW → DONE: no blocking findings; 11 non-blocking dispositioned (3 noted, 1 fixed inline, 1 folded to EXC-017, 6 batched into EXC-018/EXC-019)
