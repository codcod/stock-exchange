"""
This module provides a backward-compatible re-export of all repository
classes from the `shared.db.repos` submodule.

New code should import directly from the `repos` submodule.
"""

from shared.db.repos import (  # noqa: F401
    AccountRepository,
    InstrumentRepository,
    OrderRepository,
    OutboxRepository,
    TradeRepository,
    write_outbox_rows,
)
