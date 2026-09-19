# syntax=docker/dockerfile:1
#
# Build context is the repo root (see infra/docker/compose.services.yml) — uv needs the
# workspace root (pyproject.toml + uv.lock) plus every platform/* member's pyproject.toml to
# resolve the workspace, even though this image only installs admin and its dependency
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
COPY platform/admin/pyproject.toml ./platform/admin/pyproject.toml
COPY platform/admin/src ./platform/admin/src
# uv resolves the whole workspace declared in pyproject.toml, so every other member's
# pyproject.toml must be present too, even though only admin gets installed.
COPY platform/gateway/pyproject.toml ./platform/gateway/pyproject.toml
COPY platform/market_data/pyproject.toml ./platform/market_data/pyproject.toml
COPY platform/account/pyproject.toml ./platform/account/pyproject.toml
COPY platform/matching_engine/pyproject.toml ./platform/matching_engine/pyproject.toml
COPY platform/risk_engine/pyproject.toml ./platform/risk_engine/pyproject.toml
COPY platform/order_management/pyproject.toml ./platform/order_management/pyproject.toml
COPY platform/clearing/pyproject.toml ./platform/clearing/pyproject.toml
COPY platform/notifications/pyproject.toml ./platform/notifications/pyproject.toml

RUN uv sync --locked --no-dev --no-editable --package admin

#
# RUNTIME
#
FROM gcr.io/distroless/python3-debian13
WORKDIR /opt/admin
COPY --from=builder /app/.venv/lib/python3.13/site-packages /opt/site-packages
COPY platform/admin/src/admin ./admin
COPY platform/admin/static ./static
COPY platform/admin/templates ./templates
ENV PYTHONPATH=/opt/site-packages

EXPOSE 8008

# admin owns no schema — no -migrate service, unlike its stateful siblings.
ENTRYPOINT ["python"]
CMD ["-m", "admin"]
