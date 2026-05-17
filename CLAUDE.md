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

- The HTTP gateway (`services/gateway/`) is a thin FastAPI layer that routes requests to downstream microservices
- Each service exposes a plain Python class interface — no HTTP in the core service loop; HTTP lives in `app.py`
- Services communicate via HTTP (httpx); after a match the matching engine writes events to a Postgres outbox table and a background relay delivers them to downstream services
- Persistence uses SQLAlchemy Core (async) only — no ORM; see `shared/db/`
- `DATABASE_URL` is required for stateful services (risk_engine, order_management, matching_engine, clearing); stateless services (gateway, market_data) do not need it
- Tests live alongside each service in its `tests/` directory
- Use dataclasses for domain models (`shared/models/`)
- Keep each service file under ~200 lines; split into submodules when it grows
- Services use `async def` throughout — FastAPI and asyncpg both require it
- Client code (`clients/tui/`) is synchronous; use `@work(thread=True)` for blocking I/O instead of coroutines
- Always use `import typing as tp` — never `from typing import XXX`; reference types as `tp.Optional`, `tp.List`, etc.

## When modifying a service

1. Check `shared/models/` first — domain models are shared across all services
2. Update the service logic
3. If the change produces new events, add rows to the outbox in the matching engine's `_enqueue_events()` and register the destination in `_EVENT_DESTINATIONS`
4. If the change affects persistent state, update the relevant repository in `shared/db/repositories.py` (and the table in `shared/db/tables.py` if the schema changes)
5. Add or update tests in the service's `tests/` directory
6. Update `docs/architecture.md` if the data flow changed
