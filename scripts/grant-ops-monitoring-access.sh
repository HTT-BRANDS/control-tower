#!/usr/bin/env bash
# Grant ops team access to monitoring dashboards (App Insights + Log Analytics).
#
# Creates (if needed) an "HTT Governance Platform Ops" Entra group,
# then grants it Monitoring Reader on the production resource group so
# members can view App Insights and Log Analytics dashboards.
#
# Context: ct-8by -- ops team needs read-only dashboard access.
#
# Prereqs:
#   - Az CLI installed and logged in to HTT tenant
#   - Caller has Owner or User Access Administrator on HTT-CORE sub
#
# Run:
#   ./scripts/grant-ops-monitoring-access.sh           # dry run
#   ./scripts/grant-ops-monitoring-access.sh --apply   # actually grant

set -euo pipefail

PROD_SUB_ID="32a28177-6fb2-4668-a528-6d6cafb9665e"
PROD_RG="rg-governance-production"
GROUP_NAME="HTT Governance Platform Ops"
GROUP_DESC="Platform ops team — read-only access to App Insights and Log Analytics dashboards"
ROLE="Monitoring Reader"

DRY_RUN=true
for arg in "$@"; do
  case "$arg" in
    --apply) DRY_RUN=false ;;
    -h|--help)
      cat <<HELP
Usage: $(basename "$0") [flags]

Flags:
  --apply    Actually perform grants (default is dry-run)
  -h, --help Show this help
HELP
      exit 0
      ;;
  esac
done

echo "==============================================================="
echo "  Grant ops monitoring dashboard access"
echo "==============================================================="
echo "  Group:     ${GROUP_NAME}"
echo "  Role:      ${ROLE}"
echo "  Scope:     ${PROD_RG}"
echo "  Mode:      $([ "$DRY_RUN" = true ] && echo 'DRY RUN' || echo 'APPLY')"
echo "==============================================================="
echo

# Step 1: Find or create the group
GROUP_ID="$(az ad group list --query "[?displayName=='${GROUP_NAME}'].id" -o tsv 2>/dev/null | head -1 || echo '')"
if [[ -z "$GROUP_ID" ]]; then
  if [[ "$DRY_RUN" = true ]]; then
    echo "WOULD create group: ${GROUP_NAME}"
    echo "  (description: ${GROUP_DESC})"
    GROUP_ID="<would-be-created>"
  else
    GROUP_ID="$(az ad group create \
      --display-name "$GROUP_NAME" \
      --description "$GROUP_DESC" \
      --mail-nickname "htt-gov-ops" \
      --query id -o tsv 2>&1)"
    echo "Created group: ${GROUP_NAME} (${GROUP_ID})"
  fi
else
  echo "Found existing group: ${GROUP_NAME} (${GROUP_ID})"
fi
echo

# Step 2: Add members (Tyler must add real members; we add the caller as placeholder)
CALLER_ID="$(az ad signed-in-user show --query id -o tsv 2>/dev/null || echo '')"
if [[ -n "$CALLER_ID" ]]; then
  IS_MEMBER="$(az ad group member check \
    --group "$GROUP_ID" \
    --member-id "$CALLER_ID" \
    --query value -o tsv 2>/dev/null || echo 'false')"
  if [[ "$IS_MEMBER" != "true" ]]; then
    if [[ "$DRY_RUN" = true ]]; then
      echo "WOULD add caller ($CALLER_ID) as initial group member"
    else
      az ad group member add --group "$GROUP_ID" --member-id "$CALLER_ID" 2>&1 | tail -1
      echo "Added caller as initial group member"
    fi
  else
    echo "Caller already a member"
  fi
fi
echo

# Step 3: Grant Monitoring Reader on the production RG
SCOPE="/subscriptions/${PROD_SUB_ID}/resourceGroups/${PROD_RG}"
EXISTING="$(az role assignment list \
  --assignee "$GROUP_ID" \
  --role "$ROLE" \
  --scope "$SCOPE" \
  --query "[0].id" -o tsv 2>/dev/null || echo '')"
if [[ -n "$EXISTING" ]]; then
  echo "Monitoring Reader already assigned on ${PROD_RG}"
else
  if [[ "$DRY_RUN" = true ]]; then
    echo "WOULD grant '${ROLE}' on ${SCOPE} to group ${GROUP_ID}"
  else
    echo "Granting '${ROLE}' on ${PROD_RG}..."
    az role assignment create \
      --assignee-object-id "$GROUP_ID" \
      --assignee-principal-type Group \
      --role "$ROLE" \
      --scope "$SCOPE" \
      --query "{role:roleDefinitionName,scope:scope,principal:principalId}" \
      -o table
  fi
fi
echo

# Step 4: Also grant Log Analytics Reader at workspace scope for KQL queries
LA_WORKSPACE_ID="/subscriptions/${PROD_SUB_ID}/resourceGroups/${PROD_RG}/providers/Microsoft.OperationalInsights/workspaces/governance-logs"
EXISTING_LA="$(az role assignment list \
  --assignee "$GROUP_ID" \
  --role "Log Analytics Reader" \
  --scope "$LA_WORKSPACE_ID" \
  --query "[0].id" -o tsv 2>/dev/null || echo '')"
if [[ -n "$EXISTING_LA" ]]; then
  echo "Log Analytics Reader already assigned on governance-logs"
else
  if [[ "$DRY_RUN" = true ]]; then
    echo "WOULD grant 'Log Analytics Reader' on governance-logs to group ${GROUP_ID}"
  else
    echo "Granting 'Log Analytics Reader' on governance-logs..."
    az role assignment create \
      --assignee-object-id "$GROUP_ID" \
      --assignee-principal-type Group \
      --role "Log Analytics Reader" \
      --scope "$LA_WORKSPACE_ID" \
      --query "{role:roleDefinitionName,scope:scope,principal:principalId}" \
      -o table
  fi
fi
echo

if [[ "$DRY_RUN" = true ]]; then
  echo "=== DRY RUN COMPLETE — rerun with --apply to actually grant ==="
else
  echo "=== DONE. Ops team members can now open monitoring dashboards. ==="
  echo "Add members with:  az ad group member add --group '${GROUP_NAME}' --member-id <user-object-id>"
  echo "Verify dashboard access: open App Insights in Azure portal as an ops user"
fi
