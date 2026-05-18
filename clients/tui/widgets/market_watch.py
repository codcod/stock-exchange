"""
This module defines the `MarketWatchWidget`, a scrollable ticker list that
displays live bid, ask, last price, and volume data.

When a user selects a row by pressing Enter, this widget posts a
`TickerSelected` message containing the selected ticker. The `Last` price
column is color-coded green (▲) or red (▼) to indicate the price
direction relative to the previous update.
"""

import typing as tp

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable

from clients.tui.models import QuoteRow


class MarketWatchWidget(Widget):
    """A widget that displays a live-updating list of tickers."""

    BORDER_TITLE = 'MARKET WATCH'

    class TickerSelected(Message):
        """Posted when the user selects a ticker from the list."""

        def __init__(self, ticker: str) -> None:
            super().__init__()
            self.ticker = ticker

    def compose(self) -> ComposeResult:
        """Compose the widget's layout."""
        yield DataTable(cursor_type='row', zebra_stripes=True, id='mw-table')

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        table = self.query_one('#mw-table', DataTable)
        table.add_column('Ticker', key='ticker')
        table.add_column('Bid', key='bid')
        table.add_column('Ask', key='ask')
        table.add_column('Last', key='last')
        table.add_column('Vol', key='vol')
        table.add_column('Chg', key='chg')

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle a row selection event."""
        if event.data_table.id == 'mw-table' and event.row_key.value:
            self.post_message(self.TickerSelected(str(event.row_key.value)))

    def update(self, quotes: tp.List[QuoteRow], selected: str) -> None:
        """Update the widget with new quote data."""
        table = self.query_one('#mw-table', DataTable)
        for q in quotes:
            bid = Text(f'{q.bid:.2f}', style='#00e676')
            ask = Text(f'{q.ask:.2f}', style='#ff4444')
            vol_str = f'{q.volume_today:,}'

            if q.direction == 'up':
                last = Text(f'{q.last_price:.2f}', style='bold #00e676')
                chg = Text('▲', style='#00e676')
            elif q.direction == 'down':
                last = Text(f'{q.last_price:.2f}', style='bold #ff4444')
                chg = Text('▼', style='#ff4444')
            else:
                last = Text(f'{q.last_price:.2f}', style='#e6edf3')
                chg = Text('─', style='#4a6080')

            if not self._row_exists(table, q.ticker):
                ticker_cell = Text(q.ticker, style='bold #e6edf3')
                table.add_row(ticker_cell, bid, ask, last, vol_str, chg, key=q.ticker)
            else:
                table.update_cell(q.ticker, 'bid', bid)
                table.update_cell(q.ticker, 'ask', ask)
                table.update_cell(q.ticker, 'last', last)
                table.update_cell(q.ticker, 'vol', vol_str)
                table.update_cell(q.ticker, 'chg', chg)

    def _row_exists(self, table: DataTable, key: str) -> bool:
        """Check if a row with the given key exists in the table."""
        try:
            table.get_row(key)
            return True
        except Exception:
            return False
