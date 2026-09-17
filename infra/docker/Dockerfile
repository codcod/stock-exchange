FROM python:3.14-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir uv

# Copy source
COPY . .
# ponytail: whole-repo COPY before install drops the old dep-layer cache split;
# restore it (or drop this file) once EXC-005..012 give each service its own Dockerfile (EXC-015).
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Default port — overridden per-service via PORT env var
EXPOSE 8000

# Entry point is set per-service via CMD in docker-compose
CMD ["python", "-m", "services.account"]
