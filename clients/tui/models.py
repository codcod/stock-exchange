import typing as tp
from dataclasses import dataclass, field


@dataclass
class QuoteRow:
    ticker: str
    bid: float
    ask: float
    last_price: float
    volume_today: int
    prev_last: tp.Optional[float] = None
    direction: str = 'flat'  # 'up' | 'down' | 'flat'


@dataclass
class DepthLevel:
    price: float
    qty: int


@dataclass
class DepthSnapshot:
    ticker: str
    bids: tp.List[DepthLevel] = field(default_factory=list)
    asks: tp.List[DepthLevel] = field(default_factory=list)
    last_price: tp.Optional[float] = None

    @property
    def spread(self) -> tp.Optional[float]:
        if self.bids and self.asks:
            return round(self.asks[0].price - self.bids[0].price, 4)
        return None


@dataclass
class TradeRow:
    ticker: str
    price: float
    quantity: int
    executed_at_str: str


@dataclass
class OrderRow:
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
        return self.status in ('OPEN', 'PARTIALLY_FILLED')

    @property
    def price_str(self) -> str:
        return f'{self.price:.2f}' if self.price is not None else 'MKT'


@dataclass
class PositionRow:
    ticker: str
    quantity: int
    last_price: float

    @property
    def market_value(self) -> float:
        return self.quantity * self.last_price


@dataclass
class AccountSnapshot:
    account_id: str
    cash_balance: float
    available_cash: float
    reserved_cash: float
    positions: tp.Dict[str, int] = field(default_factory=dict)


@dataclass
class SubmitRequest:
    ticker: str
    side: str
    order_type: str
    quantity: int
    price: tp.Optional[float]
