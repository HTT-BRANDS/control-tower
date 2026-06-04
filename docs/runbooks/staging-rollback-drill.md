# Runbook: staging rollback drill (ct-c60)

**Goal:** *rehearse* the production rollback on **staging** so that when prod
needs it, ops have already done it - and confirm our rollback tooling actually
works. Owner: pairing (Tyler runs the Azure steps).

> Why staging: a rollback you've never executed is a rollback you don't have.
> We practice the exact motion on the staging app where a mistake is harmless.

## Step 0 - Discover the rollback shape (do this first)

Two rollback mechanisms exist; which one applies depends on the topology:

```bash
az account set --subscription HTT-CORE

# Does prod use deployment SLOTS (blue-green), or is staging a separate app?
az webapp deployment slot list -n app-governance-prod -g rg-governance-production -o table
```

- **Slots present** -> rollback = **slot swap** (Path A).
- **No slots** (staging is the separate app `app-governance-staging-xnczpwyv`)
  -> rollback = **redeploy the previous image tag** (Path B). This is the most
  likely case (the deploy workflows don't reference slot swaps).

Run whichever path matches. **Both are rehearsed against staging only.**

---

## Path A - slot-swap rehearsal (only if Step 0 shows slots)

```bash
APP=app-governance-prod ; RG=rg-governance-production    # adjust if staging has its own slot
# 1. Validate the target slot is healthy BEFORE swapping
./scripts/validate-slot.sh "$APP" "$RG" staging
# 2. Swap (this is the rollback motion)
az webapp deployment slot swap -n "$APP" -g "$RG" --slot staging --target-slot production
# 3. Verify
./scripts/verify-and-test-deployment.sh --environment staging
# 4. Swap BACK to restore the rehearsal state
az webapp deployment slot swap -n "$APP" -g "$RG" --slot staging --target-slot production
```

---

## Path B - image-tag rollback rehearsal (the likely case)

Rehearse on the **staging app** so prod is never touched.

```bash
APP=app-governance-staging-xnczpwyv ; RG=rg-governance-staging

# 1. Record the CURRENT image tag (this is your "good" state to restore to)
CURRENT=$(az webapp config container show -n "$APP" -g "$RG" \
  --query "[?name=='DOCKER_CUSTOM_IMAGE_NAME'].value | [0]" -o tsv)
echo "Current staging image: $CURRENT"

# 2. Pick a known-good PREVIOUS tag (from GHCR or the deploy history)
#    e.g. a prior commit-sha or version tag of ghcr.io/htt-brands/control-tower
PREVIOUS=ghcr.io/htt-brands/control-tower:<PREVIOUS_TAG>

# 3. Roll "back" to the previous tag (the rollback motion)
az webapp config container set -n "$APP" -g "$RG" --container-image-name "$PREVIOUS"
az webapp restart -n "$APP" -g "$RG"

# 4. Verify staging is healthy on the rolled-back image
./scripts/verify-and-test-deployment.sh --environment staging
curl -s https://${APP}.azurewebsites.net/health | jq '{status, version}'

# 5. RESTORE to the current image (end the rehearsal cleanly)
az webapp config container set -n "$APP" -g "$RG" --container-image-name "$CURRENT"
az webapp restart -n "$APP" -g "$RG"
./scripts/verify-and-test-deployment.sh --environment staging
```

---

## Step 3 - Confirm the rollback-state artifact still matches

Our machine-checkable rollback metadata should agree with the deploy workflow:

```bash
uv run python scripts/verify_release_rollback_state.py   # exit 0 = consistent
```

## Validation (the ct-c60 close criterion)

- [ ] The rollback motion (swap or image-set) **completed** on staging.
- [ ] `verify-and-test-deployment.sh --environment staging` **passed** on the
      rolled-back state.
- [ ] Staging was **restored** to its original state and re-verified.
- [ ] `verify_release_rollback_state.py` exits 0.
- [ ] Time-to-rollback noted (so we know our real RTO for an incident).

## Abort / safety

- If validation fails on the rolled-back image, **restore immediately** (Step 5
  / swap back) and file a bd issue - that means our last-known-good isn't good.
- **Never rehearse on prod.** This drill is staging-only; the prod procedure
  itself lives in `OPERATIONAL_RUNBOOK.md` -> "Rollback Procedure".

## Related

- `OPERATIONAL_RUNBOOK.md` (prod rollback how-to), `disaster-recovery.md`
  (full DR), `INCIDENT_RESPONSE.md` (when to pull the trigger), bd `uchp`
  (quarterly DR test - this drill is a lightweight subset pulled forward).
