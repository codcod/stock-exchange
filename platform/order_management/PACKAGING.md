# Packaging

`order_management` is a `hatchling`-built, `src/`-layout package
(`src/order_management/`), installed into the repo's `uv` workspace via `[tool.uv.sources]` in
the root `pyproject.toml`. Its importable package name is flat (`order_management`, not a
project-prefixed namespace) to match every other `platform/<service>/` package (`platform/base/`
and its EXC-005–EXC-012 siblings).

It ships its own Alembic migration history under `migrations/`, applied by the
`order-management-migrate` one-shot compose service before `order-management` itself starts —
replacing the shared create-on-boot `CREATE SCHEMA IF NOT EXISTS` bootstrap this service used
before EXC-010.
