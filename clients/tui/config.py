"""
This module defines the `AppConfig` dataclass and the `load_config` factory
for loading application settings from environment variables.

All configuration values are read from the environment with sensible defaults,
allowing the application to work out of the box when run against a local
instance of the exchange stack.

Supported environment variables:
- `EXCHANGE_BASE_URL`:       Gateway base URL (default: http://localhost:8000)
- `EXCHANGE_ACCOUNT_ID`:     Account to trade as (default: trader-0)
- `EXCHANGE_API_KEY`:        `X-API-Key` header value (default: none)
- `EXCHANGE_POLL_MARKET_MS`: Market data polling interval (default: 2000ms)
- `EXCHANGE_POLL_ORDERS_MS`: Account/order polling interval (default: 3000ms)
"""

import os
import typing as tp
from dataclasses import dataclass


@dataclass
class AppConfig:
    """A container for all application configuration."""

    base_url: str
    account_id: str
    api_key: str
    poll_market_ms: int
    poll_orders_ms: int

    @property
    def headers(self) -> tp.Dict[str, str]:
        """Return authentication headers if an API key is configured."""
        return {'X-Api-Key': self.api_key} if self.api_key else {}


def load_config() -> AppConfig:
    """Load application configuration from environment variables."""
    return AppConfig(
        base_url=os.getenv('EXCHANGE_BASE_URL', 'http://localhost:8000').rstrip('/'),
        account_id=os.getenv('EXCHANGE_ACCOUNT_ID', 'trader-0'),
        api_key=os.getenv('EXCHANGE_API_KEY', ''),
        poll_market_ms=int(os.getenv('EXCHANGE_POLL_MARKET_MS', '2000')),
        poll_orders_ms=int(os.getenv('EXCHANGE_POLL_ORDERS_MS', '3000')),
    )
