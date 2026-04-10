# OpenAPI Examples

This directory contains sample requests and responses for the Azure Governance Platform API.
These examples are used in the Swagger UI documentation to help developers understand
the API structure and expected formats.

## Structure

- `requests/` - Sample API request bodies
- `responses/` - Sample API response bodies
- `auth/` - Authentication examples

## Using These Examples

The examples are automatically loaded into the Swagger UI documentation when the application
starts. They provide:

- **Request/Response Format**: JSON structure examples
- **Field Descriptions**: What each field represents
- **Value Ranges**: Acceptable values for enums and ranges
- **Error Formats**: Standard error response structures

## Key Endpoints Covered

### P1 Core Endpoints (with interactive examples)
| Endpoint | Description | Example Files |
|----------|-------------|---------------|
| `GET /api/v1/costs/summary` | Cost analysis summary | `cost_summary.json`, `cost_summary_query.json` |
| `GET /api/v1/compliance/summary` | Compliance check summary | `compliance_summary.json`, `compliance_summary_query.json` |
| `GET /api/v1/resources/{resource_id}/history` | Resource lifecycle history | `resource_lifecycle_history.json`, `resource_lifecycle_query.json` |

### Additional Endpoints
1. **Authentication** - OAuth2 flow examples
2. **Dashboard** - Dashboard summary endpoints (`dashboard_summary.json`)
3. **Costs** - Cost analysis (`cost_analysis.json`) and budget endpoints (`budget_create.json`)
4. **Compliance** - Compliance status (`compliance_status.json`) and frameworks
5. **Resources** - Resource inventory management
6. **Identity** - User and group management
7. **Sync** - Data synchronization endpoints (`sync_trigger.json`, `sync_status.json`)
8. **Riverside** - Riverside compliance tracking

## Contributing

When adding new examples:

1. Follow the existing naming convention: `{endpoint}_{action}.json`
2. Include realistic data that reflects production usage
3. Document any special fields or constraints
4. Ensure examples pass schema validation
