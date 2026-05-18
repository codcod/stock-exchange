# flake8: noqa E501

"""
scripts/validate_trade.py

Validates a controlled trade between two accounts, then confirms the database
reflects the match, updated positions, and cash movements.

Scenario
--------
  trader-2  SELL  50 AAPL @ 174.50   (rests in the book first)
  trader-0  BUY  100 AAPL @ 175.00   (aggresses against trader-2's ask)

Expected outcome
  • 50 shares trade at 174.50  (the BUY may also fill against other resting
    SELL orders already in the book — this is normal and handled)
  • trader-2's sell order:  FILLED
  • trader-0's buy order:   PARTIALLY_FILLED or FILLED (≥50 filled; fully fills
    if other resting SELL orders at ≤175.00 are already in the book)
  • clearing.trades:        one row for the buy/sell order pair
  • positions delta:        matches the sum of all trades that settled
  • cash delta:             matches the sum of all settled trade values

Note: two BUY orders cannot match each other.  The script uses one SELL and
one BUY so the matching engine can produce a trade.

Usage
-----
  DATABASE_URL=postgresql://exchange:exchange@localhost:5432/exchange \
  uv run python scripts/validate_trade.py

  # Or with a custom gateway:
  GATEWAY_URL=http://localhost:8000 DATABASE_URL=... \
    uv run python scripts/validate_trade.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import asyncpg
import httpx

GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:8000').rstrip('/')
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://exchange:exchange@localhost:5432/exchange',
).replace('postgresql+asyncpg://', 'postgresql://')

SELL_ACCOUNT = 'trader-2'
BUY_ACCOUNT = 'trader-0'
TICKER = 'AAPL'
SELL_PRICE = 174.50
BUY_PRICE = 175.00
SELL_QTY = 50
BUY_QTY = 100
INITIAL_CASH = 500_000.0
INITIAL_SHARES = 1_000

POLL_INTERVAL = 0.5
POLL_TIMEOUT = 15.0
# Time after orders reach terminal state to let the outbox relay finish
# delivering fill events to the clearing service.
CLEARING_SETTLE_WAIT = 2.0


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _ok(msg: str) -> None:
    print(f'  ✓  {msg}')


def _fail(msg: str) -> None:
    print(f'  ✗  {msg}', file=sys.stderr)


async def _ensure_instrument(http: httpx.AsyncClient) -> None:
    r = await http.post(
        f'{GATEWAY_URL}/instruments',
        json={
            'ticker': TICKER,
            'name': TICKER,
            'max_order_size': 500,
            'last_price': 175.0,
        },
    )
    if r.status_code in (200, 201, 409):
        return
    r.raise_for_status()


async def _ensure_account(http: httpx.AsyncClient, account_id: str) -> None:
    r = await http.post(
        f'{GATEWAY_URL}/accounts',
        json={
            'account_id': account_id,
            'name': account_id,
            'cash_balance': INITIAL_CASH,
            'positions': {TICKER: INITIAL_SHARES},
        },
    )
    if r.status_code in (200, 201, 409):
        return
    r.raise_for_status()


async def _cancel_resting_orders(http: httpx.AsyncClient, account_id: str) -> int:
    """Cancel all OPEN/PARTIALLY_FILLED orders for account_id.

    Returns the count of cancellation requests sent.  Errors from individual
    cancels are ignored — the order may have filled between listing and
    cancelling, which is fine.
    """
    r = await http.get(f'{GATEWAY_URL}/accounts/{account_id}/orders')
    r.raise_for_status()
    orders = r.json()
    cancelled = 0
    for order in orders:
        if order['status'] in ('OPEN', 'PARTIALLY_FILLED'):
            try:
                cr = await http.delete(
                    f'{GATEWAY_URL}/orders/{order["order_id"]}',
                    params={'account_id': account_id},
                )
                if cr.status_code in (200, 404):
                    cancelled += 1
            except httpx.HTTPStatusError:
                pass
    return cancelled


async def _submit_order(
    http: httpx.AsyncClient,
    account_id: str,
    side: str,
    quantity: int,
    price: float,
) -> dict:
    r = await http.post(
        f'{GATEWAY_URL}/orders',
        json={
            'account_id': account_id,
            'ticker': TICKER,
            'side': side,
            'order_type': 'LIMIT',
            'quantity': quantity,
            'price': price,
        },
    )
    r.raise_for_status()
    return r.json()


async def _poll_order(
    http: httpx.AsyncClient,
    order_id: str,
    expected_statuses: set[str],
) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT
    while time.monotonic() < deadline:
        r = await http.get(f'{GATEWAY_URL}/orders/{order_id}')
        r.raise_for_status()
        order = r.json()
        if order['status'] in expected_statuses:
            return order
        await asyncio.sleep(POLL_INTERVAL)
    raise TimeoutError(
        f'order {order_id} did not reach {expected_statuses} within {POLL_TIMEOUT}s'
    )


# ──────────────────────────────────────────────────────────────────────────────
# DB snapshot / validation
# ──────────────────────────────────────────────────────────────────────────────


async def _snapshot(conn: asyncpg.Connection, accounts: list[str]) -> dict[str, dict]:
    """Return {account_id: {cash, qty}} for each account, read from clearing."""
    snap: dict[str, dict] = {}
    for acct_id in accounts:
        cash_row = await conn.fetchrow(
            'SELECT cash_balance FROM clearing.accounts WHERE account_id=$1',
            acct_id,
        )
        pos_row = await conn.fetchrow(
            'SELECT quantity FROM clearing.positions WHERE account_id=$1 AND ticker=$2',
            acct_id,
            TICKER,
        )
        snap[acct_id] = {
            'cash': float(cash_row['cash_balance']) if cash_row else 0.0,
            'qty': pos_row['quantity'] if pos_row else 0,
        }
    return snap


async def _validate_db(
    conn: asyncpg.Connection,
    buy_order_id: str,
    sell_order_id: str,
    before: dict[str, dict],
) -> bool:
    passed = True

    print('\n─── Database validation ─────────────────────────────────────────────')
    print(f'  (waiting {CLEARING_SETTLE_WAIT}s for outbox relay to settle all fills…)')
    await asyncio.sleep(CLEARING_SETTLE_WAIT)

    after = await _snapshot(conn, [BUY_ACCOUNT, SELL_ACCOUNT])

    # ── 1. Trade record ───────────────────────────────────────────────────────
    our_trade = await conn.fetchrow(
        """
        SELECT trade_id, buyer_account_id, seller_account_id,
               quantity, price, executed_at
        FROM   clearing.trades
        WHERE  buy_order_id  = $1
          AND  sell_order_id = $2
        """,
        buy_order_id,
        sell_order_id,
    )
    if our_trade:
        _ok(
            f'clearing.trades — trade_id={our_trade["trade_id"][:8]}…  '
            f'qty={our_trade["quantity"]}  price={float(our_trade["price"]):.2f}  '
            f'buyer={our_trade["buyer_account_id"]}  '
            f'seller={our_trade["seller_account_id"]}'
        )
    else:
        _fail(
            f'clearing.trades — no trade found for '
            f'buy={buy_order_id[:8]}… / sell={sell_order_id[:8]}…'
        )
        passed = False

    # ── 2. All trades attributed to the BUY order (may include other sellers) ─
    all_buy_trades = await conn.fetch(
        'SELECT seller_account_id, quantity, price FROM clearing.trades WHERE buy_order_id=$1',
        buy_order_id,
    )
    # All trades attributed to the SELL order (should be exactly one — our trade)
    all_sell_trades = await conn.fetch(
        'SELECT buyer_account_id, quantity, price FROM clearing.trades WHERE sell_order_id=$1',
        sell_order_id,
    )

    expected_buyer_qty_delta = sum(t['quantity'] for t in all_buy_trades)
    expected_buyer_cash_delta = -sum(
        t['quantity'] * float(t['price']) for t in all_buy_trades
    )
    expected_seller_qty_delta = -sum(t['quantity'] for t in all_sell_trades)
    expected_seller_cash_delta = sum(
        t['quantity'] * float(t['price']) for t in all_sell_trades
    )

    if len(all_buy_trades) > 1:
        print(
            f'  (note: BUY order matched {len(all_buy_trades)} sellers — '
            f'{expected_buyer_qty_delta} shares total)'
        )

    # ── 3. Buyer position delta ───────────────────────────────────────────────
    actual_buyer_qty_delta = after[BUY_ACCOUNT]['qty'] - before[BUY_ACCOUNT]['qty']
    if actual_buyer_qty_delta == expected_buyer_qty_delta:
        _ok(
            f'clearing.positions — {BUY_ACCOUNT} AAPL Δqty=+{actual_buyer_qty_delta} '
            f'(before={before[BUY_ACCOUNT]["qty"]}  after={after[BUY_ACCOUNT]["qty"]})'
        )
    else:
        _fail(
            f'clearing.positions — {BUY_ACCOUNT} AAPL Δqty={actual_buyer_qty_delta} '
            f'(expected +{expected_buyer_qty_delta}  '
            f'before={before[BUY_ACCOUNT]["qty"]}  after={after[BUY_ACCOUNT]["qty"]})'
        )
        passed = False

    # ── 4. Seller position delta ──────────────────────────────────────────────
    actual_seller_qty_delta = after[SELL_ACCOUNT]['qty'] - before[SELL_ACCOUNT]['qty']
    if actual_seller_qty_delta == expected_seller_qty_delta:
        _ok(
            f'clearing.positions — {SELL_ACCOUNT} AAPL Δqty={actual_seller_qty_delta} '
            f'(before={before[SELL_ACCOUNT]["qty"]}  after={after[SELL_ACCOUNT]["qty"]})'
        )
    else:
        _fail(
            f'clearing.positions — {SELL_ACCOUNT} AAPL Δqty={actual_seller_qty_delta} '
            f'(expected {expected_seller_qty_delta}  '
            f'before={before[SELL_ACCOUNT]["qty"]}  after={after[SELL_ACCOUNT]["qty"]})'
        )
        passed = False

    # ── 5. Buyer cash delta ───────────────────────────────────────────────────
    actual_buyer_cash_delta = after[BUY_ACCOUNT]['cash'] - before[BUY_ACCOUNT]['cash']
    if abs(actual_buyer_cash_delta - expected_buyer_cash_delta) < 0.01:
        _ok(
            f'clearing.accounts — {BUY_ACCOUNT} cash Δ={actual_buyer_cash_delta:+,.2f} '
            f'(expected {expected_buyer_cash_delta:+,.2f})'
        )
    else:
        _fail(
            f'clearing.accounts — {BUY_ACCOUNT} cash Δ={actual_buyer_cash_delta:+,.2f} '
            f'(expected {expected_buyer_cash_delta:+,.2f})'
        )
        passed = False

    # ── 6. Seller cash delta ──────────────────────────────────────────────────
    actual_seller_cash_delta = (
        after[SELL_ACCOUNT]['cash'] - before[SELL_ACCOUNT]['cash']
    )
    if abs(actual_seller_cash_delta - expected_seller_cash_delta) < 0.01:
        _ok(
            f'clearing.accounts — {SELL_ACCOUNT} cash Δ={actual_seller_cash_delta:+,.2f} '
            f'(expected {expected_seller_cash_delta:+,.2f})'
        )
    else:
        _fail(
            f'clearing.accounts — {SELL_ACCOUNT} cash Δ={actual_seller_cash_delta:+,.2f} '
            f'(expected {expected_seller_cash_delta:+,.2f})'
        )
        passed = False

    # ── 7. OMS order statuses ─────────────────────────────────────────────────
    oms_orders = await conn.fetch(
        'SELECT order_id, side, status, filled_quantity '
        'FROM order_management.orders WHERE order_id = ANY($1)',
        [buy_order_id, sell_order_id],
    )
    oms_by_id = {row['order_id']: row for row in oms_orders}

    sell_row = oms_by_id.get(sell_order_id)
    if (
        sell_row
        and sell_row['status'] == 'FILLED'
        and sell_row['filled_quantity'] == SELL_QTY
    ):
        _ok(
            f'order_management.orders — SELL status=FILLED  '
            f'filled_qty={sell_row["filled_quantity"]}'
        )
    else:
        status = sell_row['status'] if sell_row else 'not found'
        filled = sell_row['filled_quantity'] if sell_row else '—'
        _fail(
            f'order_management.orders — SELL status={status}  '
            f'filled_qty={filled} (expected FILLED/{SELL_QTY})'
        )
        passed = False

    buy_row = oms_by_id.get(buy_order_id)
    # BUY may match more than SELL_QTY shares (or fully fill) if other
    # resting asks from unrelated traders are already in the book.
    if (
        buy_row
        and buy_row['status'] in ('PARTIALLY_FILLED', 'FILLED')
        and buy_row['filled_quantity'] >= SELL_QTY
    ):
        _ok(
            f'order_management.orders — BUY status={buy_row["status"]}  '
            f'filled_qty={buy_row["filled_quantity"]} (≥{SELL_QTY})'
        )
    else:
        status = buy_row['status'] if buy_row else 'not found'
        filled = buy_row['filled_quantity'] if buy_row else '—'
        _fail(
            f'order_management.orders — BUY status={status}  '
            f'filled_qty={filled} (expected PARTIALLY_FILLED or FILLED, ≥{SELL_QTY})'
        )
        passed = False

    print('─────────────────────────────────────────────────────────────────────')
    return passed


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


async def run() -> None:
    print(f'Gateway : {GATEWAY_URL}')
    print(f'Database: {DATABASE_URL}\n')

    # ── Gateway health ────────────────────────────────────────────────────────
    async with httpx.AsyncClient(timeout=10.0) as http:
        try:
            r = await http.get(f'{GATEWAY_URL}/health')
            r.raise_for_status()
        except Exception as exc:
            print(f'ERROR: gateway not reachable — {exc}', file=sys.stderr)
            sys.exit(1)

        print('── Setup ─────────────────────────────────────────────────────────────')
        await _ensure_instrument(http)
        await _ensure_account(http, BUY_ACCOUNT)
        await _ensure_account(http, SELL_ACCOUNT)
        print(f'  instrument {TICKER} and accounts {BUY_ACCOUNT}, {SELL_ACCOUNT} ready')

        # Cancel any resting orders for the test accounts so that ghost orders
        # from previous runs (still alive in the matching engine's in-memory
        # book) cannot interfere with this test's fills or deltas.
        for acct in (BUY_ACCOUNT, SELL_ACCOUNT):
            n = await _cancel_resting_orders(http, acct)
            if n:
                print(f'  cancelled {n} resting order(s) for {acct}')
        # Brief pause for cancellation events to propagate through the outbox.
        await asyncio.sleep(1.0)
        print()

        # ── Snapshot pre-trade state ──────────────────────────────────────────
        try:
            conn = await asyncpg.connect(DATABASE_URL)
        except Exception as exc:
            print(f'ERROR: cannot connect to database — {exc}', file=sys.stderr)
            print(
                '  Set DATABASE_URL=postgresql://exchange:exchange@localhost:5432/exchange',
                file=sys.stderr,
            )
            sys.exit(1)

        before = await _snapshot(conn, [BUY_ACCOUNT, SELL_ACCOUNT])
        print('── Pre-trade snapshot ────────────────────────────────────────────────')
        for acct_id, s in before.items():
            print(f'  {acct_id}: cash={s["cash"]:>12,.2f}  AAPL={s["qty"]}')
        print()

        # ── Orders ───────────────────────────────────────────────────────────
        print('── Order submission ──────────────────────────────────────────────────')

        sell_order = await _submit_order(
            http, SELL_ACCOUNT, 'SELL', SELL_QTY, SELL_PRICE
        )
        sell_id = sell_order['order_id']
        print(
            f'  submitted SELL {SELL_QTY} {TICKER} @ {SELL_PRICE}  by {SELL_ACCOUNT}  id={sell_id[:8]}…'
        )

        buy_order = await _submit_order(http, BUY_ACCOUNT, 'BUY', BUY_QTY, BUY_PRICE)
        buy_id = buy_order['order_id']
        print(
            f'  submitted BUY  {BUY_QTY} {TICKER} @ {BUY_PRICE}  by {BUY_ACCOUNT}  id={buy_id[:8]}…\n'
        )

        # ── Poll for settlement ───────────────────────────────────────────────
        print('── Waiting for settlement ────────────────────────────────────────────')
        try:
            sell_final = await _poll_order(
                http, sell_id, {'FILLED', 'CANCELLED', 'REJECTED'}
            )
            buy_final = await _poll_order(
                http, buy_id, {'FILLED', 'PARTIALLY_FILLED', 'CANCELLED', 'REJECTED'}
            )
        except TimeoutError as exc:
            print(f'ERROR: {exc}', file=sys.stderr)
            await conn.close()
            sys.exit(1)

        print(
            f'  SELL {sell_id[:8]}… → {sell_final["status"]}  filled={sell_final["filled_quantity"]}/{SELL_QTY}'
        )
        print(
            f'  BUY  {buy_id[:8]}… → {buy_final["status"]}  filled={buy_final["filled_quantity"]}/{BUY_QTY}\n'
        )

    # ── DB validation ─────────────────────────────────────────────────────────
    try:
        passed = await _validate_db(conn, buy_id, sell_id, before)
    finally:
        await conn.close()

    print()
    if passed:
        print('RESULT: all checks passed')
        sys.exit(0)
    else:
        print('RESULT: one or more checks FAILED', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(run())
