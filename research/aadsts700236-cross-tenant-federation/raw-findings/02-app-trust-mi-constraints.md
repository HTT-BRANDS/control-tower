# Raw Finding: Configure App to Trust Managed Identity — Constraints

**Source**: https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-config-app-trust-managed-identity
**Captured**: 2026-03-30
**Last Updated on Page**: 2025-06-06

## Prerequisites (Verbatim)

> - A **user-assigned managed identity** assigned to the Azure compute resource (for example, a virtual machine or Azure App Service) that hosts your workload.
> - An app registration in Microsoft Entra ID. This app registration must belong to the **same tenant** as the managed identity.
> - If you need to access resources in another tenant, your app registration must be a **multitenant application** and provisioned into the other tenant.

## Key Constraints (Verbatim)

### Issuer
> **issuer** is the URL of the Microsoft Entra tenant's Authority URL in the form `https://login.microsoftonline.com/{tenant}/v2.0`. **Both the Microsoft Entra app and managed identity must belong to the same tenant.**

### Subject
> **subject**: This is the case-sensitive GUID of the managed identity's Object (Principal) ID assigned to the Azure workload. **The managed identity must be in the same tenant as the app registration**, even if the target resource is in a different cloud.

### Cross-Tenant Support
> **Important**: Accessing resources in another tenant is supported. Accessing resources in another cloud is not supported. Token requests to other clouds will fail.

### User-Assigned MI Only
From the Entra admin center UI:
> "Select managed identity: Click on this link to select the managed identity that will act as the federated identity credential. **You can only use User-Assigned Managed Identities as a credential.**"

## Python Code Sample (Verbatim)

```python
from azure.identity import ManagedIdentityCredential, ClientAssertionCredential
from azure.keyvault.secrets import SecretClient

MI_AUDIENCE = "api://AzureADTokenExchange"

def get_managed_identity_token(credential, audience):
    return credential.get_token(audience).token

# Client ID is passed here. Alternatively, either object ID or resource ID can be passed.
managed_identity_credential = ManagedIdentityCredential(client_id="<YOUR_MI_CLIENT_ID>")

client_assertion_credential = ClientAssertionCredential(
    "<YOUR_RESOURCE_TENANT_ID>",      # Can be a DIFFERENT tenant!
    "<YOUR_APP_CLIENT_ID>",            # Must be in SAME tenant as MI
    lambda: get_managed_identity_token(managed_identity_credential, f"{MI_AUDIENCE}/.default"))

client = SecretClient(
    vault_url="https://testfickv.vault.azure.net",
    credential=client_assertion_credential)
retrieved_secret = client.get_secret("<SECRET_NAME>")
```

Key observations from the code:
1. `YOUR_RESOURCE_TENANT_ID` — can be a **different tenant** (cross-tenant access)
2. `YOUR_APP_CLIENT_ID` — must be the app in the **same tenant** as the MI
3. `YOUR_MI_CLIENT_ID` — a **user-assigned** MI client ID
4. The audience is `api://AzureADTokenExchange` (same as what the project uses)
