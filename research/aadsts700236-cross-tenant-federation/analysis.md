# Multi-Dimensional Analysis: Cross-Tenant Secretless Authentication

## 1. Why the Current Approach Fails

### The Token Flow (Current — Broken)

```
App Service (HTT Tenant)
  │
  ├─ ManagedIdentityCredential.get_token("api://AzureADTokenExchange")
  │   → Calls IMDS endpoint → Returns MI token from login.microsoftonline.com/HTT/v2.0
  │
  ├─ ClientAssertionCredential(tenant_id=BCC, client_id=BCC_APP, func=mi_assertion)
  │   → Sends MI token as client_assertion to login.microsoftonline.com/BCC/oauth2/v2.0/token
  │   → BCC's Entra ID inspects assertion:
  │       - Issuer: login.microsoftonline.com/HTT/v2.0  ← This is Entra ID!
  │       - ❌ AADSTS700236: "Entra ID tokens may not be used for federated identity credentials"
  │
  └─ FAILS
```

### Three Separate Problems

1. **Entra-to-Entra federation blocked**: The general WIF rule prohibits Entra-issued tokens as assertions in federated identity credential flows. The MI token IS an Entra-issued token.

2. **System-assigned MI not supported**: Even if the Entra-to-Entra rule were relaxed, the "App trust MI" feature only supports user-assigned managed identities.

3. **Cross-tenant MI-to-app trust not supported**: Even with a UAMI, the MI and app registration must be in the same tenant. The current design places apps in foreign tenants.

---

## 2. Solution Comparison Matrix

### Option A: Multi-Tenant App + UAMI Federation (RECOMMENDED)

**How it works**: One multi-tenant app in the home tenant, federated to trust a UAMI. The app is provisioned into foreign tenants via admin consent, creating a service principal in each.

#### Security Analysis
| Factor | Assessment |
|--------|------------|
| Secret exposure | **None** — no secrets, no certificates to rotate |
| Credential lifetime | MI tokens are short-lived (~24h), auto-refreshed |
| Blast radius | Single app = single identity to audit across tenants |
| Least privilege | Graph API permissions granted per-tenant via service principal |
| Audit trail | All token exchanges logged in home tenant + target tenants |
| Rotation risk | Zero — MI tokens managed by platform |

#### Cost Analysis
| Factor | Assessment |
|--------|------------|
| Key Vault | Not needed for secrets (saves ~$0.03/10K ops) |
| UAMI | Free (no additional Azure cost) |
| App Registration | Free (included in Entra ID) |
| Admin Consent | One-time setup per tenant (no ongoing cost) |
| **Total additional cost** | **$0** |

#### Implementation Complexity
| Factor | Assessment |
|--------|------------|
| Code changes | ~50 lines in `oidc_credential.py` + config updates |
| Infrastructure | Create 1 UAMI, 1 app reg, 1 FIC |
| Per-tenant setup | Admin consent URL (one-time, ~5 min/tenant) |
| Graph permissions | Grant via PowerShell/CLI per tenant |
| Testing | Can test locally with `DefaultAzureCredential` fallback |
| **Estimated effort** | **1-2 days** |

#### Stability & Maintenance
| Factor | Assessment |
|--------|------------|
| Maturity | GA feature (documented June 2025) |
| Deprecation risk | Low — actively documented and promoted by Microsoft |
| Breaking changes | Low — standard OAuth2 client_credentials flow |
| Support | Covered by Microsoft support plans |
| Update frequency | N/A — platform-managed |

---

### Option B: Per-Tenant Apps + Key Vault Secrets (Current Fallback)

**How it works**: Separate app registration in each tenant, each with its own client secret stored in Azure Key Vault. The App Service MI accesses Key Vault to retrieve secrets.

#### Security Analysis
| Factor | Assessment |
|--------|------------|
| Secret exposure | Secrets in Key Vault (encrypted at rest) |
| Credential lifetime | Client secrets expire (1-2 years typically) |
| Blast radius | Per-tenant isolation (compromised secret affects one tenant) |
| Least privilege | Can be scoped per-tenant |
| Audit trail | Key Vault access logs + Entra sign-in logs |
| Rotation risk | **High** — manual rotation needed across 5 tenants |

#### Cost Analysis
| Factor | Assessment |
|--------|------------|
| Key Vault | ~$0.03/10K secret operations |
| App Registrations | Free (5 required) |
| Secret rotation | Staff time: ~2h per rotation × 5 tenants × 1-2/year |
| Outage risk | Expired secrets cause downtime |
| **Total additional cost** | **$5-10/month + staff time** |

#### Implementation Complexity
| Factor | Assessment |
|--------|------------|
| Code changes | Already implemented (`ClientSecretCredential` path) |
| Infrastructure | Key Vault + 5 app registrations (already exist) |
| Per-tenant setup | Already done |
| **Estimated effort** | **0 days** (already working) |

#### Stability & Maintenance
| Factor | Assessment |
|--------|------------|
| Maturity | Fully GA, battle-tested pattern |
| Maintenance burden | **High** — secret rotation, monitoring for expiry |
| Service disruption risk | **Medium** — expired/rotated secrets cause outages |

---

### Option C: Multi-Tenant App + Certificate from Key Vault

**How it works**: One multi-tenant app in the home tenant authenticated with a certificate stored in Key Vault. MI accesses Key Vault to retrieve the certificate for signing assertions.

#### Security Analysis
| Factor | Assessment |
|--------|------------|
| Secret exposure | Certificate in Key Vault (private key never leaves KV) |
| Credential lifetime | Certificates expire (1-3 years typically) |
| Rotation risk | Medium — less frequent than secrets but still manual |

#### Cost Analysis
| Factor | Assessment |
|--------|------------|
| Key Vault | ~$0.03/10K operations |
| Certificate | Self-signed = free; CA-signed = $50-200/year |
| **Total additional cost** | **$0-20/month** |

#### Implementation Complexity
| Factor | Assessment |
|--------|------------|
| Code changes | ~100 lines (certificate-based credential provider) |
| Infrastructure | 1 Key Vault cert + 1 multi-tenant app |
| **Estimated effort** | **1-2 days** |

---

### Option D: Azure Lighthouse

**How it works**: Azure Lighthouse delegates Azure Resource Manager access from customer tenants to the managing tenant.

#### Critical Limitation
> Azure Lighthouse supports requests handled by Azure Resource Manager (`https://management.azure.com`). It does **not** support Microsoft Graph API (`https://graph.microsoft.com`).

This project requires Graph API for:
- User enumeration (`/users`)
- MFA method analysis (`/users/{id}/authentication/methods`)
- Directory role assignments (`/directoryRoles`)
- Security events
- Audit logs

**Verdict**: Azure Lighthouse can complement but **cannot replace** the Graph API authentication requirement.

#### Compatibility Analysis
| Operation | Lighthouse | Graph API Required |
|-----------|-----------|-------------------|
| Resource inventory | ✅ | ❌ |
| Cost management | ✅ | ❌ |
| Policy compliance | ✅ | ❌ |
| User enumeration | ❌ | ✅ |
| MFA status | ❌ | ✅ |
| Directory roles | ❌ | ✅ |
| Sign-in activity | ❌ | ✅ |
| Security events | ❌ | ✅ |

---

## 3. Cross-Tenant WIF: Why AKS Can Do It But App Service Can't

AKS cross-tenant workload identity works because:
1. AKS has its own **OIDC issuer** (e.g., `https://oidc.prod-aks.azure.com/{cluster-id}`)
2. This is a **non-Entra IdP** — tokens come from the Kubernetes OIDC provider
3. The foreign tenant's UAMI trusts this external issuer — standard WIF flow
4. The Entra-to-Entra prohibition does not apply

App Service does NOT have its own OIDC issuer. The Managed Identity endpoint (`IDENTITY_ENDPOINT` / IMDS) issues standard Entra ID tokens from `login.microsoftonline.com`. There is no way to make App Service MI tokens appear as "external" tokens.

---

## 4. Decision Matrix

| Criterion (Weight) | Option A: UAMI+MT App | Option B: KV Secrets | Option C: Cert | Option D: Lighthouse |
|---|---|---|---|---|
| Zero secrets (30%) | ✅ 30 | ❌ 0 | ⚠️ 15 | ✅ 30 |
| Graph API support (25%) | ✅ 25 | ✅ 25 | ✅ 25 | ❌ 0 |
| Maintenance burden (20%) | ✅ 20 | ❌ 5 | ⚠️ 12 | ✅ 20 |
| Implementation effort (15%) | ⚠️ 10 | ✅ 15 | ⚠️ 10 | ⚠️ 8 |
| Platform maturity (10%) | ✅ 10 | ✅ 10 | ✅ 10 | ✅ 10 |
| **Total** | **95** | **55** | **72** | **68** |

**Winner: Option A (Multi-Tenant App + UAMI Federation)**
