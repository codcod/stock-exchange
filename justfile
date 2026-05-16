set dotenv-load := true

db_url := "postgresql://exchange:exchange@localhost:5432/exchange"
compose := "docker-compose -f infra/docker/compose.yml"

# List available recipes
default:
    @just --list

# ── Dependencies ─────────────────────────────────────────────────────────────

# Install all dependencies (including dev extras)
install:
    uv sync --extra dev

# ── Infrastructure ───────────────────────────────────────────────────────────

# Start Postgres and Redis
infra-up:
    {{ compose }} up -d

# Stop Postgres and Redis
infra-down:
    {{ compose }} down

# Follow infra logs
infra-logs:
    {{ compose }} logs -f

# Open a psql shell against the local exchange DB
db-shell:
    docker exec -it $(docker-compose -f infra/docker/docker-compose.yml ps -q postgres) \
        psql -U exchange exchange

# ── Running the exchange ─────────────────────────────────────────────────────

# Start the HTTP gateway with Postgres persistence (requires infra-up)
gateway:
    DATABASE_URL={{ db_url }} uv run python -m services.gateway

# Start the HTTP gateway in-memory only (no Postgres needed)
gateway-memory:
    uv run python -m services.gateway

gateway-prod:
    DATABASE_URL={{ db_url }} \
    uvicorn services.gateway.app:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 4 \
        --log-level warning

# Run the demo script (one trade between Alice and Bob, no HTTP)
demo:
    uv run python -m exchange.main

# Run the simulator (generates synthetic order traffic)
sim:
    uv run python -m clients.simulator.main

# ── Seeding ──────────────────────────────────────────────────────────────────

# Seed the database (drops all tables first — 100 instruments, 30 accounts, 100 trades)
seed:
    DATABASE_URL={{ db_url }} uv run python scripts/seed.py

# ── Linting & formatting ─────────────────────────────────────────────────────

# Check for lint errors (no auto-fix)
lint:
    uv run ruff check .

# Fix auto-fixable lint errors
lint-fix:
    uv run ruff check --fix .

# Format code in place
fmt:
    uv run ruff format .

# Check formatting without writing (CI mode)
fmt-check:
    uv run ruff format --check .

# Run all checks: lint + format-check (mirrors CI)
check: lint fmt-check

# ── Testing ──────────────────────────────────────────────────────────────────

# Run all tests (persistence tests skip automatically without Postgres)
test:
    uv run pytest

# Run tests with coverage report
test-cov:
    uv run pytest --cov --cov-report=term-missing

# Run only the persistence integration tests (requires infra-up)
test-db:
    DATABASE_URL={{ db_url }} uv run pytest tests/test_persistence.py -v
