"""
shared/events/bus.py

A minimal synchronous in-process event bus.
Services publish events; other services subscribe to event types.

This replaces a real message broker (Kafka, Redis Streams) for simplicity.
The interface is intentionally similar to what you'd use with a real broker
so it's easy to swap out later.
"""

from __future__ import annotations

import logging
import typing as tp
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event base + concrete events
# ---------------------------------------------------------------------------


@dataclass
class Event:
    event_id: str = field(default_factory=lambda: __import__('uuid').uuid4().hex)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OrderSubmitted(Event):
    order_id: str = ''
    account_id: str = ''
    ticker: str = ''


@dataclass
class OrderAccepted(Event):
    """Risk check passed; order entered the book."""

    order_id: str = ''


@dataclass
class OrderRejected(Event):
    order_id: str = ''
    reason: str = ''


@dataclass
class OrderCancelled(Event):
    order_id: str = ''


@dataclass
class TradeExecuted(Event):
    trade_id: str = ''
    buy_order_id: str = ''
    sell_order_id: str = ''
    buyer_account_id: str = ''
    seller_account_id: str = ''
    ticker: str = ''
    quantity: int = 0
    price: float = 0.0


@dataclass
class OrderFilled(Event):
    """Sent to each side of a trade."""

    order_id: str = ''
    account_id: str = ''
    fill_quantity: int = 0
    fill_price: float = 0.0
    is_fully_filled: bool = False


@dataclass
class MarketDataUpdate(Event):
    ticker: str = ''
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0
    volume: int = 0


# ---------------------------------------------------------------------------
# Bus implementation
# ---------------------------------------------------------------------------

Handler = tp.Callable[[Event], tp.Coroutine[tp.Any, tp.Any, None]]


class EventBus:
    """
    Async pub/sub bus. Handlers are awaited sequentially in registration order.
    Sequential delivery preserves causal ordering (clearing settles before OMS
    reads updated balances). Exceptions in one handler do not prevent others.
    """

    def __init__(self) -> None:
        self._subscribers: tp.Dict[tp.Type[Event], tp.List[Handler]] = defaultdict(list)

    def subscribe(self, event_type: tp.Type[Event], handler: Handler) -> None:
        self._subscribers[event_type].append(handler)
        logger.debug('Subscribed %s to %s', handler.__qualname__, event_type.__name__)

    async def publish(self, event: Event) -> None:
        handlers = self._subscribers.get(type(event), [])
        logger.debug(
            'Publishing %s to %d handler(s)', type(event).__name__, len(handlers)
        )
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    'Handler %s failed processing %s',
                    handler.__qualname__,
                    type(event).__name__,
                )


# Singleton bus — import and use this in all services
bus = EventBus()
