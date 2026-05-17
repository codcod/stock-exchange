import typing as tp

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable

from clients.tui.models import TradeRow

_MAX_ROWS = 50


class TradeTapeWidget(Widget):
    BORDER_TITLE = 'RECENT TRADES'

    def compose(self) -> ComposeResult:
        yield DataTable(id='tape-table', cursor_type='none', zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one('#tape-table', DataTable)
        table.add_column('Time', key='time')
        table.add_column('Price', key='price')
        table.add_column('Qty', key='qty')

    def update(self, trades: tp.List[TradeRow], ticker: str) -> None:
        self.border_title = f'RECENT TRADES — {ticker}' if ticker else 'RECENT TRADES'
        table = self.query_one('#tape-table', DataTable)
        table.clear()

        for trade in trades[:_MAX_ROWS]:
            time_cell = Text(trade.executed_at_str, style='#4a6080')
            price_cell = Text(f'{trade.price:.2f}', style='bold #e6edf3')
            qty_cell = Text(str(trade.quantity), style='#c9d1d9')
            table.add_row(time_cell, price_cell, qty_cell)
