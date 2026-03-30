# Source Credibility Assessment

## Primary Sources (Tier 1 — Official Microsoft Documentation)

### Source 1: Workload Identity Federation Concepts
- **URL**: https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation
- **Last Updated**: 2025-04-09
- **Authority**: Official Microsoft Learn documentation (Tier 1)
- **Key Finding**: Contains the definitive statement:
  > "Microsoft Entra ID issued tokens may not be used for federated identity flows. The federated identity credentials flow does not support tokens issued by Microsoft Entra ID."
- **Relevance**: **CRITICAL** — This is the root cause of AADSTS700236. MI tokens are Entra-issued tokens.
- **Cross-validated**: Yes, consistent with Source 2 and Source 3.

### Source 2: Configure an Application to Trust a Managed Identity
- **URL**: https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity
- **Last Updated**: 2025-06-06
- **Authority**: Official Microsoft Learn documentation (Tier 1)
- **Key Findings**:
  - MI-to-app federation IS supported, but with constraints
  - **User-assigned managed identities only** ("You can only use User-Assigned Managed Identities as a credential")
  - **Same tenant required**: "Both the Microsoft Entra app and managed identity must belong to the same tenant"
  - **Cross-tenant resource access IS supported**: "Accessing resources in another tenant is supported"
  - Provides Python code sample using `ClientAssertionCredential`
- **Relevance**: **CRITICAL** — Proves the correct pattern exists, shows the constraints.

### Source 3: Workload Identity Federation — Important Considerations and Restrictions
- **URL**: https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-considerations
- **Last Updated**: 2024-02-28
- **Authority**: Official Microsoft Learn documentation (Tier 1)
- **Key Findings**:
  - Maximum 20 federated identity credentials per app or UAMI
  - Issuer/subject/audience must match case-sensitively
  - Propagation delay can cause transient AADSTS70021 errors
  - Only RS256 signing algorithm supported
- **Relevance**: High — Important implementation constraints.

### Source 4: Configure Cross-Tenant Workload Identity on AKS
- **URL**: https://learn.microsoft.com/en-us/azure/aks/workload-identity-cross-tenant
- **Last Updated**: 2024-08-01
- **Authority**: Official Microsoft Learn documentation (Tier 1)
- **Key Findings**:
  - Cross-tenant WIF works with AKS because AKS uses its own OIDC issuer (NOT Entra ID)
  - The issuer is the AKS cluster's OIDC URL, not `login.microsoftonline.com`
  - Pattern: UAMI in remote tenant trusts AKS OIDC issuer in home tenant
  - This pattern is NOT applicable to App Service + MI (no separate OIDC issuer)
- **Relevance**: Medium — Confirms that cross-tenant WIF requires a non-Entra IdP.

### Source 5: Convert Single-Tenant App to Multi-Tenant
- **URL**: https://learn.microsoft.com/en-us/entra/identity-platform/howto-convert-app-to-be-multi-tenant
- **Last Updated**: 2024-11-13
- **Authority**: Official Microsoft Learn documentation (Tier 1)
- **Key Findings**:
  - Multi-tenant apps use `signInAudience: AzureADMultipleOrgs`
  - Service principal created in foreign tenant on first admin consent
  - App ID URI must be globally unique
  - Admin consent required for app-only permissions (e.g., Graph API)
  - Admin consent URL: `https://login.microsoftonline.com/{tenant}/adminconsent?client_id={app-id}`
- **Relevance**: High — Required for the recommended solution.

### Source 6: Azure Lighthouse — Cross-Tenant Management Experiences
- **URL**: https://learn.microsoft.com/en-us/azure/lighthouse/concepts/cross-tenant-management-experience
- **Last Updated**: 2026-01-21
- **Authority**: Official Microsoft Learn documentation (Tier 1)
- **Key Finding**:
  > "Azure Lighthouse supports requests handled by Azure Resource Manager. The operation URIs for these requests start with `https://management.azure.com`. However, Azure Lighthouse doesn't support requests that are handled by an instance of a resource type."
- **Relevance**: Medium — Confirms Lighthouse does NOT support Graph API, ruling it out as a complete solution for identity/MFA operations.

## Secondary Sources (Tier 2-3)

### Source 7: GitHub — Azure SDK for Python Issues
- **URL**: https://github.com/Azure/azure-sdk-for-python/issues?q=AADSTS700236
- **Searched**: 2026-03-30
- **Result**: 0 open, 0 closed issues matching AADSTS700236
- **Relevance**: Low — The error is an Entra platform limitation, not an SDK bug.

### Source 8: GitHub Global Search — AADSTS700236
- **URL**: https://github.com/search?q=AADSTS700236&type=issues
- **Searched**: 2026-03-30
- **Result**: 0 matching issues across all GitHub repos (1 commit found)
- **Relevance**: Low — Confirms this is a rarely-encountered error because the scenario itself is uncommon. Most teams discover the limitation during design rather than hitting the error at runtime.

## Source Validation Matrix

| Source | Authority | Currency | Cross-Validated | Bias Check | Used In |
|--------|-----------|----------|-----------------|------------|---------|
| WIF Concepts | ★★★★★ | Apr 2025 | ✅ | None (MS Docs) | Root cause |
| App Trust MI | ★★★★★ | Jun 2025 | ✅ | None (MS Docs) | Solution design |
| WIF Considerations | ★★★★★ | Feb 2024 | ✅ | None (MS Docs) | Constraints |
| AKS Cross-Tenant | ★★★★★ | Aug 2024 | ✅ | None (MS Docs) | Counter-example |
| Multi-Tenant App | ★★★★★ | Nov 2024 | ✅ | None (MS Docs) | Solution design |
| Azure Lighthouse | ★★★★★ | Jan 2026 | ✅ | None (MS Docs) | Alternative eval |
| GitHub SDK Issues | ★★★☆☆ | Mar 2026 | N/A | None | Absence evidence |
| GitHub Global | ★★★☆☆ | Mar 2026 | N/A | None | Absence evidence |
