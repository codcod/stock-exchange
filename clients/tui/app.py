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

    selected_ticker: reactive[str] = reactive('', layout=False)
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
        self.push_screen(MainScreen())
        self.set_interval(self._config.poll_market_ms / 1000.0, self._tick_market)
        self.set_interval(self._config.poll_orders_ms / 1000.0, self._tick_account)
        # immediate first load
        self._fetch_market()
        self._fetch_account()

    def on_unmount(self) -> None:
        self._api.close()

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------

    def _tick_market(self) -> None:
        self._fetch_market()

    def _tick_account(self) -> None:
        self._fetch_account()

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    @work(thread=True)
    def _fetch_market(self) -> None:
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
        try:
            account = self._api.get_account(self._config.account_id)
            orders = self._api.get_orders(self._config.account_id)
            self.call_from_thread(self._on_account_fetched, account, orders)
        except Exception as exc:
            self.call_from_thread(self.post_status, f'Account error: {exc}')

    @work(thread=True)
    def _do_submit(self, req: SubmitRequest) -> None:
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
        self.selected_ticker = event.ticker
        self.sub_title = event.ticker
        self._fetch_market()

    def on_order_entry_widget_order_submit_requested(
        self, event: OrderEntryWidget.OrderSubmitRequested
    ) -> None:
        self._do_submit(
            SubmitRequest(
                event.ticker, event.side, event.order_type, event.quantity, event.price
            )
        )

    def on_open_orders_widget_cancel_requested(
        self, event: OpenOrdersWidget.CancelRequested
    ) -> None:
        self._do_cancel(event.order_id)

    def on_tabbed_content_tab_activated(self, event) -> None:
        self._history_tab_active = getattr(event.tab, 'id', '') == 'history-tab--tab'
        if self._history_tab_active:
            self._fetch_account()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_focus_buy(self) -> None:
        try:
            oe = self.screen.query_one(OrderEntryWidget)
            oe.set_side('BUY')
            oe.focus()
        except Exception:
            pass

    def action_focus_sell(self) -> None:
        try:
            oe = self.screen.query_one(OrderEntryWidget)
            oe.set_side('SELL')
            oe.focus()
        except Exception:
            pass

    def action_force_refresh(self) -> None:
        self._fetch_market()
        self._fetch_account()

    def action_switch_main(self) -> None:
        try:
            self.screen.query_one('TabbedContent').active = 'main-tab'
        except Exception:
            pass

    def action_switch_history(self) -> None:
        try:
            self.screen.query_one('TabbedContent').active = 'history-tab'
        except Exception:
            pass

    def action_show_help(self) -> None:
        from clients.tui.screens.help_screen import HelpScreen

        self.push_screen(HelpScreen())

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def post_status(self, msg: str) -> None:
        ts = datetime.now().strftime('%H:%M:%S')
        self.sub_title = f'{msg}  {ts}'
        self.set_timer(8.0, self._clear_status)

    def _clear_status(self) -> None:
        self.sub_title = self.selected_ticker or ''

    # ------------------------------------------------------------------
    # Direction tracking
    # ------------------------------------------------------------------

    def _apply_directions(self, quotes: tp.List[QuoteRow]) -> None:
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
