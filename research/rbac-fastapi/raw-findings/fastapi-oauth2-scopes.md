# FastAPI OAuth2 Scopes — Raw Findings

**Source**: https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/
**Tier**: 1 (Official Documentation)
**Retrieved**: 2026-04-14

## Key Patterns Extracted

### 1. SecurityScopes Class

FastAPI provides `SecurityScopes` as a special injectable parameter that automatically aggregates scope requirements from the dependency chain:

```python
from fastapi import Security
from fastapi.security import SecurityScopes

async def get_current_user(
    security_scopes: SecurityScopes,  # Auto-populated by FastAPI
    token: Annotated[str, Depends(oauth2_scheme)],
):
    # security_scopes.scopes = list of ALL required scopes from dependency chain
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(status_code=401, detail="Not enough permissions")
```

### 2. Security() vs Depends()

`Security()` is a subclass of `Depends()` that adds scope declaration:

```python
# Depends() — no scope requirements
@app.get("/status")
async def status(user: User = Depends(get_current_user)):
    ...

# Security() — declares scope requirements
@app.get("/items")
async def items(
    user: User = Security(get_current_active_user, scopes=["items"]),
):
    ...
```

### 3. Scope Aggregation Through Dependency Chain

Scopes accumulate through the dependency tree:

```
/users/me/items/ → scopes=["items"]
  └─ get_current_active_user → scopes=["me"]
      └─ get_current_user → security_scopes.scopes = ["me", "items"]
```

### 4. OAuth2PasswordBearer with Scopes

Scopes are declared in the OAuth2 scheme for OpenAPI docs:

```python
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={
        "me": "Read information about the current user.",
        "items": "Read items.",
    },
)
```

### 5. Scope Format Convention

FastAPI docs use format examples:
- `users:read`
- `items:write`
- `instagram_basic` (Facebook)
- `https://www.googleapis.com/auth/drive` (Google)

No spaces allowed. Colon separator is common but not required by OAuth2 spec.

## Relevance to Our Project

- We should NOT use `SecurityScopes` directly — it's designed for OAuth2 scope-based auth where scopes are in the token. Our use case is role-to-permission resolution server-side.
- However, the `Security()` dependency pattern and scope string format are directly applicable.
- Our `require_permissions()` dependency is conceptually the same pattern but resolves permissions from roles instead of reading them from the token.

## FastAPI Version Note

All examples are from FastAPI v0.135.3 (current as of 2026-04-14). The `Security` and `SecurityScopes` APIs have been stable since FastAPI v0.50+.
