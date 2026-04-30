#!/usr/bin/env bash
# scripts/verify-federated-creds.sh
#
# Read-only verification of OIDC federated credential configuration across all 5 tenants.
# Shows issuer, subject, audience for each app registration's federated credentials.
#
# USAGE:
#   ./scripts/verify-federated-creds.sh \
#     --managing-tenant-id <managing_tenant_id> \
#     --mi-object-id <managed_identity_object_id> \
#     [--tenant HTT|BCC|FN|TLL|DCE] \
#     [--name <federated-credential-name>]
#
# NOTE: Requires bash 3.2+ (macOS default). No associative arrays used.

set -euo pipefail

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "  ${GREEN}✓ PASS${RESET}  $*"; }
warn() { echo -e "  ${YELLOW}⚠ WARN${RESET}  $*"; }
err()  { echo -e "  ${RED}✗ FAIL${RESET}  $*" >&2; }
hdr()  { echo -e "\n${BOLD}${CYAN}$*${RESET}"; }

to_upper() { echo "$1" | tr '[:lower:]' '[:upper:]'; }

# ---------------------------------------------------------------------------
# Tenant lookup — loaded from config/tenants.yaml (no hardcoded IDs)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=scripts/_tenant_lookup.sh
source "$SCRIPT_DIR/_tenant_lookup.sh"

set_status() { eval "VSTATUS_${1}=\"${2}\""; }
get_status()  { eval "echo \"\${VSTATUS_${1}:-UNKNOWN}\""; }

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
MANAGING_TENANT_ID=""
MI_OBJECT_ID=""
FILTER_TENANT=""
CRED_NAME="control-tower-app-service"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --managing-tenant-id)
            MANAGING_TENANT_ID="$2"; shift 2 ;;
        --mi-object-id)
            MI_OBJECT_ID="$2"; shift 2 ;;
        --tenant)
            FILTER_TENANT=$(to_upper "$2"); shift 2 ;;
        --name)
            CRED_NAME="$2"; shift 2 ;;
        -h|--help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *)
            err "Unknown argument: $1"
            exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
if [ -z "$MANAGING_TENANT_ID" ]; then
    err "--managing-tenant-id is required"
    exit 1
fi

if [ -z "$MI_OBJECT_ID" ]; then
    err "--mi-object-id is required"
    exit 1
fi

if [ -n "$FILTER_TENANT" ] && ! is_valid_code "$FILTER_TENANT"; then
    err "Unknown tenant code: $FILTER_TENANT. Valid: HTT BCC FN TLL DCE"
    exit 1
fi

# ---------------------------------------------------------------------------
# Build work list
# ---------------------------------------------------------------------------
if [ -n "$FILTER_TENANT" ]; then
    WORK_LIST="$FILTER_TENANT"
else
    WORK_LIST="$TENANT_ORDER"
fi

EXPECTED_ISSUER="https://login.microsoftonline.com/${MANAGING_TENANT_ID}/v2.0"
EXPECTED_AUDIENCE="api://AzureADTokenExchange"
PASS_COUNT=0
FAIL_COUNT=0

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
hdr "=== OIDC Federated Credential Verification (Read-Only) ==="
echo "  Managing Tenant  : ${MANAGING_TENANT_ID}"
echo "  Expected Issuer  : ${EXPECTED_ISSUER}"
echo "  Expected Subject : ${MI_OBJECT_ID}"
echo "  Expected Audience: ${EXPECTED_AUDIENCE}"
echo "  Credential Name  : ${CRED_NAME}"

for CODE in $WORK_LIST; do
    TENANT_ID=$(get_tenant_id "$CODE")
    APP_ID=$(get_app_id "$CODE")

    hdr "── Tenant: ${CODE} (${TENANT_ID})"
    echo "   App ID: ${APP_ID}"

    # Log in read-only
    if ! az login --tenant "$TENANT_ID" --allow-no-subscriptions --output none 2>/dev/null; then
        err "Cannot log in to tenant ${CODE}"
        set_status "$CODE" "LOGIN_FAIL"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        continue
    fi

    # List all federated credentials for this app
    ALL_CREDS=$(az ad app federated-credential list --id "$APP_ID" --output json 2>/dev/null || echo "[]")
    CRED_COUNT=$(echo "$ALL_CREDS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

    echo "   Total federated credentials: ${CRED_COUNT}"

    # Show all credentials for visibility
    if [ "$CRED_COUNT" -gt 0 ]; then
        echo "$ALL_CREDS" | python3 -c "
import sys, json
creds = json.load(sys.stdin)
for c in creds:
    print('     [' + c.get('name','?') + ']')
    print('       issuer   : ' + c.get('issuer','?'))
    print('       subject  : ' + c.get('subject','?'))
    print('       audiences: ' + str(c.get('audiences','?')))
" 2>/dev/null || true
    fi

    # Find the target credential
    TARGET_CRED=$(echo "$ALL_CREDS" | python3 -c "
import sys, json
creds = json.load(sys.stdin)
found = [c for c in creds if c.get('name') == '$CRED_NAME']
print(json.dumps(found[0]) if found else 'null')
" 2>/dev/null || echo "null")

    if [ "$TARGET_CRED" = "null" ]; then
        err "Credential '${CRED_NAME}' NOT FOUND in tenant ${CODE}"
        set_status "$CODE" "MISSING"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        continue
    fi

    # Validate each field
    ACTUAL_ISSUER=$(echo "$TARGET_CRED" | python3 -c "import sys,json; print(json.load(sys.stdin).get('issuer',''))" 2>/dev/null || echo "")
    ACTUAL_SUBJECT=$(echo "$TARGET_CRED" | python3 -c "import sys,json; print(json.load(sys.stdin).get('subject',''))" 2>/dev/null || echo "")
    ACTUAL_AUDIENCES=$(echo "$TARGET_CRED" | python3 -c "import sys,json; print(','.join(json.load(sys.stdin).get('audiences',[])))" 2>/dev/null || echo "")

    TENANT_PASS=true

    if [ "$ACTUAL_ISSUER" = "$EXPECTED_ISSUER" ]; then
        ok "Issuer matches"
    else
        err "Issuer MISMATCH"
        echo "       Expected: ${EXPECTED_ISSUER}"
        echo "       Actual  : ${ACTUAL_ISSUER}"
        TENANT_PASS=false
    fi

    if [ "$ACTUAL_SUBJECT" = "$MI_OBJECT_ID" ]; then
        ok "Subject (MI Object ID) matches"
    else
        err "Subject MISMATCH"
        echo "       Expected: ${MI_OBJECT_ID}"
        echo "       Actual  : ${ACTUAL_SUBJECT}"
        TENANT_PASS=false
    fi

    if echo "$ACTUAL_AUDIENCES" | grep -q "$EXPECTED_AUDIENCE"; then
        ok "Audience '${EXPECTED_AUDIENCE}' present"
    else
        err "Audience MISMATCH"
        echo "       Expected: ${EXPECTED_AUDIENCE}"
        echo "       Actual  : ${ACTUAL_AUDIENCES}"
        TENANT_PASS=false
    fi

    if [ "$TENANT_PASS" = true ]; then
        set_status "$CODE" "PASS"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        set_status "$CODE" "FAIL"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
hdr "=== Verification Summary ==="
printf "%-6s  %-40s  %s\n" "CODE" "TENANT_ID" "STATUS"
printf "%-6s  %-40s  %s\n" "------" "----------------------------------------" "-------"

for CODE in $WORK_LIST; do
    STATE=$(get_status "$CODE")
    TENANT_ID=$(get_tenant_id "$CODE")
    case "$STATE" in
        PASS)
            INDICATOR="${GREEN}✓ PASS${RESET}" ;;
        MISSING|FAIL|LOGIN_FAIL)
            INDICATOR="${RED}✗ ${STATE}${RESET}" ;;
        *)
            INDICATOR="${YELLOW}? ${STATE}${RESET}" ;;
    esac
    printf "%-6s  %-40s  " "$CODE" "$TENANT_ID"
    echo -e "${INDICATOR}"
done

echo ""
echo -e "  ${GREEN}Passed: ${PASS_COUNT}${RESET}  |  ${RED}Failed: ${FAIL_COUNT}${RESET}"

if [ $FAIL_COUNT -gt 0 ]; then
    echo ""
    err "Verification FAILED — run setup-federated-creds.sh to fix missing credentials"
    exit 1
else
    echo ""
    ok "All federated credentials are correctly configured!"
    exit 0
fi
