# AADSTS700236: Cross-Tenant OIDC Workload Identity Federation Research

## Executive Summary

**Error AADSTS700236** ("Entra ID tokens issued by issuer may not be used for federated identity credentials") is caused by a **hard platform limitation** in Microsoft Entra ID. The current architecture—using a system-assigned Managed Identity's token as a federated identity credential assertion against app registrations in foreign tenants—is **fundamentally unsupported** and cannot be fixed with configuration changes.

### Root Cause (Confirmed via Official Microsoft Documentation)

Microsoft's Workload Identity Federation documentation contains this explicit note:

> **"Microsoft Entra ID issued tokens may not be used for federated identity flows. The federated identity credentials flow does not support tokens issued by Microsoft Entra ID."**
>
> — [Workload Identity Federation concepts](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation), last updated 2025-04-09

Managed Identity tokens **are** Microsoft Entra ID tokens (issuer: `https://login.microsoftonline.com/{tenant}/v2.0`). When `ClientAssertionCredential` presents an MI token as a client assertion to a foreign tenant's token endpoint, that tenant's Entra ID recognizes it as an Entra-issued token and rejects it with AADSTS700236.

### The Exception: "Configure App to Trust Managed Identity" (June 2025)

Microsoft introduced a **specific exception** to the general rule — documented at [Configure an application to trust a managed identity](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity) — but with **critical constraints**:

| Constraint | Requirement | Current Implementation |
|---|---|---|
| MI Type | **User-assigned** only | ❌ System-assigned |
| Same Tenant | MI and app registration must be in the **same tenant** | ❌ MI in HTT, apps in BCC/FN/TLL/DCE |
| Cross-tenant | App can access **resources** in other tenants | ✅ This is supported |

### Verdict

The project's `oidc_credential.py` implementation is architecturally sound in its *code* but aims at an **impossible target**. The solution requires an architectural change, not a code fix.

---

## Recommended Solution: Multi-Tenant App + UAMI (Zero Secrets)

**This is the recommended path.** It achieves the same secretless goal using the officially supported pattern.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     HOME TENANT (HTT)                         │
│                                                               │
│  ┌─────────────────┐     ┌─────────────────────────────────┐ │
│  │  App Service     │     │  Multi-Tenant App Registration  │ │
│  │  ┌─────────┐    │     │  (signInAudience:               │ │
│  │  │  UAMI   │────┼─FIC─│   AzureADMultipleOrgs)          │ │
│  │  └─────────┘    │     │  Client ID: {single-app-id}     │ │
│  └─────────────────┘     └───────────┬─────────────────────┘ │
│                                      │                        │
└──────────────────────────────────────┼────────────────────────┘
                                       │ Admin consent provisioned
           ┌───────────────┬───────────┼───────────┬─────────────┐
           │               │           │           │             │
     ┌─────▼─────┐  ┌─────▼─────┐ ┌───▼───┐ ┌────▼────┐ ┌─────▼─────┐
     │    HTT    │  │    BCC    │ │  FN   │ │  TLL   │  │   DCE    │
     │ Service   │  │ Service   │ │Service│ │Service │  │ Service  │
     │ Principal │  │ Principal │ │Princ. │ │Princ.  │  │ Princ.   │
     │ (auto)    │  │ (consent) │ │(cons.)│ │(cons.) │  │ (cons.)  │
     └───────────┘  └───────────┘ └───────┘ └────────┘  └──────────┘
```

### Implementation Steps

1. **Create a User-Assigned Managed Identity (UAMI)** in the HTT tenant
2. **Assign the UAMI** to the App Service (alongside or replacing the system-assigned MI)
3. **Create ONE multi-tenant app registration** in the HTT tenant
4. **Configure a federated identity credential** on that app to trust the UAMI
5. **Provision via admin consent** into each foreign tenant using the admin consent URL
6. **Grant Graph API permissions** in each tenant via the service principal
7. **Update `oidc_credential.py`** to use the UAMI client ID and single app client ID

### Key Code Change

```python
# BEFORE (broken — cross-tenant MI federation)
def _get_mi_assertion(self) -> str:
    token = self._get_mi_credential().get_token("api://AzureADTokenExchange")
    return token.token

def get_credential_for_tenant(self, tenant_id: str, client_id: str) -> TokenCredential:
    # client_id is different per foreign tenant — ❌ won't work
    return ClientAssertionCredential(
        tenant_id=tenant_id,
        client_id=client_id,        # Foreign tenant's app
        func=self._get_mi_assertion,
    )

# AFTER (working — same-tenant MI federation, multi-tenant app)
def _get_mi_assertion(self) -> str:
    token = self._get_mi_credential().get_token("api://AzureADTokenExchange")
    return token.token

def get_credential_for_tenant(self, tenant_id: str) -> TokenCredential:
    return ClientAssertionCredential(
        tenant_id=tenant_id,
        client_id=self._home_tenant_app_id,  # ✅ Same home-tenant app
        func=self._get_mi_assertion,
    )
```

---

## Alternative Solutions (Ranked)

| # | Approach | Secrets? | Complexity | Graph API? | Recommended? |
|---|---|---|---|---|---|
| 1 | **Multi-tenant app + UAMI** | None | Medium | ✅ | ✅ **Yes** |
| 2 | **Per-tenant apps + Key Vault secrets** | In Key Vault | Low | ✅ | Fallback |
| 3 | **Multi-tenant app + certificate** | Cert in KV | Medium | ✅ | Alternative |
| 4 | **Azure Lighthouse** | None | Low | ❌ ARM only | For ARM ops only |

See [analysis.md](./analysis.md) for detailed comparison.
See [recommendations.md](./recommendations.md) for implementation plan.
