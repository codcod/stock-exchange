"""
clients/tui/widgets/order_entry.py

OrderEntryWidget — full-width horizontal order ticket.

Fields laid out in a single row: Ticker | Side | Type | Qty | Price | Notional | Submit.
Selecting MARKET order type disables the Price field.
Posts OrderSubmitRequested to the App on submit (after local validation).
Notional value updates live as Qty or Price changes.
"""

import typing as tp

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.validation import Number
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select


class OrderEntryWidget(Widget):
    BORDER_TITLE = 'ORDER ENTRY'

    class OrderSubmitRequested(Message):
        def __init__(
            self,
            ticker: str,
            side: str,
            order_type: str,
            quantity: int,
            price: tp.Optional[float],
        ) -> None:
            super().__init__()
            self.ticker = ticker
            self.side = side
            self.order_type = order_type
            self.quantity = quantity
            self.price = price

    _SIDES = [('BUY', 'BUY'), ('SELL', 'SELL')]
    _TYPES = [('LIMIT', 'LIMIT'), ('MARKET', 'MARKET')]

    def compose(self) -> ComposeResult:
        with Horizontal(id='oe-fields'):
            with Vertical(classes='oe-field oe-ticker'):
                yield Label('Ticker')
                yield Input(placeholder='AAPL', id='oe-ticker')
            with Vertical(classes='oe-field oe-side'):
                yield Label('Side')
                yield Select(self._SIDES, id='oe-side', value='BUY', allow_blank=False)
            with Vertical(classes='oe-field oe-type'):
                yield Label('Type')
                yield Select(
                    self._TYPES, id='oe-type', value='LIMIT', allow_blank=False
                )
            with Vertical(classes='oe-field oe-qty'):
                yield Label('Qty')
                yield Input(
                    placeholder='100',
                    id='oe-qty',
                    validators=[Number(minimum=1)],
                )
            with Vertical(classes='oe-field oe-price'):
                yield Label('Price')
                yield Input(
                    placeholder='0.00',
                    id='oe-price',
                    validators=[Number(minimum=0.0001)],
                )
            with Vertical(classes='oe-field oe-info'):
                yield Label('Notional', id='notional-title')
                yield Label('—', id='notional-label')
            with Vertical(classes='oe-field oe-action'):
                yield Label(' ')
                yield Button('▶  SUBMIT ORDER', id='submit-btn', variant='primary')

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in ('oe-qty', 'oe-price'):
            self._update_notional()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == 'oe-type':
            price_input = self.query_one('#oe-price', Input)
            price_input.disabled = event.value == 'MARKET'
            self._update_notional()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != 'submit-btn':
            return

        ticker = self.query_one('#oe-ticker', Input).value.strip().upper()
        side_sel = self.query_one('#oe-side', Select)
        type_sel = self.query_one('#oe-type', Select)
        qty_inp = self.query_one('#oe-qty', Input)
        price_inp = self.query_one('#oe-price', Input)

        if not ticker:
            self.app.post_status('Error: ticker required')
            return
        if side_sel.value is Select.NULL or type_sel.value is Select.NULL:
            self.app.post_status('Error: side and type required')
            return
        if not qty_inp.is_valid or not qty_inp.value:
            self.app.post_status('Error: valid quantity required')
            return

        order_type = str(type_sel.value)
        price: tp.Optional[float] = None
        if order_type == 'LIMIT':
            if not price_inp.is_valid or not price_inp.value:
                self.app.post_status('Error: price required for LIMIT order')
                return
            price = float(price_inp.value)

        self.post_message(
            self.OrderSubmitRequested(
                ticker=ticker,
                side=str(side_sel.value),
                order_type=order_type,
                quantity=int(qty_inp.value),
                price=price,
            )
        )

    def set_ticker(self, ticker: str) -> None:
        self.query_one('#oe-ticker', Input).value = ticker
        self._update_notional()

    def set_side(self, side: str) -> None:
        self.query_one('#oe-side', Select).value = side

    def _update_notional(self) -> None:
        label = self.query_one('#notional-label', Label)
        try:
            qty = float(self.query_one('#oe-qty', Input).value or '0')
            price_inp = self.query_one('#oe-price', Input)
            if not price_inp.disabled and price_inp.value:
                notional = qty * float(price_inp.value)
                label.update(f'${notional:,.2f}')
            else:
                label.update('MARKET')
        except (ValueError, TypeError):
            label.update('—')
