"""
shared/schemas.py

Re-exports OrderRequest from the canonical inter-service contracts module.
New code should import directly from shared.domain.api_schemas.
"""

from shared.domain.api_schemas import OrderRequest  # noqa: F401
