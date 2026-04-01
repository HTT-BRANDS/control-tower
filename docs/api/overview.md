# API Reference

## Base URL

```
Production: https://app-governance-prod.azurewebsites.net
Staging:    https://app-governance-staging-xnczpwyv.azurewebsites.net
```

## Authentication

All API requests require **Bearer token** (JWT):

```http
Authorization: Bearer <jwt_token>
```

Tokens obtained through Azure AD B2C OIDC flow.

---

## Response Format

### Success (200 OK)

```json
{
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150
  }
}
```

### Error (4xx/5xx)

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource was not found",
    "details": { ... }
  }
}
```

---

## Rate Limiting

- **Authenticated:** 1000 requests/hour
- **Anonymous:** 100 requests/hour

Headers:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

---

## Endpoints

### Core

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health |
| `/api/v1/status` | GET | API status |
| `/docs` | GET | Swagger UI |
| `/openapi.json` | GET | OpenAPI spec |

### Tenants

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/tenants` | GET | List tenants |
| `/api/v1/tenants` | POST | Create tenant |
| `/api/v1/tenants/{id}` | GET | Get tenant |
| `/api/v1/tenants/{id}` | PUT | Update tenant |
| `/api/v1/tenants/{id}` | DELETE | Delete tenant |

### Resources

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/resources` | GET | List resources |
| `/api/v1/resources/{id}` | GET | Get resource |
| `/api/v1/resources/sync` | POST | Trigger sync |

### Costs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/costs/summary` | GET | Cost summary |
| `/api/v1/costs/trends` | GET | Cost trends |
| `/api/v1/costs/optimization` | GET | Recommendations |

### Compliance

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/compliance/score` | GET | Compliance score |
| `/api/v1/compliance/gaps` | GET | Compliance gaps |
| `/api/v1/compliance/reports` | GET | Generate reports |

---

## Interactive Documentation

**Production:** https://app-governance-prod.azurewebsites.net/docs

Features:
- Try endpoints in browser
- See request/response examples
- Download OpenAPI spec

---

## Code Examples

### Python

```python
import requests

BASE_URL = "https://app-governance-prod.azurewebsites.net"
headers = {"Authorization": f"Bearer {token}"}

response = requests.get(f"{BASE_URL}/api/v1/resources", headers=headers)
data = response.json()
```

### cURL

```bash
# Health check (no auth)
curl https://app-governance-prod.azurewebsites.net/health

# List resources (with auth)
curl -H "Authorization: Bearer $TOKEN" \
  https://app-governance-prod.azurewebsites.net/api/v1/resources

# Create tenant
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Tenant"}' \
  https://app-governance-prod.azurewebsites.net/api/v1/tenants
```

---

<p align="center">
  <small>API Reference v1.8.1 | OpenAPI Spec: /openapi.json</small>
</p>
