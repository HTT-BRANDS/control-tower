# ct-90r.10 Contributor RBAC removal evidence

Captured: 2026-05-18T16:35:00Z

## Scope

Remove broad direct `Contributor` assignments from staging and production
resource groups for CI/CD or platform principals after environment-scoped OIDC
principals were configured with narrower roles.

## Removed assignments

Removed direct `Contributor` assignments on:

```text
/subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-staging
/subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-production
```

Principals affected:

```text
azure-governance-platform-oidc-dev
  appId:      3184145f-dab3-4f22-8cd4-4b8a11eea6ed
  objectId:   7307bf65-6bbb-428d-b21e-d7b86d3be16f

Riverside-Capital-PE-Governance-Platform
  appId:      1e3e8417-49f1-4d08-b7be-47045d8a12e9
  objectId:   b8e67903-abf5-4b53-9ced-d194d43ca277
```

Command shape:

```bash
az role assignment delete \
  --assignee <principal-object-id> \
  --role Contributor \
  --scope <staging-or-production-resource-group-id>
```

## Post-removal verification

Direct `Contributor` assignments on staging and production resource groups now
return empty:

```text
rg-governance-staging:    <none>
rg-governance-production: <none>
```

Validation command:

```bash
for rg in rg-governance-staging rg-governance-production; do
  RG_ID=$(az group show -n "$rg" --query id -o tsv)
  az role assignment list --scope "$RG_ID" \
    --query '[?roleDefinitionName==`Contributor` && scope==`'"$RG_ID"'`].{principalName:principalName,principalType:principalType,principalId:principalId,scope:scope}' \
    -o table
done
```

## Narrow deploy principals retained

The environment-scoped OIDC principals retain narrow roles required by deploy and
operations workflows.

```text
control-tower-oidc-staging
  objectId: aab735ac-d6ff-4d71-ba78-631fbf482c3c
  roles:
    Website Contributor                       rg-governance-staging
    Web Plan Contributor                      rg-governance-staging
    Monitoring Contributor                    rg-governance-staging
    Control Tower SQL Firewall Rule Operator  staging SQL server
    Control Tower Storage Account Key Reader  staging storage account

control-tower-oidc-production
  objectId: 84d2111e-f2d3-4f0e-af37-7b7e56862daf
  roles:
    Website Contributor                       rg-governance-production
    Web Plan Contributor                      rg-governance-production
    Monitoring Contributor                    rg-governance-production
    Key Vault Secrets User                    rg-governance-production
```

## Notes

- Dev resource-group roles were not changed.
- Subscription-level Reader/Security Reader/Monitoring Reader/Cost Management
  Reader assignments on the runtime/platform app were not changed.
- The removal intentionally targets only broad direct `Contributor` on staging
  and production resource groups.

## Follow-up validation

Full closure of `ct-90r.10` should wait until deployment/backup/drift validation
runs on the environment-scoped principals complete successfully. The supporting
validation-only workflow is in PR #23.
