# Drift Reconciliation

This note records the safe docs-only reconciliation state for bd
`azure-governance-platform-xzt4.5`. It covers Bicep/live-name drift only; it is
not approval to deploy, rename, re-SKU, or otherwise mutate Azure resources.

## References

- GitHub issue: [HTT-BRANDS/control-tower#11](https://github.com/HTT-BRANDS/control-tower/issues/11)
- GitHub Actions run: [25227246032](https://github.com/HTT-BRANDS/control-tower/actions/runs/25227246032)
- bd parent: `azure-governance-platform-xzt4`
- bd child: `azure-governance-platform-xzt4.5`
- Commit context:
  - `b55ee2b` / `c017007` — optional Bicep name override support
  - `cea4f29` — staging live-name pins
  - `c578c3e` — production live-name pins
  - `6b1d8c7` — closed completed xzt4.3/xzt4.4 child work

## Non-negotiable no-deploy guardrail

Do **not** run subscription/resource-group deployments from this task. In
particular, do **not** run:

```bash
az deployment sub create
```

This task intentionally makes no changes to Bicep or parameter files. Any later
actual deployment must be a separate Tyler-approved task with an explicit plan,
approval gate, and rollback notes. Sneaking infra mutation into a docs cleanup is
how we get haunted dashboards. Bad idea. Very bad.

## Why live-name pins exist

The Bicep defaults still generate conventional names for new environments. The
live staging and production environments already have historical names, random
suffixes, and operational dependencies. Optional name override parameters let the
IaC source of truth point at those live resources without forcing destructive
renames or creating parallel infrastructure.

Default behavior remains unchanged when overrides are blank. Environment params
pin only known live names where needed.

## Live name map

### Staging

| Resource | Live name | Reconciliation decision |
|---|---:|---|
| Resource group | `rg-governance-staging` | Pin existing live name. |
| App Service plan | `asp-governance-staging-xnczpwyvwsaba` | Pin existing live name. |
| Web app | `app-governance-staging-xnczpwyv` | Pin existing live name. |
| Application Insights | `ai-governance-staging-xnczpwyvwsaba` | Pin existing live name. |
| Log Analytics | `log-governance-staging-xnczpwyvwsaba` | Pin existing live name. |
| Key Vault | `kv-gov-staging-xnczpwyv` | Pin existing live name. |
| Storage account | `stgovstagingxnczpwyv` | Pin existing live name. |
| SQL server | `sql-governance-staging-77zfjyem` | Live resource exists, but remains unmanaged by this Bicep path while `enableAzureSql=false`. |
| SQL database | `governance` | Live resource exists, but remains unmanaged by this Bicep path while `enableAzureSql=false`. |

Staging SQL exists in Azure, but the current guardrail is explicit: because
`enableAzureSql=false`, staging SQL is **unmanaged / not managed** by this
reconciliation until Tyler approves a later task to bring it under IaC
management. Do not flip that flag as part of drift cleanup.

### Production

| Resource | Live name | Reconciliation decision |
|---|---:|---|
| Resource group | `rg-governance-production` | Pin existing live name. |
| App Service plan | `asp-governance-production` | Pin existing live name. |
| Web app | `app-governance-prod` | Pin existing live name. |
| Application Insights | `governance-appinsights` | Pin existing live name. |
| Log Analytics | `governance-logs` | Pin existing live name. |
| Key Vault | `kv-gov-prod` | Pin existing live name. |
| Storage account | `stgovprodbkup001` | Pin existing live backup storage name. |
| SQL server | `sql-gov-prod-mylxq53d` | Pin existing live name. |
| SQL database | `governance` | Pin existing live name. |

Production has a deliberate database governance override: live production SQL is
Basic per current cost-governance records, while `parameters.production.json`
still carries `sqlDatabaseSku=Standard_S0`. Treat the live Basic database state
as the protected operational baseline unless Tyler explicitly approves a future
SKU reconciliation. This docs task must not alter production DB SKU, flags,
image, auth settings, region, CORS, or any other behavior.

## Remaining drift classification template

Use this table for follow-up decisions. Keep each row boring and auditable.

| Date | Environment | Resource | Observed live state | IaC state | Classification | Decision | Owner | Evidence |
|---|---|---|---|---|---|---|---|---|
| YYYY-MM-DD | staging/prod | resource name | what Azure shows | what Bicep/params say | name drift / SKU drift / unmanaged live resource / expected override / unknown | accept / pin / defer / remove / Tyler approval required | name | link/run/commit |

Classification guidance:

- **Expected override:** params intentionally pin a live name.
- **Unmanaged live resource:** resource exists but IaC intentionally does not
  manage it yet, such as staging SQL while `enableAzureSql=false`.
- **Governance override:** live state intentionally differs for cost, safety, or
  compliance reasons, such as the production DB SKU baseline.
- **Decision required:** behavior-changing drift that needs Tyler approval before
  any file or Azure mutation.

## Validation checklist for this doc-only task

- Confirm only `infrastructure/DRIFT_RECONCILIATION.md` changed.
- Confirm no Bicep or params changed.
- Confirm the document stays under 600 lines.
- Run a basic Markdown sanity check.
- Commit the doc change only; do not push from this task.
