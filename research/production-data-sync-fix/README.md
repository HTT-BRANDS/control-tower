# Production Data Sync Fix — Research Summary

**Date**: 2026-04-10
**Researcher**: web-puppy-a11d20
**Context**: Azure Governance Platform — production compliance sync crashes due to Azure Policy API data exceeding database column lengths

## Executive Summary

This research addresses five technical questions arising from a production data sync failure where Azure Policy API responses contained field values exceeding the database column widths defined in the `PolicyState` model, causing `DataError` / `StringDataRightTruncation` failures that crashed the entire sync job.

### Key Findings

| # | Question | Critical Finding |
|---|----------|-----------------|
| 1 | Azure Policy API field lengths | **No max lengths documented.** All string fields are unbounded `string` type in the REST API spec. Current `String(500)` is an arbitrary limit. |
| 2 | SQLAlchemy session error handling | **`session.begin_nested()` (SAVEPOINT)** is the officially documented pattern for per-record error handling in loops. |
| 3 | APScheduler immediate execution | **`next_run_time=datetime.now(tz)`** is the documented parameter. Alternatively, omit `trigger` for one-shot immediate runs. |
| 4 | Alembic ALTER COLUMN on Azure SQL S0 | **Widening NVARCHAR is metadata-only** — fast and safe. Requires brief Sch-M lock. Safe for S0 tier with low concurrency. |
| 5 | String(N) vs Text columns | **Use String(N) with defensive truncation** for indexed/filtered columns. Use Text for truly unbounded data like `resource_id`. |

### Top Priority Recommendations

1. **Widen `policy_definition_id` to `String(1000)` or `Text`** — ARM resource IDs can be 200-500+ chars
2. **Add `[:N]` defensive truncation** before DB insert for all API-sourced string fields
3. **Wrap per-subscription processing in `session.begin_nested()`** so one bad record doesn't crash the entire sync
4. **Add `next_run_time=datetime.now(UTC)` to IntervalTrigger jobs** for immediate first sync on startup
5. **Create Alembic migration** to widen columns — safe for production Azure SQL S0

## Files in This Research

| File | Description |
|------|-------------|
| `README.md` | This executive summary |
| `sources.md` | All sources with credibility assessments |
| `analysis.md` | Multi-dimensional analysis of all five questions |
| `recommendations.md` | Project-specific action items with priority |
| `raw-findings/azure-policy-api-fields.md` | Azure Policy REST API field schema details |
| `raw-findings/sqlalchemy-session-patterns.md` | SQLAlchemy session and SAVEPOINT documentation |
| `raw-findings/apscheduler-immediate-exec.md` | APScheduler next_run_time documentation |
| `raw-findings/azure-sql-alter-column.md` | ALTER COLUMN behavior on Azure SQL |
| `raw-findings/string-vs-text-columns.md` | SQLAlchemy String vs Text comparison |
