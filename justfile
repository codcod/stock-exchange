set dotenv-load := true

db_url     := "postgresql+asyncpg://exchange:exchange@localhost:5432/exchange"
infra      := "docker-compose -f infra/docker/compose.infra.yml"
services   := "docker-compose -f infra/docker/compose.services.yml"
stack      := "docker-compose -f infra/docker/compose.infra.yml -f infra/docker/compose.services.yml"

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

# Recreate project virtualenv from scratch
[group('lifecycle')]
fresh: clean-all install

# Start Postgres
[group('infra')]
infra-up:
    docker network inspect exchange >/dev/null 2>&1 || docker network create exchange
    {{ infra }} up -d

# Stop Postgres
[group('infra')]
infra-down:
    {{ infra }} down

# Follow Postgres logs
[group('infra')]
infra-logs:
    {{ infra }} logs -f

# Open a psql shell against the local exchange DB
[group('infra')]
db-shell:
    {{ infra }} exec postgres psql -U exchange exchange

# Build all service images
[group('services')]
services-build:
    {{ services }} build

# Start all microservices (requires infra-up first)
[group('services')]
services-up:
    {{ services }} up -d

# Stop all microservices
[group('services')]
services-down:
    {{ services }} down

# Follow microservice logs (all services)
[group('services')]
services-logs:
    {{ services }} logs -f

# Follow logs for a single service  e.g.: just service-logs matching-engine
[group('services')]
service-logs name:
    {{ services }} logs -f {{ name }}

# Restart a single service after a code change  e.g.: just redeploy matching-engine
[group('services')]
redeploy name:
    {{ services }} build {{ name }} && {{ services }} up -d --no-deps {{ name }}

# Start Postgres + all microservices
[group('stack')]
up:
    docker network inspect exchange >/dev/null 2>&1 || docker network create exchange
    {{ stack }} up -d --build

# Stop everything
[group('stack')]
down:
    {{ stack }} down

# Wipe all data volumes and restart the full stack from scratch
[group('stack')]
db-wipe:
    {{ stack }} down -v
    just up

# Follow all logs (infra + services)
[group('stack')]
logs:
    {{ stack }} logs -f

# Show running containers and their ports
[group('stack')]
ps:
    @(echo "ID\tIMAGE\tSTATUS\tPORTS" && {{ stack }} ps \
        --format '{{{{.ID}}\t{{{{.Image}}\t{{{{.Status}}\t{{{{.Ports}}') \
        | column -t -s $'\t'

# ── Run locally (no Docker, services speak to each other on localhost) ────────

# Gateway (routes to local microservices)
[group('run locally')]
run-gateway:
    uv run python -m services.gateway

# Order Management Service
[group('run locally')]
run-oms:
    DATABASE_URL={{ db_url }} \
    RISK_ENGINE_URL=http://localhost:8002 \
    MATCHING_ENGINE_URL=http://localhost:8003 \
    uv run python -m services.order_management

# Risk Engine
[group('run locally')]
run-risk:
    DATABASE_URL={{ db_url }} uv run python -m services.risk_engine

# Matching Engine
[group('run locally')]
run-matching:
    DATABASE_URL={{ db_url }} \
    CLEARING_URL=http://localhost:8004 \
    ORDER_MANAGEMENT_URL=http://localhost:8001 \
    MARKET_DATA_URL=http://localhost:8005 \
    uv run python -m services.matching_engine

# Clearing Service
[group('run locally')]
run-clearing:
    DATABASE_URL={{ db_url }} uv run python -m services.clearing

# Market Data Service
[group('run locally')]
run-market-data:
    uv run python -m services.market_data

# Start a tmux session (2×4 panes) with infra + all six services
[group('run locally')]
dev:
    bash scripts/dev-tmux.sh

# Stop all local services and kill the dev tmux session
[group('run locally')]
dev-down:
    {{ infra }} down
    tmux kill-session -t exchange 2>/dev/null || true

# Run the simulator (generates synthetic order traffic against the gateway)
[group('demo')]
sim:
    uv run python -m clients.simulator.main

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

# Run all static checks: lint + format (mirrors CI)
[group('qa')]
check: lint fmt-check

# Run all unit + integration tests
[group('qa')]
test:
    uv run --extra dev python -m pytest

# Run tests with coverage report
[group('qa')]
test-cov:
    uv run --extra dev python -m pytest --cov --cov-report=term-missing

# Seed the exchange (requires full stack running — 100 instruments, 30 accounts, 100 trades)
[group('qa')]
seed:
    GATEWAY_URL=http://localhost:8000 uv run python scripts/seed.py
