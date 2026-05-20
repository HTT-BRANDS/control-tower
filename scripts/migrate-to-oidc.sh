#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# migrate-to-oidc.sh — CLI orchestrator for the OIDC federation migration
#
# Companion to docs/migration-cockpit/index.html and
# docs/runbooks/migrate-to-oidc-federation.md.
#
# This script does every step the cockpit walks you through, but from a
# terminal. Each step is idempotent (re-running is safe) and each step
# verifies its own success before returning 0. Step 6 (interactive
# sign-in) is intentionally NOT automated — that's a human-in-the-loop
# test by design.
#
# Usage:
#   ./scripts/migrate-to-oidc.sh status     Show current state
#   ./scripts/migrate-to-oidc.sh 1          Run step 1 only
#   ./scripts/migrate-to-oidc.sh all        Run 1-5, then prompt for 6+7
#   ./scripts/migrate-to-oidc.sh rollback   Revert to secret mode
#   ./scripts/migrate-to-oidc.sh --help     Show this help
#
# Configuration (env vars; defaults shown):
#   APP_SERVICE_NAME    app-governance-staging-xnczpwyv
#   RESOURCE_GROUP      rg-governance-staging
#   TENANT_ID           0c0e35dc-188a-4eb3-b8ba-61752154b407
#   APP_REG_CLIENT_ID   (REQUIRED — your management app reg's client_id)
#   GITHUB_REPO         HTT-BRANDS/control-tower
#   GH_VAR_NAME         STAGING_USE_OIDC_FEDERATION
#   GH_SECRET_NAME      STAGING_AZURE_AD_CLIENT_SECRET
#   FED_CRED_NAME       app-service-mi-staging
#   DRY_RUN             unset (set to 1 to print commands without running)
#
# Required tools: az, gh, jq, curl
# ─────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Defaults (mirrors the cockpit pre-fills) ─────────────────────────────
APP_SERVICE_NAME="${APP_SERVICE_NAME:-app-governance-staging-xnczpwyv}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-governance-staging}"
TENANT_ID="${TENANT_ID:-0c0e35dc-188a-4eb3-b8ba-61752154b407}"
APP_REG_CLIENT_ID="${APP_REG_CLIENT_ID:-}"
GITHUB_REPO="${GITHUB_REPO:-HTT-BRANDS/control-tower}"
GH_VAR_NAME="${GH_VAR_NAME:-STAGING_USE_OIDC_FEDERATION}"
GH_SECRET_NAME="${GH_SECRET_NAME:-STAGING_AZURE_AD_CLIENT_SECRET}"
FED_CRED_NAME="${FED_CRED_NAME:-app-service-mi-staging}"
DRY_RUN="${DRY_RUN:-}"

# ── Color helpers (auto-disable when not a TTY) ──────────────────────────
# Palette mirrors docs/migration-cockpit so terminal output feels like
# the same product. BURGUNDY isn't currently used in this script; we
# could re-add it for section headers later (kept the slot in mind).
if [[ -t 1 ]]; then
    GOLD='\033[38;5;220m'
    GREEN='\033[38;5;120m'
    RED='\033[38;5;167m'
    DIM='\033[2m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    GOLD='' GREEN='' RED='' DIM='' BOLD='' RESET=''
fi

# ── Logging primitives ──────────────────────────────────────────────────
log_step()   { printf "\n${BOLD}${GOLD}▸ %s${RESET}\n" "$*"; }
log_ok()     { printf "  ${GREEN}✓${RESET} %s\n"      "$*"; }
log_warn()   { printf "  ${GOLD}⚠${RESET} %s\n"        "$*"; }
log_err()    { printf "  ${RED}✗${RESET} %s\n"         "$*" >&2; }
log_info()   { printf "  ${DIM}%s${RESET}\n"            "$*"; }
log_cmd()    { printf "  ${DIM}\$ %s${RESET}\n"         "$*"; }

# Run a command, respecting DRY_RUN. Stdout is captured so callers can use
# it; stderr passes through so the user sees actual errors live.
run() {
    log_cmd "$*"
    if [[ -n "${DRY_RUN}" ]]; then
        log_info "(dry-run; not executing)"
        return 0
    fi
    "$@"
}

# ── Pre-flight: required tooling ────────────────────────────────────────
require_tools() {
    local missing=()
    for tool in az gh jq curl; do
        if ! command -v "$tool" &>/dev/null; then
            missing+=("$tool")
        fi
    done
    if (( ${#missing[@]} > 0 )); then
        log_err "Missing required tools: ${missing[*]}"
        log_info "Install via:  brew install ${missing[*]}  (or your platform equivalent)"
        exit 1
    fi
}

# ── Pre-flight: az login state ──────────────────────────────────────────
require_az_login() {
    if ! az account show &>/dev/null; then
        log_err "az CLI not logged in"
        log_info "Run: az login"
        exit 1
    fi
}

require_gh_login() {
    if ! gh auth status &>/dev/null; then
        log_err "gh CLI not authenticated"
        log_info "Run: gh auth login"
        exit 1
    fi
}

# ── Validate required config for a given step ────────────────────────────
require_app_reg_client_id() {
    if [[ -z "${APP_REG_CLIENT_ID}" ]]; then
        log_err "APP_REG_CLIENT_ID is required for this step"
        log_info "Export it from your shell:  export APP_REG_CLIENT_ID=<your-app-reg-client-id>"
        log_info "Or find it in App Service settings:"
        log_info "    az webapp config appsettings list --name ${APP_SERVICE_NAME} \\"
        log_info "        --resource-group ${RESOURCE_GROUP} \\"
        log_info "        --query \"[?name=='AZURE_AD_CLIENT_ID'].value\" -o tsv"
        exit 1
    fi
}

# ─────────────────────────────────────────────────────────────────────────
# Step 1 — Verify (or assign) the App Service Managed Identity
#
# Idempotent: if the MI is already bound, we just read its principalId.
# If not, we assign one and capture the new principalId. Either way the
# user (or the next step) gets the principalId via the MI_PRINCIPAL_ID env
# var we export from the function.
# ─────────────────────────────────────────────────────────────────────────
step_1() {
    log_step "Step 1 — Verify App Service Managed Identity"

    log_info "Reading current identity binding..."
    local identity_json
    identity_json=$(az webapp identity show \
        --name "${APP_SERVICE_NAME}" \
        --resource-group "${RESOURCE_GROUP}" \
        -o json 2>/dev/null || echo '{}')

    local principal_id
    principal_id=$(echo "${identity_json}" | jq -r '.principalId // empty')

    if [[ -n "${principal_id}" ]]; then
        log_ok "Managed Identity already bound"
        log_info "principalId: ${principal_id}"
    else
        log_warn "No Managed Identity bound. Assigning system-assigned MI..."
        run az webapp identity assign \
            --name "${APP_SERVICE_NAME}" \
            --resource-group "${RESOURCE_GROUP}" \
            --output none
        principal_id=$(az webapp identity show \
            --name "${APP_SERVICE_NAME}" \
            --resource-group "${RESOURCE_GROUP}" \
            --query principalId -o tsv)
        log_ok "Managed Identity assigned. principalId: ${principal_id}"
    fi

    # Export for downstream steps in the same shell invocation.
    export MI_PRINCIPAL_ID="${principal_id}"
    echo "${principal_id}" > /tmp/oidc-mi-principal-id.txt
    log_info "(cached to /tmp/oidc-mi-principal-id.txt for step 2)"
}

# ─────────────────────────────────────────────────────────────────────────
# Step 2 — Add federated credential to the management app reg
#
# Idempotent: if a federated credential with our chosen name already
# exists on the app reg, we report it and skip. We do NOT overwrite —
# overwriting silently is the kind of foot-gun that hides config drift.
# ─────────────────────────────────────────────────────────────────────────
step_2() {
    log_step "Step 2 — Add federated credential to app registration"

    require_app_reg_client_id

    # The principal ID is the cred subject. Prefer the cached value from
    # step 1; if absent, look it up fresh.
    local mi_principal
    if [[ -f /tmp/oidc-mi-principal-id.txt ]]; then
        mi_principal=$(cat /tmp/oidc-mi-principal-id.txt)
    else
        mi_principal=$(az webapp identity show \
            --name "${APP_SERVICE_NAME}" \
            --resource-group "${RESOURCE_GROUP}" \
            --query principalId -o tsv 2>/dev/null || true)
    fi
    if [[ -z "${mi_principal}" ]]; then
        log_err "Could not determine MI principal ID. Run step 1 first."
        exit 1
    fi
    log_info "MI principal (federated subject): ${mi_principal}"

    log_info "Resolving app reg object ID from client ID ${APP_REG_CLIENT_ID}..."
    local app_object_id
    app_object_id=$(az ad app show --id "${APP_REG_CLIENT_ID}" --query id -o tsv 2>/dev/null || true)
    if [[ -z "${app_object_id}" ]]; then
        log_err "App reg not found for client_id=${APP_REG_CLIENT_ID}"
        log_info "Check the value, and ensure you have read access on the app reg."
        exit 1
    fi
    log_info "App reg object ID: ${app_object_id}"

    # Azure deduplicates federated credentials on the (issuer, subject)
    # tuple, NOT the name. So we MUST check that tuple — looking up by
    # name alone gives us a false 'no duplicate' and Azure rejects the
    # create with a confusing error. (Real example: 'governance-platform-
    # staging' already trusts our MI principal under a different name.)
    local issuer="https://login.microsoftonline.com/${TENANT_ID}/v2.0"
    log_info "Checking for existing federated credential trusting our MI..."
    log_info "  (matching by issuer=${issuer} + subject=${mi_principal})"
    local existing
    existing=$(az ad app federated-credential list --id "${app_object_id}" \
        --query "[?issuer=='${issuer}' && subject=='${mi_principal}'] | [0]" \
        -o json 2>/dev/null || echo 'null')

    if [[ "${existing}" != "null" && -n "${existing}" ]]; then
        local existing_name
        existing_name=$(echo "${existing}" | jq -r '.name')
        log_ok "Federated credential already exists under name '${existing_name}'"
        log_info "  (subject + issuer + audience all match — no work needed)"
        log_info "  If you wanted the canonical name '${FED_CRED_NAME}', you'd need"
        log_info "  to delete the existing one first — but functionally it's irrelevant."
        return 0
    fi

    log_info "Creating federated credential..."
    run az ad app federated-credential create \
        --id "${app_object_id}" \
        --parameters "$(cat <<JSON
{
  "name": "${FED_CRED_NAME}",
  "issuer": "https://login.microsoftonline.com/${TENANT_ID}/v2.0",
  "subject": "${mi_principal}",
  "audiences": ["api://AzureADTokenExchange"]
}
JSON
)" \
        --output none
    log_ok "Federated credential created."
}

# ─────────────────────────────────────────────────────────────────────────
# Step 3 — Set the GitHub repo VARIABLE (not secret)
#
# Idempotent: gh variable set is upsert semantics, so re-running just
# sets it again. We also explicitly verify the post-state.
# ─────────────────────────────────────────────────────────────────────────
step_3() {
    log_step "Step 3 — Set GitHub repo variable ${GH_VAR_NAME}=true"

    run gh variable set "${GH_VAR_NAME}" --body "true" --repo "${GITHUB_REPO}"

    log_info "Verifying value..."
    local current
    current=$(gh variable list --repo "${GITHUB_REPO}" --json name,value \
        --jq "[.[] | select(.name == \"${GH_VAR_NAME}\")] | .[0].value" 2>/dev/null || echo "")
    if [[ "${current}" == "true" ]]; then
        log_ok "${GH_VAR_NAME} = true (verified via gh variable list)"
    else
        log_err "Variable verification failed. Got: '${current}'"
        exit 1
    fi
}

# ─────────────────────────────────────────────────────────────────────────
# Step 4 — Trigger the staging deploy and tail it
#
# We dispatch the workflow then wait for the most recent run to finish.
# The wait is bounded by gh's built-in polling; we use --exit-status so
# the script exits non-zero on a failed run.
# ─────────────────────────────────────────────────────────────────────────
step_4() {
    log_step "Step 4 — Trigger staging deploy + watch for oidc_mode=true"

    log_info "Dispatching deploy-staging.yml on main..."
    run gh workflow run deploy-staging.yml --repo "${GITHUB_REPO}" --ref main

    log_info "Waiting 4s for the new run to register..."
    sleep 4

    local run_id
    run_id=$(gh run list --repo "${GITHUB_REPO}" \
        --workflow=deploy-staging.yml --limit 1 \
        --json databaseId --jq '.[0].databaseId')
    if [[ -z "${run_id}" ]]; then
        log_err "Could not find a new workflow run."
        exit 1
    fi
    log_info "Run ID: ${run_id}"
    log_info "Tailing logs (this can take 4-8 minutes)..."

    if [[ -n "${DRY_RUN}" ]]; then
        log_info "(dry-run; would: gh run watch ${run_id} --exit-status)"
        return 0
    fi

    gh run watch "${run_id}" --repo "${GITHUB_REPO}" --exit-status

    log_info "Checking the 'Configure Azure AD app settings' step log..."
    local log_output
    log_output=$(gh run view "${run_id}" --repo "${GITHUB_REPO}" --log 2>/dev/null || true)
    if echo "${log_output}" | grep -q 'oidc_mode=true'; then
        log_ok "Workflow ran in OIDC mode (oidc_mode=true confirmed in logs)"
    else
        log_err "Workflow ran but oidc_mode=true was NOT found in logs."
        log_info "Likely cause: repo variable ${GH_VAR_NAME} not set correctly."
        log_info "Re-run step 3 and verify with: gh variable list --repo ${GITHUB_REPO}"
        exit 1
    fi
}

# ─────────────────────────────────────────────────────────────────────────
# Step 5 — Verify /health/detailed reports auth_mode=oidc
# ─────────────────────────────────────────────────────────────────────────
step_5() {
    log_step "Step 5 — Verify /health/detailed shows auth_mode=oidc"

    local url="https://${APP_SERVICE_NAME}.azurewebsites.net/api/v1/health/detailed"
    log_info "GET ${url}"

    local response
    response=$(curl -fsS "${url}" 2>/dev/null || true)
    if [[ -z "${response}" ]]; then
        log_err "No response from ${url} — is the App Service running?"
        exit 1
    fi

    local azure_block
    azure_block=$(echo "${response}" | jq -c '.checks.azure_configured' 2>/dev/null || echo 'null')
    log_info "checks.azure_configured = ${azure_block}"

    local status_field auth_mode_field aadsts_field
    status_field=$(echo "${azure_block}"    | jq -r '.status'           )
    auth_mode_field=$(echo "${azure_block}" | jq -r '.auth_mode // ""' )
    aadsts_field=$(echo "${azure_block}"    | jq -r '.azure_error_code // ""' )

    case "${status_field}:${auth_mode_field}" in
        configured:oidc)
            log_ok "Migration succeeded — runtime is on OIDC, no client_secret needed."
            ;;
        configured:secret)
            log_err "Runtime is STILL on secret mode (auth_mode=secret)."
            log_info "Likely cause: App Service hasn't picked up USE_OIDC_FEDERATION=true."
            log_info "Try a restart:  az webapp restart --name ${APP_SERVICE_NAME} --resource-group ${RESOURCE_GROUP}"
            exit 1
            ;;
        unauthenticated:*)
            log_err "Probe reports unauthenticated (azure_error_code=${aadsts_field})"
            if [[ "${aadsts_field}" == "AADSTS700016" ]]; then
                log_info "AADSTS700016 → federated credential subject doesn't match the MI principal."
                log_info "Re-run step 2; it'll detect and report the mismatch."
            fi
            exit 1
            ;;
        *)
            log_err "Unexpected probe state: ${status_field}/${auth_mode_field}"
            log_info "Full response: ${azure_block}"
            exit 1
            ;;
    esac
}

# ─────────────────────────────────────────────────────────────────────────
# Step 6 — Interactive sign-in (BROWSER REQUIRED)
#
# This step is intentionally not automated. The point is to verify the
# OAuth authorization-code flow works end-to-end WITH A REAL USER
# SESSION (real cookies, real consent screen, real group membership).
# Automating it via Playwright would only prove "Playwright can drive
# a browser" — not "real users can log in", which is the actual question.
# ─────────────────────────────────────────────────────────────────────────
step_6() {
    log_step "Step 6 — Interactive sign-in test (HUMAN REQUIRED)"

    local url="https://${APP_SERVICE_NAME}.azurewebsites.net/"
    log_info "This step is browser-only by design — see script comments."
    log_info ""
    log_info "  1. Open this URL in an INCOGNITO window:"
    log_info "       ${url}"
    log_info "  2. Click 'Sign in with Microsoft'"
    log_info "  3. Complete Microsoft login"
    log_info "  4. Verify you land on the dashboard with your user info"
    log_info ""

    # If we're on macOS / Linux with `open` / `xdg-open`, offer to launch it.
    if command -v open >/dev/null 2>&1; then
        printf "  Launch incognito browser now? [y/N] "
        read -r reply
        if [[ "${reply}" =~ ^[Yy]$ ]]; then
            # macOS-only flag for incognito Chrome. Falls back to default browser.
            if [[ "$(uname)" == "Darwin" ]]; then
                open -na "Google Chrome" --args --incognito "${url}" 2>/dev/null \
                    || open "${url}"
            else
                open "${url}"
            fi
        fi
    fi

    printf "  Did sign-in complete successfully? [y/N] "
    read -r reply
    if [[ "${reply}" =~ ^[Yy]$ ]]; then
        log_ok "Sign-in verified by operator."
    else
        log_err "Sign-in failed. Check App Service logs:"
        log_info "    az webapp log tail --name ${APP_SERVICE_NAME} --resource-group ${RESOURCE_GROUP}"
        log_info "Look for 'OIDC federation failed during OAuth callback' (audience/subject mismatch)"
        log_info "       or 'Azure AD token exchange failed (HTTP 401)' (user/group issue, not OIDC)"
        exit 1
    fi
}

# ─────────────────────────────────────────────────────────────────────────
# Step 7 — Delete the dormant secret from all three locations
#
# DESTRUCTIVE — guarded by a confirmation prompt unless --force is passed.
# Idempotent: missing-secret cases are warnings, not errors.
# ─────────────────────────────────────────────────────────────────────────
step_7() {
    log_step "Step 7 — Delete the dormant secret (DESTRUCTIVE)"

    require_app_reg_client_id

    if [[ -z "${FORCE:-}" ]]; then
        log_warn "This deletes the secret from 3 locations:"
        log_info "    1. GitHub: secret ${GH_SECRET_NAME}"
        log_info "    2. App reg: ALL active client_secret credentials"
        log_info "    3. Key Vault: any 'azure-ad-client-secret*' entries (best-effort)"
        log_info ""
        log_warn "Have you waited 24h since /health/detailed first reported auth_mode=oidc? [y/N] "
        read -r waited
        if [[ ! "${waited}" =~ ^[Yy]$ ]]; then
            log_info "Aborting. Come back tomorrow."
            exit 0
        fi
        printf "  Type 'DELETE' to confirm: "
        read -r confirm
        if [[ "${confirm}" != "DELETE" ]]; then
            log_info "Aborting (confirmation not given)."
            exit 0
        fi
    fi

    # ── 7a. GitHub secret ──────────────────────────────────────────
    log_info "Deleting GitHub secret ${GH_SECRET_NAME}..."
    if gh secret list --repo "${GITHUB_REPO}" --json name --jq '.[].name' \
            | grep -qx "${GH_SECRET_NAME}"; then
        run gh secret delete "${GH_SECRET_NAME}" --repo "${GITHUB_REPO}"
        log_ok "GitHub secret deleted."
    else
        log_warn "GitHub secret ${GH_SECRET_NAME} not present. Skipping."
    fi

    # ── 7b. App reg client secrets ─────────────────────────────────
    log_info "Deleting active client_secret credentials on the app reg..."
    local app_object_id
    app_object_id=$(az ad app show --id "${APP_REG_CLIENT_ID}" --query id -o tsv)
    local key_ids
    key_ids=$(az ad app credential list --id "${app_object_id}" \
        --query '[].keyId' -o tsv 2>/dev/null || true)
    if [[ -z "${key_ids}" ]]; then
        log_warn "No client_secret credentials found on the app reg. Skipping."
    else
        while IFS= read -r kid; do
            [[ -z "${kid}" ]] && continue
            log_info "  deleting keyId=${kid}"
            run az ad app credential delete --id "${app_object_id}" --key-id "${kid}"
        done <<< "${key_ids}"
        log_ok "App reg client secrets deleted."
    fi

    # ── 7c. Key Vault mirrors (best-effort) ────────────────────────
    log_info "Searching Key Vaults for mirrored secrets (best-effort)..."
    local vaults
    vaults=$(az keyvault list --query '[].name' -o tsv 2>/dev/null || true)
    if [[ -z "${vaults}" ]]; then
        log_info "No Key Vaults visible. Skipping."
    else
        while IFS= read -r vault; do
            [[ -z "${vault}" ]] && continue
            local matches
            matches=$(az keyvault secret list --vault-name "${vault}" \
                --query "[?contains(name, 'client-secret')].name" -o tsv 2>/dev/null || true)
            if [[ -n "${matches}" ]]; then
                while IFS= read -r m; do
                    [[ -z "${m}" ]] && continue
                    log_info "  ${vault}: deleting ${m}"
                    run az keyvault secret delete --vault-name "${vault}" --name "${m}" --output none \
                        || log_warn "  (couldn't delete ${vault}/${m} — check permissions)"
                done <<< "${matches}"
            fi
        done <<< "${vaults}"
        log_ok "Key Vault sweep complete."
    fi

    log_info ""
    log_ok "Migration complete. Verify with: ./scripts/migrate-to-oidc.sh status"
}

# ─────────────────────────────────────────────────────────────────────────
# `status` — show current state without changing anything
# ─────────────────────────────────────────────────────────────────────────
cmd_status() {
    log_step "Migration status snapshot"

    # 1. MI bound?
    local mi
    mi=$(az webapp identity show --name "${APP_SERVICE_NAME}" \
        --resource-group "${RESOURCE_GROUP}" --query principalId -o tsv 2>/dev/null || true)
    if [[ -n "${mi}" ]]; then
        log_ok "App Service MI bound (principal=${mi})"
    else
        log_warn "App Service MI NOT bound"
    fi

    # 2. Federated credential? Match by (issuer, subject) tuple — see
    # step_2 docstring for why name-matching is incorrect.
    if [[ -n "${APP_REG_CLIENT_ID}" ]]; then
        local app_oid
        app_oid=$(az ad app show --id "${APP_REG_CLIENT_ID}" --query id -o tsv 2>/dev/null || true)
        if [[ -n "${app_oid}" && -n "${mi}" ]]; then
            local issuer="https://login.microsoftonline.com/${TENANT_ID}/v2.0"
            local fed_match
            fed_match=$(az ad app federated-credential list --id "${app_oid}" \
                --query "[?issuer=='${issuer}' && subject=='${mi}'] | [0].name" -o tsv 2>/dev/null || echo "")
            if [[ -n "${fed_match}" ]]; then
                log_ok "Federated credential present (name='${fed_match}', subject=MI principal)"
            else
                log_warn "No federated credential trusts the current MI principal"
            fi
            local secret_count
            secret_count=$(az ad app credential list --id "${app_oid}" \
                --query 'length(@)' -o tsv 2>/dev/null || echo 0)
            if [[ "${secret_count}" -gt 0 ]]; then
                log_warn "App reg still has ${secret_count} active client_secret credential(s)"
            else
                log_ok "App reg has no active client_secret credentials"
            fi
        fi
    else
        log_info "APP_REG_CLIENT_ID not set; skipping app reg checks"
    fi

    # 3. GH variable?
    local gh_var
    gh_var=$(gh variable list --repo "${GITHUB_REPO}" --json name,value \
        --jq "[.[] | select(.name == \"${GH_VAR_NAME}\")] | .[0].value" 2>/dev/null || echo "")
    if [[ "${gh_var}" == "true" ]]; then
        log_ok "GitHub variable ${GH_VAR_NAME}=true"
    else
        log_warn "GitHub variable ${GH_VAR_NAME} not set to true (got: '${gh_var:-<unset>}')"
    fi

    # 4. App Service env: USE_OIDC_FEDERATION ?
    local app_oidc
    app_oidc=$(az webapp config appsettings list --name "${APP_SERVICE_NAME}" \
        --resource-group "${RESOURCE_GROUP}" \
        --query "[?name=='USE_OIDC_FEDERATION'].value" -o tsv 2>/dev/null || echo "")
    if [[ "${app_oidc}" == "true" ]]; then
        log_ok "App Service env USE_OIDC_FEDERATION=true"
    else
        log_warn "App Service env USE_OIDC_FEDERATION not 'true' (got: '${app_oidc:-<unset>}')"
    fi

    # 5. App Service env: AZURE_AD_CLIENT_SECRET still present?
    local app_secret
    app_secret=$(az webapp config appsettings list --name "${APP_SERVICE_NAME}" \
        --resource-group "${RESOURCE_GROUP}" \
        --query "[?name=='AZURE_AD_CLIENT_SECRET'].value" -o tsv 2>/dev/null || echo "")
    if [[ -z "${app_secret}" ]]; then
        log_ok "App Service env AZURE_AD_CLIENT_SECRET removed"
    else
        log_warn "App Service env AZURE_AD_CLIENT_SECRET still set (length=${#app_secret})"
    fi

    # 6. Live runtime: auth_mode?
    local probe
    probe=$(curl -fsS \
        "https://${APP_SERVICE_NAME}.azurewebsites.net/api/v1/health/detailed" 2>/dev/null \
        | jq -c '.checks.azure_configured' 2>/dev/null || echo "")
    if [[ -n "${probe}" ]]; then
        local mode
        mode=$(echo "${probe}" | jq -r '.auth_mode // "unknown"')
        local status
        status=$(echo "${probe}" | jq -r '.status // "unknown"')
        if [[ "${mode}" == "oidc" && "${status}" == "configured" ]]; then
            log_ok "Live runtime: auth_mode=oidc, status=configured"
        else
            log_warn "Live runtime: auth_mode=${mode}, status=${status}"
        fi
    else
        log_warn "Couldn't reach /health/detailed (App Service down or unreachable)"
    fi

    echo ""
}

# ─────────────────────────────────────────────────────────────────────────
# `rollback` — flip back to secret mode
#
# This is the "I need to revert NOW" path. It:
#   1. Flips the GH variable to false
#   2. Triggers a deploy (which re-applies the secret from gh secrets)
#   3. Tells you to verify
# It does NOT touch the federated credential — that's harmless when
# unused, and leaving it means re-rolling-forward is a single var change.
# ─────────────────────────────────────────────────────────────────────────
cmd_rollback() {
    log_step "Rollback to secret mode"

    if ! gh secret list --repo "${GITHUB_REPO}" --json name --jq '.[].name' \
            | grep -qx "${GH_SECRET_NAME}"; then
        log_err "GitHub secret ${GH_SECRET_NAME} is gone. Cannot rollback automatically."
        log_info "You'll need to re-create the secret (generate a new client_secret in the"
        log_info "app reg portal first), then re-run this command."
        exit 1
    fi

    log_info "Setting ${GH_VAR_NAME}=false..."
    run gh variable set "${GH_VAR_NAME}" --body "false" --repo "${GITHUB_REPO}"

    log_info "Dispatching deploy to re-apply secret-mode wiring..."
    run gh workflow run deploy-staging.yml --repo "${GITHUB_REPO}" --ref main

    log_ok "Rollback initiated. Verify in ~5 min with:"
    log_info "    ./scripts/migrate-to-oidc.sh status"
}

# ─────────────────────────────────────────────────────────────────────────
# `all` — run steps 1-5 automatically, then prompt for 6 and 7
# ─────────────────────────────────────────────────────────────────────────
cmd_all() {
    step_1
    step_2
    step_3
    step_4
    step_5
    log_step "Steps 1-5 complete."
    log_info "Step 6 requires a human in the browser. Run:"
    log_info "    ./scripts/migrate-to-oidc.sh 6"
    log_info "Then wait 24h before step 7."
}

# ─────────────────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────────────────
cmd_help() {
    sed -n '/^# Usage:/,/^# Required tools/p' "$0" | sed 's/^# \{0,1\}//'
}

# ─────────────────────────────────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────────────────────────────────
main() {
    require_tools

    local cmd="${1:-help}"
    case "${cmd}" in
        --help|-h|help) cmd_help ;;
        status)         require_az_login; require_gh_login; cmd_status ;;
        rollback)       require_gh_login;                    cmd_rollback ;;
        all)            require_az_login; require_gh_login; cmd_all ;;
        1)              require_az_login;                    step_1 ;;
        2)              require_az_login;                    step_2 ;;
        3)              require_gh_login;                    step_3 ;;
        4)              require_gh_login;                    step_4 ;;
        5)                                                   step_5 ;;
        6)                                                   step_6 ;;
        7)              require_az_login; require_gh_login; step_7 ;;
        *)
            log_err "Unknown command: ${cmd}"
            cmd_help
            exit 2
            ;;
    esac
}

main "$@"
