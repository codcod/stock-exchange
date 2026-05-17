# Architecture

## Data flow for a single order

```mermaid
flowchart TD
    HttpClient["HTTP Client"]
    Simulator["clients/simulator\n(load generator)"]
    Gateway["services/gateway :8000\nFastAPI — validates · routes"]
    OMS["services/order_management :8001\nOrder lifecycle · persists orders"]
    Risk["services/risk_engine :8002\nPre-trade checks · account state cache"]
    Matching["services/matching_engine :8003\nOrder book · price-time priority matching"]
    Clearing["services/clearing :8004\nPost-trade settlement\nUpdates cash + positions"]
    MarketData["services/market_data :8005\nQuote snapshots · trade history"]

    HttpClient -->|HTTP| Gateway
    Simulator -->|HTTP| Gateway
    Gateway -->|POST /orders| OMS
    OMS -->|POST /orders/check| Risk
    Risk -->|response| OMS
    OMS -->|FAIL: status=REJECTED| Gateway
    OMS -->|"PASS: POST /accounts/:id/reserve/cash\nPOST /accounts/:id/reserve/shares"| Risk
    OMS -->|PASS: POST /orders| Matching
    Matching -->|no match: order rests in book| Matching
    Matching -->|"POST /events/trade-executed"| Clearing
    Matching -->|"POST /events/order-filled"| OMS
    Matching -->|"POST /events/market-data-update"| MarketData
```

All inter-service calls are HTTP (httpx). The matching engine fans out trade events by calling downstream services directly after a match.

## Service responsibilities

| Service | Port | Owns | Calls | Writes to DB |
|---|---|---|---|---|
| Gateway | 8000 | HTTP interface, request/response translation | OMS, MarketData | no |
| OrderManagement | 8001 | Order lifecycle, routing | RiskEngine, MatchingEngine | orders |
| RiskEngine | 8002 | Account state cache, pre-trade rules | — | instruments |
| MatchingEngine | 8003 | Order books, trade execution, event fan-out | Clearing, OMS, MarketData | no |
| Clearing | 8004 | Account balances, positions | — | accounts, positions, trades |
| MarketData | 8005 | Quote snapshots, trade history (memory only) | — | no |

`services/account/` and `services/notifications/` are scaffolded but not yet implemented.

## HTTP gateway (`services/gateway/`)

The gateway is a thin FastAPI layer that routes requests to downstream services via `ServiceClients`.
It contains no business logic — it translates HTTP requests into service calls and maps results back to JSON.

```text
services/gateway/
├── app.py           # FastAPI app, lifespan, router wiring
├── auth.py          # Optional X-API-Key header check
├── dependencies.py  # ServiceClients singleton (injected via Depends)
├── schemas.py       # Pydantic request/response models + converters
└── routes/
    ├── orders.py        # POST /orders, GET /orders/{id}, DELETE /orders/{id}
    ├── accounts.py      # POST /accounts, GET /accounts/{id}, GET /accounts/{id}/orders
    ├── instruments.py   # POST /instruments
    └── market_data.py   # GET /market-data/{ticker}/quote|depth|trades, /tickers
```

Authentication is opt-in: set the `EXCHANGE_API_KEY` environment variable.
When set, every request must include `X-API-Key: <value>`.
When unset, the API is open (suitable for local development).

## Inter-service communication (`shared/service_clients.py`)

Each service exposes HTTP clients that mirror the Python interface of the target service.
All clients share a pooled `httpx.AsyncClient` (timeout 10s).

| Client | Calls |
|---|---|
| `OrderManagementClient` | `submit_order()`, `cancel_order()`, `get_order()`, `get_orders_for_account()` |
| `RiskEngineClient` | `check()`, `register_account()`, `register_instrument()`, `update_reserved_cash()`, `update_reserved_shares()`, `halt_ticker()`, `resume_ticker()` |
| `MatchingEngineClient` | `submit()`, `cancel()`, `snapshot()`, `restore_order()` |
| `ClearingClient` | `register_account()`, `get_account()` |
| `MarketDataClient` | `all_tickers()`, `get_quote()`, `get_trade_history()` |

Service base URLs are configured via environment variables (e.g. `ORDER_MANAGEMENT_URL`).
Default values assume localhost with the standard port assignment above.

## Persistence layer (`shared/db/`)

All persistence uses SQLAlchemy Core (async) — no ORM. Tables are split across three Postgres schemas.

```text
shared/db/
├── connection.py    # get_engine() singleton; reads DATABASE_URL env var
├── tables.py        # MetaData + 6 Table definitions across 3 schemas
└── repositories.py  # OrderRepository, AccountRepository,
                     # InstrumentRepository, TradeRepository
```

**Tables:**

| Table | Schema | Populated by |
|---|---|---|
| `orders` | `order_management` | OrderManagementService (on submit, fill, cancel, reject) |
| `accounts` | `clearing` | ClearingService (on registration via POST /accounts; on each trade) |
| `positions` | `clearing` | ClearingService (on each trade, full replace per account) |
| `reserved_shares` | `clearing` | ClearingService (on each trade, full replace per account) |
| `instruments` | `risk_engine` | RiskEngine (on registration via POST /instruments) |
| `trades` | `clearing` | ClearingService (on each trade) |

**Startup DDL** uses a Postgres advisory lock (key `20260516`) to serialise `CREATE TABLE IF NOT EXISTS`
across concurrent service instances so only one runs DDL at startup.

**`DATABASE_URL` is required** for all stateful services (risk_engine, order_management, matching_engine, clearing). Stateless services (gateway, market_data) do not need it. The connection layer (`shared/db/connection.py`) returns an `AsyncEngine` using the `postgresql+asyncpg://` URL scheme and raises immediately if the variable is absent.

**Write-through pattern.** In-memory state is authoritative at runtime; every mutation immediately writes through to Postgres so the DB is always consistent with memory.

## Event bus (`shared/events/bus.py`)

The event bus is an in-process publish/subscribe mechanism.
Each service has its own local `EventBus` instance. Within the matching engine it decouples
trade execution from HTTP fan-out: the engine publishes events to its local bus, and subscribed
handlers translate those events into HTTP calls to downstream services.

`publish()` is an async coroutine; all handlers registered via `subscribe()` must be `async def` coroutines.
Events are delivered sequentially — each handler is awaited before the next runs, preserving causal ordering.
Handler exceptions are logged but do not block other handlers.

**Events:**

| Event | Published by | Handled by |
|---|---|---|
| `OrderSubmitted` | OMS | — |
| `OrderAccepted` | OMS | — |
| `OrderRejected` | OMS | — |
| `OrderCancelled` | OMS | — |
| `TradeExecuted` | MatchingEngine | Clearing, MarketData |
| `OrderFilled` | MatchingEngine | OMS |
| `MarketDataUpdate` | MatchingEngine | MarketData |

In a production system the bus would be replaced with Kafka or Redis Streams.

## Infrastructure (`infra/docker/`)

```text
infra/docker/
├── compose.infra.yml     # Postgres 18 (postgres-data volume, named 'exchange' network)
└── compose.services.yml  # Six service containers; startup order enforced via depends_on
```

Service startup order (enforced by healthchecks): `risk-engine` → `clearing` → `market-data` → `matching-engine` → `order-management` → `gateway`.

Each service container runs `python -m services.<name>` and is reachable on `localhost:800X`.

## What's intentionally simplified

- **MarketData not persisted** — quote snapshots, trade history, and the last traded price are in-memory only and reset on restart. `instruments.last_price` reflects the price at instrument registration, not the last trade. Intraday volume is also lost.
- **No WebSocket** — market data requires polling. Add a push feed later.
- **No real authentication** — API key auth is a single shared secret. Add JWT / OAuth later.
- **Async in-process** — the event bus delivers events sequentially (each handler is awaited before the next), preserving deterministic ordering. Replace the bus with Kafka or Redis Streams to go multi-process.
- **Instant settlement (T+0)** — real exchanges settle T+1 or T+2.
- **HTTP fan-out, not a message broker** — the matching engine calls downstream services directly over HTTP rather than publishing to a topic. Add a broker (Kafka, Redis Streams) to decouple producers from consumers.
- **No service discovery** — service URLs are hardcoded env vars. Add Consul or Kubernetes service DNS for dynamic discovery.
