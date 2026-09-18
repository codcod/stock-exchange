# syntax=docker/dockerfile:1
#
# Build context is the repo root (see infra/docker/compose.services.yml) — uv needs the
# workspace root (pyproject.toml + uv.lock) plus every platform/* member's pyproject.toml to
# resolve the workspace, even though this image only installs risk_engine and its dependency
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
COPY platform/risk_engine/pyproject.toml ./platform/risk_engine/pyproject.toml
COPY platform/risk_engine/src ./platform/risk_engine/src
# uv resolves the whole workspace declared in pyproject.toml, so every other member's
# pyproject.toml must be present too, even though only risk_engine gets installed.
COPY platform/gateway/pyproject.toml ./platform/gateway/pyproject.toml
COPY platform/market_data/pyproject.toml ./platform/market_data/pyproject.toml
COPY platform/account/pyproject.toml ./platform/account/pyproject.toml
COPY platform/matching_engine/pyproject.toml ./platform/matching_engine/pyproject.toml
COPY platform/order_management/pyproject.toml ./platform/order_management/pyproject.toml
COPY platform/clearing/pyproject.toml ./platform/clearing/pyproject.toml

RUN uv sync --locked --no-dev --no-editable --package risk_engine

#
# RUNTIME
#
FROM gcr.io/distroless/python3-debian13
WORKDIR /opt/risk_engine
COPY --from=builder /app/.venv/lib/python3.13/site-packages /opt/site-packages
COPY platform/risk_engine/src/risk_engine ./risk_engine
COPY platform/risk_engine/migrations ./migrations
COPY platform/risk_engine/alembic.ini .
ENV PYTHONPATH=/opt/site-packages

EXPOSE 8002

# Entrypoint is plain `python` (no shell) so compose overrides CMD to run
# migrations instead of the app — see the `risk-engine-migrate` service in
# infra/docker/compose.services.yml.
ENTRYPOINT ["python"]
CMD ["-m", "risk_engine"]
