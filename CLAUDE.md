# Stock Exchange — Project Context

## What this is

An educational Python monorepo implementing a simplified stock exchange.
The goal is to understand how trading works (order lifecycle, matching,
risk checks, clearing) — not to build a production-grade, high-performance system.

## Architecture overview

```text
clients/simulator      → generates synthetic order traffic for testing
services/gateway       → entry point: auth, rate limiting, order routing
services/risk_engine   → pre-trade checks before orders reach the book
services/order_management → order lifecycle and persistence
services/matching_engine  → order book + price-time priority matching
services/clearing      → post-trade settlement and position updates
services/market_data   → publishes prices, depth, and trade feed
services/account       → balances, positions, portfolio
services/notifications → fill confirmations and alerts
shared/                → domain models, event bus, db layer (tables + repositories)
infra/                 → docker-compose, helper scripts
```

## Key domain concepts

- **Order**: instruction to buy/sell a quantity of a ticker at a price (or at market)
- **Order book**: per-ticker collection of resting limit orders, sorted by price then time
- **Match**: when a buy and sell order agree on price — produces a Trade
- **Fill**: notification to the client that their order (fully or partially) executed
- **Clearing**: post-match step that updates cash and position balances

## Running the project

```bash
# Install all dependencies (fastapi, uvicorn, sqlalchemy, psycopg2-binary)
pip install -e ".[dev]"

# Start Postgres (required for persistence)
docker-compose -f infra/docker/docker-compose.yml up -d

# Run all tests (persistence tests skip automatically without Postgres)
pytest

# Start the HTTP gateway with persistence enabled
DATABASE_URL=postgresql://exchange:exchange@localhost:5432/exchange python -m services.gateway

# Start the HTTP gateway in-memory only (no Postgres needed)
python -m services.gateway

# Start the exchange without HTTP (demo mode, always in-memory)
python -m exchange.main

# Run the simulator to generate traffic
python -m clients.simulator.main
```

## Development conventions

- Services communicate via an in-process event bus (see shared/events/)
- The HTTP gateway (`services/gateway/`) is a thin FastAPI layer over the Exchange facade
- Each service exposes a simple Python class interface — no HTTP in the core loop
- Persistence uses SQLAlchemy Core only (no ORM) — see shared/db/
- DB is opt-in: services accept optional `*_repo` kwargs; tests run in-memory without a DB
- Tests live alongside each service in its tests/ directory
- Use dataclasses for domain models (shared/models/)
- Keep each service file under ~200 lines; split into submodules when it grows
- No async/await — synchronous for clarity and ease of debugging

## When modifying a service

1. Check shared/models/ first — domain models are shared
2. Update the service logic
3. Publish events via shared/events/bus.py if state changed
4. If the change affects persistent state, update the relevant repository in shared/db/repositories.py (and the table in shared/db/tables.py if the schema changes)
5. Add or update tests in the service's tests/ directory
6. Update docs/architecture.md if the data flow changed
