# Packaging

`admin` is a `hatchling`-built, `src/`-layout package (`src/admin/`), installed into the
repo's `uv` workspace via `[tool.uv.sources]` in the root `pyproject.toml`. Its importable
package name is flat (`admin`, not a project-prefixed namespace) to match every other
`platform/<service>/` package (`platform/base/` and its EXC-005–EXC-012 siblings).
