"""
exchange/main.py

Wires all services together and exposes a single Exchange facade.
This is the public API used by the gateway, simulator, and tests.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from services.clearing.service import ClearingService
from services.market_data.service import MarketDataService
from services.matching_engine.engine import MatchingEngine
from services.order_management.service import OrderManagementService
from services.risk_engine.engine import RiskEngine
from shared.db.repositories import (
    AccountRepository,
    InstrumentRepository,
    OrderRepository,
    TradeRepository,
)
from shared.db.tables import metadata
from shared.events.bus import TradeExecuted, bus
from shared.models.domain import Account, Instrument, Order, OrderType, Side

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(name)s | %(message)s',
)

logger = logging.getLogger(__name__)


class Exchange:
    """
    Top-level facade. Use Exchange.create() to instantiate:

        # In-memory (tests / demo):
        exchange = await Exchange.create()

        # With persistence:
        from shared.db.connection import get_engine
        exchange = await Exchange.create(db_engine=get_engine())

    __init__ wires services synchronously but performs no I/O. The async
    factory classmethod handles DDL and state loading before returning.
    """

    def __init__(self, db_engine: Optional[AsyncEngine] = None) -> None:
        self._engine = db_engine

        if db_engine is not None:
            order_repo: Optional[OrderRepository] = OrderRepository(db_engine)
            account_repo: Optional[AccountRepository] = AccountRepository(db_engine)
            instrument_repo: Optional[InstrumentRepository] = InstrumentRepository(
                db_engine
            )
            trade_repo: Optional[TradeRepository] = TradeRepository(db_engine)
        else:
            order_repo = account_repo = instrument_repo = trade_repo = None

        self._instrument_repo = instrument_repo
        self._account_repo = account_repo

        self.risk_engine = RiskEngine()
        self.matching_engine = MatchingEngine(bus)
        self.order_management = OrderManagementService(
            self.risk_engine,
            self.matching_engine,
            bus,
            order_repo=order_repo,
        )
        self.clearing = ClearingService(
            bus,
            account_repo=account_repo,
            trade_repo=trade_repo,
        )
        self.market_data = MarketDataService(bus)

    @classmethod
    async def create(cls, db_engine: Optional[AsyncEngine] = None) -> 'Exchange':
        instance = cls(db_engine)
        if db_engine is not None:
            await instance._setup_db()
        return instance

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    async def _setup_db(self) -> None:
        assert self._engine is not None
        async with self._engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        await self._load_state()
        bus.subscribe(TradeExecuted, self._on_trade_executed)

    async def _load_state(self) -> None:
        assert self._instrument_repo and self._account_repo

        for instrument in await self._instrument_repo.load_all():
            self.risk_engine.register_instrument(instrument)
            if instrument.last_price:
                book = self.matching_engine.get_or_create_book(instrument.ticker)
                book.last_price = instrument.last_price

        for account in await self._account_repo.load_all():
            self.risk_engine.register_account(account)
            self.clearing.register_account(account)

        for order in await self.order_management._order_repo.load_all():  # type: ignore[union-attr]
            self.order_management._orders[order.order_id] = order
            if order.is_active:
                self.matching_engine.restore_order(order)

        logger.info('State loaded from database')

    async def _on_trade_executed(self, event: TradeExecuted) -> None:
        if self._instrument_repo:
            await self._instrument_repo.update_last_price(event.ticker, event.price)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    async def register_account(self, account: Account) -> None:
        self.risk_engine.register_account(account)
        self.clearing.register_account(account)
        if self._account_repo:
            await self._account_repo.save(account)

    async def register_instrument(self, instrument: Instrument) -> None:
        self.risk_engine.register_instrument(instrument)
        if self._instrument_repo:
            await self._instrument_repo.save(instrument)

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------

    async def submit_order(self, order: Order) -> Order:
        return await self.order_management.submit_order(order)

    async def cancel_order(self, order_id: str, account_id: str) -> bool:
        return await self.order_management.cancel_order(order_id, account_id)

    # ------------------------------------------------------------------
    # Queries (in-memory, no await needed)
    # ------------------------------------------------------------------

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.order_management.get_order(order_id)

    def get_orders(self, account_id: str) -> List[Order]:
        return self.order_management.get_orders_for_account(account_id)

    def get_quote(self, ticker: str):
        return self.market_data.get_quote(ticker)

    def get_depth(self, ticker: str) -> Optional[dict]:
        return self.matching_engine.snapshot(ticker)

    def get_account(self, account_id: str) -> Optional[Account]:
        return self.clearing.get_account(account_id)


# ---------------------------------------------------------------------------
# Demo — run with: python -m exchange.main
# ---------------------------------------------------------------------------
async def _demo() -> None:
    exchange = await Exchange.create()

    for ticker, name, price in [
        ('AAPL', 'Apple Inc.', 175.0),
        ('GOOG', 'Alphabet Inc.', 140.0),
        ('MSFT', 'Microsoft Corp.', 380.0),
    ]:
        await exchange.register_instrument(Instrument(ticker, name, last_price=price))

    alice = Account('alice', 'Alice', cash_balance=100_000)
    bob = Account('bob', 'Bob', cash_balance=100_000)
    await exchange.register_account(alice)
    await exchange.register_account(bob)
    alice.positions['AAPL'] = 100
    bob.positions['AAPL'] = 100

    print('\n=== Submitting orders ===')

    sell = await exchange.submit_order(
        Order(
            account_id='bob',
            ticker='AAPL',
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=10,
            price=175.0,
        )
    )
    print(f'Sell order status: {sell.status.value}')

    buy = await exchange.submit_order(
        Order(
            account_id='alice',
            ticker='AAPL',
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            price=175.0,
        )
    )
    print(f'Buy order status: {buy.status.value}')

    print('\n=== Post-trade state ===')
    print(f'Alice cash:   {exchange.get_account("alice").cash_balance:,.2f}')
    print(f'Alice AAPL:   {exchange.get_account("alice").positions.get("AAPL", 0)}')
    print(f'Bob cash:     {exchange.get_account("bob").cash_balance:,.2f}')
    print(f'Bob AAPL:     {exchange.get_account("bob").positions.get("AAPL", 0)}')

    quote = exchange.get_quote('AAPL')
    if quote:
        print(f'\nAAPL last price: {quote.last_price:.2f}')


if __name__ == '__main__':
    asyncio.run(_demo())
