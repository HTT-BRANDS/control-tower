# ACR to GHCR Migration Runbook

**Author:** Code Puppy (Richard)  
**Date:** 2025-01-28  
**Status:** ✅ Complete  
**Risk Level:** Medium (requires App Service configuration change)

---

## Executive Summary

This runbook documents the migration from **Azure Container Registry (ACR)** to **GitHub Container Registry (GHCR)** for the Azure Governance Platform. This migration provides:

| Benefit | Impact |
|---------|--------|
| **Cost Savings** | GHCR is **FREE** for public repos vs ACR Standard ($5/day = ~$150/month) |
| **Simpler Auth** | Uses `GITHUB_TOKEN` — no ACR credentials needed in GitHub Actions |
| **Better Integration** | Native GitHub integration, no Azure-specific registry dependency |
| **Improved DX** | Simpler CI/CD configuration, one less secret to manage |

---

## Pre-Migration Checklist

- [ ] Verify repository is **public** (GHCR is free for public repos)
- [ ] Confirm all team members have GitHub Packages access
- [ ] Verify Azure App Service supports GHCR (✅ Yes, via managed identity)
- [ ] Schedule migration window (minimal downtime expected)
- [ ] Notify team of upcoming change

---

## Migration Steps

### Phase 1: Infrastructure Updates (5 min)

1. **Update Bicep template** to support configurable registry URL:
   ```bicep
   // infrastructure/modules/app-service.bicep
   param containerRegistryUrl string = 'https://ghcr.io'
   ```

2. **Update environment parameters**:
   ```json
   // infrastructure/parameters.staging.json
   "containerImage": {
     "value": "ghcr.io/htt-brands/control-tower:staging"
   }
   
   // infrastructure/parameters.production.json
   "containerImage": {
     "value": "ghcr.io/htt-brands/control-tower:latest"
   }
   ```

### Phase 2: Workflow Updates (10 min)

1. **Update staging deployment workflow** (`.github/workflows/deploy-staging.yml`):
   - Replace `az acr build` with Docker Buildx → GHCR push
   - Use `docker/login-action` with `GITHUB_TOKEN`
   - Add `packages: write` permission

2. **Update production deployment workflow** (`.github/workflows/deploy-production.yml`):
   - Same changes as staging workflow

3. **Key workflow changes**:
   ```yaml
   permissions:
     packages: write  # Required for GHCR push
   
   env:
     GHCR_REGISTRY: ghcr.io
     GHCR_REPOSITORY: htt-brands/control-tower
   
   steps:
     - uses: docker/login-action@v3
       with:
         registry: ${{ env.GHCR_REGISTRY }}
         username: ${{ github.actor }}
         password: ${{ secrets.GITHUB_TOKEN }}
   
     - uses: docker/build-push-action@v6
       with:
         push: true
         tags: |
           ghcr.io/htt-brands/control-tower:${{ env.IMAGE_TAG }}
   ```

### Phase 3: Image Migration (Optional — 15 min)

If you need to preserve existing images from ACR:

1. **Run the migration workflow** (`.github/workflows/container-registry-migration.yml`):
   - Go to **Actions → Container Registry Migration**
   - Click **Run workflow**
   - Specify ACR registry and tags to migrate
   - Start with **dry_run: true** to preview
   - Run with **dry_run: false** to migrate

2. **Supported migration options**:
   | Option | Description |
   |--------|-------------|
   | `tags: latest,staging` | Migrate specific tags |
   | `tags: all` | Migrate all tags from repository |
   | `dry_run: true` | Preview without actual migration |

### Phase 4: App Service Configuration (5 min)

1. **Update Azure App Service** to pull from GHCR:
   ```bash
   # Staging
   az webapp config container set \
     --name app-governance-staging-xnczpwyv \
     --resource-group rg-governance-staging \
     --container-image-name ghcr.io/htt-brands/azure-governance-platform:staging \
     --container-registry-url https://ghcr.io
   
   # Production
   az webapp config container set \
     --name app-governance-prod \
     --resource-group rg-governance-production \
     --container-image-name ghcr.io/htt-brands/azure-governance-platform:latest \
     --container-registry-url https://ghcr.io
   ```

2. **Verify container settings**:
   - `DOCKER_REGISTRY_SERVER_URL` should be `https://ghcr.io`
   - `WEBSITES_ENABLE_APP_SERVICE_STORAGE` should be `false`

### Phase 5: Verification (10 min)

1. **Test staging deployment**:
   ```bash
   # Trigger staging deployment
   git commit --allow-empty -m "chore: verify GHCR integration"
   git push origin main
   
   # Monitor deployment in GitHub Actions
   # Verify health check passes
   curl https://app-governance-staging-xnczpwyv.azurewebsites.net/health
   ```

2. **Test production deployment**:
   - Run production deployment workflow manually
   - Verify smoke tests pass
   - Check Teams notification shows correct image reference

---

## Post-Migration Cleanup

### Optional: Remove ACR References

After successful migration and 48-hour stabilization:

1. **Delete ACR credentials** from GitHub Secrets:
   - `ACR_USERNAME`
   - `ACR_PASSWORD`

2. **Delete Azure Container Registry**:
   ```bash
   az acr delete --name acrgovprod --resource-group <rg-name>
   ```
   ⚠️ **WARNING**: Ensure all images are migrated and verified before deletion!

3. **Update cost tracking** — Document monthly savings (~$150/month)

---

## Troubleshooting

### Issue: GHCR push fails with 403

**Cause:** Missing `packages: write` permission  
**Solution:** Add to workflow permissions:
```yaml
permissions:
  packages: write
```

### Issue: App Service can't pull from GHCR

**Cause:** Missing registry URL configuration  
**Solution:** Ensure `--container-registry-url https://ghcr.io` is set

### Issue: Image not found in GHCR

**Cause:** Repository might be private or image doesn't exist  
**Solution:**
- Verify image visibility: `https://github.com/tygranlund?tab=packages`
- Check image exists: `docker manifest inspect ghcr.io/htt-brands/azure-governance-platform:latest`

### Issue: Migration workflow fails on specific tag

**Cause:** Tag might not exist in ACR  
**Solution:** Run with `dry_run: true` first to verify available tags

---

## Rollback Plan

If issues arise post-migration:

1. **Revert to ACR image**:
   ```bash
   az webapp config container set \
     --name <app-name> \
     --resource-group <rg-name> \
     --container-image-name acrgovprod.azurecr.io/azure-governance-platform:latest \
     --container-registry-url https://acrgovprod.azurecr.io
   ```

2. **Revert workflow changes** via git:
   ```bash
   git revert <migration-commit-sha>
   ```

3. **Update infrastructure** back to ACR parameters

---

## Cost Analysis

| Service | Before (ACR) | After (GHCR) | Monthly Savings |
|---------|-------------|--------------|-----------------|
| Registry | Standard SKU (~$5/day) | Free (public repo) | **~$150** |
| Data Transfer | ~$0.10/GB | Included | ~$10-50 |
| **Total** | **~$160-200/month** | **$0** | **~$150-200/month** |

---

## Files Modified

| File | Change |
|------|--------|
| `.github/workflows/deploy-staging.yml` | ACR → GHCR, GITHUB_TOKEN auth |
| `.github/workflows/deploy-production.yml` | ACR → GHCR, GITHUB_TOKEN auth |
| `.github/workflows/container-registry-migration.yml` | New: One-time migration workflow |
| `infrastructure/modules/app-service.bicep` | Add `containerRegistryUrl` parameter |
| `infrastructure/parameters.production.json` | Update image to GHCR |
| `docker-compose.prod.yml` | Update comment to reference GHCR |
| `docker-compose.yml` | Add GHCR comment |
| `docs/runbooks/acr-to-ghcr-migration.md` | New: This documentation |

---

## References

- [GitHub Container Registry Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Azure App Service Container Registry Integration](https://learn.microsoft.com/en-us/azure/app-service/configure-custom-container)
- [docker/build-push-action](https://github.com/docker/build-push-action)
- [docker/login-action](https://github.com/docker/login-action)

---

## Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Author | Richard (Code Puppy) | 2025-01-28 | 🐾 |
| Reviewer | [To be filled] | | |
| Approver | [To be filled] | | |

---

**Questions?** Contact the platform engineering team or check the GitHub Actions logs for detailed error messages.
