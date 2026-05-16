# Architecture

## Data flow for a single order

```text
HTTP Client                       Direct caller (tests / simulator)
  │                                 │
  ▼                                 │
services/gateway (FastAPI)          │
  │  validates request              │
  │  builds Order dataclass         │
  ▼                                 ▼
Exchange.submit_order(order)  ◄─────┘
  │
  ▼
OrderManagementService
  ├── Persist order (status=PENDING)
  ├── Publish OrderSubmitted event
  │
  ├── RiskEngine.check(order)
  │     ├── FAIL → order.status = REJECTED
  │     │          Publish OrderRejected event
  │     │          Return to client
  │     │
  │     └── PASS → reserve funds/shares
  │                Publish OrderAccepted event
  │
  └── MatchingEngine.submit(order)
        │
        ├── No match → order rests in book (status=OPEN)
        │             DB: UPDATE orders SET status=OPEN
        │
        └── Match found → Trade created
              │
              ├── Publish TradeExecuted event
              │     └── ClearingService (listener)
              │           ├── Update buyer/seller cash + positions (memory)
              │           └── DB: INSERT trade, UPDATE accounts + positions
              │
              ├── Publish OrderFilled events (buyer + seller)
              │     └── OrderManagementService (listener)
              │           ├── Update order status (FILLED / PARTIALLY_FILLED) (memory)
              │           └── DB: UPDATE orders SET status, filled_quantity
              │
              └── Publish MarketDataUpdate event
                    └── MarketDataService (listener)
                          └── Update quote snapshot (memory only)
```

## Service responsibilities

| Service | Owns | Listens to | Writes to DB |
|---|---|---|---|
| Gateway | HTTP interface, request/response translation | — | no |
| OrderManagement | Order lifecycle, routing | OrderFilled | orders |
| RiskEngine | Account state cache, pre-trade rules | (called directly) | no |
| MatchingEngine | Order books, trade execution | (called directly) | no |
| Clearing | Account balances, positions | TradeExecuted | accounts, positions, trades |
| MarketData | Quote snapshots, trade history | MarketDataUpdate, TradeExecuted | no |

## HTTP gateway (`services/gateway/`)

The gateway is a thin FastAPI layer that sits in front of the `Exchange` facade.
It does not contain business logic — it translates HTTP requests into domain calls and
maps domain objects back to JSON.

```text
services/gateway/
├── app.py           # FastAPI app, router wiring
├── auth.py          # Optional X-API-Key header check
├── dependencies.py  # Exchange singleton (injected via Depends)
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

## Persistence layer (`shared/db/`)

All persistence uses SQLAlchemy Core — no ORM.

```text
shared/db/
├── connection.py    # get_engine() singleton; reads DATABASE_URL env var
├── tables.py        # MetaData + 6 Table definitions
└── repositories.py  # OrderRepository, AccountRepository,
                     # InstrumentRepository, TradeRepository
```

**Tables:**

| Table | Populated by |
|---|---|
| `orders` | OrderManagementService (on submit, fill, cancel, reject) |
| `accounts` | Exchange.register_account; ClearingService (on each trade) |
| `positions` | ClearingService (on each trade, full replace per account) |
| `reserved_shares` | ClearingService (on each trade, full replace per account) |
| `instruments` | Exchange.register_instrument; Exchange (last_price on each trade) |
| `trades` | ClearingService (on each trade) |

**Persistence is opt-in.** Pass a SQLAlchemy `AsyncEngine` to `Exchange.create(db_engine=...)` to enable it.
Without an engine the exchange runs entirely in-memory — useful for tests and the demo script.
The connection layer (`shared/db/connection.py`) returns an `AsyncEngine` using the `postgresql+asyncpg://` URL scheme.
DDL operations use `await conn.run_sync(metadata.create_all)` since SQLAlchemy DDL is synchronous.

**Startup state restoration.** When an engine is provided, `Exchange._load_state()`:

1. Loads instruments → registers with RiskEngine, restores `last_price` to order book
2. Loads accounts → registers with RiskEngine and ClearingService
3. Loads all orders → restores to OrderManagement's in-memory dict
4. Loads OPEN / PARTIALLY_FILLED orders → re-inserts into the matching engine book (without triggering re-matching)

**Write-through pattern.** In-memory state is authoritative at runtime; every mutation immediately writes through to Postgres so the DB is always consistent with memory.

## Event bus

All services share a single `EventBus` instance (`shared/events/bus.py`).
`publish()` is an async coroutine; all handlers registered via `subscribe()` must
be `async def` coroutines. Events are delivered sequentially — each handler is
awaited before the next runs, preserving causal ordering (e.g. ClearingService
settles before OrderManagementService reads updated balances).
In a production system this would be replaced with Kafka or Redis Streams.

## What's intentionally simplified

- **MarketData not persisted** — quote snapshots and trade history are in-memory only; they reset on restart. The last price is recoverable via `instruments.last_price`, but intraday volume is lost.
- **No WebSocket** — market data requires polling. Add a push feed later.
- **No real authentication** — API key auth is a single shared secret. Add JWT / OAuth later.
- **Async in-process** — the entire stack uses asyncio/await. The event bus delivers events sequentially (each handler is awaited before the next), preserving deterministic ordering. Replace the bus with Kafka or Redis Streams to go multi-process.
- **Instant settlement (T+0)** — real exchanges settle T+1 or T+2.
- **Single process** — all services run together. Split into microservices later.
