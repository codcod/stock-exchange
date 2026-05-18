"""Request/response models for the Matching Engine."""

from __future__ import annotations

# The matching engine accepts orders via the shared OrderRequest model.
# Re-export it here so the app only needs to import from this module.
from shared.schemas import OrderRequest  # noqa: F401
