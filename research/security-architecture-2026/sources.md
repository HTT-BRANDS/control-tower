# Source Credibility Assessment

## Tier 1 — Official Documentation (Highest Reliability)

### S1: Azure App Service Authentication Documentation
- **URL**: https://learn.microsoft.com/en-us/azure/app-service/overview-authentication-authorization
- **Publisher**: Microsoft Learn (official)
- **Last Updated**: March 11, 2026
- **Credibility**: ★★★★★ — Primary source for Easy Auth capabilities and limitations
- **Used for**: Authentication architecture comparison (Section 1)
- **Key finding**: Easy Auth runs as sidecar container on Linux, injects identity via headers, provides CSRF mitigation, supports PKCE

### S2: Azure Front Door Pricing
- **URL**: https://azure.microsoft.com/en-us/pricing/details/frontdoor/
- **Publisher**: Microsoft Azure (official pricing page)
- **Last Updated**: Current (live pricing)
- **Credibility**: ★★★★★ — Official pricing, authoritative for cost calculations
- **Used for**: Front Door cost analysis (Section 2)
- **Key data**: Standard $35/mo base, Premium $330/mo base, data transfer from $0.083/GB

### S3: Azure Private Link Pricing
- **URL**: https://azure.microsoft.com/en-us/pricing/details/private-link/
- **Publisher**: Microsoft Azure (official pricing page)
- **Last Updated**: Current (live pricing)
- **Credibility**: ★★★★★ — Official pricing
- **Used for**: Private Endpoints cost analysis (Section 4)
- **Key data**: $0.01/hour per endpoint (~$7.30/mo), $0.01/GB data processing

### S4: Azure Monitor Pricing
- **URL**: https://azure.microsoft.com/en-us/pricing/details/monitor/
- **Publisher**: Microsoft Azure (official pricing page)
- **Last Updated**: Current (live pricing)
- **Credibility**: ★★★★★ — Official pricing
- **Used for**: Monitoring cost analysis (Section 6)
- **Key data**: Log Analytics Pay-As-You-Go $2.30/GB, 5 GB/mo free, Prometheus $0.16/10M samples

### S5: Azure Bicep Documentation
- **URL**: https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/overview
- **Publisher**: Microsoft Learn (official)
- **Last Updated**: 2026
- **Credibility**: ★★★★★ — Primary source for Bicep capabilities
- **Used for**: IaC comparison (Section 5)

### S6: Azure Managed Identity Documentation
- **URL**: https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview
- **Publisher**: Microsoft Learn (official)
- **Last Updated**: 2026
- **Credibility**: ★★★★★ — Primary source for Managed Identity architecture
- **Used for**: Managed Identity analysis (Section 3)

## Tier 1 — Project Source Code (Primary)

### S7: app/core/auth.py
- **Type**: Source code analysis
- **Credibility**: ★★★★★ — Primary source for current auth implementation
- **Key findings**: Dual-token architecture (HS256 internal + RS256 Azure AD), JWKS caching, token blacklist integration, group-to-role mapping

### S8: app/core/oidc_credential.py
- **Type**: Source code analysis
- **Credibility**: ★★★★★ — Primary source for OIDC federation implementation
- **Key findings**: 3-tier credential resolution (App Service → Workload Identity → Dev fallback), zero-secret MI-backed assertions

### S9: infrastructure/main.bicep + modules/
- **Type**: Source code analysis
- **Credibility**: ★★★★★ — Primary source for infrastructure configuration
- **Key findings**: System-assigned MI on App Service, Key Vault access policies, SQL publicNetworkAccess='Disabled', storage key exposure via listKeys()

### S10: app/core/monitoring.py + app_insights.py
- **Type**: Source code analysis
- **Credibility**: ★★★★★ — Primary source for monitoring architecture
- **Key findings**: 4 overlapping telemetry systems, Prometheus endpoint with no scraper, OpenTelemetry disabled by default

## Tier 2 — Established Technical Publications

### S11: PyJWT Security Advisory (prior architecture audit)
- **Source**: research/architecture-audit-2026/recommendations.md
- **Credibility**: ★★★★ — Prior research, validated against PyJWT GitHub
- **Key finding**: Migration from python-jose to PyJWT completed. Current PyJWT 2.8+ is actively maintained.

### S12: Azure Well-Architected Framework — Security Pillar
- **URL**: https://learn.microsoft.com/en-us/azure/well-architected/security/
- **Publisher**: Microsoft (official architectural guidance)
- **Credibility**: ★★★★ — Authoritative design guidance but principles-level, not implementation-specific
- **Used for**: General security posture validation

## Cross-Referencing Notes

- All pricing data cross-referenced between the official pricing pages and the Azure Pricing Calculator
- Authentication patterns validated against both Microsoft documentation and the project's existing implementation
- Managed Identity recommendations validated against the project's `oidc_credential.py` implementation
- IaC comparison based on direct feature analysis of project's Bicep templates, not third-party comparisons
- Monitoring analysis based on dependency audit of `pyproject.toml` and runtime behavior of middleware classes
