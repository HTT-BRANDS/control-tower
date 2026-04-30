# Azure Governance Platform - Makefile
# Common development and deployment tasks

.PHONY: help install install-dev test test-cov test-e2e lint format type-check security-check clean migrate migrate-up migrate-down run run-dev docker-build docker-push deploy-staging deploy-production backup db-backup db-shell shell logs docs visual-test accessibility-test mutation-test phase3-tests

# Default target
.DEFAULT_GOAL := help

# Colors for terminal output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m # No Color

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

test-all: ## Run all tests (unit, integration, e2e)
	@echo "$(BLUE)Running all tests...$(NC)"
	pytest tests/ -v --tb=short

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

visual-test:
	@echo "=== Running Visual Regression Tests ==="
	pytest tests/e2e/test_visual_regression.py -v -m visual

accessibility-test:
	@echo "=== Running Accessibility Tests ==="
	pytest tests/e2e/test_accessibility.py -v -m accessibility

mutation-test:
	@echo "=== Running Mutation Tests ==="
	bash scripts/run-mutation-tests.sh

# Combined Phase 3 test suite
phase3-tests: visual-test accessibility-test
	@echo "✅ Phase 3 tests complete"

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
	python -c "
from app.core.database import SessionLocal, get_db_stats
from sqlalchemy import text
db = SessionLocal()
stats = get_db_stats(db)
for table, count in stats.items():
    print(f'  {table}: {count} rows')
db.close()
"

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
	python -c "
from app.core.database import SessionLocal
from app.core.config import get_settings
from app.models import *
import sys
print('Available: SessionLocal, get_settings, models')
" -i

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
	python -c "
from app.main import app
import json
with open('docs/openapi.json', 'w') as f:
    json.dump(app.openapi(), f, indent=2)
print('Documentation saved to docs/openapi.json')
"

health-check: ## Check application health
	@echo "$(BLUE)Checking application health...$(NC)"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "$(RED)App not running on localhost:8000$(NC)"

env-check: ## Validate environment variables
	@echo "$(BLUE)Checking environment configuration...$(NC)"
	python -c "
from app.core.config import get_settings
try:
    settings = get_settings()
    print('$(GREEN)✓ Environment configuration valid$(NC)')
    print(f'  App Name: {settings.app_name}')
    print(f'  Environment: {settings.environment}')
    print(f'  Database: {settings.database_url.split(\"@\")[-1] if \"@\" in settings.database_url else \"local\"}')
except Exception as e:
    print(f'$(RED)✗ Configuration error: {e}$(NC)')
    exit(1)
"

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
