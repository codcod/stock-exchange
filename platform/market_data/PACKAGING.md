# Packaging

`market_data` is a `hatchling`-built, `src/`-layout package (`src/market_data/`), installed into
the repo's `uv` workspace via `[tool.uv.sources]` in the root `pyproject.toml`. Its importable
package name is flat (`market_data`, not a project-prefixed namespace) to match every other
`platform/<service>/` package (`platform/base/` and its EXC-005–EXC-012 siblings).
