FROM python:3.14-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir -e .

# Copy source
COPY . .

# Default port — overridden per-service via PORT env var
EXPOSE 8000

# Entry point is set per-service via CMD in docker-compose
CMD ["python", "-m", "services.gateway"]
