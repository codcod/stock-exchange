"""
shared/request_context.py

Per-request context variables. Set by gateway middleware; read by http_client
helpers to propagate correlation headers across all downstream service calls.

Usage:
    # In gateway middleware:
    request_id.set(some_uuid)

    # In shared/http_client.py (automatic):
    headers = {'X-Request-ID': request_id.get()} if request_id.get() else {}
"""

from __future__ import annotations

import contextvars

request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    'request_id', default=''
)
