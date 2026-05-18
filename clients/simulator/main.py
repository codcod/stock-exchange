"""
A standalone client that generates synthetic order traffic for the exchange.

This script exercises the full microservice stack by sending a configurable
number of random orders through the HTTP gateway.

It can be configured with the following environment variables:
- `GATEWAY_URL`: Base URL of the gateway (default: http://localhost:8000)
- `API_KEY`: Value for the `X-Api-Key` header (default: none)
"""

from __future__ import annotations

import asyncio
import os
import random
import sys

import httpx

GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:8000').rstrip('/')
API_KEY = os.getenv('API_KEY', '')

TICKERS = [
    ('AAPL', 175.0),
    ('GOOG', 140.0),
    ('MSFT', 380.0),
]

NUM_ACCOUNTS = 5
INITIAL_CASH = 500_000.0
INITIAL_SHARES = 1_000
ORDERS_TO_SIMULATE = 50


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _headers() -> dict:
    """Return authentication headers if an API key is configured."""
    return {'X-Api-Key': API_KEY} if API_KEY else {}


async def _post(http: httpx.AsyncClient, path: str, body: dict) -> dict:
    """Send a POST request to the gateway."""
    r = await http.post(f'{GATEWAY_URL}{path}', json=body, headers=_headers())
    r.raise_for_status()
    return r.json() if r.content else {}


async def _get(http: httpx.AsyncClient, path: str) -> dict:
    """Send a GET request to the gateway."""
    r = await http.get(f'{GATEWAY_URL}{path}', headers=_headers())
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def setup(http: httpx.AsyncClient) -> None:
    """
    Register the initial set of instruments and trading accounts that will
    be used in the simulation.
    """
    for ticker, price in TICKERS:
        await _post(
            http,
            '/instruments',
            {
                'ticker': ticker,
                'name': ticker,
                'max_order_size': 500,
                'last_price': price,
            },
        )

    for i in range(NUM_ACCOUNTS):
        await _post(
            http,
            '/accounts',
            {
                'account_id': f'trader-{i}',
                'name': f'Trader {i}',
                'cash_balance': INITIAL_CASH,
                'positions': {ticker: INITIAL_SHARES for ticker, _ in TICKERS},
            },
        )


# ---------------------------------------------------------------------------
# Order generation
# ---------------------------------------------------------------------------


def _random_order() -> dict:
    """Generate a single random limit order."""
    ticker, ref_price = random.choice(TICKERS)
    spread = ref_price * 0.02
    price = round(ref_price + random.uniform(-spread, spread), 2)
    return {
        'account_id': f'trader-{random.randint(0, NUM_ACCOUNTS - 1)}',
        'ticker': ticker,
        'side': random.choice(['BUY', 'SELL']),
        'order_type': 'LIMIT',
        'quantity': random.choice([1, 5, 10, 20, 50]),
        'price': price,
    }


# ---------------------------------------------------------------------------
# State reporting
# ---------------------------------------------------------------------------


async def print_state(http: httpx.AsyncClient) -> None:
    """
    Fetch and display the current market state and account balances at the
    end of the simulation.
    """
    print('\n--- Market snapshot ---')
    for ticker, _ in TICKERS:
        try:
            q = await _get(http, f'/market-data/{ticker}/quote')
            print(
                f'  {ticker:6s} last={q["last_price"]:7.2f}  '
                f'bid={q["bid"]:7.2f}  ask={q["ask"]:7.2f}  '
                f'vol={q["volume_today"]}'
            )
        except httpx.HTTPStatusError:
            print(f'  {ticker:6s} no quote yet')

        try:
            d = await _get(http, f'/market-data/{ticker}/depth')
            bids = d.get('bids', [])[:3]
            asks = d.get('asks', [])[:3]
            bid_str = ' | '.join(f'{b["price"]:.2f}x{b["quantity"]}' for b in bids)
            ask_str = ' | '.join(f'{a["price"]:.2f}x{a["quantity"]}' for a in asks)
            print(f'         bids: {bid_str or "empty"}')
            print(f'         asks: {ask_str or "empty"}')
        except httpx.HTTPStatusError:
            pass

    print('\n--- Account balances ---')
    for i in range(NUM_ACCOUNTS):
        try:
            a = await _get(http, f'/accounts/trader-{i}')
            positions = ' '.join(f'{t}:{a["positions"].get(t, 0)}' for t, _ in TICKERS)
            print(f'  trader-{i}: cash={a["cash_balance"]:>12,.2f}  {positions}')
        except httpx.HTTPStatusError:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run() -> None:
    """
    Main entry point for the simulation.

    This function connects to the gateway, sets up the initial state,
    submits a series of random orders, and then prints a summary of the
    final market and account states.
    """
    print(f'Connecting to gateway at {GATEWAY_URL} ...')
    async with httpx.AsyncClient(timeout=10.0) as http:
        try:
            r = await http.get(f'{GATEWAY_URL}/health')
            r.raise_for_status()
        except Exception as exc:
            print(f'ERROR: gateway not reachable — {exc}')
            sys.exit(1)

        print('Registering instruments and accounts ...')
        try:
            await setup(http)
        except httpx.HTTPStatusError as exc:
            print(f'ERROR during setup: {exc.response.status_code} {exc.response.text}')
            sys.exit(1)

        filled = rejected = resting = 0

        print(f'\nSimulating {ORDERS_TO_SIMULATE} orders ...\n')
        for i in range(ORDERS_TO_SIMULATE):
            payload = _random_order()
            try:
                r = await http.post(
                    f'{GATEWAY_URL}/orders', json=payload, headers=_headers()
                )
                r.raise_for_status()
                order = r.json()
            except httpx.HTTPStatusError as exc:
                print(
                    f'[{i + 1:3d}] HTTP {exc.response.status_code}: {exc.response.text}'
                )
                rejected += 1
                continue

            status = order['status']
            print(
                f'[{i + 1:3d}] {payload["side"]:4s} {payload["ticker"]}'
                f' {payload["quantity"]:3d} @ {payload["price"]:7.2f}  {status}'
                + (
                    f'  ({order["reject_reason"]})'
                    if order.get('reject_reason')
                    else ''
                )
            )

            if status == 'FILLED':
                filled += 1
            elif status == 'REJECTED':
                rejected += 1
            else:
                resting += 1

        print(
            f'\nSummary: {filled} filled, {resting} resting/partial, {rejected} reject'
        )
        await print_state(http)


if __name__ == '__main__':
    asyncio.run(run())
