#!/usr/bin/env bash
# Grant Reader + Security Reader to the DCE governance app reg
# on every DCE subscription. Run this from a Delta Crown Extensions
# tenant admin account with Owner or User Access Administrator
# privileges on the target subscription(s).
#
# Context: ct-1m0 — DCE shows partial sync (costs+identity work,
# resources+compliance fail) because the DCE-side app registration
# lacks ARM and Defender RBAC.
#
# Prereqs:
#   - Az CLI installed and logged in to DCE tenant
#   - Caller has User Access Administrator or Owner on DCE subs
#
# Run:
#   ./scripts/grant-dce-sync-permissions.sh           # dry run
#   ./scripts/grant-dce-sync-permissions.sh --apply   # actually grant

set -euo pipefail

DCE_TENANT_ID="ce62e17d-2feb-4e67-a115-8ea4af68da30"
# 2026-05-28: the multi-tenant app Riverside-Capital-PE-Governance-Platform.
# Same appId is used in HTT/BCC/FN/TLL — DCE just needed its SP granted RBAC.
# Previous value (79c22a10-...) was stale and never existed in DCE.
DCE_APP_CLIENT_ID="1e3e8417-49f1-4d08-b7be-47045d8a12e9"
DRY_RUN=true
ELEVATE=false
CLEANUP_ELEVATION=false
for arg in "$@"; do
  case "$arg" in
    --apply) DRY_RUN=false ;;
    --elevate-access) ELEVATE=true ;;
    --cleanup-elevation) CLEANUP_ELEVATION=true ;;
    -h|--help)
      cat <<HELP
Usage: $(basename "$0") [flags]

Flags:
  --apply              Actually perform grants (default is dry-run)
  --elevate-access     Self-elevate Global Admin → root-scope User Access Admin
                       (required first time if caller has no sub-scope RBAC)
  --cleanup-elevation  Remove the root-scope UAA assignment after grants
                       (recommended after --apply succeeds)
  -h, --help           Show this help

Typical flow for a Global Admin (Tyler) running this the first time:
  1. az login --tenant <DCE> --allow-no-subscriptions
  2. ./grant-dce-sync-permissions.sh --elevate-access --apply --cleanup-elevation
HELP
      exit 0
      ;;
  esac
done

echo "═══════════════════════════════════════════════════════════════"
echo "  Grant DCE sync RBAC — Reader + Security Reader"
echo "═══════════════════════════════════════════════════════════════"
echo "  Tenant:      ${DCE_TENANT_ID} (Delta Crown Extensions)"
echo "  App client:  ${DCE_APP_CLIENT_ID}"
echo "  Mode:        $([ "$DRY_RUN" = true ] && echo 'DRY RUN (preview only)' || echo 'APPLY')"
echo "═══════════════════════════════════════════════════════════════"
echo

# Confirm DCE tenant token is available.
# az account show returns the *default subscription's* tenant, which is often
# a home tenant (e.g. HTT) even when a DCE token is cached.  The reliable
# check is to request a token for the DCE tenant explicitly.
DCE_TOKEN_TENANT="$(az account get-access-token --tenant "$DCE_TENANT_ID" --query tenant -o tsv 2>/dev/null || echo '')"
if [[ "$DCE_TOKEN_TENANT" != "$DCE_TENANT_ID" ]]; then
  echo " No DCE tenant token available (got '$DCE_TOKEN_TENANT')."
  echo "   Run:  az login --tenant $DCE_TENANT_ID --use-device-code --allow-no-subscriptions"
  exit 1
fi

# Step 0: Optionally elevate Global Admin → root-scope User Access Administrator
if [[ "$ELEVATE" = true ]]; then
  echo "→ Elevating access: GA → User Access Admin at root scope '/'..."
  if [[ "$DRY_RUN" = true ]]; then
    echo "  (DRY RUN — would POST /providers/Microsoft.Authorization/elevateAccess)"
  else
    az rest --method post \
      --url "https://management.azure.com/providers/Microsoft.Authorization/elevateAccess?api-version=2016-07-01" \
      --tenant "$DCE_TENANT_ID" \
      2>&1 | tail -3
    echo "  ✓ Elevation granted (propagation can take 30s-2min)"
    echo "  Waiting 30s for propagation..."
    sleep 30
  fi
  echo
fi

# Find the SP object ID inside DCE tenant by app client ID
SP_OBJECT_ID="$(az ad sp show --id "$DCE_APP_CLIENT_ID" --query id -o tsv 2>/dev/null || echo '')"
# Fallback: query via MS Graph if cross-tenant SP lookup fails
if [[ -z "$SP_OBJECT_ID" ]]; then
  SP_OBJECT_ID="$(az rest --method get \n    --url "https://graph.microsoft.com/v1.0/servicePrincipals?\$filter=appId eq '$DCE_APP_CLIENT_ID'" \n    --tenant "$DCE_TENANT_ID" \n    --query 'value[0].id' -o tsv 2>/dev/null || echo '')"
fi
if [[ -z "$SP_OBJECT_ID" ]]; then
  echo "❌ Could not find service principal for app $DCE_APP_CLIENT_ID in DCE tenant."
  echo "   The app may need to be admin-consented in DCE first:"
  echo "   https://login.microsoftonline.com/$DCE_TENANT_ID/adminconsent?client_id=$DCE_APP_CLIENT_ID"
  exit 1
fi
echo "✓ Found SP in DCE: $SP_OBJECT_ID"
echo

# Enumerate DCE subscriptions via ARM REST API (works even when CLI default
# is a different tenant -- az account list filters by default sub context).
SUBS_JSON="$(az rest \
  --method get \
  --url "https://management.azure.com/subscriptions?api-version=2022-12-01" \
  --tenant "$DCE_TENANT_ID" \
  --query "value[?tenantId=='$DCE_TENANT_ID'].{id:subscriptionId,name:displayName}" \
  -o json 2>/dev/null || echo '[]')"
SUB_COUNT="$(echo "$SUBS_JSON" | python3 -c 'import json,sys;print(len(json.load(sys.stdin)))')"
if [[ "$SUB_COUNT" == "0" ]]; then
  echo "❌ Zero DCE subscriptions visible to current account."
  echo "   You need at least Reader on the subs to see them, and"
  echo "   User Access Administrator or Owner to grant roles."
  exit 1
fi
echo "Found $SUB_COUNT DCE subscription(s):"
echo "$SUBS_JSON" | python3 -c 'import json,sys
for s in json.load(sys.stdin):
  print(f"  - {s[\"name\"]:<40s} {s[\"id\"]}")'
echo

# Roles to assign
ROLES=("Reader" "Security Reader")

for SUB_ID in $(echo "$SUBS_JSON" | python3 -c 'import json,sys
for s in json.load(sys.stdin): print(s["id"])'); do
  for ROLE in "${ROLES[@]}"; do
    SCOPE="/subscriptions/${SUB_ID}"
    EXISTING="$(az role assignment list \
      --assignee "$SP_OBJECT_ID" \
      --role "$ROLE" \
      --scope "$SCOPE" \
      --query "[0].id" -o tsv 2>/dev/null || echo '')"
    if [[ -n "$EXISTING" ]]; then
      echo "✓ ${SUB_ID}: '$ROLE' already assigned"
      continue
    fi
    if [[ "$DRY_RUN" = true ]]; then
      echo "→ WOULD grant '$ROLE' on $SCOPE to SP $SP_OBJECT_ID"
    else
      echo "→ Granting '$ROLE' on $SCOPE..."
      az role assignment create \
        --assignee-object-id "$SP_OBJECT_ID" \
        --assignee-principal-type ServicePrincipal \
        --role "$ROLE" \
        --scope "$SCOPE" \
        --query "{role:roleDefinitionName,scope:scope,principal:principalId}" \
        -o table 2>&1
    fi
  done
done

echo
# Step N: Optionally remove root-scope UAA assignment (cleanup)
if [[ "$CLEANUP_ELEVATION" = true ]]; then
  echo "→ Cleaning up: removing root-scope User Access Admin elevation..."
  CALLER_OBJECT_ID="$(az ad signed-in-user show --query id -o tsv 2>/dev/null || echo '')"
  if [[ -z "$CALLER_OBJECT_ID" ]]; then
    echo "  ⚠ Could not resolve caller object ID — skip manual cleanup."
  elif [[ "$DRY_RUN" = true ]]; then
    echo "  (DRY RUN — would remove UAA assignment for $CALLER_OBJECT_ID at scope '/')"
  else
    az role assignment delete \
      --assignee "$CALLER_OBJECT_ID" \
      --role "User Access Administrator" \
      --scope "/" 2>&1 | tail -3
    echo "  ✓ Elevation revoked"
  fi
  echo
fi

if [[ "$DRY_RUN" = true ]]; then
  echo "═══ DRY RUN COMPLETE — rerun with --apply to actually grant ═══"
else
  echo "═══ DONE. Next sync (~hourly) will pick up new permissions. ═══"
  echo "Verify with:  python scripts/judge.py --env production"
fi
