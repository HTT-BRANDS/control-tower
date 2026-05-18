#!/bin/bash
# =============================================================================
# Azure Governance Platform - Dev Deployment Verification Script
# =============================================================================
# Usage: ./scripts/verify-dev-deployment.sh
# Requires: curl, jq, azure-cli (optional, for Azure resource checks)
#
# Verifies dev deployment with App Service warmup tolerance:
# 1. Health/readiness endpoints with bounded retries
# 2. OpenAPI/docs/login accessibility
# 3. Protected routes do not 5xx while unauthenticated
# 4. Azure resource status when az is available and logged in
# =============================================================================

set -euo pipefail

BASE_URL="${BASE_URL:-https://app-governance-dev-001.azurewebsites.net}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-governance-dev}"
APP_SERVICE="${APP_SERVICE:-app-governance-dev-001}"
EXPECTED_ENVIRONMENT="${EXPECTED_ENVIRONMENT:-development}"
TIMEOUT="${TIMEOUT:-45}"
MAX_RETRIES="${MAX_RETRIES:-12}"
RETRY_SLEEP="${RETRY_SLEEP:-10}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0
WARNINGS=0
LAST_BODY_FILE="/tmp/control-tower-dev-verify-body.txt"
LAST_CODE="000"
LAST_CURL_EXIT=0

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $1"; ((TESTS_PASSED++)) || true; }
log_failure() { echo -e "${RED}[FAIL]${NC} $1"; ((TESTS_FAILED++)) || true; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; ((WARNINGS++)) || true; }

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_section() { echo -e "\n${BLUE}--- $1 ---${NC}"; }

check_command() {
    command -v "$1" &>/dev/null || { log_warning "$1 is not installed. Some checks will be skipped."; return 1; }
    return 0
}

contains_status() {
    local expected_csv="$1"
    local actual="$2"
    IFS=',' read -ra expected <<< "$expected_csv"
    for code in "${expected[@]}"; do
        if [ "$code" = "$actual" ]; then
            return 0
        fi
    done
    return 1
}

request_once() {
    local url="$1"
    local accept="${2:-application/json}"
    rm -f "$LAST_BODY_FILE"
    set +e
    LAST_CODE=$(curl --silent --show-error \
        --connect-timeout 10 \
        --max-time "$TIMEOUT" \
        --output "$LAST_BODY_FILE" \
        --write-out "%{http_code}" \
        -H "Accept: $accept" \
        -H "User-Agent: control-tower-dev-verify" \
        "$url" 2>/tmp/control-tower-dev-verify-curl.err)
    LAST_CURL_EXIT=$?
    set -e
}

test_endpoint() {
    local path="$1"
    local description="$2"
    local expected_statuses="${3:-200}"
    local require_json="${4:-false}"
    local accept="${5:-application/json}"

    print_section "Testing: $description"
    local url="$BASE_URL$path"
    log_info "URL: $url"

    local attempt=1
    while [ "$attempt" -le "$MAX_RETRIES" ]; do
        request_once "$url" "$accept"

        if [ "$LAST_CURL_EXIT" -eq 0 ] && contains_status "$expected_statuses" "$LAST_CODE"; then
            break
        fi

        local curl_err=""
        curl_err=$(cat /tmp/control-tower-dev-verify-curl.err 2>/dev/null || true)
        log_info "Attempt $attempt/$MAX_RETRIES not ready: curl_exit=$LAST_CURL_EXIT http=$LAST_CODE ${curl_err:+curl=$curl_err}"

        if [ "$attempt" -lt "$MAX_RETRIES" ]; then
            sleep "$RETRY_SLEEP"
        fi
        attempt=$((attempt + 1))
    done

    if [ "$LAST_CURL_EXIT" -ne 0 ] || ! contains_status "$expected_statuses" "$LAST_CODE"; then
        log_failure "$description (expected HTTP $expected_statuses, got $LAST_CODE, curl_exit=$LAST_CURL_EXIT)"
        if [ -s "$LAST_BODY_FILE" ]; then
            echo "Response preview:"
            head -20 "$LAST_BODY_FILE" || true
        fi
        return 1
    fi

    log_success "$description (HTTP $LAST_CODE)"

    if [ "$require_json" = true ]; then
        if ! check_command jq >/dev/null; then
            log_warning "Cannot validate JSON without jq"
            return 0
        fi
        if jq -e . "$LAST_BODY_FILE" >/dev/null 2>&1; then
            log_success "$description returned valid JSON"
        else
            log_failure "$description response is not valid JSON"
            head -20 "$LAST_BODY_FILE" || true
            return 1
        fi
    fi

    return 0
}

test_health_endpoint() {
    print_header "Health Endpoint Test"
    test_endpoint "/health" "Basic Health Check" "200" true

    if check_command jq >/dev/null && [ -s "$LAST_BODY_FILE" ]; then
        local status env version
        status=$(jq -r '.status // empty' "$LAST_BODY_FILE")
        env=$(jq -r '.environment // empty' "$LAST_BODY_FILE")
        version=$(jq -r '.version // empty' "$LAST_BODY_FILE")

        if [ "$status" = "healthy" ]; then
            log_success "Health status is healthy"
        else
            log_failure "Health status is not healthy: ${status:-missing}"
        fi

        if [ "$env" = "$EXPECTED_ENVIRONMENT" ]; then
            log_success "Health environment is $EXPECTED_ENVIRONMENT"
        else
            log_failure "Expected environment $EXPECTED_ENVIRONMENT, got ${env:-missing}"
        fi

        if [ -n "$version" ]; then
            log_success "Health version present: $version"
        else
            log_failure "Health version missing"
        fi
    fi
}

test_detailed_health() {
    print_header "Detailed Health Check"
    test_endpoint "/health/detailed" "Detailed Health Check" "200" true
}

test_api_status() {
    print_header "API Status Endpoint"
    log_warning "Skipping /api/v1/status as a deploy readiness gate; use /health and /health/detailed for readiness."
}

test_public_pages() {
    print_header "Public Page/API Smoke"
    test_endpoint "/openapi.json" "OpenAPI schema" "200" true
    test_endpoint "/docs" "Swagger docs" "200" false "text/html"
    test_endpoint "/login" "Login page" "200" false "text/html"
    test_endpoint "/" "Root redirects or renders" "200,307" false "text/html"
}

test_protected_routes_no_5xx() {
    print_header "Protected Route No-500 Smoke"
    local routes=(
        /dashboard
        /costs
        /compliance
        /resources
        /identity
        /sync-dashboard
        /riverside
        /dmarc
    )

    local route
    for route in "${routes[@]}"; do
        test_endpoint "$route" "Protected route $route does not 5xx" "200,302,303,307,401" false "text/html"
    done
}

test_static_files() {
    print_header "Static Files Test"
    local static_url="$BASE_URL/static/css/design-tokens.css"
    request_once "$static_url" "text/css"
    if [ "$LAST_CURL_EXIT" -eq 0 ] && [ "$LAST_CODE" = "200" ]; then
        log_success "Static CSS files accessible"
    elif [ "$LAST_CODE" = "404" ]; then
        log_warning "Static CSS not found at expected path (non-blocking for dev smoke)"
    else
        log_warning "Static file check returned HTTP $LAST_CODE curl_exit=$LAST_CURL_EXIT"
    fi
}

test_azure_resources() {
    print_header "Azure Resource Verification"

    if ! check_command az; then
        log_warning "Azure CLI not available. Skipping Azure resource checks."
        return
    fi

    if ! az account show &>/dev/null; then
        log_warning "Not logged into Azure. Skipping Azure resource checks."
        return
    fi

    print_section "Checking App Service Status"
    local app_status
    app_status=$(az webapp show --name "$APP_SERVICE" --resource-group "$RESOURCE_GROUP" --query "state" -o tsv 2>/dev/null || echo "unknown")
    if [ "$app_status" = "Running" ]; then
        log_success "App Service is Running"
    elif [ "$app_status" = "unknown" ]; then
        log_warning "Could not retrieve App Service status"
    else
        log_failure "App Service status: $app_status"
    fi

    print_section "Checking App Service Container"
    local linux_fx
    linux_fx=$(az webapp show --name "$APP_SERVICE" --resource-group "$RESOURCE_GROUP" --query "siteConfig.linuxFxVersion" -o tsv 2>/dev/null || echo "unknown")
    if [[ "$linux_fx" == DOCKER\|* ]]; then
        log_success "App Service container image configured: $linux_fx"
    else
        log_warning "Could not verify App Service container image: $linux_fx"
    fi

    print_section "Checking HTTPS Only"
    local https_only
    https_only=$(az webapp show --name "$APP_SERVICE" --resource-group "$RESOURCE_GROUP" --query "httpsOnly" -o tsv 2>/dev/null || echo "unknown")
    if [ "$https_only" = "true" ]; then
        log_success "HTTPS Only is enabled"
    elif [ "$https_only" = "unknown" ]; then
        log_warning "Could not retrieve HTTPS configuration"
    else
        log_warning "HTTPS Only is not enabled"
    fi
}

print_summary() {
    print_header "Verification Summary"
    echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Tests Failed: $TESTS_FAILED${NC}"
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
    echo ""
    echo "Environment Details:"
    echo "  Base URL: $BASE_URL"
    echo "  Resource Group: $RESOURCE_GROUP"
    echo "  App Service: $APP_SERVICE"

    if [ "$TESTS_FAILED" -eq 0 ]; then
        echo -e "\n${GREEN}✅ All critical dev verification checks passed.${NC}"
    else
        echo -e "\n${RED}❌ Dev verification failed. Review logs above.${NC}"
    fi
}

main() {
    print_header "Azure Governance Platform - Dev Deployment Verification"
    log_info "Target Environment: Dev"
    log_info "Base URL: $BASE_URL"
    log_info "Max retries: $MAX_RETRIES; retry sleep: ${RETRY_SLEEP}s; request timeout: ${TIMEOUT}s"
    log_info "Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

    test_health_endpoint
    test_detailed_health
    test_public_pages
    test_protected_routes_no_5xx
    test_static_files
    test_azure_resources
    print_summary

    if [ "$TESTS_FAILED" -gt 0 ]; then
        exit 1
    fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
