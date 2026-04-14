# PyCasbin Evaluation — Raw Findings

**Source**: https://github.com/apache/casbin-pycasbin
**Tier**: 2 (Established Open Source — Apache Foundation)
**Retrieved**: 2026-04-14
**License**: Apache 2.0
**Status**: Production-ready, active development

## Overview

Casbin is a general-purpose access control library supporting ACL, RBAC, ABAC, and hybrid models. PyCasbin is the Python implementation, now under the Apache Software Foundation.

## RBAC with Domains/Tenants Model

The model most relevant to our use case:

**Model file** (`rbac_model_with_domains.conf`):
```ini
[request_definition]
r = sub, dom, obj, act

[policy_definition]
p = sub, dom, obj, act

[role_definition]
g = _, _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub, r.dom) && r.dom == p.dom && r.obj == p.obj && r.act == p.act
```

**Policy file** (`rbac_policy_with_domains.csv`):
```csv
p, admin, tenant1, costs, read
p, admin, tenant1, costs, write
p, admin, tenant2, costs, read
p, viewer, tenant1, costs, read

g, alice, admin, tenant1
g, bob, viewer, tenant1
g, alice, viewer, tenant2
```

**Usage**:
```python
import casbin

e = casbin.Enforcer("model.conf", "policy.csv")

# Check: can alice read costs in tenant1?
e.enforce("alice", "tenant1", "costs", "read")  # True

# Check: can alice write costs in tenant2?
e.enforce("alice", "tenant2", "costs", "write")  # False (she's only viewer there)
```

## Async Support

```python
e = casbin.AsyncEnforcer("model.conf", adapter)
await e.load_policy()
result = e.enforce("alice", "tenant1", "costs", "read")
```

## SQLAlchemy Adapter

Available via `casbin-sqlalchemy-adapter`:
```python
from casbin_sqlalchemy_adapter import Adapter

adapter = Adapter("postgresql://...")
e = casbin.Enforcer("model.conf", adapter)
```

## Why NOT Recommended for Our Project

### 1. Complexity vs Need
- **Our need**: 4 roles × ~30 permissions × 5 tenants = ~600 policy rules
- **Casbin's strength**: Dynamic policy changes, complex policy logic, thousands of rules
- **Mismatch**: We can represent our entire RBAC in ~50 lines of Python

### 2. Operational Overhead
- Separate policy file or DB table to manage
- Policy cache invalidation needed
- Model file is a separate DSL to learn
- Debugging policy decisions requires understanding Casbin's matcher engine

### 3. Dependency Risk
- Adds `pycasbin` dependency (~5MB)
- Optional: `casbin-sqlalchemy-adapter` for DB storage
- Version compatibility with our SQLAlchemy version

### 4. Learning Curve
- Team needs to learn Casbin's PERM metamodel (Policy, Effect, Request, Matchers)
- Custom matcher syntax
- Role hierarchy definitions

### 5. When Casbin WOULD Make Sense
- 50+ roles with complex inheritance
- Dynamic policy changes (admin UI for policy management)
- ABAC requirements (attribute-based conditions)
- Cross-service policy enforcement
- We have none of these requirements

## Verdict

**Don't adopt PyCasbin.** It's a well-maintained, powerful library — but it solves problems we don't have. A simple `dict[str, frozenset[str]]` mapping roles to permissions is equivalent to Casbin's RBAC model for our scale, with zero dependencies and instant comprehension.
