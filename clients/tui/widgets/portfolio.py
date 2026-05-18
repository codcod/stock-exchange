"""
This module defines the `PortfolioWidget`, which displays a summary of the
user's account cash and a table of their current positions.

The widget includes a header `Label` that shows the total and available cash
balances, formatted with Rich markup. The main content is a `DataTable` that
lists each ticker held, its last traded price, and its current market value.
Positions with a quantity of zero are not displayed.
"""

import typing as tp

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label

from clients.tui.models import AccountSnapshot, QuoteRow


class PortfolioWidget(Widget):
    """A widget that displays the user's cash and stock positions."""

    BORDER_TITLE = 'PORTFOLIO'

    def compose(self) -> ComposeResult:
        """Compose the widget's layout."""
        yield Label('', id='portfolio-stats')
        yield DataTable(id='pos-table', cursor_type='none', zebra_stripes=True)

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        table = self.query_one('#pos-table', DataTable)
        table.add_column('Ticker', key='ticker')
        table.add_column('Qty', key='qty')
        table.add_column('Last', key='last')
        table.add_column('Value', key='value')

    def update(
        self, account: tp.Optional[AccountSnapshot], quotes: tp.List[QuoteRow]
    ) -> None:
        """Update the widget with new account and quote data."""
        if account is None:
            return

        stats = self.query_one('#portfolio-stats', Label)
        stats.update(
            f'Cash: [bold #e6edf3]${account.cash_balance:,.2f}[/]  '
            f'Avail: [bold #00e676]${account.available_cash:,.2f}[/]'
        )

        price_map = {q.ticker: q.last_price for q in quotes}
        table = self.query_one('#pos-table', DataTable)
        table.clear()

        for ticker, qty in sorted(account.positions.items()):
            if qty == 0:
                continue
            last = price_map.get(ticker, 0.0)
            value = qty * last
            ticker_cell = Text(ticker, style='#e6edf3')
            qty_cell = Text(str(qty), style='#c9d1d9')
            last_cell = Text(f'{last:.2f}', style='#c9d1d9')
            value_cell = Text(f'${value:,.0f}', style='bold #00e676')
            table.add_row(ticker_cell, qty_cell, last_cell, value_cell)
