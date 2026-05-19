"""
Per-request context variables.

Set by gateway middleware and read by HTTP client helpers to propagate
correlation headers across all downstream service calls.
"""

from __future__ import annotations

import contextvars

request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    'request_id', default=''
)
