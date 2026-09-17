# Releasing

No release automation yet. To cut a release:

1. Bump `version` in `platform/market_data/pyproject.toml`.
2. Add a dated entry to `platform/market_data/CHANGELOG.md`.
3. Commit the changes.
4. Tag the commit `market_data-vX.Y.Z`.
5. Push the tag.
