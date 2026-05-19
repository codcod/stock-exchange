# shared/

The `shared/` package has two layers:

## `shared/domain/` — the exchange's universal vocabulary

Types that every service speaks. Import freely from any service.

| Module | Contents |
|---|---|
| `models.py` | Core entities: `Order`, `Trade`, `Account`, `Instrument`, `Side`, `OrderType`, `OrderStatus` |
| `events.py` | Domain events: `TradeExecuted`, `OrderFilled`, `MarketDataUpdate`, `OrderSubmitted`, … |
| `api_schemas.py` | Pydantic inter-service contracts: `OrderRequest`, `TradeExecutedEvent`, `RegisterAccountRequest`, … |

## `shared/platform/` — framework infrastructure

Thin helpers with no domain knowledge. Services depend on these, not on each other.

| Module | Contents |
|---|---|
| `http_client.py` | `http_get`, `http_post`, `http_delete` — correlation-header-aware async helpers |
| `request_context.py` | `request_id` context var set by the gateway and propagated downstream |
| `db/connection.py` | `get_engine()` — cached async SQLAlchemy engine from `DATABASE_URL` |
| `db/tables.py` | `ensure_tables(engine, metadata, schemas)` — DDL helper with advisory lock |
| `clients/` | One typed HTTP client per service (`RiskEngineClient`, `ClearingClient`, …) |
| `clients/converters.py` | Dict ↔ domain-object helpers shared by all clients |

## What lives next to each service (not here)

Repositories and table definitions are co-located with the service that owns them:

| Service | Repository | Tables |
|---|---|---|
| `order_management` | `repository.py` → `OrderRepository` | `tables.py` → `orders` |
| `clearing` | `repository.py` → `AccountRepository`, `TradeRepository` | `tables.py` → `accounts`, `positions`, … |
| `risk_engine` | `repository.py` → `InstrumentRepository` | `tables.py` → `instruments` |
| `matching_engine` | `outbox_repo.py` → `OutboxRepository` | `tables.py` → `outbox` |
