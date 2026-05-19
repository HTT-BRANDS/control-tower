# Azure Governance Platform - API Documentation

> **Version:** 1.0  
> **Last Updated:** February 2025  
> **Base URL:** `http://localhost:8000` (local) or `https://your-app.azurewebsites.net` (deployed)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Authentication](#2-authentication)
3. [Error Handling](#3-error-handling)
4. [Rate Limiting](#4-rate-limiting)
5. [Core Endpoints](#5-core-endpoints)
6. [Tenant Management](#6-tenant-management)
7. [Cost Management](#7-cost-management)
8. [Compliance Monitoring](#8-compliance-monitoring)
9. [Resource Management](#9-resource-management)
10. [Identity Governance](#10-identity-governance)
11. [Sync Operations](#11-sync-operations)
12. [Monitoring & Alerts](#12-monitoring--alerts)
13. [Preflight Checks](#13-preflight-checks)
14. [Riverside Compliance](#14-riverside-compliance)
15. [Bulk Operations](#15-bulk-operations)
16. [Recommendations](#16-recommendations)
17. [Exports](#17-exports)

---

## 1. Overview

The Azure Governance Platform provides a comprehensive REST API for managing multi-tenant Azure governance. All API endpoints return JSON responses unless otherwise specified.

### API Versions

| Version | Status | Base Path |
|---------|--------|-----------|
| v1 | Current | `/api/v1` |

### Content Types

All requests and responses use `application/json` unless specified otherwise.

### Response Format

Standard response structure:

```json
{
  "data": { ... },
  "meta": {
    "timestamp": "2025-02-25T10:30:00Z",
    "version": "0.1.0"
  }
}
```

For list endpoints:

```json
{
  "items": [ ... ],
  "total": 100,
  "limit": 20,
  "offset": 0
}
```

---

## 2. Authentication

> **Note:** Current implementation uses API key authentication. OAuth2/Azure AD integration is planned for future releases.

### API Key Authentication

Include the API key in the request header:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/tenants
```

### User Context (Optional)

For audit purposes, include the user performing the action:

```bash
curl -H "X-User-Id: john.doe@company.com" http://localhost:8000/api/v1/costs
```

Or as a query parameter:

```bash
curl "http://localhost:8000/api/v1/costs?user=john.doe@company.com"
```

---

## 3. Error Handling

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Successful GET, PUT, PATCH |
| 201 | Created | Successful POST |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid request format or parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists or conflict |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unexpected server error |

### Error Response Format

```json
{
  "error": "ErrorType",
  "detail": "Human-readable error message",
  "code": "ERROR_CODE",
  "timestamp": "2025-02-25T10:30:00Z"
}
```

### Common Errors

```json
// 400 Bad Request
{
  "error": "ValidationError",
  "detail": "Invalid date format. Expected: YYYY-MM-DD",
  "code": "INVALID_DATE_FORMAT"
}

// 404 Not Found
{
  "error": "NotFound",
  "detail": "Tenant with ID 'abc-123' not found",
  "code": "TENANT_NOT_FOUND"
}

// 409 Conflict
{
  "error": "Conflict",
  "detail": "Tenant with Azure tenant ID 'xxx' already exists",
  "code": "TENANT_ALREADY_EXISTS"
}

// 429 Rate Limited
{
  "error": "RateLimitExceeded",
  "detail": "Rate limit exceeded. Try again in 60 seconds",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 60
}
```

---

## 4. Rate Limiting

### Current Limits

| Endpoint Type | Requests per Minute | Burst |
|---------------|---------------------|-------|
| Read (GET) | 100 | 20 |
| Write (POST/PUT/PATCH) | 30 | 10 |
| Sync Triggers | 5 | 2 |
| Bulk Operations | 10 | 3 |

### Rate Limit Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1708867200
```

### Exceeding Limits

When rate limited, you'll receive a `429` response with a `Retry-After` header:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

---

## 5. Core Endpoints

### 5.1 Health Check

Check if the API is running and healthy.

```http
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### 5.2 Detailed Health Check

Check detailed health status of all components.

```http
GET /health/detailed
```

**Response:**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "components": {
    "database": "healthy",
    "scheduler": "running",
    "cache": "memory",
    "azure_configured": true
  }
}
```

**Status Values:**

| Component | Healthy | Warning | Error |
|-----------|---------|---------|-------|
| database | "healthy" | "degraded" | "unhealthy: {error}" |
| scheduler | "running" | - | "not_running" |
| cache | "memory"/"redis" | - | "unknown" |

### 5.3 System Status

Get comprehensive system status including sync jobs and alerts.

```http
GET /api/v1/status
```

**Response:**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2025-02-25T10:30:00Z",
  "components": {
    "database": "healthy",
    "scheduler": "running",
    "cache": "memory"
  },
  "database_stats": {
    "tenant_count": 4,
    "resource_count": 1500,
    "sync_job_count": 200
  },
  "sync_jobs": {
    "active_jobs": 4
  },
  "alerts": {
    "active_count": 2,
    "recent_count": 5
  },
  "performance": {
    "cache_stats": {
      "hit_rate_percent": 85.5,
      "total_requests": 10000
    }
  }
}
```

### 5.4 Dashboard

Main dashboard (HTML response).

```http
GET /
```

**Response:** HTML dashboard page

---

## 6. Tenant Management

### 6.1 List Tenants

```http
GET /api/v1/tenants
```

**Response:**

```json
[
  {
    "id": "tenant-uuid-1",
    "name": "Production Tenant",
    "tenant_id": "12345678-1234-1234-1234-123456789012",
    "description": "Main production environment",
    "is_active": true,
    "subscription_count": 3,
    "created_at": "2025-01-15T08:00:00Z",
    "updated_at": "2025-02-20T14:30:00Z"
  }
]
```

<!-- ct-9x9: the `use_lighthouse` field was dropped from the tenants table
     and API responses in migration 011 (May 2026) after Azure Lighthouse
     was removed in ct-59n. Earlier examples in this doc included it; all
     remaining occurrences have been removed below. -->

### 6.2 Create Tenant

```http
POST /api/v1/tenants
Content-Type: application/json

{
  "name": "Production Tenant",
  "tenant_id": "12345678-1234-1234-1234-123456789012",
  "description": "Main production environment",
  "client_id": "optional-client-id",
  "client_secret_ref": "optional-secret-ref"
}
```

**Response (201 Created):**

```json
{
  "id": "new-tenant-uuid",
  "name": "Production Tenant",
  "tenant_id": "12345678-1234-1234-1234-123456789012",
  "description": "Main production environment",
  "is_active": true,
  "subscription_count": 0,
  "created_at": "2025-02-25T10:30:00Z",
  "updated_at": "2025-02-25T10:30:00Z"
}
```

### 6.3 Get Tenant

```http
GET /api/v1/tenants/{id}
```

**Response:**

```json
{
  "id": "tenant-uuid-1",
  "name": "Production Tenant",
  "tenant_id": "12345678-1234-1234-1234-123456789012",
  "description": "Main production environment",
  "is_active": true,
  "subscription_count": 3,
  "created_at": "2025-01-15T08:00:00Z",
  "updated_at": "2025-02-20T14:30:00Z"
}
```

### 6.4 Update Tenant

```http
PATCH /api/v1/tenants/{id}
Content-Type: application/json

{
  "name": "Updated Name",
  "description": "Updated description",
  "is_active": true
}
```

**Response:** Updated tenant object

### 6.5 Delete Tenant

```http
DELETE /api/v1/tenants/{id}
```

**Response:** `204 No Content`

### 6.6 Get Tenant Subscriptions

```http
GET /api/v1/tenants/{id}/subscriptions
```

**Response:**

```json
[
  {
    "id": "sub-uuid-1",
    "subscription_id": "sub-12345-67890",
    "display_name": "Production Subscription",
    "state": "Enabled",
    "tenant_id": "tenant-uuid-1",
    "synced_at": "2025-02-25T08:00:00Z"
  }
]
```

---

## 7. Cost Management

### 7.1 Get Cost Summary

```http
GET /api/v1/costs/summary?period_days=30&tenant_ids=tenant1,tenant2
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| period_days | int | No | Days to look back (1-365, default: 30) |
| tenant_ids | array | No | Filter by tenant IDs |
| start_date | date | No | Explicit start date (YYYY-MM-DD) |
| end_date | date | No | Explicit end date (YYYY-MM-DD) |

**Response:**

```json
{
  "total_cost": 15420.50,
  "currency": "USD",
  "period_days": 30,
  "cost_by_tenant": [
    {
      "tenant_id": "tenant-1",
      "tenant_name": "Production",
      "cost": 8000.00
    },
    {
      "tenant_id": "tenant-2",
      "tenant_name": "Development",
      "cost": 7420.50
    }
  ],
  "cost_by_service": [
    {
      "service_name": "Virtual Machines",
      "cost": 8500.00,
      "percentage": 55.1
    }
  ],
  "trend": "increasing",
  "trend_percentage": 12.5
}
```

### 7.2 Get Costs by Tenant

```http
GET /api/v1/costs/by-tenant?period_days=30
```

**Response:**

```json
[
  {
    "tenant_id": "tenant-1",
    "tenant_name": "Production",
    "total_cost": 8000.00,
    "currency": "USD",
    "cost_change_percent": 15.2,
    "top_services": [
      {"service": "Virtual Machines", "cost": 5000.00}
    ]
  }
]
```

### 7.3 Get Cost Trends

```http
GET /api/v1/costs/trends?days=30
```

**Response:**

```json
[
  {
    "date": "2025-01-26",
    "cost": 450.50,
    "currency": "USD"
  },
  {
    "date": "2025-01-27",
    "cost": 480.25,
    "currency": "USD"
  }
]
```

### 7.4 Get Cost Forecast

```http
GET /api/v1/costs/trends/forecast?days=30
```

**Response:**

```json
{
  "forecast_period_days": 30,
  "projected_cost": 18500.00,
  "confidence": 0.85,
  "trend": "increasing",
  "daily_forecast": [
    {
      "date": "2025-02-26",
      "projected_cost": 520.00,
      "confidence_lower": 480.00,
      "confidence_upper": 560.00
    }
  ]
}
```

### 7.5 Get Cost Anomalies

```http
GET /api/v1/costs/anomalies?acknowledged=false&limit=50&offset=0
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| acknowledged | bool | No | Filter by acknowledged status |
| tenant_ids | array | No | Filter by tenant IDs |
| limit | int | No | Max results (1-200, default: 50) |
| offset | int | No | Pagination offset |
| sort_by | string | No | Sort field (default: detected_at) |
| sort_order | string | No | asc or desc (default: desc) |

**Response:**

```json
[
  {
    "id": 1,
    "tenant_id": "tenant-1",
    "subscription_id": "sub-123",
    "service_name": "Virtual Machines",
    "detected_at": "2025-02-20T10:00:00Z",
    "expected_cost": 400.00,
    "actual_cost": 650.00,
    "variance_percent": 62.5,
    "anomaly_type": "spike",
    "acknowledged": false,
    "acknowledged_by": null,
    "acknowledged_at": null
  }
]
```

### 7.6 Acknowledge Anomaly

```http
POST /api/v1/costs/anomalies/{anomaly_id}/acknowledge
```

**Response:**

```json
{
  "success": true,
  "anomaly_id": 1,
  "acknowledged_by": "john.doe@company.com",
  "acknowledged_at": "2025-02-25T10:30:00Z"
}
```

### 7.7 Bulk Acknowledge Anomalies

```http
POST /api/v1/costs/anomalies/bulk-acknowledge
Content-Type: application/json

{
  "anomaly_ids": [1, 2, 3]
}
```

**Response:**

```json
{
  "success": true,
  "acknowledged_count": 3,
  "failed_count": 0,
  "acknowledged_by": "john.doe@company.com"
}
```

### 7.8 Get Anomaly Trends

```http
GET /api/v1/costs/anomalies/trends?months=6
```

**Response:**

```json
{
  "period_months": 6,
  "total_anomalies": 45,
  "anomalies_by_month": [
    {
      "month": "2025-01",
      "count": 8,
      "total_variance": 1200.00
    }
  ]
}
```

---

## 8. Compliance Monitoring

### 8.1 Get Compliance Summary

```http
GET /api/v1/compliance/summary?tenant_ids=tenant1,tenant2
```

**Response:**

```json
{
  "overall_compliance_percent": 87.5,
  "total_resources": 1500,
  "compliant_resources": 1312,
  "non_compliant_resources": 188,
  "exempt_resources": 0,
  "scores_by_tenant": [
    {
      "tenant_id": "tenant-1",
      "tenant_name": "Production",
      "overall_compliance_percent": 92.0,
      "secure_score": 85,
      "compliant_resources": 800,
      "non_compliant_resources": 70,
      "exempt_resources": 0
    }
  ]
}
```

### 8.2 Get Compliance Scores

```http
GET /api/v1/compliance/scores?tenant_ids=tenant1&limit=100&offset=0
```

**Response:**

```json
[
  {
    "tenant_id": "tenant-1",
    "tenant_name": "Production",
    "subscription_id": "sub-123",
    "overall_compliance_percent": 92.0,
    "secure_score": 85,
    "compliant_resources": 800,
    "non_compliant_resources": 70,
    "exempt_resources": 0,
    "assessed_at": "2025-02-25T08:00:00Z"
  }
]
```

### 8.3 Get Non-Compliant Policies

```http
GET /api/v1/compliance/non-compliant?severity=High&limit=100
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| tenant_id | string | No | Filter by single tenant |
| tenant_ids | array | No | Filter by multiple tenants |
| severity | string | No | High, Medium, or Low |
| limit | int | No | Max results (1-500, default: 100) |
| offset | int | No | Pagination offset |
| sort_by | string | No | Sort field |
| sort_order | string | No | asc or desc |

**Response:**

```json
[
  {
    "tenant_id": "tenant-1",
    "subscription_id": "sub-123",
    "policy_definition_id": "/providers/Microsoft.Authorization/policyDefinitions/xxx",
    "policy_name": "Require encryption on storage accounts",
    "policy_category": "Data Protection",
    "compliance_state": "NonCompliant",
    "non_compliant_count": 5,
    "severity": "High",
    "recommendation": "Enable encryption on all storage accounts"
  }
]
```

### 8.4 Get Compliance Trends

```http
GET /api/v1/compliance/trends?days=30&tenant_ids=tenant1
```

**Response:**

```json
{
  "period_days": 30,
  "trends": [
    {
      "date": "2025-01-26",
      "overall_compliance_percent": 85.0,
      "compliant_resources": 1200,
      "non_compliant_resources": 200
    }
  ]
}
```

---

## 9. Resource Management

### 9.1 Get Resources

```http
GET /api/v1/resources?resource_type=VirtualMachine&limit=500&offset=0
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| tenant_id | string | No | Filter by tenant |
| tenant_ids | array | No | Filter by multiple tenants |
| resource_type | string | No | Filter by resource type |
| limit | int | No | Max results (1-1000, default: 500) |
| offset | int | No | Pagination offset |
| sort_by | string | No | Sort field (default: name) |
| sort_order | string | No | asc or desc |

**Response:**

```json
{
  "resources": [
    {
      "id": "res-uuid-1",
      "name": "vm-prod-01",
      "resource_type": "Microsoft.Compute/virtualMachines",
      "tenant_id": "tenant-1",
      "tenant_name": "Production",
      "subscription_id": "sub-123",
      "subscription_name": "Production Sub",
      "resource_group": "rg-production",
      "location": "eastus",
      "provisioning_state": "Succeeded",
      "sku": "Standard_D2s_v3",
      "tags": {
        "Environment": "Production",
        "Owner": "team@company.com"
      },
      "is_orphaned": false,
      "estimated_monthly_cost": 150.00,
      "last_synced": "2025-02-25T08:00:00Z"
    }
  ],
  "total_resources": 1500,
  "by_type": {
    "Microsoft.Compute/virtualMachines": 100,
    "Microsoft.Storage/storageAccounts": 50
  }
}
```

### 9.2 Get Orphaned Resources

```http
GET /api/v1/resources/orphaned?tenant_ids=tenant1&limit=100
```

**Response:**

```json
[
  {
    "id": "res-uuid-2",
    "name": "orphaned-disk-01",
    "resource_type": "Microsoft.Compute/disks",
    "tenant_id": "tenant-1",
    "tenant_name": "Production",
    "subscription_id": "sub-123",
    "subscription_name": "Production Sub",
    "resource_group": "rg-old",
    "location": "eastus",
    "orphan_reason": "Unattached disk",
    "estimated_monthly_cost": 25.00,
    "discovered_at": "2025-02-20T08:00:00Z"
  }
]
```

### 9.3 Get Idle Resources

```http
GET /api/v1/resources/idle?idle_type=low_cpu&is_reviewed=false&limit=100
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| tenant_ids | array | No | Filter by tenants |
| idle_type | string | No | Filter by idle type |
| is_reviewed | bool | No | Filter by review status |
| limit | int | No | Max results (1-500) |
| offset | int | No | Pagination offset |
| sort_by | string | No | Sort field |
| sort_order | string | No | asc or desc |

**Response:**

```json
[
  {
    "id": 1,
    "resource_id": "res-uuid-3",
    "resource_name": "vm-idle-01",
    "resource_type": "Microsoft.Compute/virtualMachines",
    "tenant_id": "tenant-1",
    "tenant_name": "Production",
    "idle_type": "low_cpu",
    "idle_reason": "CPU < 5% for 30 days",
    "estimated_monthly_savings": 150.00,
    "is_reviewed": false,
    "reviewed_by": null,
    "reviewed_at": null,
    "detected_at": "2025-02-20T08:00:00Z"
  }
]
```

### 9.4 Get Idle Resources Summary

```http
GET /api/v1/resources/idle/summary
```

**Response:**

```json
{
  "total_idle_resources": 25,
  "total_potential_savings": 3750.00,
  "by_type": {
    "low_cpu": 15,
    "no_connections": 10
  },
  "by_tenant": {
    "tenant-1": 15,
    "tenant-2": 10
  }
}
```

### 9.5 Tag Idle Resource as Reviewed

```http
POST /api/v1/resources/idle/{idle_resource_id}/tag
Content-Type: application/json

{
  "notes": "Confirmed idle, will decommission next week"
}
```

**Response:**

```json
{
  "success": true,
  "idle_resource_id": 1,
  "reviewed_by": "john.doe@company.com",
  "reviewed_at": "2025-02-25T10:30:00Z",
  "notes": "Confirmed idle, will decommission next week"
}
```

### 9.6 Get Tagging Compliance

```http
GET /api/v1/resources/tagging?required_tags=Environment,Owner,CostCenter
```

**Response:**

```json
{
  "total_resources": 1500,
  "compliant_resources": 1200,
  "non_compliant_resources": 300,
  "compliance_percent": 80.0,
  "by_tag": {
    "Environment": {
      "compliant": 1400,
      "non_compliant": 100
    },
    "Owner": {
      "compliant": 1200,
      "non_compliant": 300
    }
  },
  "by_tenant": {
    "tenant-1": {
      "total": 800,
      "compliant": 700,
      "percent": 87.5
    }
  }
}
```

---

## 10. Identity Governance

### 10.1 Get Identity Summary

```http
GET /api/v1/identity/summary?tenant_ids=tenant1,tenant2
```

**Response:**

```json
{
  "total_users": 500,
  "total_guests": 50,
  "total_privileged": 25,
  "mfa_enabled_count": 450,
  "mfa_disabled_count": 50,
  "mfa_coverage_percent": 90.0,
  "stale_accounts_count": 30,
  "by_tenant": {
    "tenant-1": {
      "total_users": 300,
      "mfa_coverage_percent": 92.0
    }
  }
}
```

### 10.2 Get Privileged Accounts

```http
GET /api/v1/identity/privileged?risk_level=High&mfa_enabled=false&limit=100
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| tenant_id | string | No | Filter by tenant |
| tenant_ids | array | No | Filter by tenants |
| risk_level | string | No | High, Medium, or Low |
| mfa_enabled | bool | No | Filter by MFA status |
| limit | int | No | Max results (1-500) |
| offset | int | No | Pagination offset |
| sort_by | string | No | Sort field |
| sort_order | string | No | asc or desc |

**Response:**

```json
[
  {
    "id": "user-uuid-1",
    "display_name": "John Doe",
    "user_principal_name": "john.doe@company.com",
    "tenant_id": "tenant-1",
    "tenant_name": "Production",
    "role_names": ["Global Administrator", "Security Administrator"],
    "mfa_enabled": false,
    "risk_level": "High",
    "last_sign_in": "2025-02-24T15:30:00Z"
  }
]
```

### 10.3 Get Guest Accounts

```http
GET /api/v1/identity/guests?stale_only=true&limit=100
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| tenant_id | string | No | Filter by tenant |
| tenant_ids | array | No | Filter by tenants |
| stale_only | bool | No | Only show stale accounts |
| limit | int | No | Max results |
| offset | int | No | Pagination offset |

**Response:**

```json
[
  {
    "id": "guest-uuid-1",
    "display_name": "External User",
    "user_principal_name": "external@gmail.com",
    "tenant_id": "tenant-1",
    "tenant_name": "Production",
    "invited_by": "john.doe@company.com",
    "invite_date": "2024-06-15T10:00:00Z",
    "last_sign_in": "2024-08-20T14:00:00Z",
    "is_stale": true,
    "stale_reason": "No sign-in for 180+ days"
  }
]
```

### 10.4 Get Stale Accounts

```http
GET /api/v1/identity/stale?days_inactive=90&tenant_ids=tenant1&limit=100
```

**Response:**

```json
[
  {
    "id": "user-uuid-2",
    "display_name": "Jane Smith",
    "user_principal_name": "jane.smith@company.com",
    "tenant_id": "tenant-1",
    "tenant_name": "Production",
    "last_sign_in": "2024-11-15T10:00:00Z",
    "days_inactive": 102,
    "account_type": "member"
  }
]
```

### 10.5 Get Identity Trends

```http
GET /api/v1/identity/trends?days=30&tenant_ids=tenant1
```

**Response:**

```json
{
  "period_days": 30,
  "trends": [
    {
      "date": "2025-01-26",
      "total_users": 480,
      "mfa_coverage_percent": 88.0,
      "guest_count": 45,
      "privileged_count": 22,
      "stale_count": 25
    }
  ]
}
```

---

## 11. Sync Operations

### 11.1 Trigger Manual Sync

```http
POST /api/v1/sync/{sync_type}
```

**Path Parameters:**

| Name | Type | Description |
|------|------|-------------|
| sync_type | string | costs, compliance, resources, or identity |

**Response:**

```json
{
  "status": "triggered",
  "sync_type": "costs",
  "message": "Sync job queued for execution"
}
```

### 11.2 Get Sync Job Status

```http
GET /api/v1/sync/status
```

**Response:**

```json
{
  "status": "running",
  "jobs": [
    {
      "id": "sync_costs",
      "name": "Sync Cost Data",
      "next_run": "2025-02-26T00:00:00Z"
    },
    {
      "id": "sync_compliance",
      "name": "Sync Compliance Data",
      "next_run": "2025-02-25T20:00:00Z"
    }
  ]
}
```

### 11.3 Get Sync Health

```http
GET /api/v1/sync/health
```

**Response:**

```json
{
  "status": "healthy",
  "last_sync": "2025-02-25T08:00:00Z",
  "next_sync": "2025-02-26T00:00:00Z",
  "recent_failures": 0,
  "consecutive_failures": 0
}
```

### 11.4 Get Sync History

```http
GET /api/v1/sync/history?job_type=costs&limit=50
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| job_type | string | No | Filter by job type |
| limit | int | No | Max results (default: 50) |

**Response:**

```json
{
  "logs": [
    {
      "id": 1,
      "job_type": "costs",
      "tenant_id": "tenant-1",
      "status": "completed",
      "started_at": "2025-02-25T00:00:00Z",
      "ended_at": "2025-02-25T00:05:00Z",
      "duration_ms": 300000,
      "records_processed": 500,
      "errors_count": 0,
      "error_message": null
    }
  ]
}
```

### 11.5 Get Sync Metrics

```http
GET /api/v1/sync/metrics?job_type=costs
```

**Response:**

```json
{
  "metrics": [
    {
      "job_type": "costs",
      "calculated_at": "2025-02-25T08:00:00Z",
      "total_runs": 100,
      "successful_runs": 98,
      "failed_runs": 2,
      "success_rate": 98.0,
      "avg_duration_ms": 300000,
      "min_duration_ms": 240000,
      "max_duration_ms": 600000,
      "avg_records_processed": 500,
      "total_records_processed": 50000,
      "total_errors": 5,
      "last_run_at": "2025-02-25T00:00:00Z",
      "last_success_at": "2025-02-25T00:00:00Z",
      "last_failure_at": "2025-02-24T00:00:00Z",
      "last_error_message": "Connection timeout"
    }
  ]
}
```

### 11.6 Get Sync Alerts

```http
GET /api/v1/sync/alerts?severity=high&include_resolved=false
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| job_type | string | No | Filter by job type |
| severity | string | No | Filter by severity |
| include_resolved | bool | No | Include resolved alerts |

**Response:**

```json
{
  "alerts": [
    {
      "id": 1,
      "alert_type": "sync_failure",
      "severity": "high",
      "job_type": "costs",
      "tenant_id": "tenant-1",
      "title": "Cost sync failed",
      "message": "Failed to retrieve cost data from Azure",
      "is_resolved": false,
      "created_at": "2025-02-25T00:05:00Z",
      "resolved_at": null,
      "resolved_by": null
    }
  ],
  "stats": {
    "total_active": 2,
    "by_severity": {
      "critical": 0,
      "high": 1,
      "medium": 1,
      "low": 0
    }
  }
}
```

### 11.7 Resolve Alert

```http
POST /api/v1/sync/alerts/{alert_id}/resolve
Content-Type: application/json

{
  "resolved_by": "john.doe@company.com"
}
```

**Response:**

```json
{
  "id": 1,
  "alert_type": "sync_failure",
  "is_resolved": true,
  "resolved_at": "2025-02-25T10:30:00Z",
  "resolved_by": "john.doe@company.com"
}
```

---

## 12. Monitoring & Alerts

### 12.1 Get Performance Metrics

```http
GET /monitoring/performance
```

**Response:**

```json
{
  "cache_stats": {
    "hit_rate_percent": 85.5,
    "hits": 8550,
    "misses": 1450,
    "total_requests": 10000
  },
  "sync_jobs": {
    "total_jobs": 400,
    "avg_duration_ms": 300000
  },
  "queries": {
    "total_queries": 5000,
    "slow_queries": 10,
    "avg_duration_ms": 50
  }
}
```

### 12.2 Get Cache Metrics

```http
GET /monitoring/cache
```

**Response:**

```json
{
  "backend": "memory",
  "hit_rate_percent": 85.5,
  "hits": 8550,
  "misses": 1450,
  "total_requests": 10000,
  "size_mb": 10.5,
  "entries_count": 500
}
```

### 12.3 Get Sync Job Metrics

```http
GET /monitoring/sync-jobs?job_type=costs&limit=100
```

**Response:**

```json
[
  {
    "job_type": "costs",
    "tenant_id": "tenant-1",
    "status": "completed",
    "duration_ms": 300000,
    "records_processed": 500,
    "started_at": "2025-02-25T00:00:00Z"
  }
]
```

### 12.4 Get Query Metrics

```http
GET /monitoring/queries?slow_only=true&limit=50
```

**Response:**

```json
[
  {
    "query": "SELECT * FROM resources",
    "duration_ms": 1500,
    "timestamp": "2025-02-25T10:30:00Z"
  }
]
```

### 12.5 Reset Metrics

```http
POST /monitoring/reset
```

**Response:**

```json
{
  "status": "Metrics reset successfully"
}
```

### 12.6 Health Check

```http
GET /monitoring/health
```

**Response:**

```json
{
  "status": "healthy",
  "cache_health": "good",
  "cache_hit_rate": 85.5,
  "total_sync_jobs": 400,
  "total_queries": 5000,
  "slow_queries": 10
}
```

---

## 13. Preflight Checks

### 13.1 Get Preflight Status

```http
GET /api/v1/preflight/status
```

**Response:**

```json
{
  "is_running": false,
  "last_run_at": "2025-02-25T08:00:00Z",
  "latest_report": {
    "id": "report-uuid",
    "status": "passed",
    "passed_count": 15,
    "failed_count": 0,
    "warning_count": 2,
    "started_at": "2025-02-25T08:00:00Z",
    "ended_at": "2025-02-25T08:02:00Z"
  }
}
```

### 13.2 Run Preflight Checks

```http
POST /api/v1/preflight/run
Content-Type: application/json

{
  "categories": ["azure_access", "azure_permissions"],
  "tenant_ids": ["tenant-1"],
  "fail_fast": false,
  "timeout_seconds": 300
}
```

**Response:**

```json
{
  "id": "report-uuid",
  "status": "passed",
  "passed_count": 15,
  "failed_count": 0,
  "warning_count": 2,
  "results": [
    {
      "check_name": "azure_authentication",
      "category": "azure_access",
      "status": "passed",
      "message": "Successfully authenticated to Azure"
    }
  ],
  "started_at": "2025-02-25T08:00:00Z",
  "ended_at": "2025-02-25T08:02:00Z",
  "duration_seconds": 120
}
```

### 13.3 Run Tenant-Specific Checks

```http
GET /api/v1/preflight/tenants/{tenant_id}
```

### 13.4 Run GitHub Checks

```http
GET /api/v1/preflight/github
```

### 13.5 Get Report (JSON)

```http
GET /api/v1/preflight/report/json
```

### 13.6 Get Report (Markdown)

```http
GET /api/v1/preflight/report/markdown
```

**Response:**

```json
{
  "content": "# Preflight Report\n\n## Summary\n..."
}
```

### 13.7 Get Tenant Summaries

```http
GET /api/v1/preflight/summary/tenants
```

### 13.8 Get Category Summaries

```http
GET /api/v1/preflight/summary/categories
```

### 13.9 Clear Cache

```http
POST /api/v1/preflight/clear-cache
```

**Response:**

```json
{
  "message": "Cache cleared successfully"
}
```

---

## 14. Riverside Compliance

> **Note:** Riverside endpoints are only available when `RIVERSIDE_COMPLIANCE_ENABLED=true`

### 14.1 Get Riverside Dashboard

```http
GET /riverside
```

**Response:** HTML dashboard page

### 14.2 Get Executive Summary

```http
GET /api/v1/riverside/summary
```

**Response:**

```json
{
  "days_to_deadline": 130,
  "deadline_date": "2026-07-08",
  "financial_risk": 4000000,
  "overall_maturity": 2.4,
  "mfa_coverage": {
    "current": 634,
    "total": 1992,
    "percent": 31.8
  },
  "device_compliance": {
    "compliant": 150,
    "total": 200,
    "percent": 75.0
  },
  "critical_gaps_count": 5,
  "tenants": [
    {
      "code": "HTT",
      "name": "HTT Tenant",
      "mfa_percent": 30.0
    }
  ]
}
```

### 14.3 Get MFA Status

```http
GET /api/v1/riverside/mfa-status
```

**Response:**

```json
{
  "total_users": 1992,
  "mfa_enrolled": 634,
  "mfa_coverage_percent": 31.8,
  "target_percent": 100,
  "gap_to_target": 1358,
  "admin_accounts": {
    "total": 39,
    "mfa_enabled": 12,
    "percent": 30.8
  },
  "by_tenant": {
    "HTT": {
      "total_users": 500,
      "mfa_enrolled": 150,
      "percent": 30.0
    }
  }
}
```

### 14.4 Get Maturity Scores

```http
GET /api/v1/riverside/maturity-scores
```

**Response:**

```json
{
  "overall_maturity": 2.4,
  "target_maturity": 3.0,
  "domain_scores": {
    "iam": {
      "current": 2.2,
      "target": 3.0,
      "gap": 0.8
    },
    "governance_security": {
      "current": 2.5,
      "target": 3.0,
      "gap": 0.5
    },
    "data_security": {
      "current": 2.5,
      "target": 3.0,
      "gap": 0.5
    }
  },
  "by_tenant": {
    "HTT": {
      "overall": 2.4,
      "iam": 2.2,
      "governance_security": 2.5,
      "data_security": 2.5
    }
  }
}
```

### 14.5 Get Requirements

```http
GET /api/v1/riverside/requirements?category=IAM&priority=P0&status=not_started
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| category | string | No | Filter by category (IAM, GS, DS) |
| priority | string | No | Filter by priority (P0, P1, P2) |
| status | string | No | Filter by status |

**Response:**

```json
{
  "requirements": [
    {
      "id": "IAM-12",
      "category": "IAM",
      "priority": "P0",
      "title": "Universal MFA",
      "description": "Enable MFA for all user accounts",
      "status": "in_progress",
      "deadline": "2025-03-08",
      "progress_percent": 31.8
    }
  ],
  "stats": {
    "total": 72,
    "by_status": {
      "completed": 20,
      "in_progress": 30,
      "not_started": 22
    },
    "by_priority": {
      "P0": 10,
      "P1": 25,
      "P2": 37
    }
  }
}
```

### 14.6 Get Critical Gaps

```http
GET /api/v1/riverside/gaps
```

**Response:**

```json
{
  "immediate_action": [
    {
      "id": "IAM-12",
      "title": "Universal MFA",
      "current": "31.8%",
      "target": "100%",
      "deadline": "2025-03-08",
      "risk": "$4M"
    }
  ],
  "high_priority": [...],
  "medium_priority": [...]
}
```

### 14.7 Trigger Riverside Sync

```http
POST /api/v1/riverside/sync
```

**Response:**

```json
{
  "status": "success",
  "message": "Riverside sync completed",
  "results": {
    "mfa_synced": true,
    "device_synced": true,
    "maturity_synced": true,
    "duration_seconds": 45
  }
}
```

---

## 15. Bulk Operations

### 15.1 Bulk Apply Tags

```http
POST /bulk/tags/apply
Content-Type: application/json

{
  "resource_ids": ["res-1", "res-2", "res-3"],
  "tags": {
    "Environment": "Production",
    "Owner": "team@company.com"
  },
  "filters": {
    "tenant_ids": ["tenant-1"],
    "resource_types": ["Microsoft.Compute/virtualMachines"]
  }
}
```

**Response:**

```json
{
  "success": true,
  "processed_count": 3,
  "success_count": 3,
  "failure_count": 0,
  "failures": []
}
```

### 15.2 Bulk Remove Tags

```http
POST /bulk/tags/remove
Content-Type: application/json

{
  "resource_ids": ["res-1", "res-2"],
  "tag_names": ["Environment", "Owner"]
}
```

### 15.3 Bulk Acknowledge Anomalies

```http
POST /bulk/anomalies/acknowledge
Content-Type: application/json

{
  "anomaly_ids": [1, 2, 3],
  "notes": "Acknowledged as expected seasonal spike"
}
```

### 15.4 Bulk Dismiss Recommendations

```http
POST /bulk/recommendations/dismiss
Content-Type: application/json

{
  "recommendation_ids": [1, 2, 3],
  "reason": "Business justification - required for compliance"
}
```

### 15.5 Bulk Review Idle Resources

```http
POST /bulk/idle-resources/review
Content-Type: application/json

{
  "idle_resource_ids": [1, 2, 3],
  "notes": "Confirmed idle, scheduled for decommissioning"
}
```

---

## 16. Recommendations

### 16.1 Get Recommendations

```http
GET /api/v1/recommendations?category=cost&impact=High&limit=100
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| category | string | No | cost, security, performance, reliability |
| tenant_ids | array | No | Filter by tenants |
| impact | string | No | Low, Medium, High, Critical |
| dismissed | bool | No | Include dismissed (default: false) |
| limit | int | No | Max results (1-500) |
| offset | int | No | Pagination offset |
| sort_by | string | No | Sort field |
| sort_order | string | No | asc or desc |

**Response:**

```json
[
  {
    "id": 1,
    "category": "cost",
    "impact": "High",
    "title": "Idle Virtual Machine",
    "description": "VM 'vm-idle-01' has had < 5% CPU for 30 days",
    "resource_id": "res-uuid-3",
    "resource_type": "Microsoft.Compute/virtualMachines",
    "tenant_id": "tenant-1",
    "estimated_savings": 150.00,
    "estimated_savings_period": "monthly",
    "is_dismissed": false,
    "created_at": "2025-02-20T08:00:00Z"
  }
]
```

### 16.2 Get Recommendations by Category

```http
GET /api/v1/recommendations/by-category
```

**Response:**

```json
[
  {
    "category": "cost",
    "count": 25,
    "estimated_total_savings": 5000.00,
    "by_impact": {
      "High": 5,
      "Medium": 10,
      "Low": 10
    }
  }
]
```

### 16.3 Get Recommendations by Tenant

```http
GET /api/v1/recommendations/by-tenant
```

### 16.4 Get Savings Potential

```http
GET /api/v1/recommendations/savings-potential
```

**Response:**

```json
{
  "total_potential_savings": 15000.00,
  "currency": "USD",
  "period": "monthly",
  "by_category": {
    "cost": 10000.00,
    "security": 0,
    "performance": 3000.00,
    "reliability": 2000.00
  }
}
```

### 16.5 Get Recommendation Summary

```http
GET /api/v1/recommendations/summary
```

### 16.6 Dismiss Recommendation

```http
POST /api/v1/recommendations/{recommendation_id}/dismiss
Content-Type: application/json

{
  "reason": "Business justification - required for compliance"
}
```

**Response:**

```json
{
  "success": true,
  "recommendation_id": 1,
  "dismissed_by": "john.doe@company.com",
  "dismissed_at": "2025-02-25T10:30:00Z",
  "reason": "Business justification - required for compliance"
}
```

---

## 17. Exports

### 17.1 Export Costs to CSV

```http
GET /api/v1/exports/costs?start_date=2025-01-01&end_date=2025-02-25&tenant_ids=tenant1
```

**Response:** CSV file download

```csv
type,date,tenant_id,tenant_name,cost,currency
daily_cost,2025-01-26,,,450.50,USD
tenant_summary,2025-02-25,tenant-1,Production,8000.00,USD
```

### 17.2 Export Resources to CSV

```http
GET /api/v1/exports/resources?tenant_ids=tenant1&resource_type=VirtualMachine&include_orphaned=true
```

**Response:** CSV file download

### 17.3 Export Compliance to CSV

```http
GET /api/v1/exports/compliance?tenant_ids=tenant1&include_non_compliant=true
```

**Response:** CSV file download

---

## Appendix A: HTTP Methods Reference

| Method | Description | Idempotent |
|--------|-------------|------------|
| GET | Retrieve a resource | Yes |
| POST | Create a resource or trigger action | No |
| PUT | Update/replace a resource | Yes |
| PATCH | Partial update | No |
| DELETE | Remove a resource | Yes |

## Appendix B: Pagination

List endpoints support pagination with `limit` and `offset`:

```http
GET /api/v1/resources?limit=20&offset=40
```

This returns items 41-60.

### Response Headers

```http
X-Total-Count: 100
X-Page-Size: 20
X-Current-Page: 3
```

## Appendix C: Filtering

Most list endpoints support multiple filter parameters. Combine filters with AND logic:

```http
GET /api/v1/resources?tenant_ids=tenant1,tenant2&resource_type=VirtualMachine
```

Returns resources that are in tenant1 OR tenant2 AND are VirtualMachines.

## Appendix D: Sorting

Use `sort_by` and `sort_order` parameters:

```http
GET /api/v1/resources?sort_by=created_at&sort_order=desc
```

Common sort fields:
- `name`
- `created_at`
- `updated_at`
- `cost`
- `compliance_percent`

## Appendix E: Date Formats

All dates use ISO 8601 format:

- Date: `YYYY-MM-DD` (e.g., `2025-02-25`)
- DateTime: `YYYY-MM-DDTHH:MM:SSZ` (e.g., `2025-02-25T10:30:00Z`)

## Appendix F: Common Resource Types

| Resource Type | Description |
|---------------|-------------|
| Microsoft.Compute/virtualMachines | Virtual Machines |
| Microsoft.Storage/storageAccounts | Storage Accounts |
| Microsoft.Network/virtualNetworks | Virtual Networks |
| Microsoft.Sql/servers | SQL Servers |
| Microsoft.Web/sites | App Services |
| Microsoft.KeyVault/vaults | Key Vaults |
| Microsoft.ContainerInstance/containerGroups | Container Instances |
| Microsoft.Compute/disks | Managed Disks |

---

**Document History**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | February 2025 | Initial API documentation |

---

**Need Help?**

- Review the [Implementation Guide](./IMPLEMENTATION_GUIDE.md)
- Check [Common Pitfalls](./COMMON_PITFALLS.md)
- See [Architecture Overview](../ARCHITECTURE.md)
