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
DCE_APP_CLIENT_ID="79c22a10-3f2d-4e6a-bddc-ee65c9a46cb0"
DRY_RUN=true
[[ "${1:-}" == "--apply" ]] && DRY_RUN=false

echo "═══════════════════════════════════════════════════════════════"
echo "  Grant DCE sync RBAC — Reader + Security Reader"
echo "═══════════════════════════════════════════════════════════════"
echo "  Tenant:      ${DCE_TENANT_ID} (Delta Crown Extensions)"
echo "  App client:  ${DCE_APP_CLIENT_ID}"
echo "  Mode:        $([ "$DRY_RUN" = true ] && echo 'DRY RUN (preview only)' || echo 'APPLY')"
echo "═══════════════════════════════════════════════════════════════"
echo

# Confirm auth is to DCE tenant
CURRENT_TENANT="$(az account show --query tenantId -o tsv 2>/dev/null || echo '')"
if [[ "$CURRENT_TENANT" != "$DCE_TENANT_ID" ]]; then
  echo "❌ Current az context is tenant '$CURRENT_TENANT', expected DCE '$DCE_TENANT_ID'."
  echo "   Run:  az login --tenant $DCE_TENANT_ID --use-device-code"
  exit 1
fi

# Find the SP object ID inside DCE tenant by app client ID
SP_OBJECT_ID="$(az ad sp show --id "$DCE_APP_CLIENT_ID" --query id -o tsv 2>/dev/null || echo '')"
if [[ -z "$SP_OBJECT_ID" ]]; then
  echo "❌ Could not find service principal for app $DCE_APP_CLIENT_ID in DCE tenant."
  echo "   The app may need to be admin-consented in DCE first:"
  echo "   https://login.microsoftonline.com/$DCE_TENANT_ID/adminconsent?client_id=$DCE_APP_CLIENT_ID"
  exit 1
fi
echo "✓ Found SP in DCE: $SP_OBJECT_ID"
echo

# Enumerate DCE subscriptions
SUBS_JSON="$(az account list --refresh --query "[?tenantId=='$DCE_TENANT_ID'].{id:id,name:name}" -o json)"
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
        -o table
    fi
  done
done

echo
if [[ "$DRY_RUN" = true ]]; then
  echo "═══ DRY RUN COMPLETE — rerun with --apply to actually grant ═══"
else
  echo "═══ DONE. Next sync (~hourly) will pick up new permissions. ═══"
  echo "Verify with:  python scripts/judge.py --env production"
fi
