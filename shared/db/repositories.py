"""Backward-compatibility shim — import from shared.db.repos instead."""

from shared.db.repos import (  # noqa: F401
    AccountRepository,
    InstrumentRepository,
    OrderRepository,
    OutboxRepository,
    TradeRepository,
    write_outbox_rows,
)
