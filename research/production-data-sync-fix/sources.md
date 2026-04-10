# Sources & Credibility Assessment

## Source Registry

### S1: Azure Policy States REST API — Response Schema
- **URL**: https://learn.microsoft.com/en-us/rest/api/policyinsights/policy-states/list-query-results-for-subscription?view=rest-policyinsights-2024-10-01
- **Type**: Official Microsoft REST API documentation
- **Tier**: 1 (Highest) — Primary source, official API specification
- **Last Updated**: API Version 2024-10-01
- **Key Finding**: PolicyState schema defines all string fields (`policyDefinitionId`, `policyDefinitionReferenceId`, `policyDefinitionGroupNames`) as type `string` with **no maxLength constraint** specified
- **Relevance**: Directly answers Q1 — proves current `String(500)` column limit is arbitrary

### S2: Azure Policy Initiative Definition Structure
- **URL**: https://learn.microsoft.com/en-us/azure/governance/policy/concepts/initiative-definition-structure
- **Type**: Official Microsoft conceptual documentation
- **Tier**: 1 (Highest) — Primary source, official docs
- **Key Finding**: `policyDefinitionReferenceId` is a user-defined arbitrary string within policy set definitions. Examples show short names like `"allowedLocationsSQL"` but no documented max length. Auto-generated values are ~20 char numeric strings.
- **Relevance**: Confirms `policyDefinitionReferenceId` has no guaranteed upper bound

### S3: SQLAlchemy 2.0 — Using SAVEPOINT
- **URL**: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#using-savepoint
- **Type**: Official SQLAlchemy documentation
- **Tier**: 1 (Highest) — Primary source, official docs
- **Version**: SQLAlchemy 2.0 (current release)
- **Key Finding**: `Session.begin_nested()` is the documented pattern for catching per-instance errors (specifically `IntegrityError`) within a loop without rolling back the entire transaction. Complete code example provided.
- **Relevance**: Directly answers Q2

### S4: SQLAlchemy 2.0 — Session Basics FAQ
- **URL**: https://docs.sqlalchemy.org/en/20/orm/session_basics.html#session-frequently-asked-questions
- **Type**: Official SQLAlchemy documentation
- **Tier**: 1 (Highest) — Primary source, official docs
- **Key Finding**: Session lifecycle should be "separate and external" from data-manipulating functions. Transactions should be kept short.
- **Relevance**: Supports session-per-operation pattern recommendation for Q2

### S5: APScheduler 3.x — BaseScheduler.add_job API Reference
- **URL**: https://apscheduler.readthedocs.io/en/3.x/modules/schedulers/base.html#apscheduler.schedulers.base.BaseScheduler.add_job
- **Type**: Official APScheduler documentation
- **Tier**: 1 (Highest) — Primary source, official API docs
- **Version**: APScheduler 3.11.2.post1
- **Key Finding**: `next_run_time` (datetime) parameter documented as "when to first run the job, regardless of the trigger". Pass `None` to add as paused.
- **Relevance**: Directly answers Q3

### S6: APScheduler 3.x — User Guide (Adding Jobs)
- **URL**: https://apscheduler.readthedocs.io/en/3.x/userguide.html
- **Type**: Official APScheduler documentation
- **Tier**: 1 (Highest) — Primary source
- **Key Finding**: Tip box states "To run a job immediately, omit `trigger` argument when adding the job" (one-shot). For recurring + immediate, use `next_run_time`.
- **Relevance**: Alternative approach for Q3

### S7: SQL Server ALTER TABLE — Change Column Size & Locks
- **URL**: https://learn.microsoft.com/en-us/sql/t-sql/statements/alter-table-transact-sql?view=sql-server-ver16#change-the-size-of-a-column
- **Type**: Official Microsoft SQL Server documentation
- **Tier**: 1 (Highest) — Primary source, official T-SQL reference
- **Key Finding**: 
  - ALTER COLUMN can change NVARCHAR length; new size can't be smaller than max existing data
  - ALTER TABLE acquires schema modify (Sch-M) lock during the change
  - Widening a variable-length column (NVARCHAR) is a **metadata-only operation** — does not rewrite data
  - NVARCHAR columns can remain in indexes when resized
- **Relevance**: Directly answers Q4

### S8: Azure SQL Database DTU-based Service Tiers
- **URL**: https://learn.microsoft.com/en-us/azure/azure-sql/database/service-tiers-dtu?view=azuresql
- **Type**: Official Microsoft Azure documentation
- **Tier**: 1 (Highest) — Primary source
- **Key Finding**: S0 tier provides less than one vCore, uses HDD-based storage. Best for development/testing and infrequently accessed workloads. DDL operations on S0 tier work fine but may queue behind active queries.
- **Relevance**: Context for Q4 about S0 tier limitations

### S9: SQLAlchemy 2.0 — String Type
- **URL**: https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.String
- **Type**: Official SQLAlchemy documentation
- **Tier**: 1 (Highest) — Primary source
- **Key Finding**: `String(length)` maps to VARCHAR. Length is required for CREATE TABLE on most databases. `Text` maps to CLOB/TEXT and is variably sized.
- **Relevance**: Directly answers Q5

### S10: SQLAlchemy 2.0 — Text Type
- **URL**: https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Text
- **Type**: Official SQLAlchemy documentation  
- **Tier**: 1 (Highest) — Primary source
- **Key Finding**: `Text` inherits from `String`, maps to CLOB/TEXT, does not have a length. TEXT objects cannot be indexed on most databases.
- **Relevance**: Directly answers Q5

## Credibility Summary

| Source | Tier | Type | Cross-Validated |
|--------|------|------|-----------------|
| S1 (Azure Policy API) | 1 | Official API spec | ✅ Validated against sample responses |
| S2 (Initiative Structure) | 1 | Official docs | ✅ Validated against S1 |
| S3 (SQLAlchemy SAVEPOINT) | 1 | Official docs | ✅ Code examples verified |
| S4 (SQLAlchemy FAQ) | 1 | Official docs | ✅ Consistent with S3 |
| S5 (APScheduler API) | 1 | Official API docs | ✅ Consistent with S6 |
| S6 (APScheduler Guide) | 1 | Official guide | ✅ Consistent with S5 |
| S7 (ALTER TABLE) | 1 | Official T-SQL ref | ✅ Well-established behavior |
| S8 (Azure SQL Tiers) | 1 | Official Azure docs | ✅ Standard documentation |
| S9 (SQLAlchemy String) | 1 | Official docs | ✅ Consistent with S10 |
| S10 (SQLAlchemy Text) | 1 | Official docs | ✅ Consistent with S9 |

**All 10 sources are Tier 1 (Highest credibility)** — official documentation from Microsoft, SQLAlchemy, and APScheduler projects.
