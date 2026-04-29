"""FastAPI application construction helpers."""

import textwrap
from collections.abc import AsyncIterator, Callable

from fastapi import FastAPI


def create_application(settings, lifespan: Callable[[FastAPI], AsyncIterator[None]]) -> FastAPI:
    """Create the FastAPI application with OpenAPI metadata."""
    return FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=textwrap.dedent("""
        **Azure Multi-Tenant Governance Platform**

        A comprehensive platform for managing Azure governance across multiple tenants.

        ## Key Features

        * **Cost Management** - Track, analyze, and optimize Azure spending across tenants
        * **Compliance Monitoring** - Continuous compliance assessment with CIS, ISO 27001, SOC 2, and custom frameworks
        * **Resource Management** - Inventory and lifecycle management for Azure resources
        * **Identity Governance** - MFA tracking, access reviews, and identity hygiene
        * **Riverside Compliance** - Specialized tracking for Riverside Company requirements
        * **DMARC Monitoring** - Email security posture monitoring

        ## Authentication

        The API supports multiple authentication methods:

        1. **OAuth 2.0 / OpenID Connect** via Azure AD (recommended)
        2. **Bearer Token** (JWT) for API access
        3. **API Key** for service-to-service calls

        See the authentication endpoints for details on obtaining tokens.

        ## Rate Limiting

        API requests are rate-limited to ensure fair usage:
        - Default: 100 requests per minute per client
        - Auth endpoints: 10 requests per minute
        - Sync endpoints: 5 concurrent requests

        Rate limit headers are included in all responses:
        - `X-RateLimit-Limit`: Maximum requests allowed
        - `X-RateLimit-Remaining`: Requests remaining in window
        - `X-RateLimit-Reset`: Unix timestamp when limit resets

        ## Security

        All API endpoints are protected with:
        - TLS 1.3 encryption in transit
        - Security headers (CSP, HSTS, X-Frame-Options)
        - Input validation and sanitization
        - Audit logging for sensitive operations

        ## Response Codes

        | Code | Meaning | Description |
        |------|---------|-------------|
        | 200 | OK | Request succeeded |
        | 201 | Created | Resource created successfully |
        | 400 | Bad Request | Invalid request parameters |
        | 401 | Unauthorized | Authentication required |
        | 403 | Forbidden | Insufficient permissions |
        | 404 | Not Found | Resource does not exist |
        | 409 | Conflict | Resource conflict (e.g., duplicate) |
        | 429 | Too Many Requests | Rate limit exceeded |
        | 500 | Internal Error | Server-side error |

        ## Support

        For API support, contact the Cloud Governance Team or visit:
        [Documentation](https://github.com/htt-brands/azure-governance-platform/tree/main/docs)
        """).strip(),
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "Authentication",
                "description": "OAuth2 and token-based authentication endpoints",
            },
            {"name": "Dashboard", "description": "Dashboard summaries and overview metrics"},
            {"name": "Costs", "description": "Cost analysis, budgets, and spending reports"},
            {
                "name": "Compliance",
                "description": "Compliance status, frameworks, and rule management",
            },
            {
                "name": "Resources",
                "description": "Azure resource inventory and lifecycle management",
            },
            {"name": "Identity", "description": "Identity governance, MFA, and access reviews"},
            {"name": "Sync", "description": "Data synchronization jobs and scheduling"},
            {"name": "Riverside", "description": "Riverside Company compliance tracking"},
            {"name": "DMARC", "description": "Email security and DMARC monitoring"},
            {"name": "System", "description": "Health checks, metrics, and system status"},
        ],
        contact={"name": "Cloud Governance Team", "email": "cloud-governance@example.com"},
        license_info={
            "name": "MIT",
            "url": "https://github.com/htt-brands/azure-governance-platform/blob/main/LICENSE",
        },
    )
