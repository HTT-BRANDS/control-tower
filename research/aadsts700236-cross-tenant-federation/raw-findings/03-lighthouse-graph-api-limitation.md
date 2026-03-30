# Raw Finding: Azure Lighthouse Does NOT Support Graph API

**Source**: https://learn.microsoft.com/en-us/azure/lighthouse/concepts/cross-tenant-management-experience
**Captured**: 2026-03-30
**Last Updated on Page**: 2026-01-21

## Key Limitation (Verbatim)

> "Azure Lighthouse supports requests handled by Azure Resource Manager. The operation URIs for these requests start with `https://management.azure.com`. However, Azure Lighthouse doesn't support requests that are handled by an instance of a resource type, such as Key Vault secrets access or storage data access."

## Implication for This Project

The governance platform needs Graph API access for:
- `GET /users` — user enumeration
- `GET /users/{id}/authentication/methods` — MFA status
- `GET /directoryRoles` — privileged role assignments
- `GET /reports/authenticationMethods/userRegistrationDetails` — MFA reports
- `GET /auditLogs/signIns` — sign-in activity
- `GET /security/alerts_v2` — security events

All of these hit `https://graph.microsoft.com/v1.0/` or `/beta/`, which is NOT supported by Azure Lighthouse.

## What Lighthouse CAN Do

Lighthouse is effective for ARM-based operations that the platform also needs:
- Resource inventory (VMs, storage, networking)
- Cost management & billing
- Azure Policy compliance
- Azure Monitor / Defender for Cloud
- Azure Backup management

## Conclusion

Azure Lighthouse should be used **alongside** (not instead of) the multi-tenant app + UAMI pattern:
- Lighthouse → ARM operations
- Multi-tenant app → Graph API operations
