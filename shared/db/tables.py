# Re-export from new location for backward compatibility.
# New code should import ensure_tables from the service's own tables.py.
from shared.platform.db.tables import ensure_tables  # noqa: F401
