"""
scripts/seed.py

Seed the exchange with realistic initial data via the running HTTP gateway:
  - 100 instruments across 7 sectors
  - 30 accounts (institutional and retail)
  - 100 trades generated via matched order pairs

Requires the full service stack to be running against a fresh database.
Start services first (just infra-up, then start all services), then run:

    GATEWAY_URL=http://localhost:8000 python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.disable(logging.CRITICAL)

import httpx  # noqa: E402

from shared.models.domain import Account  # noqa: E402

random.seed(42)

GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:8000').rstrip('/')

# ---------------------------------------------------------------------------
# 100 instruments — (ticker, name, last_price)
# ---------------------------------------------------------------------------

INSTRUMENTS: list[tuple[str, str, float]] = [
    # Technology (20)
    ('AAPL', 'Apple Inc.', 182.50),
    ('MSFT', 'Microsoft Corp.', 415.00),
    ('GOOGL', 'Alphabet Inc.', 175.00),
    ('AMZN', 'Amazon.com Inc.', 185.00),
    ('META', 'Meta Platforms Inc.', 510.00),
    ('NVDA', 'NVIDIA Corp.', 875.00),
    ('TSLA', 'Tesla Inc.', 180.00),
    ('ORCL', 'Oracle Corp.', 125.00),
    ('IBM', 'IBM Corp.', 185.00),
    ('INTC', 'Intel Corp.', 30.00),
    ('AMD', 'Advanced Micro Devices', 160.00),
    ('QCOM', 'Qualcomm Inc.', 175.00),
    ('AVGO', 'Broadcom Inc.', 1400.00),
    ('CRM', 'Salesforce Inc.', 290.00),
    ('ADBE', 'Adobe Inc.', 475.00),
    ('NFLX', 'Netflix Inc.', 615.00),
    ('UBER', 'Uber Technologies', 75.00),
    ('LYFT', 'Lyft Inc.', 16.00),
    ('SNAP', 'Snap Inc.', 11.00),
    ('SPOT', 'Spotify Technology', 330.00),
    # Finance (15)
    ('JPM', 'JPMorgan Chase', 200.00),
    ('BAC', 'Bank of America', 40.00),
    ('WFC', 'Wells Fargo', 62.00),
    ('GS', 'Goldman Sachs', 480.00),
    ('MS', 'Morgan Stanley', 100.00),
    ('C', 'Citigroup Inc.', 65.00),
    ('AXP', 'American Express', 230.00),
    ('BLK', 'BlackRock Inc.', 820.00),
    ('SCHW', 'Charles Schwab', 75.00),
    ('USB', 'U.S. Bancorp', 42.00),
    ('COF', 'Capital One Financial', 145.00),
    ('V', 'Visa Inc.', 275.00),
    ('MA', 'Mastercard Inc.', 470.00),
    ('PYPL', 'PayPal Holdings', 70.00),
    ('SQ', 'Block Inc.', 75.00),
    # Healthcare (15)
    ('JNJ', 'Johnson & Johnson', 155.00),
    ('PFE', 'Pfizer Inc.', 26.00),
    ('UNH', 'UnitedHealth Group', 490.00),
    ('MRK', 'Merck & Co.', 125.00),
    ('ABBV', 'AbbVie Inc.', 165.00),
    ('BMY', 'Bristol-Myers Squibb', 55.00),
    ('LLY', 'Eli Lilly', 850.00),
    ('AMGN', 'Amgen Inc.', 285.00),
    ('GILD', 'Gilead Sciences', 68.00),
    ('BIIB', 'Biogen Inc.', 230.00),
    ('VRTX', 'Vertex Pharmaceuticals', 440.00),
    ('REGN', 'Regeneron Pharma', 1000.00),
    ('CVS', 'CVS Health Corp.', 65.00),
    ('MCK', 'McKesson Corp.', 580.00),
    ('ISRG', 'Intuitive Surgical', 415.00),
    # Energy (10)
    ('XOM', 'Exxon Mobil Corp.', 115.00),
    ('CVX', 'Chevron Corp.', 155.00),
    ('COP', 'ConocoPhillips', 115.00),
    ('SLB', 'SLB (Schlumberger)', 46.00),
    ('EOG', 'EOG Resources', 120.00),
    ('PXD', 'Pioneer Natural Resources', 235.00),
    ('MPC', 'Marathon Petroleum', 185.00),
    ('PSX', 'Phillips 66', 155.00),
    ('VLO', 'Valero Energy', 170.00),
    ('KMI', 'Kinder Morgan', 19.00),
    # Consumer & Retail (15)
    ('WMT', 'Walmart Inc.', 65.00),
    ('COST', 'Costco Wholesale', 780.00),
    ('TGT', 'Target Corp.', 155.00),
    ('HD', 'Home Depot', 345.00),
    ('LOW', "Lowe's Companies", 240.00),
    ('MCD', "McDonald's Corp.", 290.00),
    ('SBUX', 'Starbucks Corp.', 90.00),
    ('NKE', 'Nike Inc.', 75.00),
    ('PG', 'Procter & Gamble', 155.00),
    ('KO', 'Coca-Cola Co.', 63.00),
    ('PEP', 'PepsiCo Inc.', 170.00),
    ('CL', 'Colgate-Palmolive', 90.00),
    ('PM', 'Philip Morris Intl', 100.00),
    ('MO', 'Altria Group', 42.00),
    ('GIS', 'General Mills', 68.00),
    # Industrials (10)
    ('BA', 'Boeing Co.', 185.00),
    ('GE', 'GE Aerospace', 170.00),
    ('HON', 'Honeywell Intl', 215.00),
    ('CAT', 'Caterpillar Inc.', 355.00),
    ('DE', 'Deere & Company', 390.00),
    ('UPS', 'United Parcel Service', 125.00),
    ('FDX', 'FedEx Corp.', 250.00),
    ('LMT', 'Lockheed Martin', 450.00),
    ('RTX', 'RTX Corp.', 125.00),
    ('MMM', '3M Co.', 125.00),
    # Materials, Utilities, REIT, Global (15)
    ('LIN', 'Linde plc', 460.00),
    ('APD', 'Air Products', 290.00),
    ('SHW', 'Sherwin-Williams', 310.00),
    ('NEE', 'NextEra Energy', 72.00),
    ('DUK', 'Duke Energy', 98.00),
    ('AMT', 'American Tower', 210.00),
    ('PLD', 'Prologis Inc.', 120.00),
    ('CCI', 'Crown Castle Inc.', 105.00),
    ('SPG', 'Simon Property Group', 155.00),
    ('PSA', 'Public Storage', 295.00),
    ('BRKB', 'Berkshire Hathaway B', 420.00),
    ('BABA', 'Alibaba Group', 85.00),
    ('TSM', 'Taiwan Semiconductor', 145.00),
    ('ASML', 'ASML Holding', 800.00),
    ('SAP', 'SAP SE', 215.00),
]

# ---------------------------------------------------------------------------
# 30 accounts — (account_id, name, cash_balance)
# ---------------------------------------------------------------------------

ACCOUNTS: list[tuple[str, str, float]] = [
    ('acc-01', 'Apex Capital Fund', 5_000_000.00),
    ('acc-02', 'BlueStar Asset Mgmt', 3_500_000.00),
    ('acc-03', 'Cedar Grove Partners', 2_200_000.00),
    ('acc-04', 'Dune Capital LLC', 8_000_000.00),
    ('acc-05', 'Evergreen Investments', 1_800_000.00),
    ('acc-06', 'Falcon Ridge Advisors', 950_000.00),
    ('acc-07', 'Golden Oak Holdings', 4_100_000.00),
    ('acc-08', 'Harbor View Capital', 1_200_000.00),
    ('acc-09', 'Iron Bridge Fund', 6_300_000.00),
    ('acc-10', 'Juniper Street Mgmt', 750_000.00),
    ('acc-11', 'Keystone Portfolio', 500_000.00),
    ('acc-12', 'Lakewood Equity Fund', 1_600_000.00),
    ('acc-13', 'Maple Street Capital', 2_900_000.00),
    ('acc-14', 'Nordic Alpha Fund', 3_300_000.00),
    ('acc-15', 'Oakbrook Investments', 420_000.00),
    ('acc-16', 'Pacific Rim Advisors', 7_500_000.00),
    ('acc-17', 'Quartz Hill Capital', 1_100_000.00),
    ('acc-18', 'Redwood Asset Mgmt', 2_400_000.00),
    ('acc-19', 'Silverline Partners', 1_750_000.00),
    ('acc-20', 'Thornwood Capital', 890_000.00),
    ('acc-21', 'Union Square Fund', 650_000.00),
    ('acc-22', 'Venture Peak LLC', 3_800_000.00),
    ('acc-23', 'Westgate Portfolio', 1_950_000.00),
    ('acc-24', 'Xanadu Capital', 310_000.00),
    ('acc-25', 'Yale Street Advisors', 2_600_000.00),
    ('acc-26', 'Zenith Markets LLC', 4_700_000.00),
    ('acc-27', 'Alice Chen', 250_000.00),
    ('acc-28', 'Bob Okafor', 180_000.00),
    ('acc-29', 'Carol Mendez', 120_000.00),
    ('acc-30', 'David Park', 300_000.00),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_qty(price: float, max_shares: int) -> int:
    """Largest quantity that fits in one order without breaching the $1M value limit."""
    max_by_value = int(999_000 / price) if price else 9999
    return min(max_shares, max_by_value)


def _print_bar(label: str, done: int, total: int, width: int = 30) -> None:
    filled = int(width * done / total)
    bar = '█' * filled + '░' * (width - filled)
    print(f'\r  {label}: [{bar}] {done}/{total}', end='', flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def seed() -> None:  # noqa: C901, PLR0912, PLR0915
    async with httpx.AsyncClient(base_url=GATEWAY_URL, timeout=30.0) as http:

        # -- Instruments -------------------------------------------------------
        print(f'\nRegistering {len(INSTRUMENTS)} instruments...')
        instrument_prices: dict[str, float] = {}
        for ticker, name, price in INSTRUMENTS:
            resp = await http.post(
                '/instruments', json={'ticker': ticker, 'name': name, 'last_price': price}
            )
            resp.raise_for_status()
            instrument_prices[ticker] = price
        print(f'  Done — {len(instrument_prices)} instruments registered.')

        # -- Accounts with initial positions -----------------------------------
        print(f'\nRegistering {len(ACCOUNTS)} accounts...')
        tickers = list(instrument_prices.keys())
        account_map: dict[str, Account] = {}

        for account_id, name, cash in ACCOUNTS:
            positions = {t: 200 for t in random.sample(tickers, 15)}
            resp = await http.post(
                '/accounts',
                json={'account_id': account_id, 'name': name, 'cash_balance': cash, 'positions': positions},
            )
            resp.raise_for_status()
            # Mirror state locally so trade generation can check availability
            acct = Account(account_id=account_id, name=name, cash_balance=cash)
            acct.positions = positions
            account_map[account_id] = acct

        print(f'  Done — {len(account_map)} accounts registered.')

        # -- Trades via matched order pairs ------------------------------------
        print('\nGenerating 100 trades...')
        account_list = list(account_map.values())
        trades_done = 0
        attempts = 0
        max_attempts = 2_000

        while trades_done < 100 and attempts < max_attempts:
            attempts += 1

            ticker = random.choice(tickers)
            price = instrument_prices[ticker]

            sellers = [a for a in account_list if a.available_shares(ticker) >= 5]
            if not sellers:
                continue
            seller = random.choice(sellers)

            max_qty = _safe_qty(price, seller.available_shares(ticker) // 2)
            if max_qty < 1:
                continue
            qty = random.randint(1, min(max_qty, 20))
            cost = price * qty

            buyers = [
                a
                for a in account_list
                if a.account_id != seller.account_id and a.available_cash() >= cost
            ]
            if not buyers:
                continue
            buyer = random.choice(buyers)

            # Submit sell — should rest in the book
            sell_resp = await http.post(
                '/orders',
                json={
                    'account_id': seller.account_id,
                    'ticker': ticker,
                    'side': 'SELL',
                    'order_type': 'LIMIT',
                    'quantity': qty,
                    'price': price,
                },
            )
            sell_resp.raise_for_status()
            sell_data = sell_resp.json()
            if sell_data['status'] == 'REJECTED':
                continue
            sell_order_id = sell_data['order_id']
            # Reserve shares in local model
            seller.reserved_shares[ticker] = seller.reserved_shares.get(ticker, 0) + qty

            # Submit matching buy — should fill immediately
            buy_resp = await http.post(
                '/orders',
                json={
                    'account_id': buyer.account_id,
                    'ticker': ticker,
                    'side': 'BUY',
                    'order_type': 'LIMIT',
                    'quantity': qty,
                    'price': price,
                },
            )
            buy_resp.raise_for_status()
            buy_data = buy_resp.json()

            if buy_data['status'] == 'FILLED':
                trades_done += 1
                # Mirror clearing in local model
                buyer.cash_balance -= cost
                buyer.positions[ticker] = buyer.positions.get(ticker, 0) + qty
                seller.cash_balance += cost
                seller.positions[ticker] = max(0, seller.positions.get(ticker, 0) - qty)
                seller.reserved_shares[ticker] = max(
                    0, seller.reserved_shares.get(ticker, 0) - qty
                )
                _print_bar('trades', trades_done, 100)
            else:
                # Buy was rejected — release reservation and cancel resting sell
                seller.reserved_shares[ticker] = max(
                    0, seller.reserved_shares.get(ticker, 0) - qty
                )
                await http.delete(
                    f'/orders/{sell_order_id}', params={'account_id': seller.account_id}
                )

        print()  # newline after progress bar

        if trades_done < 100:
            print(
                f'  Warning: only {trades_done}/100 trades completed'
                f' after {attempts} attempts.'
            )
        else:
            print(f'  Done — 100 trades in {attempts} attempts.')

    print(f"""
Seed complete:
  instruments : {len(instrument_prices)}
  accounts    : {len(account_map)}
  trades      : {trades_done}
""")


if __name__ == '__main__':
    asyncio.run(seed())
