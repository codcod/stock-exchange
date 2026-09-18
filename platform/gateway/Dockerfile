# syntax=docker/dockerfile:1
#
# Build context is the repo root (see infra/docker/compose.services.yml) — uv needs the
# workspace root (pyproject.toml + uv.lock) plus every platform/* member's pyproject.toml to
# resolve the workspace, even though this image only installs gateway and its dependency
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
# uv resolves the whole workspace declared in pyproject.toml, so every other member's
# pyproject.toml must be present too, even though only gateway gets installed.
COPY platform/market_data/pyproject.toml ./platform/market_data/pyproject.toml
COPY platform/account/pyproject.toml ./platform/account/pyproject.toml
COPY platform/matching_engine/pyproject.toml ./platform/matching_engine/pyproject.toml
COPY platform/risk_engine/pyproject.toml ./platform/risk_engine/pyproject.toml
COPY platform/gateway/pyproject.toml ./platform/gateway/pyproject.toml
COPY platform/gateway/src ./platform/gateway/src

# --no-editable: the workspace member installs as a regular wheel, so the final stage can run
# off a copied site-packages dir instead of needing /app/platform around at runtime.
RUN uv sync --locked --no-dev --no-editable --package gateway

#
# RUNTIME
#
# distroless debian13 ships Python 3.13 (3.14 has no distroless build yet) with no
# shell/package manager — smallest, lowest attack surface, non-root by default. Only the
# venv's site-packages are copied over, so no shell is needed to activate it; PYTHONPATH does
# the same job.
FROM gcr.io/distroless/python3-debian13
WORKDIR /opt/gateway
COPY --from=builder /app/.venv/lib/python3.13/site-packages /opt/site-packages
COPY platform/gateway/src/gateway ./gateway
ENV PYTHONPATH=/opt/site-packages

EXPOSE 8000

ENTRYPOINT ["python"]
CMD ["-m", "gateway"]
