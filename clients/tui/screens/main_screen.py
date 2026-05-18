"""
This module defines the main trading screen for the TUI application.

The `MainScreen` class arranges all the primary trading widgets into a
three-row layout:
- Row 1: `MarketWatchWidget`, `OrderBookWidget`, `PortfolioWidget`
- Row 2: A full-width, horizontal `OrderEntryWidget`
- Row 3: `OpenOrdersWidget`, `TradeTapeWidget`

A `TabbedContent` widget is used to provide a secondary tab for the
`OrderHistoryWidget`.
"""

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
    """The main screen of the application, containing all trading widgets."""

    def compose(self) -> ComposeResult:
        """Compose the layout of the main screen."""
        yield Header()
        with TabbedContent(initial='main-tab'):
            with TabPane('Main', id='main-tab'):
                # Row 1: Market data panels that fill the available vertical space.
                with Horizontal(id='top-row'):
                    yield MarketWatchWidget(id='market-watch')
                    yield OrderBookWidget(id='order-book')
                    yield PortfolioWidget(id='portfolio')
                # Row 2: A full-width, horizontal order entry ticket.
                yield OrderEntryWidget(id='order-entry')
                # Row 3: Open orders and the live trade tape.
                with Horizontal(id='bottom-row'):
                    yield OpenOrdersWidget(id='open-orders')
                    yield TradeTapeWidget(id='trade-tape')
            with TabPane('Order History', id='history-tab'):
                yield OrderHistoryWidget(id='order-history')
        yield Footer()
