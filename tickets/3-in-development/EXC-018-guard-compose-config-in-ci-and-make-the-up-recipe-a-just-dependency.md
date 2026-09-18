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
unchanged" while it sat there. EXC-016's Decision 1 recorded the convention in prose only —
future `<svc>-migrate` containers put their Postgres ordering in the `justfile`, never in
`depends_on: postgres`. **Re-verified at refinement (2026-09-18): EXC-008 through EXC-012 have
since shipped and merged** (each did follow the convention — `compose.services.yml`'s
`<svc>-migrate` containers have no `depends_on: postgres`), so there is nothing left to patch
retroactively; only the missing mechanical guard remains in scope. Suggested fix: a
`compose-check` recipe running `docker compose -f infra/docker/compose.infra.yml config -q`,
the single-file `compose.services.yml` form, and the merged two-file form, wired into CI.

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

**EXC-014 landed first (impact sweep, 2026-09-18) — `.github/workflows/ci.yaml` no longer
exists.** CI is now `service-ci.yml` (reusable; `lint` job runs `just "<service>" lint`) called
by nine path-filtered `ci-<service>.yml`, plus one always-on `ci-repo.yml` (`lint` job runs
`just lint-repo`, no path filter — runs on every push/PR regardless of which file changed). The
compose files this ticket guards (`infra/docker/compose.*.yml`) aren't under any
`platform/<service>/` path, so a per-service workflow's path filter would never fire on a
compose-only edit; `ci-repo.yml` is the only one of the ten that reliably runs on every PR
regardless of path, so the guard belongs in its `lint` job, not any per-service one (Decision 1
and Task 2 below, patched accordingly). Still soft-coupled to EXC-002 ("Add static
type-checking (ty) to lint pipeline and CI", `2-ready/`), which will hit the same
now-nonexistent `ci.yaml` target — whichever of EXC-018/EXC-002 lands second should place its
new step without clobbering the other's, same as before, just against the new file.

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-018-guard-compose-config-in-ci-and-make-up-recipe-a-just-dependency
```

`exchange` is the root-path child (`path = "."` in `pickle.toml`) — tidy WIP commits into
atomic ones before presenting (Finish, below).

### Prerequisite gate (hard)

None. No `depends-on:`; no unmerged branches this ticket builds on.

### Confirmed design decisions (do not deviate without asking)

1. **The compose-config guard runs as a new step inside `ci-repo.yml`'s existing `lint` job**
   (patched 2026-09-18 impact sweep — was `ci.yaml`'s `lint` job before EXC-014 deleted that
   file; `ci-repo.yml` is the only always-on workflow left, see Description), not a new job —
   decided at refinement to avoid an extra runner startup for a check that takes a few seconds.
   (User decision, 2026-09-18.)
2. **The guard checks all three compose invocations the repo actually uses**: the infra-only
   file, the services-only file, and the merged two-file form — not just the one EXC-016 fixed,
   since a future dangling reference could appear in either file or only surface in the merge.
3. **`up` becomes `up: infra-up` with only the services-up line in its body** (rules out the
   `just infra-up` shell-out EXC-016 left behind), so `just --dry-run up` shows both lines,
   `infra-up`'s own dry-run output (including the `--wait` flag) and the services line.

### Tasks

#### Task 1 — Add a `compose-check` recipe
Add to `justfile` in the `[group('qa')]` block (near `lint`/`fmt-check`):
```
[group('qa')]
compose-check:
    docker compose -f infra/docker/compose.infra.yml config -q
    docker compose -f infra/docker/compose.services.yml config -q
    docker compose -f infra/docker/compose.infra.yml -f infra/docker/compose.services.yml config -q
```
Note GitHub Actions runners ship the `docker compose` v2 plugin (space, not the hyphenated
`docker-compose` the rest of the `justfile` uses via its `infra`/`services`/`stack` variables)
— this recipe intentionally uses `docker compose` to match what CI has installed; leave the
existing hyphenated variables alone, that's out of this ticket's scope.

#### Task 2 — Wire the guard into CI
In `.github/workflows/ci-repo.yml`'s `lint` job, add a step after "Lint" (`just lint-repo`) —
or after whatever step EXC-002/other tickets have since added there — place it without removing
an existing step:
```yaml
      - name: Validate compose config
        run: just compose-check
```
`ci-repo.yml`'s job already installs `just` (`extractions/setup-just@v3`, EXC-014) — no new
setup step needed; re-confirm at pickup in case that's changed.

#### Task 3 — Make `up` a just recipe dependency
`justfile`, the `up` recipe (currently a body that shells `just infra-up`):
```
[group('stack')]
up: infra-up
    {{ services }} up -d --build
```

### Acceptance test

- `just --dry-run up` prints the `infra-up` recipe's own commands (including the `--wait` flag
  passed to `{{ infra }} up -d --wait`) followed by the services-up line — the `--wait` gate is
  now visible without running anything.
- `just compose-check` passes on the current (fixed) compose files.
- Temporarily reintroduce a dangling `depends_on:` reference in `compose.services.yml`, confirm
  `just compose-check` fails non-zero with docker compose's own error naming the missing
  service, then revert — do not commit the broken state.
- `just lint-repo` and the `ci-repo.yml` `lint` job (run locally via `act` or by re-reading the
  job's exact commands) both stay green with the new step added.

### Docs update (mandatory when user-facing)

No user-facing surface — this is internal CI/tooling plumbing (`justfile`, `ci-repo.yml`); no
docs reference the old `up` shell-out or the absence of a compose guard.

### Finish (mandatory)

1. Acceptance test green; `just lint` and `just test` clean.
2. No docs to update (see above).
3. Write a summary: files touched, the `lint`-job-vs-new-job decision, anything deferred.
4. Suggest a Conventional Commit message, e.g.:
   ```
   fix(ci): guard compose config and make up depend on infra-up (EXC-018)
   ```
5. Tidy WIP commits into atomic ones (root-path child).
6. Commit locally; do not push or open an MR without user approval. Under `layout = "in-tree"`,
   before pushing verify `git fetch origin main && git diff --name-only origin/main...HEAD |
   grep '^tickets/'` prints nothing. Present the commit message for approval, then push and
   open the merge request — merging is always the human's.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-17 — created (TO DO). source: review: EXC-016's review findings F3 and F1, batched by
  theme (compose/justfile robustness). Promoted over noting because the missing CI guard let a
  build-breaking config error sit on `main` across four tickets, and five queued tickets plan the
  same container shape that caused it.
- 2026-09-18 — TO DO → READY: plan complete
- 2026-09-18 — plan amended: EXC-014's review impact sweep patched Decision 1 and Task 2 to
  target `ci-repo.yml`'s `lint` job instead of the now-deleted `ci.yaml`
- 2026-09-18 — READY → IN DEVELOPMENT: picked up
- 2026-09-18 — implemented on `feat/EXC-018-guard-compose-config-in-ci-and-make-up-recipe-a-just-dependency`
  (commit `cb2bb8d`): added `compose-check` to the `justfile`'s `[group('qa')]` block (checks
  the infra-only, services-only, and merged two-file compose forms), wired it into
  `ci-repo.yml`'s `lint` job as a step after `just lint-repo`, and changed `up` from a body that
  shelled out `just infra-up` to `up: infra-up` so `just --dry-run up` now shows the `--wait`
  gate. Acceptance test run: `just --dry-run up` prints `infra-up`'s commands (incl. `--wait`)
  followed by the services-up line; `just compose-check` passes on the current compose files;
  temporarily reintroducing a dangling `postgres` reference in `compose.services.yml` made
  `just compose-check` fail non-zero with docker compose's own "depends on undefined service"
  error, then reverted; `just lint`, `just lint-repo`, and `just test` (67 passed) all green.
  Nothing deferred.
