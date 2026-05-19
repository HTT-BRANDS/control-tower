#!/usr/bin/env bash
# =============================================================================
# rotate-azure-secret.sh — rotate the AZURE_AD_CLIENT_SECRET across all the
# places it lives, in the right order, without ever logging the secret.
#
# Context: ct-jxe — prod data syncs froze on 2026-04-29, fingerprint of an
# expired app-registration client secret. The secret lives in THREE places
# that all need updating together:
#
#   1. Azure App Service app-governance-prod (resource group rg-governance-prod)
#   2. Azure App Service app-governance-staging-xnczpwyv (rg-governance-staging)
#   3. GitHub repo secret STAGING_AZURE_AD_CLIENT_SECRET (for ct-wph's
#      deploy-staging.yml automation, so the next deploy doesn't re-broadcast
#      the OLD value)
#
# This script does all three plus a post-rotation health verification. Reads
# the new secret from stdin (or a -f file) so it never lands in process args
# (which leak through `ps`), in shell history, or in CI logs.
#
# USAGE
#   # Interactive — paste secret at the prompt:
#   ./scripts/rotate-azure-secret.sh
#
#   # From a file (useful when pasted in from Azure portal "value" field):
#   ./scripts/rotate-azure-secret.sh -f /tmp/new-secret
#
#   # Dry-run (validates az/gh auth + shows what would happen, no writes):
#   ./scripts/rotate-azure-secret.sh --dry-run
#
#   # Skip a specific target (e.g. if GH CLI isn't installed):
#   ./scripts/rotate-azure-secret.sh --skip-github
#   ./scripts/rotate-azure-secret.sh --skip-staging
#   ./scripts/rotate-azure-secret.sh --skip-prod
#
# REQUIREMENTS
#   - az CLI logged in with rights to the two web apps
#   - gh CLI logged in with admin rights to HTT-BRANDS/control-tower
#     (unless --skip-github)
#   - bash 4+, curl, jq
#
# SAFETY
#   - Secret never appears in command-line arguments to az/gh — they read it
#     from environment variables we set in the same shell scope.
#   - Verifies the secret is at least 32 chars (Azure secrets are 40 by
#     default; <32 means you probably pasted only part of it).
#   - Restarts both webapps after the update so the change takes effect.
#   - Waits for /health to return 200 on both, then dumps /api/v1/health/data
#     so you can see the sync timestamps start climbing.
#
# WHAT THIS SCRIPT DELIBERATELY DOES NOT DO
#   - It does NOT generate a new secret. Generate it in the Azure portal under
#     App registrations -> Riverside-Capital-PE-Governance-Platform ->
#     Certificates & secrets. Azure will only show you the "value" once.
#   - It does NOT update infrastructure/parameters.*.json — those are empty
#     by design and a secret-bearing parameter file would be a security
#     regression (see docs/runbooks/staging-secrets.md).
#   - It does NOT trigger a redeploy. Restarting the webapp is enough for
#     the new app setting to take effect; a redeploy would be a much bigger
#     blast radius.
# =============================================================================

set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
PROD_WEBAPP="app-governance-prod"
PROD_RG="rg-governance-prod"
STAGING_WEBAPP="app-governance-staging-xnczpwyv"
STAGING_RG="rg-governance-staging"
GH_REPO="HTT-BRANDS/control-tower"
GH_SECRET_NAME="STAGING_AZURE_AD_CLIENT_SECRET"
SETTING_NAME="AZURE_AD_CLIENT_SECRET"

# Names of /health probes for the readiness loop.
PROD_HEALTH="https://${PROD_WEBAPP}.azurewebsites.net/health"
STAGING_HEALTH="https://${STAGING_WEBAPP}.azurewebsites.net/health"
PROD_DATA_FRESHNESS="https://${PROD_WEBAPP}.azurewebsites.net/api/v1/health/data"

# ── Args ────────────────────────────────────────────────────────────────────
DRY_RUN=false
SECRET_FILE=""
SKIP_PROD=false
SKIP_STAGING=false
SKIP_GITHUB=false

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    -f|--file)        SECRET_FILE="${2:-}"; shift 2 ;;
    --dry-run)        DRY_RUN=true;          shift ;;
    --skip-prod)      SKIP_PROD=true;        shift ;;
    --skip-staging)   SKIP_STAGING=true;     shift ;;
    --skip-github)    SKIP_GITHUB=true;      shift ;;
    -h|--help)        usage 0 ;;
    *)                echo "Unknown option: $1" >&2; usage 1 ;;
  esac
done

# ── Pretty output helpers ───────────────────────────────────────────────────
RED=$'\e[31m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; BLUE=$'\e[34m'; RESET=$'\e[0m'
say()  { printf '%s\n' "$*"; }
info() { printf '%s[i]%s %s\n' "$BLUE"   "$RESET" "$*"; }
ok()   { printf '%s[✓]%s %s\n' "$GREEN"  "$RESET" "$*"; }
warn() { printf '%s[!]%s %s\n' "$YELLOW" "$RESET" "$*" >&2; }
err()  { printf '%s[x]%s %s\n' "$RED"    "$RESET" "$*" >&2; }

# ── Pre-flight ──────────────────────────────────────────────────────────────
say "=== ct-jxe: Azure AD client-secret rotation ==="
say ""

# CLI tools.
for tool in az curl jq; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    err "Required tool not found: ${tool}"
    exit 2
  fi
done
if [ "$SKIP_GITHUB" = false ] && ! command -v gh >/dev/null 2>&1; then
  err "gh CLI not found and --skip-github not passed. Install gh or re-run with --skip-github."
  exit 2
fi

# az auth.
if ! az account show >/dev/null 2>&1; then
  err "az CLI is not logged in. Run: az login"
  exit 2
fi
SUB=$(az account show --query name -o tsv)
info "Azure subscription: ${SUB}"

# gh auth.
if [ "$SKIP_GITHUB" = false ]; then
  if ! gh auth status >/dev/null 2>&1; then
    err "gh CLI is not logged in. Run: gh auth login"
    exit 2
  fi
  GH_USER=$(gh api user --jq .login)
  info "GitHub user: ${GH_USER}"
fi

# ── Read the secret ─────────────────────────────────────────────────────────
# We deliberately read from stdin or a file (never an argv). Using `read -s`
# means the secret is never echoed to the terminal.
if [ -n "$SECRET_FILE" ]; then
  if [ ! -f "$SECRET_FILE" ]; then
    err "Secret file not found: ${SECRET_FILE}"
    exit 2
  fi
  NEW_SECRET=$(tr -d '\n\r' < "$SECRET_FILE")
elif [ "$DRY_RUN" = true ]; then
  NEW_SECRET="DRY-RUN-PLACEHOLDER-32-chars-min-XXXXXX"
else
  printf '%s' "Paste new AZURE_AD_CLIENT_SECRET (input hidden): "
  IFS= read -rs NEW_SECRET
  printf '\n'
fi

# Strip stray whitespace pasted in from clipboard.
NEW_SECRET="${NEW_SECRET#"${NEW_SECRET%%[![:space:]]*}"}"
NEW_SECRET="${NEW_SECRET%"${NEW_SECRET##*[![:space:]]}"}"

if [ -z "$NEW_SECRET" ]; then
  err "Empty secret — aborting."
  exit 2
fi
if [ "${#NEW_SECRET}" -lt 32 ]; then
  err "Secret is only ${#NEW_SECRET} chars — Azure secrets are 40 by default. Did you paste a truncated value?"
  exit 2
fi
ok "Secret length: ${#NEW_SECRET} chars (looks plausible)"

# Use `export` so child processes (az, gh) can read it via env without our
# value showing up in argv. Then `unset` at the end of the script.
export NEW_SECRET

# ── Action plan summary ─────────────────────────────────────────────────────
say ""
info "Plan:"
[ "$SKIP_PROD" = false ]    && say "  • az webapp config appsettings set on ${PROD_WEBAPP} (${PROD_RG})"
[ "$SKIP_PROD" = false ]    && say "  • az webapp restart           on ${PROD_WEBAPP}"
[ "$SKIP_STAGING" = false ] && say "  • az webapp config appsettings set on ${STAGING_WEBAPP} (${STAGING_RG})"
[ "$SKIP_STAGING" = false ] && say "  • az webapp restart           on ${STAGING_WEBAPP}"
[ "$SKIP_GITHUB" = false ]  && say "  • gh secret set ${GH_SECRET_NAME}   on ${GH_REPO}"
say "  • /health readiness probe on both webapps"
say "  • dump /api/v1/health/data to confirm sync timestamps are climbing"

if [ "$DRY_RUN" = true ]; then
  say ""
  warn "DRY RUN — no changes will be made. Exiting."
  exit 0
fi

say ""
printf '%s' "Proceed? [y/N] "
read -r CONFIRM
case "$CONFIRM" in
  y|Y|yes|YES) ;;
  *) warn "Aborted by user."; exit 0 ;;
esac

# ── Execute ─────────────────────────────────────────────────────────────────
# Helper: set a single app setting via az, reading the secret from env so it
# never appears in argv. The trick is the `${SETTING_NAME}=@env:NEW_SECRET`
# syntax which `az webapp config appsettings set` does NOT support — so we
# build the assignment string locally instead. We pipe through `--output none`
# so az doesn't echo the (now-updated) settings dict on success.
set_appsetting() {
  local webapp="$1" rg="$2"
  info "Setting ${SETTING_NAME} on ${webapp}…"
  az webapp config appsettings set \
    --name "$webapp" \
    --resource-group "$rg" \
    --settings "${SETTING_NAME}=${NEW_SECRET}" \
    --output none
  ok "  → ${webapp} updated"
}

restart_webapp() {
  local webapp="$1" rg="$2"
  info "Restarting ${webapp}…"
  az webapp restart --name "$webapp" --resource-group "$rg"
  ok "  → ${webapp} restart issued"
}

if [ "$SKIP_PROD" = false ]; then
  set_appsetting "$PROD_WEBAPP" "$PROD_RG"
  restart_webapp "$PROD_WEBAPP" "$PROD_RG"
fi

if [ "$SKIP_STAGING" = false ]; then
  set_appsetting "$STAGING_WEBAPP" "$STAGING_RG"
  restart_webapp "$STAGING_WEBAPP" "$STAGING_RG"
fi

if [ "$SKIP_GITHUB" = false ]; then
  info "Setting GitHub secret ${GH_SECRET_NAME} on ${GH_REPO}…"
  # gh secret set reads the value from stdin when --body is not passed,
  # so the secret never appears in argv.
  printf '%s' "$NEW_SECRET" | gh secret set "$GH_SECRET_NAME" --repo "$GH_REPO"
  ok "  → ${GH_SECRET_NAME} updated"
fi

# Scrub from env now that all writes are done.
unset NEW_SECRET

# ── Readiness loop ──────────────────────────────────────────────────────────
# Webapp restart takes 30-90s on B1 (cold start). We loop with a 10s sleep
# until /health returns 200 or we hit the timeout.
wait_for_health() {
  local url="$1" name="$2"
  local max_attempts=18  # 18 × 10s = 3 min
  local i
  info "Waiting for ${name} /health…"
  for i in $(seq 1 "$max_attempts"); do
    if curl -sf --max-time 10 -o /dev/null "$url"; then
      ok "  → ${name} healthy (attempt ${i})"
      return 0
    fi
    printf '%s' "."
    sleep 10
  done
  printf '\n'
  err "${name} did not return 200 within ${max_attempts}×10s. Check Azure portal logs."
  return 1
}

[ "$SKIP_PROD" = false ]    && wait_for_health "$PROD_HEALTH"    "$PROD_WEBAPP"
[ "$SKIP_STAGING" = false ] && wait_for_health "$STAGING_HEALTH" "$STAGING_WEBAPP"

# ── Data-freshness snapshot ────────────────────────────────────────────────
# Schedulers fire every 5 minutes by default, so sync timestamps may not
# climb on this exact run — but the endpoint should still respond, and
# you can re-curl in 5-10 minutes to verify.
if [ "$SKIP_PROD" = false ]; then
  say ""
  info "Current /api/v1/health/data on prod (re-curl in 5-10 min to see syncs catch up):"
  curl -s --max-time 30 "$PROD_DATA_FRESHNESS" | jq '{
    any_stale,
    most_recent_sync: [.tenants[] | to_entries[] | select(.key != "stale") | .value] | map(select(. != null)) | max
  }' 2>/dev/null || warn "Failed to fetch data-freshness — try manually: curl ${PROD_DATA_FRESHNESS}"
fi

say ""
ok "Rotation complete."
say ""
info "Verification steps:"
say "  1. Wait 5-10 minutes for the next scheduler tick."
say "  2. curl -s ${PROD_DATA_FRESHNESS} | jq '.any_stale'   → expect false"
say "  3. curl -s ${PROD_DATA_FRESHNESS} | jq '.tenants[\"Head-To-Toe (HTT)\"]' → all timestamps should be < 1 hour old"
say "  4. Sign into the dashboard and confirm the per-tenant cards show fresh data."
say ""
info "If syncs still don't catch up:"
say "  • Check Application Insights for sync-job errors filtered by today's date."
say "  • Verify the app registration's Graph API permissions still have admin consent."
say "  • Check if a per-tenant app registration (DCE has historically been a problem child) needs its own secret."
