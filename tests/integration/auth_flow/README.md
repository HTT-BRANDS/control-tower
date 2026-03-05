# Authentication Flow Integration Tests 🔐

Comprehensive end-to-end integration tests for authentication and authorization flows.

## 🎯 What's Tested

### Complete Auth Lifecycle

```
┌─────────────┐
│   Login     │  → Credentials
└─────┬───────┘
      │
      ▼
┌─────────────┐
│   Token     │  → JWT Access + Refresh Token
└─────┬───────┘
      │
      ▼
┌─────────────┐
│  Protected  │  → Authorized Access
│  Endpoint   │
└─────────────┘
```

## 📊 Test Coverage: 23 Tests

| Module | Tests | Focus |
|--------|-------|-------|
| **test_login.py** | 3 | Login flow, credentials validation, environment checks |
| **test_token_validation.py** | 5 | Valid, invalid, expired, missing, malformed tokens |
| **test_token_refresh.py** | 5 | Refresh token lifecycle and validation |
| **test_tenant_access.py** | 4 | Multi-tenant authorization and access control |
| **test_logout.py** | 3 | Logout flow and stateless JWT behavior |
| **test_auth_endpoints.py** | 3 | Health check, user info, Azure AD config |

## 🚀 Quick Start

### Run All Auth Flow Tests
```bash
uv run pytest tests/integration/auth_flow/ -v
```

### Run Specific Test Module
```bash
uv run pytest tests/integration/auth_flow/test_login.py -v
```

### Run with Coverage
```bash
uv run pytest tests/integration/auth_flow/ -v \
  --cov=app.api.routes.auth \
  --cov-report=term-missing
```

### Run Specific Test Class
```bash
uv run pytest tests/integration/auth_flow/test_token_validation.py::TestTokenValidation -v
```

### Run Single Test
```bash
uv run pytest tests/integration/auth_flow/test_login.py::TestLoginFlow::test_login_success_and_access_protected_endpoint -v
```

## 📁 File Organization

Each file is **focused and concise** (under 600 lines):

- **conftest.py** - Shared test helpers (`create_test_token`, `create_test_refresh_token`)
- **test_login.py** - Full login flow tests
- **test_token_validation.py** - Token validation scenarios
- **test_token_refresh.py** - Token refresh lifecycle
- **test_tenant_access.py** - Multi-tenant authorization
- **test_logout.py** - Logout and token revocation
- **test_auth_endpoints.py** - Utility endpoints

## 🔑 Key Features

### ✅ Real End-to-End Flows
```python
# Example: Full login flow
response = client.post("/api/v1/auth/login", data={...})
token = response.json()["access_token"]

response = client.get("/api/v1/auth/me", 
                      headers={"Authorization": f"Bearer {token}"})
assert response.status_code == 200
```

### ✅ Multi-Tenant Authorization
```python
# User A can access Tenant 1 ✅
# User A CANNOT access Tenant 2 ❌
# Admin can access ALL tenants ✅
```

### ✅ Token Lifecycle Testing
```python
# Valid token → Access granted
# Expired token → 401 Unauthorized
# Invalid token → 401 Unauthorized
# Refresh token → New access token
```

## 🛠️ Test Utilities

### Token Generators

```python
from tests.integration.auth_flow.conftest import create_test_token, create_test_refresh_token

# Create valid access token
token = create_test_token(
    user_id="user-123",
    roles=["admin"],
    tenant_ids=["tenant-1", "tenant-2"],
)

# Create expired token for testing
expired_token = create_test_token(
    user_id="user-123",
    expired=True,
)

# Create refresh token
refresh_token = create_test_refresh_token(user_id="user-123")
```

## 🎓 Best Practices Demonstrated

### 1. Descriptive Test Names
```python
def test_login_success_and_access_protected_endpoint(...):
    """Login with valid credentials → get token → access protected endpoint."""
```

### 2. FastAPI Dependency Overrides (Not Patching!)
```python
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = lambda: test_user
app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz
```

### 3. Proper Cleanup
```python
try:
    # Test logic here
finally:
    app.dependency_overrides.clear()
```

### 4. Realistic Test Data
```python
# Uses shared fixtures from tests/integration/conftest.py
- seeded_db - Pre-populated test database
- test_tenant_id - Consistent tenant IDs
- test_user - Pre-configured users
```

## 📝 Test Patterns

### Arrange-Act-Assert

```python
def test_example(self, seeded_db):
    # ARRANGE: Set up test state
    def override_get_db():
        yield seeded_db
    app.dependency_overrides[get_db] = override_get_db
    
    # ACT: Execute the test
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/me")
    
    # ASSERT: Verify results
    assert response.status_code == 200
    
    # CLEANUP
    app.dependency_overrides.clear()
```

## 🔍 What's NOT Covered

These areas require Azure AD infrastructure or complex mocking:

- Azure AD OAuth2 callback flows (requires live Azure AD)
- Authorization code exchange with Microsoft
- User-tenant mapping sync from Azure AD groups
- PKCE (Proof Key for Code Exchange) flows

For these, consider:
- E2E tests with test Azure AD tenant
- Contract testing with Pact
- Manual testing in staging environment

## 🐛 Known Limitations

### Stateless JWT Logout
```python
# After logout, tokens remain technically valid
# This is by design for stateless JWT systems
# For true revocation, implement token blacklist (Redis/DB)
```

### Development-Only Login
```python
# Direct username/password login only works in development
# Production uses Azure AD OAuth2
@pytest.mark.skipif(
    not get_settings().is_development,
    reason="Direct login only available in development mode"
)
```

## 📊 Coverage Report

**Current Coverage:** 66% of `app/api/routes/auth.py`

**Covered:**
- ✅ Login endpoint (dev mode)
- ✅ Token refresh endpoint
- ✅ User info endpoint
- ✅ Logout endpoint
- ✅ Health check endpoint
- ✅ Azure AD config endpoint

**Not Covered:**
- ❌ Azure AD OAuth2 callback
- ❌ Authorization code exchange
- ❌ User-tenant sync from Azure AD

## 🚦 Running in CI/CD

These tests are fast and reliable for CI/CD:

```yaml
# .github/workflows/test.yml
- name: Run Auth Flow Tests
  run: |
    uv run pytest tests/integration/auth_flow/ \
      -v \
      --cov=app.api.routes.auth \
      --cov-fail-under=60 \
      --junit-xml=auth-flow-results.xml
```

## 🎯 Future Enhancements

1. **Token Blacklist Tests** - When server-side revocation is implemented
2. **Rate Limiting Tests** - Auth endpoint rate limiting
3. **Concurrent Request Tests** - Token validation under load
4. **RBAC Permission Tests** - Fine-grained permission testing
5. **MFA Flow Tests** - Multi-factor authentication flows

---

**Created by:** Richard the Code Puppy 🐶  
**Date:** March 2026  
**Status:** ✅ All 23 tests passing!  
**Code Quality:** Files average 119 lines (well under 600 limit!)  
