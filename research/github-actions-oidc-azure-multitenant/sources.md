# Sources and credibility assessment

All primary sources below are Tier 1 unless noted otherwise.

| Source | Reliability | Notes |
|---|---:|---|
| Microsoft Learn: [Authenticate to Azure from GitHub Actions by OpenID Connect](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect) | Tier 1 | Official Microsoft guidance for Azure Login action, required `id-token: write`, `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, and environment secrets note. |
| Microsoft Learn: [Workload identity federation concepts](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation) | Tier 1 | Official Entra concepts for exchanging external identity provider tokens for Microsoft identity platform access tokens. |
| Microsoft Learn CLI: [`az ad app federated-credential`](https://learn.microsoft.com/en-us/cli/azure/ad/app/federated-credential?view=azure-cli-latest) | Tier 1 | Official CLI command group for listing/showing federated identity credentials. |
| Microsoft Learn CLI: [`az ad app`](https://learn.microsoft.com/en-us/cli/azure/ad/app?view=azure-cli-latest) | Tier 1 | Official CLI app registration command group; used for `az ad app list`. |
| Microsoft Learn CLI: [`az ad sp`](https://learn.microsoft.com/en-us/cli/azure/ad/sp?view=azure-cli-latest) | Tier 1 | Official CLI service principal command group; used for `az ad sp list`. |
| Microsoft Learn CLI: [`az role assignment`](https://learn.microsoft.com/en-us/cli/azure/role/assignment?view=azure-cli-latest) | Tier 1 | Official Azure RBAC role assignment command group. |
| Microsoft Learn: [What is Azure Lighthouse?](https://learn.microsoft.com/en-us/azure/lighthouse/overview) | Tier 1 | Official product overview for cross-tenant delegated resource management. |
| Microsoft Learn: [View and manage service providers](https://learn.microsoft.com/en-us/azure/lighthouse/how-to/view-manage-service-providers) | Tier 1 | Official portal-oriented guidance for viewing delegated service-provider access. |
| Microsoft Learn CLI: [`az managedservices assignment`](https://learn.microsoft.com/en-us/cli/azure/managedservices/assignment?view=azure-cli-latest) | Tier 1 | Official CLI command group for Lighthouse registration assignments. |
| Microsoft Learn CLI: [`az managedservices definition`](https://learn.microsoft.com/en-us/cli/azure/managedservices/definition?view=azure-cli-latest) | Tier 1 | Official CLI command group for Lighthouse registration definitions. |
| GitHub Docs: [Configuring OpenID Connect in Azure](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-azure) | Tier 1 | Official GitHub guidance for Azure OIDC, requiring Azure login and federated credentials. |
| GitHub Docs: [OpenID Connect / hardening deployments](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/about-security-hardening-with-openid-connect) | Tier 1 | Official GitHub OIDC security model and token claim guidance. |
| GitHub Docs: [Secrets reference](https://docs.github.com/en/actions/reference/security/secrets) | Tier 1 | Official GitHub secret scope and behavior reference. |
| GitHub CLI manual: [`gh secret list`](https://cli.github.com/manual/gh_secret_list) | Tier 1 | Official CLI manual for listing repository/environment/organization secrets. |
| GitHub CLI manual: [`gh api`](https://cli.github.com/manual/gh_api) | Tier 1 | Official CLI manual for calling GitHub REST APIs, used to list environments and secret metadata. |

## Validation

Findings were cross-checked across Microsoft Learn and GitHub Docs. Command syntax was grounded in the official Azure CLI and GitHub CLI manuals. Raw extracted source text snapshots are in `raw-findings/` for local review.
