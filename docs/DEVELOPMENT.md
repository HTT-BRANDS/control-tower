# Azure Governance Platform - Developer Guide

> **Version:** 1.0  
> **Last Updated:** July 2025  
> **Audience:** Developers contributing to the platform

---

## Table of Contents

1. [Development Environment Setup](#1-development-environment-setup)
2. [Project Structure](#2-project-structure)
3. [Running Tests](#3-running-tests)
4. [Adding New Sync Modules](#4-adding-new-sync-modules)
5. [Code Style Guidelines](#5-code-style-guidelines)
6. [Commit Message Conventions](#6-commit-message-conventions)
7. [Pull Request Process](#7-pull-request-process)
8. [Debugging](#8-debugging)
9. [Database Migrations](#9-database-migrations)

---

## 1. Development Environment Setup

### 1.1 Prerequisites

| Tool | Version | Installation |
|------|---------|--------------|
| Python | 3.11+ | python.org or pyenv |
| uv | Latest | curl -LsSf https://astral.sh/uv/install.sh \| sh |
| Git | Latest | git-scm.com |
| Azure CLI | 2.50+ | brew install azure-cli |
| VS Code | Latest | Recommended IDE |

### 1.2 Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd control-tower

# Create virtual environment
uv venv
source .venv/bin/activate

# Install with dev dependencies
uv pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
# Edit .env with your credentials

# Initialize database
python -c "from app.core.database import init_db; init_db()"

# Run the application
uvicorn app.main:app --reload
```

### 1.3 VS Code Configuration

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "ruff",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"]
}
```

---

## 2. Project Structure

```
app/
├── api/                      # API layer
│   ├── routes/               # FastAPI route handlers
│   └── services/             # Business logic
├── core/                     # Core infrastructure
│   ├── sync/                 # Sync job implementations
│   ├── cache.py
│   ├── config.py
│   ├── database.py
│   └── scheduler.py
├── services/                 # Service integrations
│   ├── lighthouse_client.py  # Lighthouse API client
│   ├── backfill_service.py   # Data backfill operations
│   ├── parallel_processor.py # Parallel task processing
│   ├── retention_service.py  # Data retention policies
│   ├── riverside_sync.py     # Riverside data sync
│   ├── teams_webhook.py      # Teams webhook notifications
│   ├── email_service.py      # Email notifications
│   └── theme_service.py      # Theme management
├── preflight/                # Preflight check system
├── alerts/                   # Alert management
├── models/                   # SQLAlchemy models
├── schemas/                  # Pydantic schemas
├── templates/                # Jinja2 templates
├── static/
│   ├── css/
│   │   ├── accessibility.css # Accessibility styles
│   │   ├── dark-mode.css     # Dark mode theme
│   │   ├── theme.css         # Base theme styles
│   │   └── riverside.css     # Riverside-specific styles
│   └── js/
│       ├── darkMode.js       # Dark mode toggle logic
│       └── navigation/       # Navigation components
└── main.py                   # Application entry point
```

---

## 3. Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_tenants.py

# Run with verbose output
pytest -v

# Run with fail-fast
pytest -x
```

---

## 4. Adding New Sync Modules

1. Create sync implementation in `app/core/sync/`
2. Add to scheduler in `app/core/scheduler.py`
3. Add API route in `app/api/routes/`
4. Update router exports in `app/api/routes/__init__.py`
5. Write tests

---

## 5. Code Style Guidelines

We use:
- **ruff** for linting and formatting
- **mypy** for type checking
- **pytest** for testing

### Key Rules

- Line length: 100 characters
- Use type hints
- Docstrings for all public functions
- Follow PEP 8

```bash
# Run linting
ruff check .

# Run type checking
mypy app/

# Fix auto-fixable issues
ruff check . --fix
```

---

## 6. Commit Message Conventions

Format: `type(scope): description`

Types:
- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation
- **style**: Code style (formatting)
- **refactor**: Code refactoring
- **test**: Tests
- **chore**: Maintenance

Examples:
```
feat(costs): add anomaly detection
docs(api): update endpoint documentation
fix(sync): handle rate limiting errors
```

---

## 7. Pull Request Process

1. **Create a branch**: `git checkout -b feature/description`
2. **Make changes**: Write code and tests
3. **Run quality checks**: `ruff check . && mypy app/ && pytest`
4. **Commit**: Follow commit message conventions
5. **Push**: `git push origin feature/description`
6. **Create PR**: Include description and link to issue
7. **Review**: Address review comments
8. **Merge**: Squash merge after approval

### PR Requirements

- [ ] Tests pass
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No linting errors

---

## 8. Debugging

### Enable Debug Mode

```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG
```

### Common Debug Commands

```bash
# Check application logs
uvicorn app.main:app --reload --log-level debug

# Test specific endpoint
curl -v http://localhost:8000/health

# Database inspection
sqlite3 data/governance.db ".tables"
```

---

## 9. Database Migrations

The application uses SQLAlchemy for database management.

```python
# Add new model to app/models/
# Import in app/models/__init__.py
# Initialize will auto-create tables

from app.core.database import init_db
init_db()
```

---

**Related Documents:**
- [API Documentation](./API.md)
- [Implementation Guide](./IMPLEMENTATION_GUIDE.md)
- [Architecture Overview](../ARCHITECTURE.md)
