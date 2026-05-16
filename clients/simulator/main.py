"""
clients/simulator/main.py

Generates synthetic order traffic to exercise the exchange.
Useful for watching the order book fill up, seeing matches happen,
and understanding how prices evolve.

Run with: python -m clients.simulator.main
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from exchange.main import Exchange
from shared.models.domain import Account, Instrument, Order, OrderType, Side

TICKERS = [
    ('AAPL', 175.0),
    ('GOOG', 140.0),
    ('MSFT', 380.0),
]

NUM_ACCOUNTS = 5
INITIAL_CASH = 500_000.0
INITIAL_SHARES = 1_000
ORDERS_TO_SIMULATE = 50
SLEEP_BETWEEN_ORDERS = 0.1  # seconds; set to 0 for speed


async def make_exchange() -> Exchange:
    exchange = await Exchange.create()

    for ticker, price in TICKERS:
        await exchange.register_instrument(
            Instrument(ticker, ticker, last_price=price, max_order_size=500)
        )

    for i in range(NUM_ACCOUNTS):
        acct = Account(
            account_id=f'trader-{i}',
            name=f'Trader {i}',
            cash_balance=INITIAL_CASH,
        )
        for ticker, _ in TICKERS:
            acct.positions[ticker] = INITIAL_SHARES
        await exchange.register_account(acct)

    return exchange


def random_order(exchange: Exchange) -> Order:
    ticker, ref_price = random.choice(TICKERS)
    account_id = f'trader-{random.randint(0, NUM_ACCOUNTS - 1)}'
    side = random.choice([Side.BUY, Side.SELL])
    quantity = random.choice([1, 5, 10, 20, 50])

    # Price within ±2% of reference
    spread = ref_price * 0.02
    price = round(ref_price + random.uniform(-spread, spread), 2)

    return Order(
        account_id=account_id,
        ticker=ticker,
        side=side,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=price,
    )


def print_state(exchange: Exchange) -> None:
    print('\n--- Market snapshot ---')
    for ticker, _ in TICKERS:
        quote = exchange.get_quote(ticker)
        depth = exchange.get_depth(ticker)
        if quote:
            print(
                f'  {ticker:6s} last={quote.last_price:7.2f}  '
                f'bid={quote.bid:7.2f}  ask={quote.ask:7.2f}  '
                f'vol={quote.volume_today}'
            )
        if depth:
            bids = depth.get('bids', [])[:3]
            asks = depth.get('asks', [])[:3]
            bid_str = ' | '.join(f'{b["price"]:.2f}x{b["quantity"]}' for b in bids)
            ask_str = ' | '.join(f'{a["price"]:.2f}x{a["quantity"]}' for a in asks)
            print(f'         bids: {bid_str or "empty"}')
            print(f'         asks: {ask_str or "empty"}')

    print('\n--- Account balances ---')
    for i in range(NUM_ACCOUNTS):
        acct = exchange.get_account(f'trader-{i}')
        if acct:
            positions = ' '.join(f'{t}:{acct.positions.get(t, 0)}' for t, _ in TICKERS)
            print(f'  trader-{i}: cash={acct.cash_balance:,.0f}  {positions}')


async def run() -> None:
    print('Initialising exchange...')
    exchange = await make_exchange()

    filled = rejected = resting = 0

    print(f'Simulating {ORDERS_TO_SIMULATE} orders...\n')
    for i in range(ORDERS_TO_SIMULATE):
        order = random_order(exchange)
        result = await exchange.submit_order(order)

        status = result.status.value
        price_str = f'@ {order.price:.2f}' if order.price else '@ MARKET'
        print(
            f'[{i + 1:3d}] {order.side.value:4s} {order.ticker} {order.quantity:3d} '
            f'{price_str:12s} {status}'
            + (f' ({result.reject_reason})' if result.reject_reason else '')
        )

        if status == 'FILLED':
            filled += 1
        elif status == 'REJECTED':
            rejected += 1
        else:
            resting += 1

        if SLEEP_BETWEEN_ORDERS:
            time.sleep(SLEEP_BETWEEN_ORDERS)

    print(f'\nSummary: {filled} filled, {resting} resting/partial, {rejected} rejected')
    print_state(exchange)


if __name__ == '__main__':
    asyncio.run(run())
