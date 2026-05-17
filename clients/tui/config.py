"""
clients/tui/config.py

AppConfig dataclass and load_config() factory.

All values are read from environment variables with sensible defaults so the
app works out of the box against a local exchange stack.

Environment variables:
  EXCHANGE_BASE_URL       — gateway base URL     (default: http://localhost:8000)
  EXCHANGE_ACCOUNT_ID     — account to trade as  (default: trader-0)
  EXCHANGE_API_KEY        — X-API-Key header      (default: empty / no auth)
  EXCHANGE_POLL_MARKET_MS — market data interval  (default: 2000 ms)
  EXCHANGE_POLL_ORDERS_MS — account/orders interval (default: 3000 ms)
"""

import os
import typing as tp
from dataclasses import dataclass


@dataclass
class AppConfig:
    base_url: str
    account_id: str
    api_key: str
    poll_market_ms: int
    poll_orders_ms: int

    @property
    def headers(self) -> tp.Dict[str, str]:
        return {'X-Api-Key': self.api_key} if self.api_key else {}


def load_config() -> AppConfig:
    return AppConfig(
        base_url=os.getenv('EXCHANGE_BASE_URL', 'http://localhost:8000').rstrip('/'),
        account_id=os.getenv('EXCHANGE_ACCOUNT_ID', 'trader-0'),
        api_key=os.getenv('EXCHANGE_API_KEY', ''),
        poll_market_ms=int(os.getenv('EXCHANGE_POLL_MARKET_MS', '2000')),
        poll_orders_ms=int(os.getenv('EXCHANGE_POLL_ORDERS_MS', '3000')),
    )
