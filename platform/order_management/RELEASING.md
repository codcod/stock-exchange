# Releasing

No release automation yet. To cut a release:

1. Bump `version` in `platform/order_management/pyproject.toml`.
2. Add a dated entry to `platform/order_management/CHANGELOG.md`.
3. Commit the changes.
4. Tag the commit `order_management-vX.Y.Z`.
5. Push the tag.
