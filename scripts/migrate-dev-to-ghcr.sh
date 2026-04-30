#!/bin/bash
# =============================================================================
# migrate-dev-to-ghcr.sh — gz6i (Phase 2 follow-up to ll49)
# =============================================================================
#
# Migrates app-governance-dev-001 from acrgovernancedev → GHCR.
# Strategy: Option B (reuse the :staging tag — dev becomes a free soak-test).
# Rationale:
#   - YAGNI: no separate :dev tag means one fewer workflow to maintain.
#   - The dev image hasn't been actively iterated since 2026-03-31 per ll49,
#     so independent dev cadence isn't buying us anything right now.
#   - If dev ever needs its own cadence again, add a :dev tag and this script
#     becomes a 1-line sed.
#
# PREREQUISITES:
#   1. GHCR personal access token with read:packages scope
#      (same value staging webapp uses — see GitHub repo secrets)
#   2. az CLI logged in to the subscription holding rg-governance-dev
#
# USAGE:
#   GHCR_PAT='ghp_...' ./scripts/migrate-dev-to-ghcr.sh
#   GHCR_PAT='ghp_...' ./scripts/migrate-dev-to-ghcr.sh --delete-acr  # purge ACR after verify
#
# =============================================================================

set -euo pipefail

# ── Config ──
RESOURCE_GROUP="rg-governance-dev"
APP_NAME="app-governance-dev-001"
GHCR_URL="https://ghcr.io"
GHCR_USER="HTT-BRANDS"
GHCR_IMAGE="ghcr.io/htt-brands/control-tower:staging"
OLD_ACR_NAME="acrgovernancedev"
HEALTH_TIMEOUT_SEC=120

# ── Flags ──
DELETE_ACR=false
for arg in "$@"; do
    case "$arg" in
        --delete-acr) DELETE_ACR=true ;;
        -h|--help)    sed -n '3,25p' "$0"; exit 0 ;;
        *)            echo "Unknown flag: $arg" >&2; exit 1 ;;
    esac
done

# ── Colors ──
if [ -t 1 ]; then
    RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
    BLUE=$'\033[0;34m'; NC=$'\033[0m'
else
    RED=""; GREEN=""; YELLOW=""; BLUE=""; NC=""
fi

# ── Guards ──
if [ -z "${GHCR_PAT:-}" ]; then
    echo -e "${RED}✗ GHCR_PAT env var is required.${NC}"
    echo "  Get the value from the 'GHCR_PAT' (or equivalent) GitHub repo secret"
    echo "  that deploy-staging.yml already uses."
    exit 1
fi

az account show >/dev/null 2>&1 || { echo -e "${RED}✗ Not logged in. Run: az login${NC}"; exit 1; }

echo -e "${BLUE}╭─ dev → GHCR migration (gz6i) ─────────────────────────────────╮${NC}"
echo -e "${BLUE}│${NC}   App:            $APP_NAME"
echo -e "${BLUE}│${NC}   Resource group: $RESOURCE_GROUP"
echo -e "${BLUE}│${NC}   New image:      $GHCR_IMAGE"
echo -e "${BLUE}│${NC}   Old ACR:        $OLD_ACR_NAME  (delete? $DELETE_ACR)"
echo -e "${BLUE}╰────────────────────────────────────────────────────────────────╯${NC}"
echo ""

# ── Step 1: swap registry config on the webapp ──
echo -e "${YELLOW}→${NC} Configuring container registry credentials..."
az webapp config container set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --docker-registry-server-url "$GHCR_URL" \
    --docker-registry-server-user "$GHCR_USER" \
    --docker-registry-server-password "$GHCR_PAT" \
    --container-image-name "$GHCR_IMAGE" \
    >/dev/null
echo -e "${GREEN}✓${NC} Registry config updated."

# ── Step 2: restart so the new pull happens ──
echo -e "${YELLOW}→${NC} Restarting webapp to pick up the new image..."
az webapp restart --name "$APP_NAME" --resource-group "$RESOURCE_GROUP"
echo -e "${GREEN}✓${NC} Restart issued."

# ── Step 3: wait for /health ──
APP_URL="https://${APP_NAME}.azurewebsites.net/health"
echo -e "${YELLOW}→${NC} Waiting up to ${HEALTH_TIMEOUT_SEC}s for $APP_URL to respond 200..."
elapsed=0
until curl -fsS -o /dev/null -w '%{http_code}' "$APP_URL" 2>/dev/null | grep -q '^200$'; do
    sleep 5
    elapsed=$((elapsed + 5))
    if [ $elapsed -ge $HEALTH_TIMEOUT_SEC ]; then
        echo -e "${RED}✗ Health check timed out after ${HEALTH_TIMEOUT_SEC}s${NC}"
        echo "  Inspect logs: az webapp log tail -g $RESOURCE_GROUP -n $APP_NAME"
        exit 1
    fi
    printf '.'
done
echo ""
echo -e "${GREEN}✓${NC} Dev webapp is healthy on the GHCR image."

# ── Step 4 (optional): delete the old ACR ──
if [ "$DELETE_ACR" = true ]; then
    echo ""
    read -r -p "Really delete ACR '$OLD_ACR_NAME'? This is irreversible. [y/N] " reply
    case "$reply" in
        y|Y|yes|YES)
            echo -e "${YELLOW}→${NC} Deleting $OLD_ACR_NAME..."
            az acr delete --name "$OLD_ACR_NAME" --resource-group "$RESOURCE_GROUP" --yes
            echo -e "${GREEN}✓${NC} ACR deleted. ~\$5/mo saved."
            ;;
        *)
            echo "Skipped ACR deletion. Re-run with --delete-acr later if desired."
            ;;
    esac
else
    echo ""
    echo "ACR '$OLD_ACR_NAME' left in place. Re-run with --delete-acr once you're"
    echo "satisfied dev is stable on the GHCR image (suggested soak: 1–2 days)."
fi

echo ""
echo -e "${GREEN}╭─ DONE ────────────────────────────────────────────────────────╮${NC}"
echo -e "${GREEN}│${NC} Dev now pulls from GHCR. No new workflow needed — it trails"
echo -e "${GREEN}│${NC} the :staging tag, so every staging deploy rolls to dev too."
echo -e "${GREEN}╰────────────────────────────────────────────────────────────────╯${NC}"
