# Azure Governance Platform - Makefile
# Common development and deployment tasks

.PHONY: help install install-dev doctor local-fast-gate local-gate local-db-reset local-seed local-data-smoke local-reset-seed-smoke test test-cov test-e2e lint format type-check security-check clean migrate migrate-up migrate-down run run-dev docker-build docker-push deploy-staging deploy-production backup db-backup db-shell shell logs docs visual-test accessibility-test mutation-test phase3-tests

# Default target
.DEFAULT_GOAL := help

# Colors for terminal output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m # No Color

LOCAL_DB_PATH ?= data/local-dev.db
LOCAL_DB_URL ?= sqlite:///./$(LOCAL_DB_PATH)
LOCAL_ENV := ENVIRONMENT=development DATABASE_URL=$(LOCAL_DB_URL)

help: ## Show this help message
	@echo "$(BLUE)Azure Governance Platform$(NC) - Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make test              # Run all unit tests"
	@echo "  make test-cov          # Run tests with coverage"
	@echo "  make deploy-staging    # Deploy to staging environment"
	@echo "  make db-backup         # Create database backup"

# =============================================================================
# Installation & Dependencies
# =============================================================================

install: ## Install production dependencies
	@echo "$(BLUE)Installing production dependencies...$(NC)"
	pip install -e .

install-dev: ## Install development dependencies
	@echo "$(BLUE)Installing development dependencies...$(NC)"
	pip install -e ".[dev]"
	pre-commit install

install-uv: ## Install dependencies using uv (faster)
	@echo "$(BLUE)Installing with uv...$(NC)"
	uv pip install -e ".[dev]"

# =============================================================================
# Local-first validation gates
# =============================================================================

doctor: ## Validate local prerequisites without Azure credentials
	@echo "$(BLUE)Running local doctor...$(NC)"
	uv run python scripts/doctor.py

local-fast-gate: doctor ## Run fast local preflight gate
	@echo "$(BLUE)Running fast local gate...$(NC)"
	uv run ruff check app tests scripts
	uv run ruff format --check app tests scripts
	uv run pytest tests/e2e/test_browser_smoke.py -q --tb=short
	uv run pytest tests/e2e/test_accessibility_e2e.py tests/e2e/test_axe_accessibility.py -q --tb=short
	@echo "$(GREEN)✓ Fast local gate passed$(NC)"

local-gate: doctor ## Run full local gate before staging/product validation
	@echo "$(BLUE)Running full local gate...$(NC)"
	uv run ruff check app tests scripts
	uv run ruff format --check app tests scripts
	@echo "$(BLUE)Running unit and integration suites in parallel...$(NC)"
	@rm -f /tmp/control-tower-unit.log /tmp/control-tower-integration.log
	@(uv run pytest tests/unit -q --tb=short > /tmp/control-tower-unit.log 2>&1 & \
		unit_pid=$$!; \
		uv run pytest tests/integration -q --tb=short > /tmp/control-tower-integration.log 2>&1 & \
		integration_pid=$$!; \
		wait $$unit_pid; unit_status=$$?; \
		wait $$integration_pid; integration_status=$$?; \
		tail -n 30 /tmp/control-tower-unit.log; \
		tail -n 30 /tmp/control-tower-integration.log; \
		if [ $$unit_status -ne 0 ] || [ $$integration_status -ne 0 ]; then \
			echo "$(RED)Unit or integration suite failed$(NC)"; \
			exit 1; \
		fi)
	$(MAKE) local-reset-seed-smoke
	$(LOCAL_ENV) uv run pytest tests/e2e/test_browser_smoke.py tests/e2e/test_accessibility_e2e.py tests/e2e/test_seeded_data_flows.py -q --tb=short
	$(LOCAL_ENV) uv run pytest tests/e2e/test_axe_accessibility.py -q --tb=short
	@echo "$(GREEN)✓ Full local gate passed$(NC)"

local-db-reset: ## Reset dedicated local SQLite demo database only
	@echo "$(YELLOW)Resetting dedicated local DB: $(LOCAL_DB_PATH)$(NC)"
	@mkdir -p $(dir $(LOCAL_DB_PATH))
	@rm -f $(LOCAL_DB_PATH) $(LOCAL_DB_PATH)-shm $(LOCAL_DB_PATH)-wal
	@echo "$(GREEN)✓ Local DB reset$(NC)"

local-seed: ## Seed dedicated local SQLite demo database
	@echo "$(BLUE)Seeding local demo data into $(LOCAL_DB_PATH)...$(NC)"
	$(LOCAL_ENV) uv run python scripts/seed_data.py --force

local-data-smoke: ## Validate local seeded data contract
	@echo "$(BLUE)Running local data smoke...$(NC)"
	$(LOCAL_ENV) uv run python scripts/local_data_smoke.py

local-reset-seed-smoke: local-db-reset local-seed local-data-smoke ## Reset, seed, and validate local demo data
	@echo "$(GREEN)✓ Local reset/seed/smoke passed$(NC)"

# =============================================================================
# Testing
# =============================================================================

test: ## Run unit tests
	@echo "$(BLUE)Running unit tests...$(NC)"
	pytest tests/unit -v --tb=short

test-cov: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	pytest tests/unit --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=80

test-integration: ## Run integration tests
	@echo "$(BLUE)Running integration tests...$(NC)"
	pytest tests/integration -v --tb=short

test-e2e: ## Run end-to-end tests (requires running server)
	@echo "$(BLUE)Running E2E tests...$(NC)"
	pytest tests/e2e -v --tb=short

test-architecture: ## Run architecture/fitness function tests
	@echo "$(BLUE)Running architecture tests...$(NC)"
	pytest tests/architecture -v --tb=short

test-security: ## Run security tests only
	@echo "$(BLUE)Running security tests...$(NC)"
	pytest tests/ -k "security" -v --tb=short

test-all: ## Run every test group in ISOLATED passes (avoids cross-group event-loop pollution; see ct-pm3)
	@echo "$(BLUE)Running all test groups in isolated passes...$(NC)"
	# NOTE: do NOT collapse these into a single `pytest tests/` run. The
	# architecture/chaos/performance suites exercise sync<->async bridges and
	# pytest-asyncio (asyncio_mode=auto) loops that, when run in the SAME
	# process as the 4000+ unit tests, leak a running event loop and cause
	# order-dependent `Runner.run() cannot be called from a running event
	# loop` cascades. Each group passes cleanly in its own process.
	pytest tests/unit tests/integration -m "not visual" --tb=short
	pytest tests/architecture --tb=short
	pytest tests/chaos --tb=short
	pytest tests/performance --tb=short

test-ci: ## Run tests for CI pipeline (with coverage)
	@echo "$(BLUE)Running CI test suite...$(NC)"
	pytest tests/unit tests/integration --cov=app --cov-report=xml --cov-fail-under=75

# =============================================================================
# Load & Performance Testing
# =============================================================================

load-test: ## Run Locust load tests (requires running server)
	@echo "$(BLUE)Running Locust load tests...$(NC)"
	@echo "Make sure the server is running: make run-dev"
	uv run locust -f tests/load/locustfile.py \
		--host http://localhost:8000 \
		--headless \
		--users 50 \
		--spawn-rate 10 \
		--run-time 60s

load-test-smoke: ## Run quick smoke load test (30s, 10 users)
	@echo "$(BLUE)Running smoke load test...$(NC)"
	@echo "Make sure the server is running: make run-dev"
	uv run locust -f tests/load/locustfile.py \
		--host http://localhost:8000 \
		--headless \
		--users 10 \
		--spawn-rate 5 \
		--run-time 30s

smoke-test: ## Run all smoke tests (API, Azure, connectivity)
	@echo "$(BLUE)Running smoke tests...$(NC)"
	pytest tests/smoke -v --tb=short

e2e-test: ## Run Playwright E2E tests
	@echo "$(BLUE)Running E2E tests with Playwright...$(NC)"
	pytest tests/e2e -v --tb=short

# =============================================================================
# Phase 3: Advanced Testing Targets
# =============================================================================

visual-test: ## Run visual-regression tests (requires baselines in tests/e2e/baselines/)
	@echo "=== Running Visual Regression Tests ==="
	ENVIRONMENT=test DATABASE_URL=$(LOCAL_DB_URL) E2E_HARNESS=true BROWSER_TEST_DISABLE_SCHEDULERS=true \
	  uv run pytest tests/e2e/test_visual_parity.py -v -m visual

capture-baselines: ## Bless visual-parity baselines via the test's own context (seeds DB first)
	@echo "=== Blessing visual baselines ==="
	@echo "Seeding local demo DB first..."
	$(MAKE) local-db-reset local-seed
	@echo "Blessing baselines through the test path (VISUAL_UPDATE=1)..."
	@echo "NB: baselines MUST be captured by the same browser context that"
	@echo "    compares them, or sub-pixel font drift breaks every run. The"
	@echo "    standalone capture script is for remote-URL captures only."
	ENVIRONMENT=test DATABASE_URL=$(LOCAL_DB_URL) E2E_HARNESS=true BROWSER_TEST_DISABLE_SCHEDULERS=true \
	  VISUAL_UPDATE=1 uv run pytest tests/e2e/test_visual_parity.py -m visual -q
	@echo "Baselines blessed. Verifying they pass..."
	$(MAKE) visual-test
	@echo "Commit the PNGs in tests/e2e/baselines/ alongside your change."

accessibility-test:
	@echo "=== Running Accessibility Tests ==="
	pytest tests/e2e/test_accessibility.py -v -m accessibility

mutation-test:
	@echo "=== Running Mutation Tests ==="
	bash scripts/run-mutation-tests.sh

# Combined Phase 3 test suite
phase3-tests: visual-test accessibility-test
	@echo "✅ Phase 3 tests complete"

full-suite: ## Run the unified end-to-end gate (security, compliance, design/a11y, chaos, architecture, regression) with a consolidated report
	@echo "$(BLUE)Running unified full suite...$(NC)"
	bash scripts/run_full_suite.sh

full-suite-fast: ## Fast subset of the full suite (security + compliance + design only)
	FAST=1 bash scripts/run_full_suite.sh

full-suite-load: ## Full suite plus the 100+ user local load profile
	WITH_LOAD=1 bash scripts/run_full_suite.sh

load-profile: ## Run the staged 100+ concurrent-user load profile against a local server
	bash scripts/run_load_profile.sh

load-profile-quick: ## Quick 100-user / 20s load verification against a local server
	QUICK=1 bash scripts/run_load_profile.sh

# =============================================================================
# Code Quality
# =============================================================================

lint: ## Run linting (ruff, pylint)
	@echo "$(BLUE)Running linters...$(NC)"
	ruff check app tests
	@echo "$(GREEN)✓ Linting passed$(NC)"

lint-fix: ## Run linting with auto-fix
	@echo "$(BLUE)Running linters with auto-fix...$(NC)"
	ruff check --fix app tests
	@echo "$(GREEN)✓ Linting fixes applied$(NC)"

format: ## Format code with ruff and black
	@echo "$(BLUE)Formatting code...$(NC)"
	ruff format app tests
	@echo "$(GREEN)✓ Formatting complete$(NC)"

format-check: ## Check code formatting without modifying
	@echo "$(BLUE)Checking code formatting...$(NC)"
	ruff format --check app tests

type-check: ## Run type checking with mypy
	@echo "$(BLUE)Running type checker...$(NC)"
	mypy app --ignore-missing-imports --show-error-codes

security-check: ## Run security checks (bandit, safety)
	@echo "$(BLUE)Running security checks...$(NC)"
	bandit -r app -f json -o bandit-report.json || true
	@echo "$(GREEN)✓ Security scan complete (see bandit-report.json)$(NC)"

pre-commit: ## Run pre-commit hooks on all files
	@echo "$(BLUE)Running pre-commit hooks...$(NC)"
	pre-commit run --all-files

# =============================================================================
# Database Operations
# =============================================================================

migrate: ## Create new Alembic migration (use: make migrate msg="description")
	@if [ -z "$(msg)" ]; then \
		echo "$(RED)Error: Please provide a migration message$(NC)"; \
		echo "Usage: make migrate msg='add user table'"; \
		exit 1; \
	fi
	@echo "$(BLUE)Creating migration: $(msg)...$(NC)"
	alembic revision --autogenerate -m "$(msg)"

migrate-up: ## Run all pending migrations (upgrade to latest)
	@echo "$(BLUE)Running migrations...$(NC)"
	alembic upgrade head

migrate-down: ## Rollback last migration
	@echo "$(YELLOW)Rolling back last migration...$(NC)"
	alembic downgrade -1

migrate-history: ## Show migration history
	@echo "$(BLUE)Migration history:$(NC)"
	alembic history --verbose

migrate-current: ## Show current migration version
	@echo "$(BLUE)Current migration:$(NC)"
	alembic current

db-backup: ## Create database backup
	@echo "$(BLUE)Creating database backup...$(NC)"
	python scripts/backup_database.py

db-shell: ## Open database shell (SQLite) or connect string
	@echo "$(BLUE)Connecting to database...$(NC)"
	@source .env && \
	if echo "$$DATABASE_URL" | grep -q "sqlite"; then \
		sqlite3 $$(echo "$$DATABASE_URL" | sed 's/sqlite:\/\///'); \
	else \
		echo "PostgreSQL/SQL Server: Use your preferred client with: $$DATABASE_URL"; \
	fi

db-stats: ## Show database statistics
	@echo "$(BLUE)Database statistics...$(NC)"
	python -c "from app.core.database import SessionLocal, get_db_stats; db = SessionLocal(); stats = get_db_stats(db); [print(f'  {table}: {count} rows') for table, count in stats.items()]; db.close()"

# =============================================================================
# Application Operations
# =============================================================================

run: ## Run production server
	@echo "$(BLUE)Starting production server...$(NC)"
	uvicorn app.main:app --host 0.0.0.0 --port 8000

run-dev: ## Run development server with auto-reload
	@echo "$(BLUE)Starting development server...$(NC)"
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

run-worker: ## Run background worker (if using separate worker process)
	@echo "$(BLUE)Starting background worker...$(NC)"
	python -m app.worker

shell: ## Open Python shell with app context
	@echo "$(BLUE)Opening Python shell...$(NC)"
	python -i -c "from app.core.database import SessionLocal; from app.core.config import get_settings; from app.models import *; print('Available: SessionLocal, get_settings, models')"

logs: ## Show recent logs (if using docker-compose)
	@echo "$(BLUE)Showing logs...$(NC)"
	docker-compose logs -f app

# =============================================================================
# Docker Operations
# =============================================================================

docker-build: ## Build Docker image
	@echo "$(BLUE)Building Docker image...$(NC)"
	docker build -t control-tower:latest .

docker-run: ## Run Docker container locally
	@echo "$(BLUE)Running Docker container...$(NC)"
	docker run -p 8000:8000 --env-file .env control-tower:latest

docker-push: ## Push Docker image to registry (requires ACR login)
	@echo "$(BLUE)Pushing to container registry...$(NC)"
	@if [ -z "$(ACR_NAME)" ]; then \
		echo "$(RED)Error: Please set ACR_NAME$(NC)"; \
		exit 1; \
	fi
	docker tag control-tower:latest $(ACR_NAME).azurecr.io/control-tower:latest
	docker push $(ACR_NAME).azurecr.io/control-tower:latest

# =============================================================================
# Deployment
# =============================================================================

deploy-staging: ## Deploy to staging environment
	@echo "$(BLUE)Deploying to staging...$(NC)"
	@if [ -z "$(GITHUB_TOKEN)" ]; then \
		echo "$(YELLOW)Warning: GITHUB_TOKEN not set, using git push$(NC)"; \
		git push origin main; \
	else \
		gh workflow run deploy-staging.yml; \
	fi
	@echo "$(GREEN)✓ Staging deployment triggered$(NC)"

deploy-production: ## Deploy to production environment
	@echo "$(YELLOW)⚠️  Deploying to PRODUCTION...$(NC)"
	@read -p "Are you sure? [y/N] " confirm && [ $$confirm = y ] || exit 1
	@if [ -z "$(GITHUB_TOKEN)" ]; then \
		echo "$(YELLOW)Warning: GITHUB_TOKEN not set, using git push$(NC)"; \
		git push origin production; \
	else \
		gh workflow run deploy-production.yml; \
	fi
	@echo "$(GREEN)✓ Production deployment triggered$(NC)"

# =============================================================================
# Maintenance & Utilities
# =============================================================================

clean: ## Clean temporary files and caches
	@echo "$(BLUE)Cleaning temporary files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type f -name "bandit-report.json" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

docs: ## Generate API documentation
	@echo "$(BLUE)Generating documentation...$(NC)"
	python -c "from app.main import app; import json; json.dump(app.openapi(), open('docs/openapi.json', 'w'), indent=2); print('Documentation saved to docs/openapi.json')"

health-check: ## Check application health
	@echo "$(BLUE)Checking application health...$(NC)"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "$(RED)App not running on localhost:8000$(NC)"

env-check: ## Validate environment variables
	@echo "$(BLUE)Checking environment configuration...$(NC)"
	python -c "from app.core.config import get_settings; settings = get_settings(); db = settings.database_url.split('@')[-1] if '@' in settings.database_url else 'local'; print('$(GREEN)✓ Environment configuration valid$(NC)'); print(f'  App Name: {settings.app_name}'); print(f'  Environment: {settings.environment}'); print(f'  Database: {db}')"

# =============================================================================
# CI/CD Utilities
# =============================================================================

ci-lint: ## Run all linting checks for CI
	@echo "$(BLUE)Running CI lint checks...$(NC)"
	ruff check app tests
	ruff format --check app tests
	@echo "$(GREEN)✓ All lint checks passed$(NC)"

ci-test: ## Run tests for CI pipeline
	@echo "$(BLUE)Running CI test suite...$(NC)"
	pytest tests/unit tests/integration --cov=app --cov-report=xml --cov-fail-under=75 -v

ci-security: ## Run security checks for CI
	@echo "$(BLUE)Running CI security checks...$(NC)"
	bandit -r app -ll -ii
	@echo "$(GREEN)✓ Security checks passed$(NC)"

# =============================================================================
# Release Management
# =============================================================================

version: ## Show current version
	@echo "$(BLUE)Current version:$(NC)"
	@python -c "from app.core.config import get_settings; print(get_settings().app_version)"

changelog: ## Show recent changelog
	@echo "$(BLUE)Recent changes:$(NC)"
	@head -50 CHANGELOG.md

# =============================================================================
# Backup & Recovery
# =============================================================================

backup: ## Create full backup (database + configs)
	@echo "$(BLUE)Creating full backup...$(NC)"
	@mkdir -p backups/$(shell date +%Y%m%d)
	make db-backup
	cp .env backups/$(shell date +%Y%m%d)/.env.backup 2>/dev/null || true
	@echo "$(GREEN)✓ Backup saved to backups/$(shell date +%Y%m%d)/$(NC)"

# Catch-all for undefined targets
%:
	@echo "$(RED)Unknown target: $@$(NC)"
	@echo "Run 'make help' for available targets"
	@exit 1
