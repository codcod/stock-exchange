# syntax=docker/dockerfile:1
#
# Build context is the repo root (see infra/docker/compose.services.yml) — uv needs the
# workspace root (pyproject.toml + uv.lock) plus every platform/* member's pyproject.toml to
# resolve the workspace, even though this image only installs account and its dependency
# closure.
#

#
# BUILD
#
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /app
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY platform/base ./platform/base
COPY platform/account/pyproject.toml ./platform/account/pyproject.toml
COPY platform/account/src ./platform/account/src
# uv resolves the whole workspace declared in pyproject.toml, so every other member's
# pyproject.toml must be present too, even though only account gets installed.
COPY platform/gateway/pyproject.toml ./platform/gateway/pyproject.toml
COPY platform/market_data/pyproject.toml ./platform/market_data/pyproject.toml
COPY platform/matching_engine/pyproject.toml ./platform/matching_engine/pyproject.toml
COPY platform/risk_engine/pyproject.toml ./platform/risk_engine/pyproject.toml
COPY platform/order_management/pyproject.toml ./platform/order_management/pyproject.toml

RUN uv sync --locked --no-dev --no-editable --package account

#
# RUNTIME
#
FROM gcr.io/distroless/python3-debian13
WORKDIR /opt/account
COPY --from=builder /app/.venv/lib/python3.13/site-packages /opt/site-packages
COPY platform/account/src/account ./account
COPY platform/account/migrations ./migrations
COPY platform/account/alembic.ini .
ENV PYTHONPATH=/opt/site-packages

EXPOSE 8006

# Entrypoint is plain `python` (no shell) so compose overrides CMD to run
# migrations instead of the app — see the `account-migrate` service in
# infra/docker/compose.services.yml.
ENTRYPOINT ["python"]
CMD ["-m", "account"]
