"""
clients/tui/widgets/portfolio.py

PortfolioWidget — account cash summary and position table.

The cash header (Label) shows total and available cash in Rich markup.
The positions DataTable shows each held ticker with its last price and
current market value.  Zero-quantity positions are omitted.
"""

import typing as tp

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label

from clients.tui.models import AccountSnapshot, QuoteRow


class PortfolioWidget(Widget):
    BORDER_TITLE = 'PORTFOLIO'

    def compose(self) -> ComposeResult:
        yield Label('', id='portfolio-stats')
        yield DataTable(id='pos-table', cursor_type='none', zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one('#pos-table', DataTable)
        table.add_column('Ticker', key='ticker')
        table.add_column('Qty', key='qty')
        table.add_column('Last', key='last')
        table.add_column('Value', key='value')

    def update(
        self, account: tp.Optional[AccountSnapshot], quotes: tp.List[QuoteRow]
    ) -> None:
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
