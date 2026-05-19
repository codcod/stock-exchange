"""
shared/service_clients.py

Re-exports all service clients from their canonical per-client modules under
shared/platform/clients/. New code should import directly from there.

The `_order_to_dict` alias is kept for the one caller (order_management/app.py)
that still uses it as a serialisation helper.
"""

from shared.platform.clients.clearing import ClearingClient  # noqa: F401
from shared.platform.clients.converters import (
    order_to_dict as _order_to_dict,  # noqa: F401
)
from shared.platform.clients.market_data import MarketDataClient  # noqa: F401
from shared.platform.clients.matching_engine import MatchingEngineClient  # noqa: F401
from shared.platform.clients.order_management import OrderManagementClient  # noqa: F401
from shared.platform.clients.risk_engine import RiskEngineClient  # noqa: F401
