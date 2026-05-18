"""
This module defines the `OpenOrdersWidget`, which displays a table of all
active orders (i.e., those with `OPEN` or `PARTIALLY_FILLED` statuses).

Pressing the 'd' key on a selected row posts a `CancelRequested` message
to the main application, which then dispatches a worker to cancel the order.
The status values in the table are color-coded for readability.
"""

import typing as tp

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable

from clients.tui.models import OrderRow

_STATUS_STYLE = {
    'OPEN': '#00e676',
    'PARTIALLY_FILLED': '#ff8f00',
    'FILLED': '#4a6080',
    'CANCELLED': '#4a6080',
    'REJECTED': '#ff4444',
    'PENDING': '#c9d1d9',
}


class OpenOrdersWidget(Widget):
    """A widget that displays a list of all open orders."""

    BORDER_TITLE = 'OPEN ORDERS  [d=cancel]'

    BINDINGS = [
        Binding('d', 'cancel_selected', 'Cancel order', show=False),
    ]

    class CancelRequested(Message):
        """Posted when the user requests to cancel an order."""

        def __init__(self, order_id: str) -> None:
            super().__init__()
            self.order_id = order_id

    def compose(self) -> ComposeResult:
        """Compose the widget's layout."""
        yield DataTable(id='oo-table', cursor_type='row', zebra_stripes=True)

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        table = self.query_one('#oo-table', DataTable)
        table.add_column('Ticker', key='ticker')
        table.add_column('Side', key='side')
        table.add_column('Qty', key='qty')
        table.add_column('Filled', key='filled')
        table.add_column('Price', key='price')
        table.add_column('Status', key='status')

    def action_cancel_selected(self) -> None:
        """Handle the 'd' key binding to cancel the selected order."""
        table = self.query_one('#oo-table', DataTable)
        if table.cursor_row >= 0:
            try:
                cursor_key = table.coordinate_to_cell_key(
                    table.cursor_coordinate
                ).row_key.value
                if cursor_key:
                    self.post_message(self.CancelRequested(str(cursor_key)))
            except Exception:
                pass

    def update(self, orders: tp.List[OrderRow]) -> None:
        """Update the widget with a new list of orders."""
        active = [o for o in orders if o.is_active]
        self.border_title = f'OPEN ORDERS ({len(active)})  [d=cancel]'

        table = self.query_one('#oo-table', DataTable)
        table.clear()

        for o in active:
            style = _STATUS_STYLE.get(o.status, '#c9d1d9')
            side_style = '#00e676' if o.side == 'BUY' else '#ff4444'

            ticker_cell = Text(o.ticker, style='#e6edf3')
            side_cell = Text(o.side, style=f'bold {side_style}')
            qty_cell = Text(str(o.quantity), style='#c9d1d9')
            filled_cell = Text(str(o.filled_quantity), style='#4a6080')
            price_cell = Text(o.price_str, style='#c9d1d9')
            status_cell = Text(o.status, style=style)

            table.add_row(
                ticker_cell,
                side_cell,
                qty_cell,
                filled_cell,
                price_cell,
                status_cell,
                key=o.order_id,
            )
