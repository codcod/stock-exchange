# Stock Exchange

An educational Python monorepo that implements a simplified stock exchange.
The goal is to understand how trading works, not to build a production system.

## Quick start

```bash
# Install
uv sync --extra dev

# Start Postgres + all six microservices
just up

# Run the simulator (generates synthetic order traffic)
just sim

# Run tests
just test

# Launch the interactive terminal trading app
EXCHANGE_ACCOUNT_ID=trader-0 uv run python -m clients.tui
```

## HTTP API

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/instruments`              | Register a new tradeable instrument (e.g., a stock). |
| POST   | `/accounts`                 | Create a new trading account with an initial cash balance. |
| GET    | `/accounts/{id}`            | Retrieve account details, including balances and positions. |
| GET    | `/accounts/{id}/orders`     | List all historical and open orders for a specific account. |
| POST   | `/orders`                   | Submit a new buy or sell order (limit or market). |
| GET    | `/orders/{id}`              | Check the current status of a specific order. |
| DELETE | `/orders/{id}?account_id=`  | Cancel an open order. |
| GET    | `/market-data/tickers`      | Get a list of all tickers that have available quote data. |
| GET    | `/market-data/{ticker}/quote` | Fetch the latest bid, ask, and last traded price for a ticker. |
| GET    | `/market-data/{ticker}/depth` | Get a snapshot of the order book's depth (top 5 levels). |
| GET    | `/market-data/{ticker}/trades`| Retrieve the most recent trade history for a ticker. |
| GET    | `/health`                   | Perform a health check on the API. |

Authentication is opt-in: set `EXCHANGE_API_KEY=<secret>` and pass `X-API-Key: <secret>` on each request.

## Project Structure

This repository is organized as a monorepo containing multiple services and shared libraries.

```text
services/
  gateway/          # FastAPI HTTP layer (public entry point for clients)
  matching_engine/  # Core order book, price-time priority matching, and outbox event relay
  risk_engine/      # Pre-trade checks (e.g., balance, position, price sanity)
  order_management/ # Manages the lifecycle and routing of orders
  clearing/         # Handles post-trade settlement, updating cash and share balances
  market_data/      # Provides live quotes and trade history (in-memory)
shared/
  models/domain.py     # Contains dataclasses for Order, Trade, Account, and Instrument
  service_clients.py   # Implements HTTP client classes for inter-service communication
  db/                  # Manages the database schema, repositories, and connection factory using SQLAlchemy Core (async)
clients/
  simulator/        # A simple tool to generate synthetic order flow for testing purposes
  tui/              # An interactive terminal-based trading application built with Textual
infra/
  docker/           # Includes Docker Compose files for infrastructure (Postgres) and services
docs/
  architecture.md   # Provides detailed data flow diagrams and design notes
CLAUDE.md           # Contains project context for the Claude Code project
```

## Concepts this project illustrates

- **Order book**: how bids and asks are stored and matched
- **Price-time priority**: best price wins; ties go to earliest order
- **Pre-trade risk**: checks that run before an order enters the book
- **Fund reservation**: how cash/shares are locked while orders are open
- **Outbox pattern**: matching engine persists events to a DB table; a relay delivers them to downstream services, guaranteeing delivery without a message broker
- **Event-driven clearing**: how balances update after a trade
- **Partial fills**: what happens when only part of an order can be matched
- **Write-through persistence**: every mutation writes to Postgres; state is fully restored on restart

## Extending it

Suggested next steps, roughly in order:

1. Add WebSocket feed for live market data (remove polling requirement)
2. Implement stop orders and order expiry (GTC, IOC, FOK)
3. Add a circuit breaker: halt a ticker if it moves >X% in Y minutes
4. Replace the outbox HTTP relay with a message broker (Kafka, Redis Streams)
