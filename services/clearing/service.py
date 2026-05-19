"""
The clearing service is responsible for the settlement of trades and
the management of reservations.

Settlement involves updating the cash and share balances of the buyer
and seller accounts after a trade is executed.

Reservations are temporary holds on cash or shares that are created
when an order is submitted. This ensures that the assets remain
available while the order is open and prevents them from being used in
other transactions. When an order is filled or canceled, the
corresponding reservation is released.
"""

from __future__ import annotations

import logging
import typing as tp

from shared.domain.events import TradeExecuted
from shared.domain.models import Account, Trade

if tp.TYPE_CHECKING:
    from services.clearing.repository import AccountRepository, TradeRepository

logger = logging.getLogger(__name__)


class ClearingService:
    """
    A service that handles trade settlement and asset reservations.

    This service maintains the authoritative state of all trading accounts,
    including cash balances and share positions. It processes `TradeExecuted`
    events from the matching engine to settle trades and provides endpoints
    for the order management service to manage reservations.
    """

    def __init__(
        self,
        account_repo: 'AccountRepository',
        trade_repo: 'TradeRepository',
    ) -> None:
        self._accounts: tp.Dict[str, Account] = {}
        self._settled_trades: tp.List[str] = []
        self._account_repo = account_repo
        self._trade_repo = trade_repo

    def register_account(self, account: Account) -> None:
        """Add or update an account in the local cache."""
        self._accounts[account.account_id] = account

    def list_accounts(self) -> tp.List[Account]:
        """Return all registered accounts."""
        return list(self._accounts.values())

    # ------------------------------------------------------------------
    # Reservation management (called by Order Management on order submit/cancel)
    # ------------------------------------------------------------------

    async def reserve_cash(self, account_id: str, delta: float) -> tp.Optional[Account]:
        """
        Update the reserved cash for an account by a given delta.

        A positive delta increases the reservation, while a negative delta
        releases it. The updated account state is persisted to the database.
        """
        account = self._accounts.get(account_id)
        if account is None:
            return None
        account.reserved_cash = max(0.0, account.reserved_cash + delta)
        await self._account_repo.save(account)
        return account

    async def reserve_shares(
        self, account_id: str, ticker: str, delta: int
    ) -> tp.Optional[Account]:
        """
        Update the reserved shares for a specific ticker by a given delta.

        A positive delta increases the reservation, while a negative delta
        releases it. The updated account state is persisted to the database.
        """
        account = self._accounts.get(account_id)
        if account is None:
            return None
        current = account.reserved_shares.get(ticker, 0)
        account.reserved_shares[ticker] = max(0, current + delta)
        await self._account_repo.save(account)
        return account

    # ------------------------------------------------------------------
    # Settlement logic (called on TradeExecuted events)
    # ------------------------------------------------------------------

    async def on_trade_executed(
        self, event: TradeExecuted
    ) -> tp.Tuple[tp.Optional[Account], tp.Optional[Account]]:
        """
        Settle a trade by updating the cash and share balances of both parties.

        This method adjusts the buyer's and seller's accounts to reflect the
        transfer of assets. It also releases any reservations that were held
        for the corresponding orders.

        Returns a tuple containing the updated buyer and seller accounts.
        """
        buyer = self._accounts.get(event.buyer_account_id)
        seller = self._accounts.get(event.seller_account_id)
        trade_value = event.price * event.quantity

        if buyer:
            # Deduct cash, add shares
            buyer.cash_balance -= trade_value
            buyer.positions[event.ticker] = (
                buyer.positions.get(event.ticker, 0) + event.quantity
            )
            # Release the reservation that was held since order submission
            buyer.reserved_cash = max(0.0, buyer.reserved_cash - trade_value)
            logger.info(
                'Cleared BUY for %s | %s +%d shares, -%.2f cash',
                buyer.account_id,
                event.ticker,
                event.quantity,
                trade_value,
            )

        if seller:
            # Add cash, deduct shares
            seller.cash_balance += trade_value
            seller.positions[event.ticker] = max(
                0, seller.positions.get(event.ticker, 0) - event.quantity
            )
            # Release the reservation
            reserved = seller.reserved_shares.get(event.ticker, 0)
            seller.reserved_shares[event.ticker] = max(0, reserved - event.quantity)
            logger.info(
                'Cleared SELL for %s | %s -%d shares, +%.2f cash',
                seller.account_id,
                event.ticker,
                event.quantity,
                trade_value,
            )

        self._settled_trades.append(event.trade_id)

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
        if buyer:
            await self._account_repo.save(buyer)
        if seller:
            await self._account_repo.save(seller)

        return buyer, seller

    def get_account(self, account_id: str) -> Account | None:
        """Retrieve a single account by its ID from the local cache."""
        return self._accounts.get(account_id)
