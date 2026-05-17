from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, TabbedContent, TabPane

from clients.tui.widgets.market_watch import MarketWatchWidget
from clients.tui.widgets.open_orders import OpenOrdersWidget
from clients.tui.widgets.order_book import OrderBookWidget
from clients.tui.widgets.order_entry import OrderEntryWidget
from clients.tui.widgets.order_history import OrderHistoryWidget
from clients.tui.widgets.portfolio import PortfolioWidget
from clients.tui.widgets.trade_tape import TradeTapeWidget


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial='main-tab'):
            with TabPane('Main', id='main-tab'):
                # Row 1: market data panels fill available vertical space
                with Horizontal(id='top-row'):
                    yield MarketWatchWidget(id='market-watch')
                    yield OrderBookWidget(id='order-book')
                    yield PortfolioWidget(id='portfolio')
                # Row 2: full-width horizontal order ticket
                yield OrderEntryWidget(id='order-entry')
                # Row 3: open orders + trade tape
                with Horizontal(id='bottom-row'):
                    yield OpenOrdersWidget(id='open-orders')
                    yield TradeTapeWidget(id='trade-tape')
            with TabPane('Order History', id='history-tab'):
                yield OrderHistoryWidget(id='order-history')
        yield Footer()
