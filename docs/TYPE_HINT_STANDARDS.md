# Type Hint Standards

## Requirements

All public functions in the Azure Governance Platform must have comprehensive type hints for:
- All parameters
- Return types
- Generic types where applicable

## Standards

### Python Version Compatibility

Use Python 3.10+ syntax for type hints:
- Use `str | None` instead of `Optional[str]`
- Use `list[Type]` instead of `List[Type]`
- Use `dict[Key, Value]` instead of `Dict[Key, Value]`

For backwards compatibility with Python 3.9, use `from __future__ import annotations`.

### Function Signatures

All public functions must follow this pattern:

```python
async def get_resources(
    self,
    tenant_id: str,
    resource_type: str | None = None,
    tags: dict[str, str] | None = None,
) -> list[ResourceSummary]:
    """Get resources with optional filtering.

    Args:
        tenant_id: The tenant ID to query (required)
        resource_type: Optional resource type filter
        tags: Optional tag filters as key-value pairs

    Returns:
        List of ResourceSummary objects matching the filters

    Raises:
        ValueError: If tenant_id is empty or invalid
    """
    pass
```

### Type Hint Guidelines

1. **Required Parameters**: No default value, must include type
   ```python
   tenant_id: str
   ```

2. **Optional Parameters**: Use `| None` with default `= None`
   ```python
   start_date: str | None = None
   ```

3. **Boolean Flags**: Include type and default
   ```python
   include_guests: bool = False
   ```

4. **Collection Types**: Use generic syntax
   ```python
   tenant_ids: list[str]
   results: dict[str, IdentityStats]
   ```

5. **Avoid Any**: Use specific types instead of `Any` when possible
   - Use `dict[str, object]` for flexible dictionaries
   - Create TypedDict for structured dicts
   - Use Union types for multiple possibilities

### Examples by Module

#### Identity Service

```python
async def get_user_summary(
    self,
    tenant_id: str,
    include_guests: bool = False,
) -> UserSummary:
    """Get user summary for a tenant."""
    pass

async def get_identity_stats(
    self,
    tenant_ids: list[str],
) -> dict[str, IdentityStats]:
    """Get identity statistics across multiple tenants."""
    pass
```

#### Cost Service

```python
async def get_cost_breakdown(
    self,
    tenant_id: str,
    group_by: str = "service",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[CostBreakdown]:
    """Get cost breakdown grouped by service, resource, or tag."""
    pass
```

### Coverage Reporting

Run the type hint coverage analysis:

```bash
# Count functions with/without type hints
echo "Functions without return type hints:"
grep -r "def " app/api/services/*.py | grep -v '\->' | wc -l

echo "Functions with return type hints:"
grep -r "def " app/api/services/*.py | grep '\->' | wc -l
```

### Target: 100% Type Hint Coverage

All public functions in service modules should have complete type annotations.

## Current Status

| Module | Functions | With Hints | Coverage |
|--------|-----------|------------|----------|
| identity_service.py | 12 | 3 | 25% |
| cost_service.py | 13 | 4 | 31% |
| All services | 289 | 166 | 57% |

## Tools

- **mypy**: Static type checking
- **ruff**: Linting with type hint checks
- **pyright**: Alternative type checker

Run type checking:
```bash
mypy app/api/services/
pyright app/api/services/
```
