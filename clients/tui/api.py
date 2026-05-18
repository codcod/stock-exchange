"""
A synchronous HTTP client for the exchange gateway.

This client wraps every gateway endpoint in a plain Python method, so the
rest of the TUI application does not need to interact with `httpx` directly.
All methods are blocking and are intended to be called from a background
worker thread, not from the main UI thread.
"""

import typing as tp
from datetime import datetime

import httpx

from clients.tui.config import AppConfig
from clients.tui.models import (
    AccountSnapshot,
    DepthLevel,
    DepthSnapshot,
    OrderRow,
    QuoteRow,
    SubmitRequest,
    TradeRow,
)

_DATE_FMTS = ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S')


def _fmt_ts(raw: str) -> str:
    """Format an ISO timestamp into a more readable HH:MM:SS format."""
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(raw[:26], fmt).strftime('%H:%M:%S')
        except ValueError:
            continue
    return raw[:8]


class GatewayClient:
    """A blocking HTTP client for all gateway API endpoints."""

    def __init__(self, config: AppConfig) -> None:
        self._base = config.base_url
        self._headers = config.headers
        self._client = httpx.Client(timeout=5.0)

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_tickers(self) -> tp.List[str]:
        """Fetch the list of all tradeable tickers."""
        r = self._client.get(f'{self._base}/market-data/tickers', headers=self._headers)
        r.raise_for_status()
        return r.json()

    def get_quote(self, ticker: str) -> tp.Optional[QuoteRow]:
        """Fetch the latest top-of-book quote for a single ticker."""
        try:
            r = self._client.get(
                f'{self._base}/market-data/{ticker}/quote', headers=self._headers
            )
            r.raise_for_status()
            d = r.json()
            return QuoteRow(
                ticker=d['ticker'],
                bid=float(d.get('bid') or 0),
                ask=float(d.get('ask') or 0),
                last_price=float(d.get('last_price') or 0),
                volume_today=int(d.get('volume_today') or 0),
            )
        except Exception:
            return None

    def get_all_quotes(self) -> tp.List[QuoteRow]:
        """Fetch the latest quotes for all tradeable tickers."""
        tickers = self.get_tickers()
        rows = []
        for t in tickers:
            q = self.get_quote(t)
            if q:
                rows.append(q)
        return rows

    def get_depth(self, ticker: str) -> DepthSnapshot:
        """Fetch the current order book depth for a single ticker."""
        try:
            r = self._client.get(
                f'{self._base}/market-data/{ticker}/depth', headers=self._headers
            )
            r.raise_for_status()
            d = r.json()
            return DepthSnapshot(
                ticker=ticker,
                bids=[
                    DepthLevel(float(b['price']), int(b['quantity']))
                    for b in d.get('bids', [])
                ],
                asks=[
                    DepthLevel(float(a['price']), int(a['quantity']))
                    for a in d.get('asks', [])
                ],
                last_price=float(d['last_price']) if d.get('last_price') else None,
            )
        except Exception:
            return DepthSnapshot(ticker=ticker)

    def get_trades(self, ticker: str, limit: int = 30) -> tp.List[TradeRow]:
        """Fetch the most recent trades for a single ticker."""
        try:
            r = self._client.get(
                f'{self._base}/market-data/{ticker}/trades',
                params={'limit': limit},
                headers=self._headers,
            )
            r.raise_for_status()
            return [
                TradeRow(
                    ticker=t['ticker'],
                    price=float(t['price']),
                    quantity=int(t['quantity']),
                    executed_at_str=_fmt_ts(t['executed_at']),
                )
                for t in r.json()
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account(self, account_id: str) -> tp.Optional[AccountSnapshot]:
        """Fetch the current state of a single trading account."""
        try:
            r = self._client.get(
                f'{self._base}/accounts/{account_id}', headers=self._headers
            )
            r.raise_for_status()
            d = r.json()
            return AccountSnapshot(
                account_id=d['account_id'],
                cash_balance=float(d['cash_balance']),
                available_cash=float(d['available_cash']),
                reserved_cash=float(d['reserved_cash']),
                positions=d.get('positions', {}),
            )
        except Exception:
            return None

    def get_orders(self, account_id: str) -> tp.List[OrderRow]:
        """Fetch all orders for a single trading account."""
        try:
            r = self._client.get(
                f'{self._base}/accounts/{account_id}/orders', headers=self._headers
            )
            r.raise_for_status()
            rows = []
            for o in r.json():
                rows.append(
                    OrderRow(
                        order_id=o['order_id'],
                        ticker=o['ticker'],
                        side=o['side'],
                        quantity=int(o['quantity']),
                        filled_quantity=int(o['filled_quantity']),
                        price=float(o['price']) if o.get('price') is not None else None,
                        status=o['status'],
                        created_at_str=_fmt_ts(o['created_at']),
                    )
                )
            return rows
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def submit_order(self, account_id: str, req: SubmitRequest) -> dict:
        """Submit a new order to the exchange."""
        body: dict = {
            'account_id': account_id,
            'ticker': req.ticker,
            'side': req.side,
            'order_type': req.order_type,
            'quantity': req.quantity,
        }
        if req.price is not None:
            body['price'] = req.price
        r = self._client.post(f'{self._base}/orders', json=body, headers=self._headers)
        r.raise_for_status()
        return r.json()

    def cancel_order(self, order_id: str, account_id: str) -> bool:
        """Request cancellation of an active order."""
        try:
            r = self._client.delete(
                f'{self._base}/orders/{order_id}',
                params={'account_id': account_id},
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json().get('cancelled', False)
        except Exception:
            return False

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
