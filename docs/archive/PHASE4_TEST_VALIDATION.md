# Phase 4 Test Execution Guide

**Purpose:** Manual test execution commands for Phase 4 validation  
**Date:** 2026-03-31  
**Status:** Ready to Execute

---

## Prerequisites

```bash
# Ensure virtual environment is active
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install test dependencies
pip install pytest pytest-cov pytest-asyncio mutmut
```

---

## 1. Mutation Testing

### Quick Test (10% sample)
```bash
# Run mutation testing on 10% of codebase
mutmut run --paths-to-mutate=app/services --runner="pytest tests/ -x -q" --tests-dir=tests/
mutmut results
```

### Full Test (Recommended)
```bash
# Run full mutation test suite
mutmut run --runner="pytest tests/ --tb=no -q" --tests-dir=tests/
mutmut html
mutmut results
```

### Expected Results
- Mutation score: >70% for critical paths
- Survivors: <30% of mutations
- Timeout mutants: <10%

---

## 2. Coverage Analysis

### Generate Coverage Report
```bash
# Run tests with coverage
pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html  # Mac
# or
start htmlcov/index.html  # Windows
# or
xdg-open htmlcov/index.html  # Linux
```

### Coverage Targets
```bash
# Check specific module coverage
pytest tests/unit/test_services/ --cov=app/services --cov-report=term-missing

# Check API routes coverage
pytest tests/unit/test_routes/ --cov=app/api/routes --cov-report=term-missing
```

### Expected Results
- Overall: >80% (current: 84%)
- Services: >85%
- Routes: >90%

---

## 3. Type Validation

### Check Type Hint Coverage
```bash
# Install mypy if not already
pip install mypy

# Run type checking
mypy app/services/compliance_service.py app/services/sync_service.py --ignore-missing-imports

# Full type check (optional)
mypy app/ --ignore-missing-imports --exclude=app/models
```

### Expected Results
- compliance_service.py: 0 errors
- sync_service.py: 0 errors
- Type coverage: 84%+

---

## 4. Full Test Suite

### Unit Tests
```bash
# Run all unit tests
pytest tests/unit/ -v --tb=short

# Run with coverage
pytest tests/unit/ --cov=app --cov-report=term
```

### Integration Tests
```bash
# Run integration tests
pytest tests/integration/ -v --tb=short
```

### Schema Validation Tests
```bash
# Test new Pydantic schemas
pytest tests/unit/test_schemas/ -v -k "compliance or sync"
```

---

## 5. Quick Validation (All-in-One)

```bash
#!/bin/bash
# save as: scripts/phase4_validate.sh

echo "=== Phase 4 Validation ==="
echo ""

echo "1. Running unit tests with coverage..."
pytest tests/unit/ --cov=app --cov-report=term -q

echo ""
echo "2. Type checking target files..."
mypy app/services/compliance_service.py app/services/sync_service.py --ignore-missing-imports

echo ""
echo "3. Checking schema validation..."
python -c "from app.schemas.compliance import ComplianceTrend, ComplianceGap; from app.schemas.sync import SyncJob, SyncStatus, SyncResult; print('✅ All schemas import successfully')"

echo ""
echo "=== Validation Complete ==="
```

---

## Makefile Commands

```bash
# Use the Makefile targets
make phase4-tests        # Run Phase 4 specific tests
make mutation-test       # Run mutation testing
make test-coverage       # Generate coverage report
make type-check          # Run mypy type checking
```

---

## Expected Execution Time

| Command | Time | Memory |
|---------|------|--------|
| Unit tests | 2-3 min | ~500MB |
| Coverage | 3-4 min | ~1GB |
| Mutation (10%) | 10-15 min | ~2GB |
| Mutation (full) | 2-4 hours | ~4GB |
| Type check | 30 sec | ~200MB |

---

## Success Criteria

- [ ] All unit tests pass
- [ ] Coverage >= 84%
- [ ] Type hints validated
- [ ] Schemas import correctly
- [ ] Mutation score >70% (if run)

---

## Troubleshooting

### Issue: mutmut not found
```bash
pip install mutmut
```

### Issue: Coverage too low
```bash
# Check which files need attention
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

### Issue: mypy errors on dependencies
```bash
# Add to pyproject.toml
[tool.mypy]
ignore_missing_imports = true
```

---

**Status:** Ready for execution 🚀
