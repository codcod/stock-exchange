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
services/clearing      → post-trade settlement and position updates
services/market_data   → publishes prices, depth, and trade feed
shared/                → domain models, HTTP service clients, outbox event routing, db layer
infra/                 → docker-compose files and helper scripts
```

## Key domain concepts

- **Order**: instruction to buy/sell a quantity of a ticker at a price (or at market)
- **Order book**: per-ticker collection of resting limit orders, sorted by price then time
- **Match**: when a buy and sell order agree on price — produces a Trade
- **Fill**: notification to the client that their order (fully or partially) executed
- **Clearing**: post-match step that updates cash and position balances

## Running the project

```bash
# Install all dependencies
uv sync --extra dev

# Start Postgres + all six microservices
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
- Persistence is handled using SQLAlchemy Core (async) without an ORM. See the `shared/db/` directory for more details.
- A `DATABASE_URL` is required for stateful services (i.e., `risk_engine`, `order_management`, `matching_engine`, and `clearing`). Stateless services like `gateway` and `market_data` do not require it.
- Tests are located alongside each service in its corresponding `tests/` directory.
- Domain models are defined as dataclasses in `shared/models/`.
- To maintain readability, each service file should ideally be kept under 200 lines. If a file grows beyond this, consider splitting it into submodules.
- All services are built with `async def`, as both FastAPI and `asyncpg` require it.
- The client-side code in `clients/tui/` is synchronous. For blocking I/O operations, use `@work(thread=True)` instead of coroutines.
- Always use `import typing as tp` instead of `from typing import XXX`. This convention ensures that types are referenced consistently (e.g., `tp.Optional`, `tp.List`).

## When modifying a service

1. Check `shared/models/` first — domain models are shared across all services
2. Update the service logic
3. If the change produces new events, add rows to the outbox in the matching engine's `_enqueue_events()` and register the destination in `_EVENT_DESTINATIONS`
4. If the change affects persistent state, update the relevant repository in `shared/db/repositories.py` (and the table in `shared/db/tables.py` if the schema changes)
5. Add or update tests in the service's `tests/` directory
6. Update `docs/architecture.md` if the data flow changed
