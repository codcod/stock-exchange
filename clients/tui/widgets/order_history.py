import typing as tp

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable

from clients.tui.models import OrderRow

_STATUS_STYLE = {
    'OPEN': '#00e676',
    'PARTIALLY_FILLED': '#ff8f00',
    'FILLED': '#00e676',
    'CANCELLED': '#4a6080',
    'REJECTED': '#ff4444',
    'PENDING': '#c9d1d9',
}


class OrderHistoryWidget(Widget):
    BORDER_TITLE = 'ORDER HISTORY'

    def compose(self) -> ComposeResult:
        yield DataTable(id='oh-table', cursor_type='row', zebra_stripes=True)

    def on_mount(self) -> None:
        table = self.query_one('#oh-table', DataTable)
        table.add_column('Time', key='time')
        table.add_column('Ticker', key='ticker')
        table.add_column('Side', key='side')
        table.add_column('Qty', key='qty')
        table.add_column('Filled', key='filled')
        table.add_column('Price', key='price')
        table.add_column('Status', key='status')

    def update(self, orders: tp.List[OrderRow]) -> None:
        self.border_title = f'ORDER HISTORY ({len(orders)})'
        table = self.query_one('#oh-table', DataTable)
        table.clear()

        for o in reversed(orders):
            style = _STATUS_STYLE.get(o.status, '#c9d1d9')
            side_style = '#00e676' if o.side == 'BUY' else '#ff4444'

            time_cell = Text(o.created_at_str, style='#4a6080')
            ticker_cell = Text(o.ticker, style='#e6edf3')
            side_cell = Text(o.side, style=f'bold {side_style}')
            qty_cell = Text(str(o.quantity), style='#c9d1d9')
            filled_cell = Text(str(o.filled_quantity), style='#4a6080')
            price_cell = Text(o.price_str, style='#c9d1d9')
            status_cell = Text(o.status, style=style)

            table.add_row(
                time_cell,
                ticker_cell,
                side_cell,
                qty_cell,
                filled_cell,
                price_cell,
                status_cell,
                key=o.order_id,
            )
