#!/bin/bash
# =============================================================================
# Azure Governance Platform - Comprehensive Deployment Verification Script
# =============================================================================
# Usage: ./scripts/verify-deployment.sh [--url BASE_URL] [--env ENVIRONMENT]
#
# This script performs comprehensive deployment verification:
# 1. Health endpoint checks (basic and detailed)
# 2. API endpoint accessibility tests
# 3. Authentication flow verification
# 4. Database connectivity checks
# 5. Cache functionality tests
# 6. Azure connectivity verification
# 7. All tenant sync status validation
# 8. Static assets accessibility
#
# Exit Codes:
#   0 - All checks passed (deployment healthy)
#   1 - Critical checks failed (deployment unhealthy)
#   2 - Configuration or runtime error
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

# Default configuration (override with environment variables)
BASE_URL="${BASE_URL:-https://app-governance-prod.azurewebsites.net}"
ENVIRONMENT="${ENVIRONMENT:-production}"
TIMEOUT="${TIMEOUT:-30}"
MAX_RETRIES="${MAX_RETRIES:-3}"
RETRY_DELAY="${RETRY_DELAY:-5}"

# Azure resource names (for Azure CLI checks)
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-governance-prod}"
APP_SERVICE="${APP_SERVICE:-app-governance-prod}"
KEY_VAULT="${KEY_VAULT:-kv-governance-prod}"

# Expected tenant count
EXPECTED_TENANT_COUNT="${EXPECTED_TENANT_COUNT:-5}"

# =============================================================================
# COLOR OUTPUT
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# =============================================================================
# STATE TRACKING
# =============================================================================

TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0
WARNINGS=0

# JSON report data
REPORT_JSON='{"timestamp":"","url":"","environment":"","tests":[],"summary":{}}'

# =============================================================================
# LOGGING FUNCTIONS
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++)) || true
}

log_failure() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++)) || true
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++)) || true
}

log_skip() {
    echo -e "${CYAN}[SKIP]${NC} $1"
    ((TESTS_SKIPPED++)) || true
}

log_section() {
    echo -e "\n${MAGENTA}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${MAGENTA}  $1${NC}"
    echo -e "${MAGENTA}══════════════════════════════════════════════════════════════${NC}"
}

print_header() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║        Azure Governance Platform - Deployment Verification      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Target URL:      ${CYAN}${BASE_URL}${NC}"
    echo -e "  Environment:     ${CYAN}${ENVIRONMENT}${NC}"
    echo -e "  Timestamp:       ${CYAN}$(date -u +"%Y-%m-%d %H:%M:%S UTC")${NC}"
    echo ""
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

check_command() {
    if ! command -v "$1" &> /dev/null; then
        return 1
    fi
    return 0
}

make_request() {
    local url=$1
    local method=${2:-GET}
    local headers=${3:-}
    local data=${4:-}
    
    local curl_args=(
        -s -w "\n%{http_code}"
        --max-time "$TIMEOUT"
        -X "$method"
    )
    
    if [[ -n "$headers" ]]; then
        IFS='|' read -ra HEADER_ARRAY <<< "$headers"
        for header in "${HEADER_ARRAY[@]}"; do
            curl_args+=(-H "$header")
        done
    fi
    
    if [[ -n "$data" ]]; then
        curl_args+=(-d "$data")
    fi
    
    curl_args+=("$url")
    
    local response
    response=$(curl "${curl_args[@]}" 2>/dev/null || echo -e "\n000")
    echo "$response"
}

parse_json() {
    local json=$1
    local query=$2
    echo "$json" | jq -r "$query" 2>/dev/null || echo "null"
}

retry_request() {
    local url=$1
    local expected_status=${2:-200}
    local description=$3
    local max_attempts=${4:-$MAX_RETRIES}
    
    local attempt=0
    local http_code="000"
    local response=""
    local body=""
    
    while [[ $attempt -lt $max_attempts ]]; do
        response=$(make_request "$url")
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | sed '$d')
        
        if [[ "$http_code" == "$expected_status" ]]; then
            echo -e "${body}\n${http_code}"
            return 0
        fi
        
        ((attempt++)) || true
        if [[ $attempt -lt $max_attempts ]]; then
            log_info "Retry $attempt/$max_attempts for $description..."
            sleep "$RETRY_DELAY"
        fi
    done
    
    echo -e "${body}\n${http_code}"
    return 1
}

# =============================================================================
# TEST FUNCTIONS
# =============================================================================

test_basic_health() {
    log_section "TEST 1: Basic Health Endpoint"
    
    local url="${BASE_URL}/health"
    log_info "Testing: $url"
    
    local result
    result=$(retry_request "$url" 200 "basic health check")
    local http_code=$(echo "$result" | tail -n1)
    local body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" ]]; then
        local status=$(parse_json "$body" ".status")
        local version=$(parse_json "$body" ".version")
        
        if [[ "$status" == "healthy" ]]; then
            log_success "Health endpoint returns healthy status"
            log_info "  Version: $version"
            return 0
        else
            log_failure "Health status is '$status' (expected 'healthy')"
            return 1
        fi
    else
        log_failure "Health endpoint returned HTTP $http_code (expected 200)"
        return 1
    fi
}

test_detailed_health() {
    log_section "TEST 2: Detailed Health Endpoint"
    
    local url="${BASE_URL}/health/detailed"
    log_info "Testing: $url"
    
    local result
    result=$(retry_request "$url" 200 "detailed health check")
    local http_code=$(echo "$result" | tail -n1)
    local body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" ]]; then
        local overall_status=$(parse_json "$body" ".status")
        local db_status=$(parse_json "$body" ".components.database")
        local scheduler_status=$(parse_json "$body" ".components.scheduler")
        local cache_status=$(parse_json "$body" ".components.cache")
        
        log_info "  Overall Status: $overall_status"
        log_info "  Database: $db_status"
        log_info "  Scheduler: $scheduler_status"
        log_info "  Cache: $cache_status"
        
        local all_healthy=true
        
        if [[ "$db_status" != "healthy" && "$db_status" != "sqlite" ]]; then
            log_failure "Database is not healthy: $db_status"
            all_healthy=false
        fi
        
        if [[ "$scheduler_status" != "running" && "$scheduler_status" != "healthy" ]]; then
            log_warning "Scheduler is not running: $scheduler_status"
        fi
        
        if [[ "$overall_status" == "healthy" || "$overall_status" == "degraded" ]]; then
            log_success "Detailed health check passed"
            return 0
        else
            log_failure "Overall status is unhealthy: $overall_status"
            return 1
        fi
    else
        log_failure "Detailed health endpoint returned HTTP $http_code"
        return 1
    fi
}

test_api_status() {
    log_section "TEST 3: System Status API"
    
    local url="${BASE_URL}/api/v1/status"
    log_info "Testing: $url"
    
    local result
    result=$(retry_request "$url" 200 "system status")
    local http_code=$(echo "$result" | tail -n1)
    local body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" ]]; then
        local db_component=$(parse_json "$body" ".components.database")
        local scheduler=$(parse_json "$body" ".components.scheduler")
        
        log_info "  Database: $db_component"
        log_info "  Scheduler: $scheduler"
        
        log_success "System status API is accessible"
        return 0
    else
        log_failure "System status API returned HTTP $http_code"
        return 1
    fi
}

test_auth_endpoints() {
    log_section "TEST 4: Authentication Endpoints"
    
    # Test login page
    local login_url="${BASE_URL}/auth/login"
    log_info "Testing login page: $login_url"
    
    local result
    result=$(make_request "$login_url")
    local http_code=$(echo "$result" | tail -n1)
    
    if [[ "$http_code" == "200" ]]; then
        log_success "Login page is accessible"
    else
        log_failure "Login page returned HTTP $http_code"
    fi
    
    # Test auth health
    local auth_health_url="${BASE_URL}/api/v1/auth/health"
    log_info "Testing auth health: $auth_health_url"
    
    result=$(make_request "$auth_health_url")
    http_code=$(echo "$result" | tail -n1)
    local body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" ]]; then
        local jwt_configured=$(parse_json "$body" ".jwt_configured")
        local azure_ad_configured=$(parse_json "$body" ".azure_ad_configured")
        
        log_info "  JWT Configured: $jwt_configured"
        log_info "  Azure AD Configured: $azure_ad_configured"
        
        if [[ "$jwt_configured" == "true" ]]; then
            log_success "Auth health endpoint shows JWT configured"
        else
            log_warning "JWT is not fully configured"
        fi
    else
        log_failure "Auth health endpoint returned HTTP $http_code"
    fi
}

test_protected_endpoints() {
    log_section "TEST 5: Protected Endpoint Security"
    
    # Test that protected endpoints require auth
    local protected_url="${BASE_URL}/api/v1/riverside/summary"
    log_info "Testing protected endpoint without auth: $protected_url"
    
    local result
    result=$(make_request "$protected_url")
    local http_code=$(echo "$result" | tail -n1)
    
    if [[ "$http_code" == "401" || "$http_code" == "307" || "$http_code" == "302" ]]; then
        log_success "Protected endpoint correctly rejects unauthenticated requests (HTTP $http_code)"
    else
        log_failure "Protected endpoint should reject unauthenticated requests (got HTTP $http_code)"
    fi
    
    # Test invalid token rejection
    log_info "Testing invalid token rejection..."
    result=$(make_request "$protected_url" "GET" "Authorization: Bearer invalid-token")
    http_code=$(echo "$result" | tail -n1)
    
    if [[ "$http_code" == "401" ]]; then
        log_success "Invalid tokens are correctly rejected"
    else
        log_warning "Invalid token returned HTTP $http_code (expected 401)"
    fi
}

test_metrics_endpoint() {
    log_section "TEST 6: Metrics Endpoint"
    
    local url="${BASE_URL}/metrics"
    log_info "Testing: $url"
    
    local result
    result=$(retry_request "$url" 200 "metrics endpoint")
    local http_code=$(echo "$result" | tail -n1)
    local body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" ]]; then
        local content_length=${#body}
        if [[ $content_length -gt 100 ]]; then
            log_success "Metrics endpoint returns data ($content_length bytes)"
            return 0
        else
            log_warning "Metrics endpoint returned minimal data"
            return 0
        fi
    else
        log_failure "Metrics endpoint returned HTTP $http_code"
        return 1
    fi
}

test_static_files() {
    log_section "TEST 7: Static Files"
    
    local css_url="${BASE_URL}/static/css/theme.css"
    log_info "Testing CSS: $css_url"
    
    local result
    result=$(make_request "$css_url")
    local http_code=$(echo "$result" | tail -n1)
    
    if [[ "$http_code" == "200" ]]; then
        log_success "Static CSS files are accessible"
    else
        log_warning "Static CSS returned HTTP $http_code (may be normal if not built)"
    fi
    
    # Test JS files
    local js_url="${BASE_URL}/static/js/navigation/index.js"
    log_info "Testing JS: $js_url"
    
    result=$(make_request "$js_url")
    http_code=$(echo "$result" | tail -n1)
    
    if [[ "$http_code" == "200" ]]; then
        log_success "Static JS files are accessible"
    else
        log_warning "Static JS returned HTTP $http_code"
    fi
}

test_database_connectivity() {
    log_section "TEST 8: Database Connectivity"
    
    # Check from detailed health endpoint
    local url="${BASE_URL}/health/detailed"
    log_info "Checking database status via health endpoint..."
    
    local result
    result=$(make_request "$url")
    local http_code=$(echo "$result" | tail -n1)
    local body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" ]]; then
        local db_status=$(parse_json "$body" ".components.database")
        local pool_stats=$(parse_json "$body" ".database_pool")
        
        if [[ "$db_status" == "healthy" || "$db_status" == *"sqlite"* ]]; then
            log_success "Database connectivity confirmed (status: $db_status)"
            if [[ "$pool_stats" != "null" && "$pool_stats" != "n/a (SQLite)" ]]; then
                log_info "  Pool stats: $pool_stats"
            fi
            return 0
        else
            log_failure "Database is not healthy: $db_status"
            return 1
        fi
    else
        log_failure "Cannot check database status (HTTP $http_code)"
        return 1
    fi
}

test_cache_functionality() {
    log_section "TEST 9: Cache Functionality"
    
    local url="${BASE_URL}/health/detailed"
    log_info "Checking cache status..."
    
    local result
    result=$(make_request "$url")
    local http_code=$(echo "$result" | tail -n1)
    local body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" ]]; then
        local cache_status=$(parse_json "$body" ".components.cache")
        local cache_metrics=$(parse_json "$body" ".cache_metrics")
        
        log_info "  Cache backend: $cache_status"
        
        if [[ "$cache_status" == "memory" || "$cache_status" == "redis" || "$cache_status" == "healthy" ]]; then
            log_success "Cache is functional ($cache_status backend)"
            
            local hit_rate=$(parse_json "$cache_metrics" ".hit_rate_percent")
            if [[ "$hit_rate" != "null" ]]; then
                log_info "  Hit rate: ${hit_rate}%"
            fi
            return 0
        else
            log_warning "Cache status: $cache_status"
            return 0
        fi
    else
        log_warning "Cannot verify cache status (HTTP $http_code)"
        return 0
    fi
}

test_azure_connectivity() {
    log_section "TEST 10: Azure Connectivity"
    
    # Check from detailed health endpoint
    local url="${BASE_URL}/health/detailed"
    log_info "Checking Azure configuration..."
    
    local result
    result=$(make_request "$url")
    local http_code=$(echo "$result" | tail -n1)
    local body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" ]]; then
        local azure_configured=$(parse_json "$body" ".components.azure_configured")
        
        if [[ "$azure_configured" == "true" ]]; then
            log_success "Azure is configured"
        else
            log_warning "Azure may not be fully configured (azure_configured: $azure_configured)"
        fi
    fi
    
    # Try to hit preflight status (may require auth)
    local preflight_url="${BASE_URL}/api/v1/preflight/status"
    log_info "Testing preflight endpoint..."
    
    result=$(make_request "$preflight_url")
    http_code=$(echo "$result" | tail -n1)
    body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" || "$http_code" == "401" ]]; then
        log_success "Preflight endpoint is accessible (HTTP $http_code)"
    else
        log_warning "Preflight endpoint returned HTTP $http_code"
    fi
}

test_tenant_sync_status() {
    log_section "TEST 11: Tenant Sync Status"
    
    local sync_url="${BASE_URL}/api/v1/sync/status"
    log_info "Checking sync status: $sync_url"
    
    local result
    result=$(make_request "$sync_url")
    local http_code=$(echo "$result" | tail -n1)
    local body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" ]]; then
        local job_count=$(parse_json "$body" '.jobs | length')
        log_info "  Active sync jobs: $job_count"
        
        if [[ $job_count -gt 0 ]]; then
            log_success "Sync system has $job_count active jobs"
        else
            log_warning "No active sync jobs found"
        fi
        
        # Check for tenants
        local tenants_url="${BASE_URL}/api/v1/tenants"
        log_info "Checking tenants: $tenants_url"
        
        result=$(make_request "$tenants_url")
        http_code=$(echo "$result" | tail -n1)
        body=$(echo "$result" | sed '$d')
        
        if [[ "$http_code" == "200" ]]; then
            local tenant_count=$(parse_json "$body" 'length')
            log_info "  Configured tenants: $tenant_count"
            
            if [[ $tenant_count -ge $EXPECTED_TENANT_COUNT ]]; then
                log_success "All $EXPECTED_TENANT_COUNT+ tenants are configured"
            else
                log_warning "Only $tenant_count tenants configured (expected $EXPECTED_TENANT_COUNT)"
            fi
        fi
        
        return 0
    elif [[ "$http_code" == "401" ]]; then
        log_skip "Sync status requires authentication"
        return 0
    else
        log_warning "Sync status returned HTTP $http_code"
        return 0
    fi
}

test_azure_resources() {
    log_section "TEST 12: Azure Resource Verification (Optional)"
    
    if ! check_command az; then
        log_skip "Azure CLI not available - skipping Azure resource checks"
        return 0
    fi
    
    if ! az account show &>/dev/null; then
        log_skip "Not logged into Azure - skipping Azure resource checks"
        log_info "Run 'az login' to enable Azure resource verification"
        return 0
    fi
    
    # Check App Service status
    log_info "Checking App Service: $APP_SERVICE"
    local app_status
    app_status=$(az webapp show --name "$APP_SERVICE" --resource-group "$RESOURCE_GROUP" --query "state" -o tsv 2>/dev/null || echo "unknown")
    
    if [[ "$app_status" == "Running" ]]; then
        log_success "App Service is Running"
    else
        log_warning "App Service status: $app_status"
    fi
    
    # Check HTTPS only
    log_info "Checking HTTPS configuration..."
    local https_only
    https_only=$(az webapp show --name "$APP_SERVICE" --resource-group "$RESOURCE_GROUP" --query "httpsOnly" -o tsv 2>/dev/null || echo "unknown")
    
    if [[ "$https_only" == "true" ]]; then
        log_success "HTTPS Only is enabled"
    else
        log_warning "HTTPS Only is not enabled"
    fi
    
    # Check App Insights
    log_info "Checking Application Insights..."
    local ai_name
    ai_name=$(az monitor app-insights component list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || echo "")
    
    if [[ -n "$ai_name" ]]; then
        log_success "Application Insights configured: $ai_name"
    else
        log_warning "Application Insights not found"
    fi
}

test_dashboard_load() {
    log_section "TEST 13: Dashboard Load Test"
    
    local url="${BASE_URL}/"
    log_info "Testing dashboard: $url"
    
    # Follow redirects
    local result
    result=$(curl -s -L --max-time "$TIMEOUT" -w "\n%{http_code}" "$url" 2>/dev/null || echo -e "\n000")
    local http_code=$(echo "$result" | tail -n1)
    local body=$(echo "$result" | sed '$d')
    
    if [[ "$http_code" == "200" || "$http_code" == "307" || "$http_code" == "302" ]]; then
        if [[ "$body" == *"<!DOCTYPE"* || "$body" == *"<html"* ]]; then
            log_success "Dashboard loads and returns HTML content"
        else
            log_warning "Dashboard returned unexpected content type"
        fi
    else
        log_warning "Dashboard returned HTTP $http_code"
    fi
}

# =============================================================================
# SUMMARY AND REPORTING
# =============================================================================

print_summary() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                      VERIFICATION SUMMARY                       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    local total=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))
    
    echo -e "  ${GREEN}✓ Tests Passed:   $TESTS_PASSED${NC}"
    echo -e "  ${RED}✗ Tests Failed:   $TESTS_FAILED${NC}"
    echo -e "  ${CYAN}⊘ Tests Skipped:  $TESTS_SKIPPED${NC}"
    echo -e "  ${YELLOW}! Warnings:       $WARNINGS${NC}"
    echo -e "  ─────────────────────────────────────────"
    echo -e "  Total Tests:      $total"
    echo ""
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "  ${GREEN}✅ DEPLOYMENT VERIFICATION PASSED${NC}"
        echo -e "  ${GREEN}   All critical checks passed successfully.${NC}"
        echo ""
        echo -e "  Environment: ${CYAN}${ENVIRONMENT}${NC}"
        echo -e "  URL: ${CYAN}${BASE_URL}${NC}"
        echo ""
        return 0
    else
        echo -e "  ${RED}❌ DEPLOYMENT VERIFICATION FAILED${NC}"
        echo -e "  ${RED}   $TESTS_FAILED critical check(s) failed.${NC}"
        echo ""
        echo -e "  Review the failed tests above and:"
        echo -e "  • Check Azure Portal for resource health"
        echo -e "  • Review Application Insights logs"
        echo -e "  • Run: az webapp log tail --name $APP_SERVICE --resource-group $RESOURCE_GROUP"
        echo ""
        return 1
    fi
}

print_next_steps() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${CYAN}Recommended Next Steps:${NC}"
    echo ""
    echo "  1. Review any warnings above"
    echo "  2. Check Application Insights for errors:"
    echo "     az monitor app-insights query --apps $APP_SERVICE --analytics-query 'traces | where severityLevel >= 3'"
    echo ""
    echo "  3. View application logs:"
    echo "     az webapp log tail --name $APP_SERVICE --resource-group $RESOURCE_GROUP"
    echo ""
    echo "  4. Run preflight checks (requires auth):"
    echo "     curl -X POST ${BASE_URL}/api/v1/preflight/run"
    echo ""
    echo "  5. Test with smoke test script:"
    echo "     python scripts/smoke_test.py --url ${BASE_URL}"
    echo ""
}

# =============================================================================
# COMMAND LINE PARSING
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --url)
                BASE_URL="$2"
                shift 2
                ;;
            --env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --resource-group)
                RESOURCE_GROUP="$2"
                shift 2
                ;;
            --app-service)
                APP_SERVICE="$2"
                shift 2
                ;;
            --help)
                cat << 'EOF'
Azure Governance Platform - Deployment Verification Script

Usage: ./scripts/verify-deployment.sh [OPTIONS]

Options:
  --url URL              Base URL to test (default: https://app-governance-prod.azurewebsites.net)
  --env ENVIRONMENT      Environment name (default: production)
  --resource-group NAME  Azure resource group name
  --app-service NAME     Azure App Service name
  --help                 Show this help message

Environment Variables:
  BASE_URL               Base URL to test
  ENVIRONMENT            Environment name
  RESOURCE_GROUP         Azure resource group name
  APP_SERVICE            Azure App Service name
  KEY_VAULT              Azure Key Vault name
  EXPECTED_TENANT_COUNT  Number of tenants expected (default: 5)
  TIMEOUT                Request timeout in seconds (default: 30)
  MAX_RETRIES            Number of retries for failed requests (default: 3)

Examples:
  # Test production deployment
  ./scripts/verify-deployment.sh

  # Test development deployment
  ./scripts/verify-deployment.sh --url https://app-governance-dev.azurewebsites.net --env development

  # Test with custom resource names
  ./scripts/verify-deployment.sh --resource-group my-rg --app-service my-app

Exit Codes:
  0 - All checks passed
  1 - Critical checks failed
  2 - Configuration error
EOF
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                echo "Run with --help for usage information"
                exit 2
                ;;
        esac
    done
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    parse_args "$@"
    print_header
    
    # Check dependencies
    if ! check_command curl; then
        echo -e "${RED}Error: curl is required but not installed.${NC}"
        exit 2
    fi
    
    if ! check_command jq; then
        echo -e "${YELLOW}Warning: jq is not installed. Some checks will be limited.${NC}"
        echo "Install jq for better JSON parsing: https://stedolan.github.io/jq/"
        echo ""
    fi
    
    # Run all tests
    test_basic_health
    test_detailed_health
    test_api_status
    test_auth_endpoints
    test_protected_endpoints
    test_metrics_endpoint
    test_static_files
    test_database_connectivity
    test_cache_functionality
    test_azure_connectivity
    test_tenant_sync_status
    test_azure_resources
    test_dashboard_load
    
    # Print summary
    print_summary
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        print_next_steps
    fi
    
    exit $exit_code
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
