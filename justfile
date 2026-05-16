set dotenv-load := true

db_url := "postgresql://exchange:exchange@localhost:5432/exchange"
compose := "docker-compose -f infra/docker/compose.yaml"

# List available recipes
@_:
   just --list


# Install all dependencies (including dev extras)
[group('lifecycle')]
install:
    uv sync --extra dev

# Update dependencies
[group('lifecycle')]
update:
    uv sync --upgrade

# Remove temporary files
[group('lifecycle')]
clean:
    rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
    find . -type d -name "__pycache__" -exec rm -r {} +

# Remove uploaded files
[group('lifecycle')]
clean-instance:
    rm -rf .instance || true

# Remove temporary files, incl. virtualenv
[group('lifecycle')]
clean-all: clean clean-instance
    rm -rf .venv || true

# Recreate project virtualenv from nothing
[group('lifecycle')]
fresh: clean-all install

# Start Postgres
[group('infra')]
infra-up:
    {{ compose }} up -d

# Stop Postgres
[group('infra')]
infra-down:
    {{ compose }} down

# Follow infra logs
[group('infra')]
infra-logs:
    {{ compose }} logs -f

# Open a psql shell against the local exchange DB
[group('run')]
db-shell:
    docker exec -it $(docker-compose -f infra/docker/docker-compose.yaml ps -q postgres) \
        psql -U exchange exchange

# Start the HTTP gateway with Postgres persistence (requires infra-up)
[group('run')]
gateway:
    DATABASE_URL={{ db_url }} uv run python -m services.gateway

# Start the HTTP gateway in-memory only (no Postgres needed)
[group('run')]
gateway-memory:
    uv run python -m services.gateway

# Start the HTTP gateway with prod like settings (minimal logging)
[group('run')]
gateway-prod:
    DATABASE_URL={{ db_url }} \
    uvicorn services.gateway.app:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 4 \
        --log-level warning

# Run the demo script (one trade between Alice and Bob, no HTTP)
[group('demo')]
demo:
    uv run python -m exchange.main

# Run the simulator (generates synthetic order traffic)
[group('demo')]
sim:
    uv run python -m clients.simulator.main

# Seed the database (drops all tables first — 100 instruments, 30 accounts, 100 trades)
[group('qa')]
seed:
    DATABASE_URL={{ db_url }} uv run python scripts/seed.py

# Check for lint errors (no auto-fix)
[group('qa')]
lint:
    uv run ruff check .

# Fix auto-fixable lint errors
[group('qa')]
lint-fix:
    uv run ruff check --fix .

# Format code in place
[group('qa')]
fmt:
    uv run ruff format .

# Check formatting without writing (CI mode)
[group('qa')]
fmt-check:
    uv run ruff format --check .

# Run all checks: lint + format-check (mirrors CI)
[group('qa')]
check: lint fmt-check

# Run all tests (persistence tests skip automatically without Postgres)
[group('qa')]
test:
    uv run pytest

# Run tests with coverage report
[group('qa')]
test-cov:
    uv run pytest --cov --cov-report=term-missing

# Run only the persistence integration tests (requires infra-up)
[group('qa')]
test-db:
    DATABASE_URL={{ db_url }} uv run pytest tests/test_persistence.py -v
