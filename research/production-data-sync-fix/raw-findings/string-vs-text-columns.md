# String(N) vs Text Columns — Best Practices

**Source**: SQLAlchemy 2.0 Official Documentation (Tier 1)  
**URLs**:
- https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.String
- https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Text

## SQLAlchemy Type Documentation

### String Type

From official docs:

> **class sqlalchemy.types.String**  
> The base for all string and character types.
>
> In SQL, corresponds to VARCHAR.
>
> The *length* field is usually required when the *String* type is used within a CREATE TABLE
> statement, as VARCHAR requires a length on most databases.

Constructor:
```python
sqlalchemy.types.String.__init__(length: int | None = None, collation: str | None = None)
```

> **length** – optional, a length for the column for use in DDL and CAST expressions. May be
> safely omitted if no `CREATE TABLE` will be issued. Certain databases may require a
> `length` for use in DDL, and will raise an exception when the `CREATE TABLE` DDL is
> issued if a `VARCHAR` with no length is included. Whether the value is interpreted as
> bytes or characters is database specific.

### Text Type

From official docs:

> **class sqlalchemy.types.Text**  
> *inherits from sqlalchemy.types.String*
>
> A variably sized string type.
>
> In SQL, usually corresponds to CLOB or TEXT. In general, TEXT objects do not have a length;
> while some databases will accept a length argument here, it will be rejected by others.

### Unicode Note

> In most cases, the **Unicode** or **UnicodeText** datatypes should be used for a `Column` that
> expects to store non-ascii data. These datatypes will ensure that the correct types are
> used on the database.

## SQL Server / Azure SQL Mapping

| SQLAlchemy | SQL Server DDL | Storage | Max Size | Indexable |
|-----------|----------------|---------|----------|-----------|
| `String(N)` | `NVARCHAR(N)` | In-row (≤8000 bytes) | N chars (2N bytes) | ✅ Yes (key ≤900 bytes = 450 chars) |
| `String()` (no N) | `NVARCHAR(max)` | In-row if ≤8000, else off-row | 2^31-1 bytes (~1B chars) | ❌ Not in index key |
| `Text` | `NVARCHAR(max)` | Same as above | 2^31-1 bytes | ❌ Not in index key |

### NVARCHAR(N) vs NVARCHAR(max) on SQL Server

- **NVARCHAR(N)**: Max N = 4000 characters. Stored in-row. Can be indexed. Value truncated/errored if exceeds N.
- **NVARCHAR(max)**: No practical limit. Stored in-row if ≤ 4000 chars, off-row otherwise. Cannot be used as index key column.

### Performance Implications on Azure SQL S0 (HDD-based)

| Aspect | NVARCHAR(N) | NVARCHAR(max) |
|--------|------------|---------------|
| In-row storage | Always (up to 8000 bytes) | Only if value ≤ 4000 chars |
| Index support | Full index key support | Cannot be index key |
| WHERE clause | Efficient with index | Full scan required |
| Storage overhead | Minimal | Pointer overhead for off-row |
| HDD impact | Single I/O for in-row | Extra I/O for off-row LOB |

## Best Practices for External API Data

### The Problem

External APIs (like Azure Policy) return data with no guaranteed max length. This creates a tension:
1. **Bounded columns** (`String(N)`) provide schema safety but risk `DataError` on unexpected lengths
2. **Unbounded columns** (`Text`) never error but lose indexability and schema discipline

### Recommended Strategy: Defense in Depth

#### Layer 1: Application-Level Truncation (REQUIRED)
```python
def safe_str(value: str | None, max_len: int, field_name: str = "") -> str | None:
    if value is None:
        return None
    if len(value) > max_len:
        logger.warning(f"Truncating {field_name}: {len(value)} → {max_len}")
        return value[:max_len]
    return value
```

#### Layer 2: Generous Column Widths (RECOMMENDED)
- Set column widths 2-3x wider than the longest expected value
- Use knowledge of the data format (ARM paths, GUIDs, names) to estimate
- For `policy_definition_id`: ARM paths top out ~200-300 chars → use `String(1000)`
- For `policy_name`: user-defined but typically short → use `String(500)`

#### Layer 3: Text for Truly Unbounded Data (SELECTIVE)
Use `Text` only when:
- The column is never filtered/indexed (e.g., `recommendation`, `resource_id` in our schema)
- The data is genuinely unbounded (free-text descriptions, JSON blobs)
- You don't need schema-level length validation

### Decision Framework

```
Is this column filtered, indexed, or used in WHERE clauses?
├── YES → String(N) with defensive truncation
│         Choose N based on data analysis + safety margin
│         Add application-level truncation before insert
│
└── NO → Is the data format predictable?
         ├── YES → String(N) with generous width
         │         Still add application-level truncation
         │
         └── NO → Text
                   No truncation needed, but log unexpectedly long values
```

## Application to Our PolicyState Model

| Column | Used in queries? | Data format | Decision |
|--------|-----------------|-------------|----------|
| `policy_definition_id` | Yes (aggregation key) | ARM resource path, ~100-300 chars | `String(1000)` + truncation |
| `policy_name` | Yes (display, search) | User-defined reference ID | `String(500)` + truncation |
| `policy_category` | Yes (filter/group) | Comma-joined group names | `String(1000)` + truncation |
| `compliance_state` | Yes (filter) | Enum: Compliant/NonCompliant/Exempt | `String(50)` (keep) |
| `resource_id` | Display only | ARM resource path (very long) | `Text` (keep) |
| `recommendation` | Display only | Free text | `Text` (keep) |
