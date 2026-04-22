# Rollback Plan — v2.5.0 → Previous Known-Good

**Scope**: production transition of artifact `79d72c4` (v2.5.0, pyproject 2.5.0).
**Author**: code-puppy-bf0510 on behalf of Tyler Granlund.
**Last reviewed**: 2026-04-22.
**Consumers**: release-gate-arbiter (Pillar 8 — Rollback), on-call engineer at 2 AM.

> This plan is **release-specific**. It supersedes the generic guidance in
> `docs/OPERATIONAL_RUNBOOK.md §Rollback` for the v2.5.0 promotion only.

---

## 1. Deploy mechanic in play (context)

Production is a **single-slot Azure App Service** running a container.
`deploy-production.yml` deploys by:

```bash
az webapp config container set \
  --container-image-name ghcr.io/htt-brands/azure-governance-platform:${SHA} \
  --container-registry-user ${GITHUB_ACTOR} \
  --container-registry-password ${GHCR_PAT}
az webapp restart
sleep 120    # allow startup + alembic migrations
# 3× health-check retry against /health with 30s spacing
```

There is **no staging slot** on prod App Service, so "slot swap" is NOT
the rollback mechanic. Rollback is done by re-pointing
`--container-image-name` at the previous known-good SHA.

---

## 2. Previous known-good target

| Tag | Commit SHA | GHCR image tag | Role |
|-----|-----------|----------------|------|
| **`v2.5.0`** | `b1137cb` | `ghcr.io/htt-brands/azure-governance-platform:sha-b1137cb10d3c8bea8ed2952652f5ea4fe2e791be` | **Primary rollback target** |
| (recent) | `5c82c71` | `...:sha-5c82c7197eb45b5126f70311f2933cd51d348027` | Secondary fallback (intermediate-state, post-v2.5.0) |
| (HEAD) | `79d72c4` | `...:sha-79d72c440669b1d721272ca42f6ce6939229ce80` | The artifact being promoted |

**Verified 2026-04-22** (via `gh api /orgs/htt-brands/packages/.../versions`):
- `v2.5.0` (`b1137cb`) image exists: package version id `800071134`, tag `sha-b1137cb10d3c8bea8ed2952652f5ea4fe2e791be`, created 2026-04-15 ✓
- `5c82c71` image exists (secondary fallback) ✓
- **`v2.3.0` (`c4929227`) image is NO LONGER in GHCR** — retention policy has pruned pre-April-18 images. If a two-version rollback is ever needed, image must be rebuilt via emergency `workflow_dispatch` on the `v2.3.0` tag first. (Only 79 SHA-tagged images currently retained in GHCR — recency cliff around 2026-04-18.)

**IMAGE TAG FORMAT NOTE**: GHCR tags are `sha-<full 40-char SHA>`, NOT `<short 7-char SHA>`. The `az webapp config container set --container-image-name` command below uses the full-SHA form. Pasting a short-SHA form will silently fail with an opaque "manifest unknown" error.

---

## 3. Reversibility risk assessment

### 3.1 Schema / data migrations — **CLEAN**

```
$ git diff v2.5.0..79d72c4 -- alembic/versions/
 alembic/versions/000_initial_schema.py | 4 ++--
 1 file changed, 2 insertions(+), 2 deletions(-)
```

The *only* change to `alembic/` in the v2.5.0→79d72c4 window is a
**noqa-directive cleanup** (commit `5292c5e`, Python lint hygiene). No
schema DDL changes, no new tables, no new columns, no new indexes, no
data transforms. Rolling the image back does not require any data
reversal.

### 3.2 Config changes — **NONE ACTIVE**

Both `parameters.production.json` deltas (`containerImage` registry-org
change in `399c209`, `enableRedis` flip in `0f47f33`) landed **before**
`v2.5.0` (2026-04-17 vs v2.5.0 tag 2026-04-15 content but tagged later).
They are NOT in the v2.5.0→79d72c4 promotion delta.

### 3.3 Secrets — **NO ROTATION REQUIRED**

No secrets were rotated in this release window. GHCR_PAT, AZURE_CLIENT_ID,
tenant credentials are unchanged.

### 3.4 External contracts — **NONE BROKEN**

Scan for breaking API changes in release window:

```
$ git log --oneline v2.5.0..79d72c4 -- app/api/ app/schemas/
# (no commits touching api/ or schemas/ in window)
```

No consumer impact. GitHub Pages static docs site and the FastAPI backend
remained version-compatible across this entire window.

---

## 4. Rollback procedure (authoritative)

> **Run in this exact order.** Timings below are measured from the last
> successful prod deploy (ref `v2.5.0` at `b1137cb`). Worst-case budget:
> **4 minutes to restored /health on b1137cb**.

### Step 0 — Confirm rollback is the right move (30 seconds)

Before rolling back, answer:
- Is `/health` returning 5xx for > 2 minutes? → yes: proceed.
- Is Application Insights showing a coherent error class (single stack
  trace dominant > 50% of errors)? → yes: proceed.
- Is the error surface traceable to code in the v2.5.0→79d72c4 delta
  specifically (vs. an unrelated Azure-side incident)? → yes: proceed.

If any answer is "no", first check `az webapp log tail` before deciding.

### Step 1 — Pin the image back (60 seconds)

```bash
# Pre-flight: confirm the target image exists in GHCR.
# NOTE: tag is the FULL 40-char sha, prefixed with `sha-`.
gh api -H "Accept: application/vnd.github+json" \
  /orgs/htt-brands/packages/container/azure-governance-platform/versions \
  --jq '.[] | select(.metadata.container.tags[]? == "sha-b1137cb10d3c8bea8ed2952652f5ea4fe2e791be") | .id' \
  | head -1
# Expect: a non-empty numeric ID (was 800071134 at last audit 2026-04-22).

# Pin prod to v2.5.0 (full-SHA tag is required):
az webapp config container set \
  --name app-governance-prod \
  --resource-group rg-governance-prod-001 \
  --container-image-name ghcr.io/htt-brands/azure-governance-platform:sha-b1137cb10d3c8bea8ed2952652f5ea4fe2e791be \
  --container-registry-url https://ghcr.io \
  --container-registry-user "${GITHUB_ACTOR:-htt-brands-deploy}" \
  --container-registry-password "$GHCR_PAT"
```

### Step 2 — Restart with the pinned image (120 seconds)

```bash
az webapp restart \
  --name app-governance-prod \
  --resource-group rg-governance-prod-001

sleep 120   # allow alembic + app startup; migrations are idempotent
```

### Step 3 — Verify `/health` returns 200 (up to 90 seconds)

```bash
for i in 1 2 3; do
  STATUS=$(curl -sf https://app-governance-prod.azurewebsites.net/health \
           -w "%{http_code}" -o /dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "✅ rollback verified (attempt $i)"
    break
  fi
  echo "⏳ HTTP $STATUS — retry in 30s"
  sleep 30
done
```

**If /health still non-200 after 3 attempts**: page Tyler AND escalate to
secondary fallback (Step 5).

### Step 4 — Verify deep health + smoke-test a governance read (30 seconds)

```bash
curl -sf https://app-governance-prod.azurewebsites.net/health/detailed | jq .
curl -sf https://app-governance-prod.azurewebsites.net/healthz/data   | jq .
# Both should return status=ok and no any_stale=true flags.
```

### Step 5 — ONLY IF v2.5.0 also bad

**v2.3.0 image (`c4929227`) is no longer available in GHCR** per the retention
audit in §2 above. Two paths:

**5a. Preferred — drop to `5c82c71` (intermediate-state, post-v2.5.0):**
```bash
az webapp config container set \
  --name app-governance-prod \
  --resource-group rg-governance-prod-001 \
  --container-image-name ghcr.io/htt-brands/azure-governance-platform:sha-5c82c7197eb45b5126f70311f2933cd51d348027 \
  --container-registry-url https://ghcr.io \
  --container-registry-user "${GITHUB_ACTOR:-htt-brands-deploy}" \
  --container-registry-password "$GHCR_PAT"
# Then re-run Steps 2-4.
```
Note: `5c82c71` is the test-fix commit (closes bd 6o4g); it has identical app
behavior to v2.5.0 for any runtime codepath, differing only in the test suite.
Safe rollback target.

**5b. Emergency — rebuild v2.3.0 from source tag:**
If something is so broken that even `5c82c71` is inadequate, trigger the
build workflow via `workflow_dispatch` on the `v2.3.0` tag to produce a fresh
image. This is a ~8-minute operation and should not be attempted unless both
`v2.5.0` and `5c82c71` are known-failing — it means you're in a cross-version
data-compatibility scenario that warrants paging beyond Tyler.

---

## 5. Post-rollback mandatory actions

1. **Open an incident ticket** in bd (P0, tag `incident,rollback`).
2. **Preserve the bad image** in GHCR: `gh api ... tags` — do NOT delete
   `:79d72c4`, it is evidence.
3. **Attach to incident**:
   - Application Insights query window (time of deploy → time of rollback)
   - `az webapp log download` output
   - Health-check failure output
4. **Block re-deploy of 79d72c4** by reverting the promotion ref on `main`
   and tagging the revert commit `v2.5.1` before re-attempting forward.
5. **Write up a 5-whys retro** within 24 hours. File it at
   `docs/incidents/YYYY-MM-DD-v2.5.0-rollback.md`.

---

## 6. People on deck for this rollback

| Role | Person | Method |
|------|--------|--------|
| Release owner | Tyler Granlund | direct |
| On-call Azure access | Tyler Granlund | direct (only holder today) |
| Comms → franchisees | deferred — tag `ops-comms-collie` if > 10 min outage |
| Secondary reviewer | (none assigned — single-operator environment) |

> **Single-operator risk is flagged for this release.** Landing `7mk8`
> (supply-chain) + bringing a second human into the rollback runbook is
> a pre-condition for production-gate going from CONDITIONAL to
> unconditional PASS.

---

## 7. Non-goals of this plan

- Does NOT cover DNS failover (CDN / Front Door not in play for this service).
- Does NOT cover database restore-from-backup (not needed — no schema changes).
- Does NOT cover rolling back the CHANGELOG / git tags (those remain
  historical record; roll forward with a v2.5.1 revert if needed).
