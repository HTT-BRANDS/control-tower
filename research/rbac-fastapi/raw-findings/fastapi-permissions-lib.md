# fastapi-permissions Library — Raw Findings

**Source**: https://github.com/holgi/fastapi-permissions
**Tier**: 3 (Community Library)
**Retrieved**: 2026-04-14
**GitHub Stars**: ~500+
**Last Significant Update**: ~2022
**License**: Unknown (not clearly stated in README)

## Library Overview

Pyramid-inspired ACL (Access Control List) system for FastAPI. Focuses on **row-level permissions** — determining access based on both the user's identity AND the resource's state.

## Key Concepts

### 1. ACL on Resources

Resources define access control via `__acl__` attribute:

```python
class Item(BaseModel):
    name: str
    owner: str

    def __acl__(self):
        return [
            (Allow, Authenticated, "view"),
            (Allow, "role:admin", "edit"),
            (Allow, f"user:{self.owner}", "delete"),
        ]
```

### 2. Principals

Users are identified by a list of "principal" strings:

```python
def get_active_principals(user):
    principals = [Everyone, Authenticated]
    principals.append(f"user:{user.name}")
    principals.extend(f"role:{role}" for role in user.roles)
    return principals
```

### 3. Permission Checking

```python
Permission = configure_permissions(get_active_user_principals)

@app.get("/item/{item_id}")
async def show_item(item: Item = Permission("view", get_item)):
    return {"item": item}
```

### 4. Programmatic Checking

```python
from fastapi_permissions import has_permission

if has_permission(user_principals, "eat", apple_acl):
    print("Yum!")
```

## Why NOT Recommended for Our Project

1. **Unmaintained**: Last significant commit ~2022, no recent activity
2. **Wrong abstraction level**: Designed for row-level ACL (per-resource permissions), not role-based module permissions
3. **Synchronous only**: No async support
4. **Limited adoption**: ~500 stars, few production users
5. **Author's own recommendation**: "Use scopes until you need something different"
6. **Pyramid dependency**: Conceptual dependency on Pyramid's ACL model — unfamiliar to most developers
7. **PyPI availability**: PyPI was returning Cloudflare challenges during research — reliability concern

## When It WOULD Be Useful

- If we needed per-resource permissions (e.g., "user X can edit document Y but not document Z")
- If we needed state-dependent permissions (e.g., "draft documents can be edited by authors, published documents only by admins")
- We don't have either of these requirements — our permissions are module-level, not resource-level
