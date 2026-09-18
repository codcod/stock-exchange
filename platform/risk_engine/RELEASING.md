# Releasing

No release automation yet. To cut a release:

1. Bump `version` in `platform/risk_engine/pyproject.toml`.
2. Add a dated entry to `platform/risk_engine/CHANGELOG.md`.
3. Commit the changes.
4. Tag the commit `risk_engine-vX.Y.Z`.
5. Push the tag.
