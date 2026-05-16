"""
tests/test_persistence.py

Integration tests for the DB persistence layer.
Requires a running Postgres instance (DATABASE_URL env var or default).
Skipped automatically when the DB is not reachable.
"""

import typing as tp

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from exchange.main import Exchange
from shared.db.repositories import (
    AccountRepository,
    InstrumentRepository,
    OrderRepository,
    TradeRepository,
)
from shared.db.tables import metadata
from shared.models.domain import (
    Account,
    Instrument,
    Order,
    OrderStatus,
    OrderType,
    Side,
    Trade,
)

DB_URL = 'postgresql+asyncpg://exchange:exchange@localhost:5432/exchange'


async def _try_engine() -> tp.Optional[AsyncEngine]:
    try:
        engine = create_async_engine(DB_URL)
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        return engine
    except Exception:
        return None


@pytest.fixture(scope='module')
async def engine():
    e = await _try_engine()
    if e is None:
        pytest.skip('Postgres not reachable — skipping persistence tests')
    async with e.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
    yield e
    async with e.begin() as conn:
        await conn.run_sync(metadata.drop_all)


@pytest.fixture()
async def exchange(engine):
    # Drop and recreate between tests for isolation
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
    return await Exchange.create(db_engine=engine)


# ---------------------------------------------------------------------------
# Repository unit tests
# ---------------------------------------------------------------------------


async def test_instrument_repo_round_trip(engine):
    repo = InstrumentRepository(engine)
    instr = Instrument(
        'TEST', 'Test Corp', lot_size=1, max_order_size=1000, last_price=42.0
    )
    await repo.save(instr)

    loaded = await repo.load_all()
    assert len(loaded) == 1
    assert loaded[0].ticker == 'TEST'
    assert loaded[0].last_price == 42.0

    await repo.update_last_price('TEST', 50.0)
    loaded2 = await repo.load_all()
    assert loaded2[0].last_price == 50.0


async def test_account_repo_round_trip(engine):
    repo = AccountRepository(engine)
    acct = Account('acc-1', 'Alice', cash_balance=10_000.0, reserved_cash=500.0)
    acct.positions = {'AAPL': 10, 'GOOG': 5}
    acct.reserved_shares = {'AAPL': 2}
    await repo.save(acct)

    loaded = await repo.load_all()
    assert len(loaded) == 1
    a = loaded[0]
    assert a.account_id == 'acc-1'
    assert a.cash_balance == 10_000.0
    assert a.reserved_cash == 500.0
    assert a.positions == {'AAPL': 10, 'GOOG': 5}
    assert a.reserved_shares == {'AAPL': 2}

    # Mutate and re-save
    a.cash_balance = 9_000.0
    a.positions['AAPL'] = 20
    await repo.save(a)
    loaded2 = await repo.load_all()
    assert loaded2[0].cash_balance == 9_000.0
    assert loaded2[0].positions['AAPL'] == 20


async def test_order_repo_round_trip(engine):
    repo = OrderRepository(engine)
    order = Order(
        account_id='acc-1',
        ticker='AAPL',
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        price=175.0,
    )
    await repo.save(order)

    loaded = await repo.load_all()
    assert len(loaded) == 1
    o = loaded[0]
    assert o.order_id == order.order_id
    assert o.side == Side.BUY
    assert o.price == 175.0
    assert o.status == OrderStatus.PENDING

    order.status = OrderStatus.FILLED
    order.filled_quantity = 10
    order.average_fill_price = 175.0
    await repo.update(order)

    loaded2 = await repo.load_all()
    assert loaded2[0].status == OrderStatus.FILLED
    assert loaded2[0].filled_quantity == 10


async def test_trade_repo_round_trip(engine):
    repo = TradeRepository(engine)
    trade = Trade(
        ticker='AAPL',
        buy_order_id='b-1',
        sell_order_id='s-1',
        buyer_account_id='alice',
        seller_account_id='bob',
        quantity=5,
        price=175.0,
    )
    await repo.save(trade)


# ---------------------------------------------------------------------------
# End-to-end Exchange tests with real DB
# ---------------------------------------------------------------------------


async def test_exchange_persists_trade(exchange):
    await exchange.register_instrument(Instrument('AAPL', 'Apple', last_price=175.0))
    alice = Account('alice', 'Alice', cash_balance=50_000.0)
    bob = Account('bob', 'Bob', cash_balance=50_000.0)
    alice.positions['AAPL'] = 100
    bob.positions['AAPL'] = 100
    await exchange.register_account(alice)
    await exchange.register_account(bob)

    await exchange.submit_order(
        Order(
            account_id='bob',
            ticker='AAPL',
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=10,
            price=175.0,
        )
    )
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
    assert buy.status == OrderStatus.FILLED

    # Verify state survived: reload a fresh Exchange from same DB
    exchange2 = await Exchange.create(db_engine=exchange._engine)
    acct = exchange2.get_account('alice')
    assert acct is not None
    assert acct.positions.get('AAPL') == 110
    assert acct.cash_balance == 50_000.0 - 175.0 * 10


async def test_exchange_restores_open_order_to_book(exchange):
    await exchange.register_instrument(
        Instrument('MSFT', 'Microsoft', last_price=380.0)
    )
    bob = Account('bob', 'Bob', cash_balance=50_000.0)
    bob.positions['MSFT'] = 100
    await exchange.register_account(bob)

    sell = await exchange.submit_order(
        Order(
            account_id='bob',
            ticker='MSFT',
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            quantity=5,
            price=385.0,  # above market, stays open
        )
    )
    assert sell.status == OrderStatus.OPEN

    # Reload exchange — open order should be back in the book
    exchange2 = await Exchange.create(db_engine=exchange._engine)
    depth = exchange2.get_depth('MSFT')
    assert depth is not None
    asks = depth['asks']
    assert len(asks) == 1
    assert asks[0]['price'] == 385.0
    assert asks[0]['quantity'] == 5
