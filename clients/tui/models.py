"""
Presentation-layer dataclasses for the TUI.

These models are distinct from the core domain models found in the `shared/`
directory. They are specifically designed for the terminal UI, containing only
the data required by the widgets and adding display-oriented properties like
`price_str`, `is_active`, and `direction`.
"""

import typing as tp
from dataclasses import dataclass, field


@dataclass
class QuoteRow:
    """Represents a single row in the market watch widget."""

    ticker: str
    bid: float
    ask: float
    last_price: float
    volume_today: int
    prev_last: tp.Optional[float] = None
    direction: str = 'flat'  # 'up' | 'down' | 'flat'


@dataclass
class DepthLevel:
    """Represents a single price level in the order book."""

    price: float
    qty: int


@dataclass
class DepthSnapshot:
    """Represents the state of the order book for a single ticker."""

    ticker: str
    bids: tp.List[DepthLevel] = field(default_factory=list)
    asks: tp.List[DepthLevel] = field(default_factory=list)
    last_price: tp.Optional[float] = None

    @property
    def spread(self) -> tp.Optional[float]:
        """The difference between the best ask and the best bid."""
        if self.bids and self.asks:
            return round(self.asks[0].price - self.bids[0].price, 4)
        return None


@dataclass
class TradeRow:
    """Represents a single row in the trade tape widget."""

    ticker: str
    price: float
    quantity: int
    executed_at_str: str


@dataclass
class OrderRow:
    """Represents a single row in the open orders or order history widgets."""

    order_id: str
    ticker: str
    side: str
    quantity: int
    filled_quantity: int
    price: tp.Optional[float]
    status: str
    created_at_str: str

    @property
    def is_active(self) -> bool:
        """Return True if the order is still active (not filled or cancelled)."""
        return self.status in ('OPEN', 'PARTIALLY_FILLED')

    @property
    def price_str(self) -> str:
        """Return a display-friendly string for the order price."""
        return f'{self.price:.2f}' if self.price is not None else 'MKT'


@dataclass
class PositionRow:
    """Represents a single row in the portfolio widget."""

    ticker: str
    quantity: int
    last_price: float

    @property
    def market_value(self) -> float:
        """The current market value of this position."""
        return self.quantity * self.last_price


@dataclass
class AccountSnapshot:
    """Represents the state of a single trading account."""

    account_id: str
    cash_balance: float
    available_cash: float
    reserved_cash: float
    positions: tp.Dict[str, int] = field(default_factory=dict)


@dataclass
class SubmitRequest:
    """A request to submit a new order."""

    ticker: str
    side: str
    order_type: str
    quantity: int
    price: tp.Optional[float]
