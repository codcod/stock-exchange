"""
The root Textual application for the exchange terminal.

This `ExchangeApp` class owns all shared reactive state (like the currently
selected ticker) and manages all background workers that poll the gateway
for fresh data.

Widgets do not call the API client directly. Instead, they post custom
`Message` objects, which are handled by the `App`. The `App` then dispatches
background workers and pushes the results back to the appropriate widgets
via direct `update()` calls on the UI thread.

This architecture centralizes data fetching and state management, keeping
the individual widgets simple and focused on rendering.

Polling timers:
- `_fetch_market`:  every `EXCHANGE_POLL_MARKET_MS` (default: 2s)
- `_fetch_account`: every `EXCHANGE_POLL_ORDERS_MS` (default: 3s)
"""

import typing as tp
from datetime import datetime

from textual import work
from textual.app import App
from textual.binding import Binding
from textual.reactive import reactive

from clients.tui.api import GatewayClient
from clients.tui.config import AppConfig
from clients.tui.models import (
    AccountSnapshot,
    DepthSnapshot,
    OrderRow,
    QuoteRow,
    SubmitRequest,
    TradeRow,
)
from clients.tui.screens.main_screen import MainScreen
from clients.tui.widgets.market_watch import MarketWatchWidget
from clients.tui.widgets.open_orders import OpenOrdersWidget
from clients.tui.widgets.order_book import OrderBookWidget
from clients.tui.widgets.order_entry import OrderEntryWidget
from clients.tui.widgets.order_history import OrderHistoryWidget
from clients.tui.widgets.portfolio import PortfolioWidget
from clients.tui.widgets.trade_tape import TradeTapeWidget


class ExchangeApp(App):
    """The main Textual application class."""

    CSS_PATH = 'tui.tcss'
    TITLE = 'Exchange Terminal'
    BINDINGS = [
        Binding('q', 'quit', 'Quit'),
        Binding('b', 'focus_buy', 'Buy', show=False),
        Binding('s', 'focus_sell', 'Sell', show=False),
        Binding('ctrl+r', 'force_refresh', 'Refresh'),
        Binding('1', 'switch_main', 'Main', show=False),
        Binding('2', 'switch_history', 'History', show=False),
        Binding('f1', 'show_help', 'Help'),
    ]

    # The currently selected ticker, which drives the order book and trade tape.
    selected_ticker: reactive[str] = reactive('', layout=False)

    # A message to be displayed in the status bar.
    status_message: reactive[str] = reactive('')

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._api = GatewayClient(config)
        self._last_quotes: tp.List[QuoteRow] = []
        self._last_account: tp.Optional[AccountSnapshot] = None
        self._history_tab_active = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Called when the app is first mounted."""
        self.push_screen(MainScreen())
        self.set_interval(self._config.poll_market_ms / 1000.0, self._tick_market)
        self.set_interval(self._config.poll_orders_ms / 1000.0, self._tick_account)
        # Perform an immediate first load to populate the UI.
        self._fetch_market()
        self._fetch_account()

    def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        self._api.close()

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    def _tick_market(self) -> None:
        """Called periodically to refresh market data."""
        self._fetch_market()

    def _tick_account(self) -> None:
        """Called periodically to refresh account data."""
        self._fetch_account()

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    @work(thread=True)
    def _fetch_market(self) -> None:
        """Fetch all market data in a background thread."""
        try:
            quotes = self._api.get_all_quotes()
            self._apply_directions(quotes)
            depth = (
                self._api.get_depth(self.selected_ticker)
                if self.selected_ticker
                else DepthSnapshot(ticker='')
            )
            trades = (
                self._api.get_trades(self.selected_ticker)
                if self.selected_ticker
                else []
            )
            self.call_from_thread(self._on_market_fetched, quotes, depth, trades)
        except Exception as exc:
            self.call_from_thread(self.post_status, f'Market data error: {exc}')

    @work(thread=True)
    def _fetch_account(self) -> None:
        """Fetch all account data in a background thread."""
        try:
            account = self._api.get_account(self._config.account_id)
            orders = self._api.get_orders(self._config.account_id)
            self.call_from_thread(self._on_account_fetched, account, orders)
        except Exception as exc:
            self.call_from_thread(self.post_status, f'Account error: {exc}')

    @work(thread=True)
    def _do_submit(self, req: SubmitRequest) -> None:
        """Submit a new order in a background thread."""
        try:
            result = self._api.submit_order(self._config.account_id, req)
            status = result.get('status', '?')
            oid = result.get('order_id', '')[:8]
            reject = result.get('reject_reason', '')
            if status == 'REJECTED':
                msg = f'REJECTED {req.ticker} {req.side}: {reject}'
            else:
                price_str = f'@{req.price:.2f}' if req.price else '@MKT'
                msg = f'Order {req.ticker} {req.side} {req.quantity}{price_str} → {status} ({oid}…)'  # noqa: E501
            self.call_from_thread(self.post_status, msg)
            self.call_from_thread(self._fetch_account)
        except Exception as exc:
            self.call_from_thread(self.post_status, f'Submit failed: {exc}')

    @work(thread=True)
    def _do_cancel(self, order_id: str) -> None:
        """Cancel an order in a background thread."""
        try:
            ok = self._api.cancel_order(order_id, self._config.account_id)
            msg = (
                f'Cancelled {order_id[:8]}…'
                if ok
                else f'Cancel failed for {order_id[:8]}…'
            )
            self.call_from_thread(self.post_status, msg)
            self.call_from_thread(self._fetch_account)
        except Exception as exc:
            self.call_from_thread(self.post_status, f'Cancel error: {exc}')

    # ------------------------------------------------------------------
    # Data callbacks (UI thread)
    # ------------------------------------------------------------------

    def _on_market_fetched(
        self,
        quotes: tp.List[QuoteRow],
        depth: DepthSnapshot,
        trades: tp.List[TradeRow],
    ) -> None:
        """
        Callback executed on the UI thread after market data has been fetched.
        Updates all relevant widgets with the new data.
        """
        self._last_quotes = quotes
        try:
            self.screen.query_one(MarketWatchWidget).update(
                quotes, self.selected_ticker
            )
        except Exception:
            pass
        if depth.ticker:
            try:
                self.screen.query_one(OrderBookWidget).update(depth)
            except Exception:
                pass
            try:
                self.screen.query_one(TradeTapeWidget).update(trades, depth.ticker)
            except Exception:
                pass
        self._refresh_portfolio()

    def _on_account_fetched(
        self,
        account: tp.Optional[AccountSnapshot],
        orders: tp.List[OrderRow],
    ) -> None:
        """
        Callback executed on the UI thread after account data has been fetched.
        Updates all relevant widgets with the new data.
        """
        self._last_account = account
        try:
            self.screen.query_one(OpenOrdersWidget).update(orders)
        except Exception:
            pass
        if self._history_tab_active:
            try:
                self.screen.query_one(OrderHistoryWidget).update(orders)
            except Exception:
                pass
        self._refresh_portfolio()

    def _refresh_portfolio(self) -> None:
        """
        Recalculate and update the portfolio display. This is called after
        either market or account data has been updated.
        """
        if self._last_account is not None:
            try:
                self.screen.query_one(PortfolioWidget).update(
                    self._last_account, self._last_quotes
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Message handlers (from widgets)
    # ------------------------------------------------------------------

    def on_market_watch_widget_ticker_selected(
        self, event: MarketWatchWidget.TickerSelected
    ) -> None:
        """Handle a ticker selection event from the market watch widget."""
        self.selected_ticker = event.ticker
        self.sub_title = event.ticker
        self._fetch_market()

    def on_order_entry_widget_order_submit_requested(
        self, event: OrderEntryWidget.OrderSubmitRequested
    ) -> None:
        """Handle an order submission request from the order entry widget."""
        self._do_submit(
            SubmitRequest(
                event.ticker, event.side, event.order_type, event.quantity, event.price
            )
        )

    def on_open_orders_widget_cancel_requested(
        self, event: OpenOrdersWidget.CancelRequested
    ) -> None:
        """Handle an order cancellation request from the open orders widget."""
        self._do_cancel(event.order_id)

    def on_tabbed_content_tab_activated(self, event) -> None:
        """
        Keep track of whether the history tab is active, so we can avoid
        updating it when it's not visible.
        """
        self._history_tab_active = getattr(event.tab, 'id', '') == 'history-tab--tab'
        if self._history_tab_active:
            self._fetch_account()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_focus_buy(self) -> None:
        """Focus the order entry widget and set the side to BUY."""
        try:
            oe = self.screen.query_one(OrderEntryWidget)
            oe.set_side('BUY')
            oe.focus()
        except Exception:
            pass

    def action_focus_sell(self) -> None:
        """Focus the order entry widget and set the side to SELL."""
        try:
            oe = self.screen.query_one(OrderEntryWidget)
            oe.set_side('SELL')
            oe.focus()
        except Exception:
            pass

    def action_force_refresh(self) -> None:
        """Force an immediate refresh of all data."""
        self._fetch_market()
        self._fetch_account()

    def action_switch_main(self) -> None:
        """Switch to the main tab."""
        try:
            self.screen.query_one('TabbedContent').active = 'main-tab'
        except Exception:
            pass

    def action_switch_history(self) -> None:
        """Switch to the history tab."""
        try:
            self.screen.query_one('TabbedContent').active = 'history-tab'
        except Exception:
            pass

    def action_show_help(self) -> None:
        """Show the help screen."""
        from clients.tui.screens.help_screen import HelpScreen

        self.push_screen(HelpScreen())

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def post_status(self, msg: str) -> None:
        """Display a message in the status bar for a few seconds."""
        ts = datetime.now().strftime('%H:%M:%S')
        self.sub_title = f'{msg}  {ts}'
        self.set_timer(8.0, self._clear_status)

    def _clear_status(self) -> None:
        """Clear the status bar message."""
        self.sub_title = self.selected_ticker or ''

    # ------------------------------------------------------------------
    # Direction tracking
    # ------------------------------------------------------------------

    def _apply_directions(self, quotes: tp.List[QuoteRow]) -> None:
        """
        Compare the latest quotes with the previous ones to determine the
        price direction (up, down, or flat) for the market watch display.
        """
        prev = {q.ticker: q.last_price for q in self._last_quotes}
        for q in quotes:
            old = prev.get(q.ticker)
            if old is None:
                q.direction = 'flat'
            elif q.last_price > old:
                q.direction = 'up'
            elif q.last_price < old:
                q.direction = 'down'
            else:
                q.direction = 'flat'
            q.prev_last = old
