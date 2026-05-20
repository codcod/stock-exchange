"""
Clearing service — pure trade record keeper.

Receives TradeExecuted events from the Matching Engine and persists the
trade record. Account settlement (cash/share adjustments) is handled by
the Account service, which also receives TradeExecuted from the Matching
Engine's outbox.
"""

from __future__ import annotations

import logging

from shared.domain.events import TradeExecuted
from shared.domain.models import Trade

if __import__('typing').TYPE_CHECKING:
    from services.clearing.repository import TradeRepository

logger = logging.getLogger(__name__)


class ClearingService:
    """Persists trade records for the audit ledger."""

    def __init__(self, trade_repo: 'TradeRepository') -> None:
        self._trade_repo = trade_repo

    async def on_trade_executed(self, event: TradeExecuted) -> None:
        """Persist the trade record."""
        logger.info(
            'Recording trade %s: %s qty=%d price=%.4f',
            event.trade_id,
            event.ticker,
            event.quantity,
            event.price,
        )
        await self._trade_repo.save(
            Trade(
                trade_id=event.trade_id,
                ticker=event.ticker,
                buy_order_id=event.buy_order_id,
                sell_order_id=event.sell_order_id,
                buyer_account_id=event.buyer_account_id,
                seller_account_id=event.seller_account_id,
                quantity=event.quantity,
                price=event.price,
            )
        )
