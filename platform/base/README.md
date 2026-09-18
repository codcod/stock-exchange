# platform/base/

The `base` package has two layers:

## `base.domain` — the exchange's universal vocabulary

Types that every service speaks. Import freely from any service.

| Module | Contents |
|---|---|
| `models.py` | Core entities: `Order`, `Trade`, `Account`, `Instrument`, `Side`, `OrderType`, `OrderStatus` |
| `events.py` | Domain events: `TradeExecuted`, `OrderFilled`, `MarketDataUpdate`, `OrderSubmitted`, … |
| `api_schemas.py` | Pydantic inter-service contracts: `OrderRequest`, `TradeExecutedEvent`, `RegisterAccountRequest`, … |

## `base` (top-level) — framework infrastructure

Thin helpers with no domain knowledge. Services depend on these, not on each other.

| Module | Contents |
|---|---|
| `http_client.py` | `http_get`, `http_post`, `http_delete` — correlation-header-aware async helpers |
| `request_context.py` | `request_id` context var set by the gateway and propagated downstream |
| `db/connection.py` | `get_engine()` — cached async SQLAlchemy engine from `DATABASE_URL` |
| `db/tables.py` | `ensure_tables(engine, metadata, schemas)` — DDL helper with advisory lock; unused now that every stateful service creates its schema via its own Alembic `*-migrate` one-shot container instead |
| `clients/` | One typed HTTP client per service (`RiskEngineClient`, `ClearingClient`, …) |
| `clients/converters.py` | Dict ↔ domain-object helpers shared by all clients |
