# Stock Exchange — Project Context

## What this is

An educational Python monorepo implementing a simplified stock exchange.
The goal is to understand how trading works (order lifecycle, matching,
risk checks, clearing) — not to build a production-grade, high-performance system.

## Architecture overview

```text
clients/simulator      → generates synthetic order traffic for testing
clients/tui/           → interactive terminal trading app (Textual)
services/gateway       → entry point: auth, rate limiting, order routing
services/risk_engine   → pre-trade checks before orders reach the book
services/order_management → order lifecycle and persistence
services/matching_engine  → order book + price-time priority matching
services/clearing      → post-trade trade-record keeper (audit ledger only)
services/account       → source of truth for cash, positions, and reservations
services/notifications → per-account event feed; WebSocket push + HTTP backfill
services/market_data   → publishes prices, depth, and trade feed
shared/                → domain models, HTTP service clients, outbox event routing, db layer
infra/                 → docker-compose files and helper scripts
```

## Key domain concepts

- **Order**: instruction to buy/sell a quantity of a ticker at a price (or at market)
- **Order book**: per-ticker collection of resting limit orders, sorted by price then time
- **Match**: when a buy and sell order agree on price — produces a Trade
- **Fill**: notification to the client that their order (fully or partially) executed
- **Settlement**: post-match step (owned by Account service) that updates cash and positions
- **Reservation**: temporary hold on cash (BUY) or shares (SELL) while an order is open

## Running the project

```bash
# Install all dependencies
uv sync --extra dev

# Start Postgres + all eight microservices
just up

# Run all tests
just test

# Run the simulator to generate traffic
just sim

# Launch the interactive TUI (set account and base URL as needed)
EXCHANGE_ACCOUNT_ID=trader-0 uv run python -m clients.tui
```

## Development conventions

- The HTTP gateway (`services/gateway/`) is a lightweight FastAPI layer that routes incoming requests to the appropriate downstream microservices.
- Each service exposes a plain Python class interface. HTTP-specific logic is confined to the `app.py` file, keeping the core service logic clean and framework-agnostic.
- Services communicate with each other via synchronous HTTP calls using `httpx`. After a match, the matching engine writes events to a PostgreSQL outbox table. A background relay process then delivers these events to downstream services.
- Three services run outbox relays: `matching_engine` (TradeExecuted/OrderFilled/MarketDataUpdate), `account` (AccountUpdated → Risk Engine), and `order_management` (OrderAccepted/Rejected/Cancelled → Notifications).
- Persistence is handled using SQLAlchemy Core (async) without an ORM. See the `shared/db/` directory for more details.
- Stateful services (require `DATABASE_URL`): `risk_engine`, `order_management`, `matching_engine`, `clearing`, `account`, `notifications`. Stateless: `gateway`, `market_data`.
- Tests are located alongside each service in its corresponding `tests/` directory.
- Domain models are defined as dataclasses in `shared/domain/models.py`.
- To maintain readability, each service file should ideally be kept under 200 lines. If a file grows beyond this, consider splitting it into submodules.
- All services are built with `async def`, as both FastAPI and `asyncpg` require it.
- The client-side code in `clients/tui/` is synchronous. For blocking I/O operations, use `@work(thread=True)` instead of coroutines.
- Always use `import typing as tp` instead of `from typing import XXX`. This convention ensures that types are referenced consistently (e.g., `tp.Optional`, `tp.List`).

## Account and Risk Engine freshness

- **Account** is the authoritative source for all cash/position/reservation state.
- On every mutation, Account does a best-effort synchronous HTTP push to Risk Engine (fast path) and also enqueues an `AccountUpdated` event via its outbox (resilient path).
- On boot, Risk Engine fetches all accounts from Account service (`GET /accounts`) to warm its cache.

## When modifying a service

1. Check `shared/domain/` first — domain models and events are shared across all services
2. Update the service logic
3. If the change produces new events, update the relevant outbox relay's `EVENT_DESTINATIONS` and `ENDPOINT_FOR_EVENT_TYPE` maps
4. If the change affects persistent state, update the service's own `tables.py` and `repository.py`
5. Add or update tests in the service's `tests/` directory
6. Update `docs/architecture.md` if the data flow changed

<!-- pickle:begin -->
## Brine (start here)

**Start at [`tickets/BOARD.md`](tickets/BOARD.md)** — the generated index of every ticket by
status. No feature is built directly from a chat message or a raw idea — work enters only as a
ticket whose Implementation Plan has met the READY gate. A *review finding* is different: it
earns a **disposition** (rules §5), and most are resolved without a new ticket.

- The flow engine is the **brine skill** at `.agents/skills/brine/`. It holds
  the rules (`resources/tickets-README.md`), the ticket template
  (`resources/TEMPLATE.md`), and the review protocol
  (`resources/review-protocol.md`). Agents that read `.agents/skills/` find it there
  directly; `pickle install --agent claude` adds a `.claude/skills/brine` view for
  Claude Code. The directory is pickle-owned — `pickle install` and `pickle upgrade`
  both replace it wholesale, so keep hand-written notes outside it.
- Triggers: "make it a ticket", "refine ticket T-NNN", "implement ticket T-NNN", "rework ticket
  T-NNN", "validate ticket T-NNN" (or "review ticket T-NNN"), "audit the board".

### Project configuration

- **Build target.** Every ticket targets one registered child-project via `project:`
  frontmatter (`pickle project list`). Registered child-projects: `exchange`.
- **Commands** (each child's, from `pickle.toml`):
  - `exchange`: build `just services-build` · test `just test` · lint `just lint`
- **Branch & commit.** Conventional Commits with the **ticket id in brackets at the end of
  the subject** (e.g. `feat(cli): add board audit (T-2)`) for child-project code. Ticket/board
  bookkeeping uses its own `board: T-NNN <verb phrase>` form instead — grammar and scope in
  the rules §0. Branch per child:
  - `exchange`: `feat/EXC-NNN-<slug>`
- **WIP limits** (per child):
  - `exchange`: `3-in-development/` ≤ 1 · `4-in-review/` ≤ 1
- **Commit policy.** Child-projects are **publish-gated**: local WIP commits are encouraged;
  **no push / no merge request without explicit user approval**; after approval, finalize
  (squash or keep history) + push + open the MR — **merging is always the human's**.
  Overarching bookkeeping (tickets, board, docs) may be committed automatically,
  always with **explicit pathspecs** (`git add <paths>`, never `git add -A`/`.`).
- **Where commits land.** Code goes on the child's feature branch; **ticket and board
  bookkeeping is committed on the base branch**, never on a feature branch — a squash-merge
  folds or drops it and the board then disagrees with the tickets it indexes. This covers a
  review's own moves too, and it is why a reviewer on a feature branch reads the ticket from
  the base branch. This project uses the `in-tree` layout, where the board and the code share
  one repository, which is what makes the rule load-bearing here.
  `pickle hooks install` enforces it locally, once per clone: a `pre-commit`
  hook refuses the commit, and a `pre-push` hook refuses the push if it still slipped through
  (bypass either with `--no-verify`).

### Board rule

`tickets/BOARD.md` is **generated** — regenerated wholesale from the ticket files by
`pickle ticket new`, `pickle ticket move` and `pickle board sync`. **Never edit it by
hand**; hand-written planning notes go in `tickets/NOTES.md`. Every ticket move = move
the file + one dated `## History` line, and the board regenerates. Prefer
`pickle ticket move` — it does all of it atomically.
<!-- pickle:end -->
