"""
This module defines the `OrderBookWidget`, which displays the bid and ask
depth for the currently selected ticker.

It renders two `DataTable` widgets: one for asks (descending from the top)
and one for bids (ascending from the bottom). A `Label` in the middle
displays the current spread or the last traded price. The border title is
updated to reflect the currently selected ticker.
"""

import typing as tp

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label

from clients.tui.models import DepthSnapshot

_DEPTH_LEVELS = 6


class OrderBookWidget(Widget):
    """A widget that displays the order book for a single ticker."""

    BORDER_TITLE = 'ORDER BOOK'

    def compose(self) -> ComposeResult:
        """Compose the widget's layout."""
        yield DataTable(
            id='ob-asks', show_header=False, cursor_type='none', zebra_stripes=False
        )
        yield Label('── no data ──', id='ob-spread')
        yield DataTable(
            id='ob-bids', show_header=False, cursor_type='none', zebra_stripes=False
        )

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        for table_id in ('#ob-asks', '#ob-bids'):
            t = self.query_one(table_id, DataTable)
            t.add_column('Price', key='price')
            t.add_column('Qty', key='qty')
            t.add_column('Side', key='side')

    def update(self, depth: DepthSnapshot) -> None:
        """Update the widget with new order book depth data."""
        self.border_title = f'ORDER BOOK: {depth.ticker}'

        asks_table = self.query_one('#ob-asks', DataTable)
        bids_table = self.query_one('#ob-bids', DataTable)
        spread_label = self.query_one('#ob-spread', Label)

        # Show asks descending so the best ask is nearest the spread.
        asks = list(reversed(depth.asks[:_DEPTH_LEVELS]))
        bids = depth.bids[:_DEPTH_LEVELS]

        self._fill_table(asks_table, asks, side='ASK')
        self._fill_table(bids_table, bids, side='BID')

        spread = depth.spread
        if spread is not None:
            spread_label.update(f'── spread {spread:.2f} ──')
        elif depth.last_price:
            spread_label.update(f'── last {depth.last_price:.2f} ──')
        else:
            spread_label.update('── empty ──')

    def _fill_table(self, table: DataTable, levels: tp.List, side: str) -> None:
        """Fill a table with order book depth data."""
        table.clear()
        color = '#ff4444' if side == 'ASK' else '#00e676'
        for lvl in levels:
            price_cell = Text(f'{lvl.price:.2f}', style=f'bold {color}')
            qty_cell = Text(str(lvl.qty), style='#c9d1d9')
            side_cell = Text(side, style=f'dim {color}')
            table.add_row(price_cell, qty_cell, side_cell)
