# Raw Finding: Workload Identity Federation Concepts — Key Restriction

**Source**: https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation
**Captured**: 2026-03-30
**Last Updated on Page**: 2025-04-09

## Critical Note (Verbatim)

> **Note**
> Microsoft Entra ID issued tokens may not be used for federated identity flows. The federated identity credentials flow does not support tokens issued by Microsoft Entra ID.

## Context

This note appears in the main "Workload Identity Federation" concepts page, within the "Supported scenarios" section. The supported scenarios listed are:

1. Workloads running on **any Kubernetes cluster** (AKS, EKS, GKE, on-prem)
2. **GitHub Actions**
3. **Workloads running on Azure compute platforms using app identities** — "First assign a user-assigned managed identity to your Azure VM or App Service. Then, configure a trust relationship between your app and the user-assigned identity."
4. **Google Cloud**
5. **Amazon Web Services (AWS)**
6. **Other workloads** running in compute platforms outside of Azure
7. **SPIFFE and SPIRE**
8. **Azure Pipelines** service connections

## Important Supported Scenario (#3)

The third supported scenario explicitly mentions App Service:

> "Workloads running on Azure compute platforms using app identities. First assign a **user-assigned managed identity** to your Azure VM or App Service. Then, configure a trust relationship between your **app and the user-assigned identity**."

This confirms:
- User-assigned MI is required (not system-assigned)
- The trust relationship is between the **app registration** and the **UAMI**
- Both must be in the same tenant (clarified in the detailed doc)

## How It Works

Verbatim from documentation:

> 1. The external workload (such as a GitHub Actions workflow) requests a token from the external IdP (such as GitHub).
> 2. The external IdP issues a token to the external workload.
> 3. The external workload sends the token to Microsoft identity platform and requests an access token.
> 4. Microsoft identity platform checks the trust relationship on the user-assigned managed identity or app registration and validates the external token against the OpenID Connect (OIDC) issuer URL on the external IdP.
> 5. When the checks are satisfied, Microsoft identity platform issues an access token to the external workload.
> 6. The external workload accesses Microsoft Entra protected resources using the access token.

The key insight: in the MI-to-app pattern, the MI token acts as the "external IdP token" but it's still an Entra token. Microsoft allows this as a **specific carve-out** within the same tenant only.
