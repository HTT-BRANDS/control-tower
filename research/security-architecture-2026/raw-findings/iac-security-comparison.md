# IaC Security Comparison: Bicep vs Terraform vs Pulumi

## State Management Security

### Bicep (Current)
- **State storage**: None. ARM API is the source of truth.
- **Secret exposure in state**: N/A — no state file exists.
- **State locking**: N/A — Azure Resource Manager handles concurrency.
- **State backup**: N/A — deployment history stored in Azure.
- **Blast radius**: Deployment history may contain `@secure()` parameter values internally (masked in portal). Mitigated by purging old deployments.

### Terraform
- **State storage**: `.tfstate` file (JSON) — must be stored remotely for team use.
- **Secret exposure in state**: ⚠️ **HIGH RISK**. All resource attribute values stored in plaintext JSON, including passwords, connection strings, and keys. Even with `sensitive = true` flag, values are in the state file.
- **State locking**: Azure Blob lease or DynamoDB (AWS). Must be configured manually.
- **State backup**: Must configure versioning on storage account.
- **Blast radius**: If state file is leaked, ALL secrets are exposed. This is the #1 security risk of Terraform.
- **Mitigation**: Azure Blob with encryption, access policies, versioning. Backend config:
  ```hcl
  terraform {
    backend "azurerm" {
      resource_group_name  = "rg-terraform-state"
      storage_account_name = "stterraformstate"
      container_name       = "tfstate"
      key                  = "governance.tfstate"
    }
  }
  ```
- **Cost**: Storage account for state (~$1/mo) + optional Terraform Cloud ($20/mo+)

### Pulumi
- **State storage**: Pulumi Cloud (SaaS) or self-managed backend (S3, Azure Blob, local file).
- **Secret exposure in state**: Better than Terraform. Pulumi encrypts secret values in state by default when using Pulumi Cloud. With self-managed backends, secrets are marked but may be in plaintext depending on configuration.
- **State locking**: Built-in with Pulumi Cloud. Manual with self-managed.
- **Cost**: Free for individual. $50/mo+ for team features.

## Drift Detection

| Feature | Bicep | Terraform | Pulumi |
|---------|-------|-----------|--------|
| Command | `az deployment sub what-if` | `terraform plan` | `pulumi preview` |
| Detects config drift | Yes (compares desired vs actual) | Yes (compares state vs actual + config) | Yes |
| Detects manual changes | Yes | Yes | Yes |
| Automatic remediation | Via incremental deployment | Via `terraform apply` | Via `pulumi up` |
| Azure Policy integration | Native | Via provider | Via provider |

## Secret Handling

### Bicep
```bicep
@secure()
param sqlAdminPassword string   // Not logged in deployment
param jwtSecretKey string       // But stored in ARM deployment history

// Key Vault reference (preferred):
value: '@Microsoft.KeyVault(SecretUri=https://vault.vault.azure.net/secrets/key)'
```

### Terraform
```hcl
variable "sql_admin_password" {
  type      = string
  sensitive = true  // Hidden in CLI output but IN STATE FILE
}

// Better: read from Key Vault data source
data "azurerm_key_vault_secret" "sql_password" {
  name         = "sql-admin-password"
  key_vault_id = azurerm_key_vault.main.id
}
```

### Pulumi
```python
import pulumi

config = pulumi.Config()
sql_password = config.require_secret("sqlPassword")  # Encrypted in state
```

## Azure-Native Advantages of Bicep

1. **Day-0 support**: New Azure APIs available immediately in Bicep (auto-generated from ARM schemas)
2. **No provider lag**: Terraform's azurerm provider typically has 1-7 day lag for new features
3. **What-if previews**: Native integration with Azure Resource Manager
4. **Template specs**: Store and version Bicep templates in Azure (no external registry)
5. **Deployment stacks**: Group related resources for lifecycle management
6. **Azure Policy as Code**: Native integration with Azure Policy for compliance
7. **Visual Studio Code extension**: First-party IntelliSense, validation, and deployment

## Current Project's Bicep Usage Assessment

### Strengths
- Uses `@secure()` for passwords and keys ✅
- Key Vault references for JWT secret ✅
- Module decomposition (app-service, sql-server, key-vault, etc.) ✅
- Environment parameterization (dev, staging, production) ✅
- System-assigned Managed Identity ✅

### Weaknesses
- Storage account key in outputs (identified in prior audit) ❌
- No Azure Policy definitions for enforcement ⚠️
- No deployment history cleanup automation ⚠️
- `sqlAdminPassword` default uses `newGuid()` — not stored but regenerated each deployment ⚠️
