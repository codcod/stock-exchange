# Re-export from new location for backward compatibility.
# New code should import from shared.platform.http_client.
from shared.platform.http_client import http_delete, http_get, http_post  # noqa: F401
