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
