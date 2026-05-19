# Re-exports kept for backward compatibility.
# New code should import repos directly from the owning service:
#   services/order_management/repository.py  → OrderRepository
#   services/risk_engine/repository.py       → InstrumentRepository
#   services/clearing/repository.py          → AccountRepository, TradeRepository
#   services/matching_engine/outbox_repo.py  → OutboxRepository, write_outbox_rows
from services.clearing.repository import (  # noqa: F401
    AccountRepository,
    TradeRepository,
)
from services.matching_engine.outbox_repo import (  # noqa: F401
    OutboxRepository,
    write_outbox_rows,
)
from services.order_management.repository import OrderRepository  # noqa: F401
from services.risk_engine.repository import InstrumentRepository  # noqa: F401

__all__ = [
    'AccountRepository',
    'InstrumentRepository',
    'OrderRepository',
    'OutboxRepository',
    'TradeRepository',
    'write_outbox_rows',
]
