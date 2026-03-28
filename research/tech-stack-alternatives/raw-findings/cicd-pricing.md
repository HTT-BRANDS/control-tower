# CI/CD Pipeline Pricing Comparison

## GitHub Actions

**Source**: https://docs.github.com/en/billing/concepts/product-billing/github-actions
**Date**: Accessed March 2026

### Free Tier by Plan

| Plan | Artifact Storage | Minutes/month | Cache Storage |
|------|-----------------|---------------|---------------|
| GitHub Free | 500 MB | 2,000 | 10 GB |
| GitHub Pro | 1 GB | 3,000 | 10 GB |
| GitHub Free for orgs | 500 MB | 2,000 | 10 GB |
| GitHub Team | 2 GB | 3,000 | 10 GB |
| GitHub Enterprise Cloud | 50 GB | 50,000 | 10 GB |

### Overage Pricing
| Resource | Cost |
|----------|------|
| Additional minutes (Linux) | $0.008/minute |
| Additional minutes (Windows) | $0.016/minute |
| Additional minutes (macOS) | $0.08/minute |
| Additional storage | $0.25/GB/month |
| Additional cache storage | $0.07/GiB/month |

### OIDC Federation for Azure
- Uses `azure/login@v2` action with federated identity
- Well-documented: https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure
- No service principal secrets needed — uses GitHub's OIDC token
- Already configured in this project

### Key Features
- GHCR (GitHub Container Registry) included free with 500MB
- Environment protection rules for approval gates
- Matrix builds for testing across versions
- Marketplace with 20,000+ reusable actions
- Dependabot for automated dependency updates
- Code and CI/CD in same platform

### Estimated Usage for This Project
- ~10 deployments/month × 5 min each = ~50 minutes
- ~30 test runs/month × 3 min each = ~90 minutes
- Total: ~140 minutes/month — well within 2,000 free minutes
- **Monthly cost: $0**

---

## Azure DevOps Pipelines

**Source**: https://azure.microsoft.com/en-us/pricing/details/devops/azure-devops-services/
**Date**: Accessed March 2026

### Free Tier

| Feature | Free Allowance |
|---------|---------------|
| Users (Basic plan) | First 5 free |
| Microsoft-hosted parallel jobs | 1 free (1,800 min/month) |
| Self-hosted parallel jobs | 1 free (unlimited minutes) |
| Azure Artifacts | 2 GB free |

### Paid Tiers
| Resource | Cost |
|----------|------|
| Additional users (Basic) | $6/user/month |
| Additional MS-hosted parallel job | $40/month each |
| Additional self-hosted parallel job | $15/month each |
| Additional Azure Artifacts storage | $2/GB/month |

### OIDC Federation for Azure
- Service connections with workload identity federation
- More setup overhead than GitHub Actions
- Integrated with Azure AD/Entra ID

### Key Features
- Built-in test reporting and analytics
- Release pipelines with stage gates and approvals
- Azure Boards integration for work item tracking
- Better artifact management (Azure Artifacts)
- YAML or visual designer for pipelines
- Deeper Azure Portal integration
- ARM/Bicep deployment tasks (first-party)

### Estimated Usage for This Project
- 1-3 developers → within 5 free users
- 1 parallel job → within free tier
- ~140 minutes/month → within 1,800 minutes
- **Monthly cost: $0**

---

## Side-by-Side Comparison

| Feature | GitHub Actions | Azure DevOps |
|---------|---------------|-------------|
| **Free minutes/month** | 2,000 (Free), 3,000 (Team) | 1,800 |
| **Free parallel jobs** | Unlimited (but queued on 1 runner) | 1 |
| **Additional parallel job** | N/A (uses shared pool) | $40/month |
| **OIDC to Azure** | `azure/login@v2` (easy) | Service connections (medium) |
| **Container registry** | GHCR (500MB free) | ACR ($5+/month) |
| **Approval gates** | Environment protection rules | Release stage gates |
| **Deployment slots** | `azure/webapps-deploy` action | First-party task |
| **Code proximity** | Same platform as code | Separate platform |
| **Work item tracking** | GitHub Issues | Azure Boards |
| **Test reporting** | Third-party actions | Built-in |
| **Visual pipeline editor** | No (YAML only) | Yes + YAML |
| **Self-hosted runners** | Free (unlimited minutes) | 1 free, then $15/mo |

---

## Recommendation

**GitHub Actions is the better choice for this project** because:

1. Already configured and working
2. More free minutes (2,000 vs 1,800)
3. Code + CI/CD in same platform (simpler workflow)
4. GHCR included (no separate container registry cost)
5. Well-documented OIDC federation for Azure
6. Simpler YAML configuration
7. Larger marketplace of reusable actions

**Azure DevOps would be preferred only if:**
- Organization mandates Azure DevOps
- Need for Azure Boards work item tracking
- Need for built-in test reporting
- Multiple parallel jobs needed ($40/mo vs upgrading GitHub plan)
