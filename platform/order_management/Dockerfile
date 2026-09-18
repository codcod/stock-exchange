# syntax=docker/dockerfile:1
#
# Build context is the repo root (see infra/docker/compose.services.yml) — uv needs the
# workspace root (pyproject.toml + uv.lock) plus every platform/* member's pyproject.toml to
# resolve the workspace, even though this image only installs order_management and its
# dependency closure.
#

#
# BUILD
#
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /app
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY platform/base ./platform/base
COPY platform/order_management/pyproject.toml ./platform/order_management/pyproject.toml
COPY platform/order_management/src ./platform/order_management/src
# uv resolves the whole workspace declared in pyproject.toml, so every other member's
# pyproject.toml must be present too, even though only order_management gets installed.
COPY platform/gateway/pyproject.toml ./platform/gateway/pyproject.toml
COPY platform/market_data/pyproject.toml ./platform/market_data/pyproject.toml
COPY platform/account/pyproject.toml ./platform/account/pyproject.toml
COPY platform/matching_engine/pyproject.toml ./platform/matching_engine/pyproject.toml
COPY platform/risk_engine/pyproject.toml ./platform/risk_engine/pyproject.toml

RUN uv sync --locked --no-dev --no-editable --package order_management

#
# RUNTIME
#
FROM gcr.io/distroless/python3-debian13
WORKDIR /opt/order_management
COPY --from=builder /app/.venv/lib/python3.13/site-packages /opt/site-packages
COPY platform/order_management/src/order_management ./order_management
COPY platform/order_management/migrations ./migrations
COPY platform/order_management/alembic.ini .
ENV PYTHONPATH=/opt/site-packages

EXPOSE 8001

# Entrypoint is plain `python` (no shell) so compose overrides CMD to run
# migrations instead of the app — see the `order-management-migrate` service in
# infra/docker/compose.services.yml.
ENTRYPOINT ["python"]
CMD ["-m", "order_management"]
