# SESSION HANDOFF — Azure Governance Platform

**Last session:** code-puppy-0e02df — Version: 1.5.7 + OIDC (pending release tag)
**Status:** 🟢 ALL ENVIRONMENTS LIVE — OIDC implementation complete, pending Azure-side activation

---

## Current State

```
2933 unit/integration tests passed, 0 failed
74 staging E2E tests passed, 31 skipped (auth-gated)
9 smoke tests: SKIPPED (correct — no MI env on dev machine)
ruff check: All checks passed (0 errors)
Version: 1.5.7 (code complete; OIDC changes unreleased, tagged as Unreleased in CHANGELOG)
Requirements: 57/57 implemented (100%)
```

---

## Environment Status

| Environment | URL | Version | Health | Routes |
|-------------|-----|---------|--------|--------|
| **Dev** | https://app-governance-dev-001.azurewebsites.net | 0.2.0 | ✅ | Legacy |
| **Staging** | https://app-governance-staging-xnczpwyv.azurewebsites.net | **1.5.7** | ✅ | 167 |
| **Production** | https://app-governance-prod.azurewebsites.net | **1.5.7** | ✅ | 167 |

---

## What Was Done This Session

### OIDC Workload Identity Federation — Full Implementation

Complete replacement of `ClientSecretCredential` (secret-based auth) with
`ClientAssertionCredential` backed by App Service Managed Identity. No Key Vault,
no client secrets, no rotation.

#### Code changes
| File | Change |
|------|--------|
| `app/core/oidc_credential.py` | NEW — `OIDCCredentialProvider` with 3-tier resolution |
| `app/core/config.py` | Added `use_oidc_federation`, `azure_managed_identity_client_id` fields; updated `is_configured` |
| `app/core/tenants_config.py` | `key_vault_secret_name` optional; `oidc_enabled=True` all tenants; `get_app_id_for_tenant()` helper |
| `app/models/tenant.py` | Added `use_oidc: bool` column |
| `app/api/services/azure_client.py` | `get_credential()` OIDC path |
| `app/api/services/graph_client.py` | `_get_credential()` OIDC path |
| `app/preflight/azure_checks.py` | Preflight bypasses secret check in OIDC mode |
| `.env.example` | OIDC section added |

#### Scripts
| Script | Purpose |
|--------|---------|
| `scripts/setup-federated-creds.sh` | One-time: creates federated credentials on all 5 app registrations |
| `scripts/verify-federated-creds.sh` | Read-only: verifies federated cred config |
| `scripts/seed_riverside_tenants.py` | Upserts all 5 tenants into DB with `use_oidc=True` |

#### Migrations
| Migration | Change |
|-----------|--------|
| `alembic/versions/007_add_oidc_federation.py` | Adds `use_oidc` bool column to `tenants` table |

#### Tests
| File | Tests | Status |
|------|-------|--------|
| `tests/unit/test_oidc_credential.py` | 39 | ✅ All pass |
| `tests/smoke/test_oidc_connectivity.py` | 9 | ✅ Skip gracefully (no MI env) |
| `tests/unit/test_config.py` | +6 OIDC tests appended | ✅ All pass |

#### Docs
| Doc | Purpose |
|-----|---------|
| `docs/OIDC_TENANT_AUTH.md` | Complete setup, operation, troubleshooting guide |
| `CHANGELOG.md` | `[Unreleased]` section updated |

#### Bug fixed along the way
`test_graph_async_token.py` poisons `sys.modules["azure.identity"]` with a
`MagicMock`, which caused `MagicMock(spec=<azure class>)` → `InvalidSpecError`
in the full suite. Fixed by dropping `spec=` on 3 return-value mocks in
`test_oidc_credential.py`.

---

## Remaining Items (Azure-Side — Requires Manual Execution)

Code is 100% complete and tested. These steps require Azure admin access and
a running App Service. They cannot be done from a dev machine without the MI.

| Step | Command | Status |
|------|---------|--------|
| 1. Get MI Object ID | `az webapp identity show --name app-governance-prod --resource-group rg-governance-production --query principalId -o tsv` | ⏳ Run first |
| 2. Configure federated creds (all 5 tenants) | `./scripts/setup-federated-creds.sh --managing-tenant-id 0c0e35dc-188a-4eb3-b8ba-61752154b407 --mi-object-id <MI_OBJECT_ID>` | ⏳ Needs admin |
| 3. Enable OIDC on App Service | `az webapp config appsettings set --name app-governance-prod --resource-group rg-governance-production --settings USE_OIDC_FEDERATION=true` | ⏳ Pending |
| 4. Set MI client ID (user-assigned only) | `az webapp config appsettings set ... AZURE_MANAGED_IDENTITY_CLIENT_ID=<id>` | ⏳ If user-assigned |
| 5. Apply DB migration (if not already) | `uv run alembic upgrade head` | ⏳ Pending |
| 6. Seed tenant records | `uv run python scripts/seed_riverside_tenants.py` | ⏳ Pending |
| 7. Verify federated creds | `./scripts/verify-federated-creds.sh --managing-tenant-id 0c0e35dc-... --mi-object-id <id>` | ⏳ Pending |
| 8. Run smoke tests from staging | `uv run pytest tests/smoke/test_oidc_connectivity.py -v` | ⏳ Needs Azure env |

---

## Billing RBAC Status (CO-007, from previous session)

| Tenant | Billing Account | RBAC Role | DB Config |
|--------|----------------|-----------|-----------|
| HTT | Enterprise (Head to Toe Brands) | ✅ Cost Mgmt Reader | ✅ Set |
| BCC | BISHOPS CUTS - BCC LLC | ✅ Cost Mgmt Reader | ✅ Set |
| FN | Tyler Granlund (Frenchies) | ✅ Cost Mgmt Reader | ✅ Set |
| TLL | Tyler Granlund (Lash Lounge) | ✅ Cost Mgmt Reader | ✅ Set |
| DCE | No subscription | ⏭️ N/A | Not set |

---

## Other Open Items

| Item | Status | Blocker |
|------|--------|---------|
| Sui Generis full integration | Placeholder endpoints live | API credentials from MSP |
| DCE tenant billing | Skipped | No subscription/billing account |
| Dev environment update | At v0.2.0 | Low priority, not used for validation |

---

## Quick Resume Commands

```bash
cd /Users/tygranlund/dev/azure-governance-platform
git status && git log --oneline -5
uv run pytest -q --ignore=tests/e2e --ignore=tests/smoke --ignore=tests/staging --ignore=tests/load
uv run ruff check .
curl -s https://app-governance-prod.azurewebsites.net/health
curl -s https://app-governance-staging-xnczpwyv.azurewebsites.net/health
```

### Azure-side OIDC activation (run when ready)

```bash
# Step 1: Get the MI Object ID
MI_OBJECT_ID=$(az webapp identity show \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --query principalId -o tsv)
echo "MI Object ID: $MI_OBJECT_ID"

# Step 2: Configure federated credentials on all 5 tenants
./scripts/setup-federated-creds.sh \
  --managing-tenant-id 0c0e35dc-188a-4eb3-b8ba-61752154b407 \
  --mi-object-id "$MI_OBJECT_ID"

# Step 3: Enable OIDC mode on App Service
az webapp config appsettings set \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --settings USE_OIDC_FEDERATION=true

# Step 4: Run migrations + seed
uv run alembic upgrade head
uv run python scripts/seed_riverside_tenants.py

# Step 5: Verify
./scripts/verify-federated-creds.sh \
  --managing-tenant-id 0c0e35dc-188a-4eb3-b8ba-61752154b407 \
  --mi-object-id "$MI_OBJECT_ID"
```

---

**Plane Status: 🛬 LANDED — Code complete, tests green, docs written. Azure-side activation pending.**
