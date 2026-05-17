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
| POST | `/instruments` | Register a tradeable instrument |
| POST | `/accounts` | Register an account |
| GET | `/accounts/{id}` | Get account balances and positions |
| GET | `/accounts/{id}/orders` | List orders for an account |
| POST | `/orders` | Submit an order |
| GET | `/orders/{id}` | Get order status |
| DELETE | `/orders/{id}?account_id=` | Cancel an order |
| GET | `/market-data/tickers` | List tickers with quote data |
| GET | `/market-data/{ticker}/quote` | Latest bid/ask/last price |
| GET | `/market-data/{ticker}/depth` | Order book snapshot (5 levels) |
| GET | `/market-data/{ticker}/trades` | Recent trade history |
| GET | `/health` | Health check |

Authentication is opt-in: set `EXCHANGE_API_KEY=<secret>` and pass `X-API-Key: <secret>` on each request.

## Structure

```text
services/
  gateway/         # FastAPI HTTP layer (entry point for HTTP clients)
  matching_engine/ # Order book, price-time priority matching, outbox event relay
  risk_engine/     # Pre-trade checks (balance, position, price sanity)
  order_management/# Order lifecycle and routing
  clearing/        # Post-trade settlement (updates cash + shares)
  market_data/     # Live quotes and trade history (in-memory)
shared/
  models/domain.py    # Order, Trade, Account, Instrument dataclasses
  service_clients.py  # HTTP client classes for inter-service communication
  db/                 # SQLAlchemy Core (async): tables, repositories, connection factory
clients/
  simulator/       # Generates synthetic order flow for testing
  tui/             # Interactive terminal trading app (Textual)
infra/
  docker/          # compose.infra.yml (Postgres) + compose.services.yml (six services)
docs/
  architecture.md  # Data flow diagrams and design notes
CLAUDE.md          # Claude Code project context
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
