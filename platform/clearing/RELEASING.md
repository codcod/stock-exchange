# Releasing

No release automation yet. To cut a release:

1. Bump `version` in `platform/clearing/pyproject.toml`.
2. Add a dated entry to `platform/clearing/CHANGELOG.md`.
3. Commit the changes.
4. Tag the commit `clearing-vX.Y.Z`.
5. Push the tag.
