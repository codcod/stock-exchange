---
id: EXC-001
title: Add Repository/Unit-of-Work base classes and migrate account + order_management
project: exchange
depends-on: []
spawned-by: []
impact: medium
complexity: medium
cost: L
---

# EXC-001 — Add Repository/Unit-of-Work base classes and migrate account + order_management

## Outcome

After this ships, a developer touching `account` or `order_management` writes transactional
persistence code against one shared `AbstractUnitOfWork`/`AbstractRepository` pair instead of
each service hand-rolling its own commit/rollback split, and a forgotten `commit()` rolls back
safely by default instead of silently doing nothing.

## Description

Every stateful service currently manages its own transactions ad hoc. `services/account/repository.py`
is the clearest example: `AccountRepository.save()` opens its own `engine.begin()` transaction,
while `save_with_conn()` takes a borrowed connection for callers that need to join an existing
transaction — the same split, hand-written per repository, with no shared base class and no
guaranteed rollback-on-forgotten-commit.

This mirrors a pattern already proven in a reference project
(`~/Projects/private/monolith`, `stelo-base/src/stelo/base/unit_of_work.py`): an
`AbstractUnitOfWork` ABC as an async context manager whose `__aexit__` always calls `rollback()`
(so a forgotten `commit()` is safe-by-default, not a silent no-op), and an `AbstractRepository[T]`
port with just `add`/`get`. Each service subclasses the UoW purely to attach its own concrete
repository in `__aenter__` — no generic SQLAlchemy repository is shared, since each service's row
shape differs.

Scope for this ticket: add `AbstractRepository`/`AbstractUnitOfWork` (plus a
`SqlAlchemyUnitOfWork` base) to `platform/base/`, then migrate `services/account/` and
`services/order_management/` — confirmed with the user during refinement, replacing the
original draft's `services/matching_engine/` (rules §5-style correction, not a finding against
this ticket): `matching_engine` turned out to have no domain repository at all — its only DB
write is a single outbox-table insert, since order books are pure in-memory and restored via
HTTP from `order_management` on boot, not from its own storage. `order_management/repository.py`
is the actual second-best fit: a real multi-method `OrderRepository` (`save`/`update`/
`load_all`/`load_open`), each opening its own ad-hoc `engine.begin()` transaction — the same
hand-rolled pattern `account` has. `account` additionally shows the sharper motivating case for
a UoW: `AccountService.register_account`/`reserve_cash`/`reserve_shares`/`apply_settlement`
each open one `engine.begin()` block that writes through *two* collaborators (the account
repository **and** the outbox insert) — exactly the "coordinate several repositories in one
transaction" case a UoW exists for. Other services (`matching_engine`, `risk_engine`,
`clearing`, `notifications`) are explicitly out of scope here; migrate them in a follow-up once
this pattern has proven itself on two real services.

## Implementation Plan

### 0. Feature branch (mandatory)

```
git checkout main
git checkout -b feat/EXC-001-add-repository-unit-of-work-base-classes
```

Work and commit locally per the project's commit policy (`exchange` is a root-path child —
tidy WIP commits into atomic ones before presenting; no push/MR without explicit user
approval).

### Prerequisite gate (hard)

None. `depends-on: []`. Both target services (`services/account/`, `services/order_management/`)
are still under `services/` as of this writing (their own `platform/` migrations, EXC-007 and a
not-yet-filed order_management ticket, haven't landed) — this plan is written against that
current layout. If either service's `platform/` migration lands first, the only adjustment
needed is updating this plan's paths from `services/<name>/` to
`platform/<name>/src/<name>/` before picking this ticket up (note-and-close, not a blocker).

### Confirmed design decisions (do not deviate without asking)

1. **Swap `matching_engine` → `order_management`** (see Description) — settled with the user
   during refinement.
2. **`platform/base/src/base/unit_of_work.py`**: `AbstractUnitOfWork` (async-context-manager ABC;
   `__aexit__` always calls `rollback()`) and `SqlAlchemyUnitOfWork` (owns one `AsyncConnection` +
   transaction for the `async with` block's lifetime; tracks whether `commit()` ran so
   `__aexit__`'s unconditional `rollback()` is a no-op after a real commit), ported near-verbatim
   from the reference project's `stelo-base/src/stelo/base/unit_of_work.py` (package name `base`,
   not `stelo.base`, per EXC-004 decision 1 — otherwise unchanged).
3. **`platform/base/src/base/repository.py`**: `AbstractRepository[T]` — exactly `add(item: T) ->
   None` and `get(id: str) -> T | None`, ported verbatim from the reference's
   `stelo-base/src/stelo/base/repository.py`. Concrete repositories may add further
   domain-specific methods beyond this minimal port (decision 5) — the ABC is the shared
   contract, not a ceiling.
4. **Each service gets its own `<Service>UnitOfWork(SqlAlchemyUnitOfWork)`** in its own
   `unit_of_work.py`, overriding `__aenter__` to construct its repository bound to
   `self.connection` after calling `super().__aenter__()` — same shape as the reference's
   `platform/inbox/src/stelo/inbox/service_layer/unit_of_work.py`.
5. **Concrete repositories become connection-scoped, not engine-scoped, and implement the ABC
   literally (`add`/`get`) while keeping their existing richer methods as extras**, rather than
   renaming every existing call site to `add`/`get`-only:
   - `AccountRepository(connection: AsyncConnection)`: `add()` is the existing upsert logic
     (`save`/`save_with_conn`/`_save`'s body, now always given a connection at construction
     time instead of choosing between an owned or borrowed one); new `get(account_id) ->
     Account | None` (single-account fetch, reusing `load_all`'s three-query shape filtered by
     id). `save`/`save_with_conn`/`_save` are removed — every caller goes through
     `AccountUnitOfWork.accounts.add(...)` instead (Task 2).
   - `OrderRepository(connection: AsyncConnection)`: `add()` is the existing `save()` body; new
     `get(order_id) -> Order | None`. `update()` stays as an extra method (not part of the ABC —
     it has no `add`/`get` equivalent to collapse into) using `self._connection`. `save()` is
     removed (replaced by `add()`).
   - **Bulk, read-only startup hydration moves out of the repository classes entirely**, since
     it's a one-shot scan outside any write transaction: `load_all()` on each repository becomes
     a module-level function taking an `engine` directly —
     `async def load_all_accounts(engine: AsyncEngine) -> list[Account]` in
     `services/account/repository.py`, and `load_all_orders`/`load_open_orders(engine:
     AsyncEngine)` in `services/order_management/repository.py` — same query bodies, just
     detached from the now connection-scoped class.
6. **Services take a UoW factory, not a repo + engine.** `AccountService.__init__` changes from
   `(account_repo, engine)` to `(uow_factory: tp.Callable[[], AccountUnitOfWork])`;
   `OrderManagementService.__init__` drops its `order_repo` parameter for the same
   `uow_factory` one (other constructor args unchanged). Every method that used to do
   `async with self._engine.begin() as conn: await self._repo.save_with_conn(conn, x); ...` now
   does `async with self._uow_factory() as uow: await uow.accounts.add(x); ...; await
   uow.commit()` — this is what makes rollback-on-forgotten-commit real: forgetting the
   `uow.commit()` line now safely rolls back instead of silently no-op-ing (today's ad hoc
   `engine.begin()` block commits unconditionally on clean exit, so there's nothing to forget).
   This mirrors the reference's own service-layer idiom (`stelo.inbox.service_layer.services`
   functions take a `uow: AbstractUnitOfWork` parameter) adapted to this codebase's
   class-based services (a factory callable, not a bare instance, since each service method
   needs its own fresh UoW/transaction, not one shared for the service's whole lifetime).
7. **`apply_settlement`'s ad hoc queries stay ad hoc**, now against `uow.connection` instead of
   the old `conn` — `SqlAlchemyUnitOfWork.connection` is a public attribute (per the reference),
   usable directly for the `processed_events` idempotency check/insert that doesn't go through
   any repository.
8. **Test doubles bypass `SqlAlchemyUnitOfWork` entirely**, exactly like the reference's own
   `FakeUnitOfWork(AbstractUnitOfWork)` — no `AsyncEngine`/`AsyncConnection` faking needed. Each
   service's test module gets a `Fake<Service>UnitOfWork(AbstractUnitOfWork)` whose `__init__`
   sets `.accounts`/`.orders` to a fake repo and `.connection` to the existing `_FakeConn` stub
   (`services/account/tests/test_service.py` already has one — reuse it), and whose
   `commit`/`rollback` just flip a flag. The test helper's `uow_factory` returns the *same*
   fake instance on every call (`lambda: uow`), not a fresh one, so assertions after a service
   method call (or across several calls in one test) still see accumulated state.

### Tasks

#### Task 1 — Add the base classes to `platform/base/`
Create `platform/base/src/base/unit_of_work.py` (decision 2) and
`platform/base/src/base/repository.py` (decision 3), adapted from the reference paths named
above. Both are pure ABCs/generic infrastructure — no service-specific code.

#### Task 2 — Migrate `services/account/`
- `services/account/repository.py`: retype `AccountRepository.__init__` to take a `connection:
  AsyncConnection`; rename the upsert body to `add()` (subclass `AbstractRepository[Account]`);
  add `get(account_id) -> Account | None`; remove `save`/`save_with_conn`/`_save`; add the
  module-level `load_all_accounts(engine: AsyncEngine) -> list[Account]` function (decision 5).
- `services/account/unit_of_work.py` (new): `AccountUnitOfWork(SqlAlchemyUnitOfWork)` attaching
  `self.accounts = AccountRepository(self.connection)` in `__aenter__` (decision 4).
- `services/account/service.py`: `AccountService.__init__(self, uow_factory)`; rewrite
  `register_account`, `reserve_cash`, `reserve_shares`, `apply_settlement` per decision 6/7 —
  each existing `async with self._engine.begin() as conn:` block becomes `async with
  self._uow_factory() as uow:`, `self._repo.save_with_conn(conn, x)` → `await
  uow.accounts.add(x)`, `_enqueue_account_updated(conn, x)` → `_enqueue_account_updated(
  uow.connection, x)`, ad hoc `processed_events` queries in `apply_settlement` → `uow.connection`,
  and an explicit `await uow.commit()` at the end of each `async with` block (before it exits
  normally).
- `services/account/app.py`: lifespan wiring changes from `repo = AccountRepository(db); _state.svc
  = AccountService(repo, db)` to `_state.svc = AccountService(lambda: AccountUnitOfWork(db))`;
  startup hydration changes from `for account in await repo.load_all():` to `for account in
  await load_all_accounts(db):` (new import).
- `services/account/tests/test_service.py`: per decision 8 — `FakeAccountRepo` implements
  `add`/`get` instead of `save`/`save_with_conn`/`load_all`; add
  `FakeAccountUnitOfWork(AbstractUnitOfWork)` wrapping it plus the existing `_FakeConn`; update
  `make_svc()` to build `AccountService(lambda: uow)` over one shared `FakeAccountUnitOfWork`
  instance; keep every existing test assertion's intent (what gets saved/enqueued/committed),
  adjusted to the new collaborator shape.

#### Task 3 — Migrate `services/order_management/`
Same shape as Task 2, decisions 5/6/8 applied to `order_management`:
- `services/order_management/repository.py`: `OrderRepository(connection)`; `add()` replaces
  `save()`; new `get(order_id) -> Order | None`; `update()` stays, retargeted at
  `self._connection`; add module-level `load_all_orders`/`load_open_orders(engine)`.
- `services/order_management/unit_of_work.py` (new): `OrderManagementUnitOfWork` attaching
  `self.orders = OrderRepository(self.connection)`.
- `services/order_management/service.py`: `OrderManagementService.__init__` drops `order_repo`
  for `uow_factory` (keeps `risk_engine`, `matching_engine`, `account_client`); rewrite the 5
  call sites (`submit_order`'s `save`/2×`update`, `cancel_order`'s `update`, `on_order_filled`'s
  `update`) to open `async with self._uow_factory() as uow: await uow.orders.add(...)` /
  `await uow.orders.update(...)`, each followed by `await uow.commit()`. These stay as
  independent per-call transactions (not merged into one) — `submit_order`'s three writes are
  separated by HTTP calls to Risk Engine/Clearing/Matching Engine, and holding one DB
  transaction open across outbound network calls would be a regression, not an improvement.
- `services/order_management/app.py`: lifespan wiring drops `order_repo = OrderRepository(...)`
  for `_state.svc = OrderManagementService(risk_client, matching_client, lambda:
  OrderManagementUnitOfWork(_state.db), account_client)`; startup hydration uses
  `await load_all_orders(_state.db)`.
- `services/order_management/tests/test_service.py`: `FakeOrderRepo` → `add`/`get`/`update`;
  add `FakeOrderManagementUnitOfWork(AbstractUnitOfWork)`; update the service construction
  helper to inject `lambda: uow` in place of the old repo argument.

### Acceptance test

From the repo root, on `feat/EXC-001-add-repository-unit-of-work-base-classes`:
```
uv sync --extra dev
uv run python -c "import base.unit_of_work, base.repository"
just lint
just test
```
Expect: the new base modules import cleanly; `just lint` clean; `just test` green, including
`services/account/tests/test_service.py` and `services/order_management/tests/test_service.py`
with their fakes updated per decision 8 — a passing test suite that still exercises the same
behavioural assertions (what gets persisted, what gets enqueued to the outbox, that a
forgotten/failed commit doesn't persist) is the real proof this refactor preserved behaviour,
not just that the fakes were mechanically patched to match new signatures.

### Docs update (mandatory when user-facing)

- `README.md` / `development/design.md`: if either documents `AccountRepository`'s or
  `OrderRepository`'s constructor shape or the account/order-management persistence flow, update
  it to the connection-scoped, UoW-mediated version. `grep -rn "AccountRepository(db\|AccountRepository(engine\|OrderRepository(db\|OrderRepository(engine" README.md development/design.md`
  first to check whether this documentation exists at all — if it prints nothing, "no
  user-facing surface" applies and no doc edit is needed.

### Finish (mandatory)

1. Acceptance test green: base modules import, `just lint`/`just test` clean.
2. Docs updated per above (or confirmed not applicable).
3. Write a summary: the two new `platform/base/` modules, the account and order_management
   migrations (repository/UoW/service/app/tests per file), and the matching_engine → 
   order_management scope swap with its rationale.
4. Suggested commit message:
   ```
   feat: add Repository/Unit-of-Work base classes; migrate account and order_management (EXC-001)

   Add AbstractUnitOfWork/SqlAlchemyUnitOfWork and AbstractRepository to
   platform/base, then migrate account and order_management off ad hoc
   per-call engine.begin() transactions onto service-specific UnitOfWork
   subclasses, so a forgotten commit() rolls back instead of silently
   doing nothing.
   ```
5. Tidy WIP commits into a small number of atomic commits before presenting (root-path child).
6. Commit locally; present the commit message for approval before any push/MR
   (`layout = "in-tree"`: verify `origin/main...HEAD` carries no `tickets/` path before
   pushing). `pickle ticket move EXC-001 in-review --reason "acceptance green"` and hand back.

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-16 — created (TO DO). source: pickle ticket new
- 2026-09-16 — Description corrected: target path `shared/platform/` → `platform/base/`
  (EXC-004 impact sweep — `shared/` no longer exists post-EXC-004).
- 2026-09-17 — TO DO → READY: plan complete
