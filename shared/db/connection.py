# Re-export from new location for backward compatibility.
# New code should import from shared.platform.db.connection.
from shared.platform.db.connection import get_engine  # noqa: F401
