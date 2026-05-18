"""
This module defines the `TradeTapeWidget`, which displays a time-and-sales
tape for the currently selected ticker.

The widget shows the most recent trades, with the newest trades appearing
at the top, up to a maximum of `_MAX_ROWS` entries. The table is cleared
and reloaded on every update, rather than performing a diff.
"""

import typing as tp

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable

from clients.tui.models import TradeRow

_MAX_ROWS = 50


class TradeTapeWidget(Widget):
    """A widget that displays a time-and-sales tape for a single ticker."""

    BORDER_TITLE = 'RECENT TRADES'

    def compose(self) -> ComposeResult:
        """Compose the widget's layout."""
        yield DataTable(id='tape-table', cursor_type='none', zebra_stripes=True)

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        table = self.query_one('#tape-table', DataTable)
        table.add_column('Time', key='time')
        table.add_column('Price', key='price')
        table.add_column('Qty', key='qty')

    def update(self, trades: tp.List[TradeRow], ticker: str) -> None:
        """Update the widget with a new list of trades."""
        self.border_title = f'RECENT TRADES — {ticker}' if ticker else 'RECENT TRADES'
        table = self.query_one('#tape-table', DataTable)
        table.clear()

        for trade in trades[:_MAX_ROWS]:
            time_cell = Text(trade.executed_at_str, style='#4a6080')
            price_cell = Text(f'{trade.price:.2f}', style='bold #e6edf3')
            qty_cell = Text(str(trade.quantity), style='#c9d1d9')
            table.add_row(time_cell, price_cell, qty_cell)
