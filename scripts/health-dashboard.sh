#!/bin/bash
# =============================================================================
# Health Dashboard
# =============================================================================
# Real-time terminal dashboard showing health status of all environments.
# Displays Dev, Staging, and Production health at a glance.
#
# Usage: ./scripts/health-dashboard.sh
# Press Ctrl+C to exit, R to refresh
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# Environment URLs
DEV_URL="https://app-governance-dev-001.azurewebsites.net"
STAGING_URL="https://app-governance-staging-001.azurewebsites.net"
PROD_URL="https://app-governance-prod-001.azurewebsites.net"

# Configuration
REFRESH_INTERVAL=${REFRESH_INTERVAL:-10}  # seconds
SHOW_DETAILS=${SHOW_DETAILS:-true}

# Functions
clear_screen() {
    clear
}

print_header() {
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║        ${WHITE}Azure Governance Platform - Health Dashboard${CYAN}              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_footer() {
    echo ""
    echo -e "${GRAY}──────────────────────────────────────────────────────────────────${NC}"
    echo -e "${GRAY}Last updated: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${GRAY}Auto-refresh: ${REFRESH_INTERVAL}s | Press Ctrl+C to exit${NC}"
}

# Check health of a specific environment
check_health() {
    local url=$1
    local name=$2
    local response
    local status
    local http_code
    local response_time
    
    # Measure response time
    local start_time=$(date +%s%N)
    
    # Try to get health endpoint
    response=$(curl -s -w "\n%{http_code}\n%{time_total}" \
        --max-time 10 \
        "${url}/health" 2>/dev/null || echo -e "\n000\n0")
    
    local end_time=$(date +%s%N)
    
    # Parse response
    local http_code=$(echo "$response" | tail -n 2 | head -n 1)
    local response_time=$(echo "$response" | tail -n 1)
    local body=$(echo "$response" | head -n -2)
    
    # Calculate response time in ms
    if command -v bc &> /dev/null; then
        response_time=$(echo "$response_time * 1000" | bc 2>/dev/null | cut -d'.' -f1)
    else
        response_time="N/A"
    fi
    
    # Determine status
    if [ "$http_code" == "200" ]; then
        local health_status=$(echo "$body" | grep -o '"status"[^,}]*' | cut -d'"' -f4 2>/dev/null || echo "unknown")
        if [ "$health_status" == "healthy" ]; then
            status="${GREEN}✅ HEALTHY${NC}"
        else
            status="${YELLOW}⚠️  DEGRADED${NC}"
        fi
    elif [ "$http_code" == "000" ]; then
        status="${RED}❌ UNREACHABLE${NC}"
        http_code="TIMEOUT"
    elif [ "$http_code" == "503" ]; then
        status="${RED}❌ ERROR 503${NC}"
    else
        status="${RED}❌ ERROR${NC}"
    fi
    
    echo -e "${CYAN}│${NC} ${WHITE}$(printf "%-10s" "$name")${NC} $status ${GRAY}(${http_code})${NC} $(printf "%6s" "${response_time}ms") ${CYAN}│${NC}"
}

# Get detailed status
check_detailed_status() {
    local url=$1
    local name=$2
    
    local detailed=$(curl -s --max-time 5 "${url}/health/detailed" 2>/dev/null || echo "{}")
    
    # Try to extract component statuses
    local db_status=$(echo "$detailed" | grep -o '"database"[^,}]*' | cut -d'"' -f4 2>/dev/null || echo "unknown")
    local scheduler_status=$(echo "$detailed" | grep -o '"scheduler"[^,}]*' | cut -d'"' -f4 2>/dev/null || echo "unknown")
    local cache_status=$(echo "$detailed" | grep -o '"cache"[^,}]*' | cut -d'"' -f4 2>/dev/null || echo "unknown")
    
    echo -e "${CYAN}│${NC} ${GRAY}  → Database:  $(_color_status "$db_status")${NC}"
    echo -e "${CYAN}│${NC} ${GRAY}  → Scheduler: $(_color_status "$scheduler_status")${NC}"
    echo -e "${CYAN}│${NC} ${GRAY}  → Cache:     $(_color_status "$cache_status")${NC}"
}

# Colorize status
_color_status() {
    local status=$1
    case "$status" in
        healthy|up|connected)
            echo -e "${GREEN}$status${NC}"
            ;;
        degraded|warning)
            echo -e "${YELLOW}$status${NC}"
            ;;
        error|down|unhealthy|unknown)
            echo -e "${RED}$status${NC}"
            ;;
        *)
            echo -e "${GRAY}$status${NC}"
            ;;
    esac
}

# Print quick links
print_quick_links() {
    echo ""
    echo -e "${CYAN}┌─ Quick Links ───────────────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│${NC}                                                                  ${CYAN}│${NC}"
    echo -e "${CYAN}│${NC} ${GRAY}Dev:${NC}     ${DEV_URL}"
    echo -e "${CYAN}│${NC} ${GRAY}Staging:${NC} ${STAGING_URL}"
    echo -e "${CYAN}│${NC} ${GRAY}Prod:${NC}    ${PROD_URL}"
    echo -e "${CYAN}│${NC}                                                                  ${CYAN}│${NC}"
    echo -e "${CYAN}└──────────────────────────────────────────────────────────────────┘${NC}"
}

# Print Azure CLI commands
print_cli_commands() {
    echo ""
    echo -e "${CYAN}┌─ Useful Commands ───────────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│${NC} ${GRAY}# View dev logs${NC}                                                 ${CYAN}│${NC}"
    echo -e "${CYAN}│${NC} az webapp log tail -n app-governance-dev-001 -g rg-governance-dev ${CYAN}│${NC}"
    echo -e "${CYAN}│${NC}                                                                  ${CYAN}│${NC}"
    echo -e "${CYAN}│${NC} ${GRAY}# Check configuration${NC}                                           ${CYAN}│${NC}"
    echo -e "${CYAN}│${NC} az webapp config show -n app-governance-dev-001 -g rg-governance-dev ${CYAN}│${NC}"
    echo -e "${CYAN}└──────────────────────────────────────────────────────────────────┘${NC}"
}

# Main dashboard display
show_dashboard() {
    clear_screen
    print_header
    
    echo -e "${CYAN}┌─ Environment Health ────────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│${NC}                                                                  ${CYAN}│${NC}"
    
    # Check each environment
    check_health "$DEV_URL" "Dev"
    if [ "$SHOW_DETAILS" == "true" ]; then
        check_detailed_status "$DEV_URL" "Dev"
    fi
    
    echo -e "${CYAN}│${NC}                                                                  ${CYAN}│${NC}"
    
    check_health "$STAGING_URL" "Staging"
    if [ "$SHOW_DETAILS" == "true" ]; then
        check_detailed_status "$STAGING_URL" "Staging"
    fi
    
    echo -e "${CYAN}│${NC}                                                                  ${CYAN}│${NC}"
    
    check_health "$PROD_URL" "Prod"
    if [ "$SHOW_DETAILS" == "true" ]; then
        check_detailed_status "$PROD_URL" "Prod"
    fi
    
    echo -e "${CYAN}│${NC}                                                                  ${CYAN}│${NC}"
    echo -e "${CYAN}└──────────────────────────────────────────────────────────────────┘${NC}"
    
    print_quick_links
    print_cli_commands
    print_footer
}

# Main loop
main() {
    # Handle Ctrl+C gracefully
    trap 'echo -e "\n\n${GREEN}Dashboard closed.${NC}"; exit 0' INT
    
    # Check for dependencies
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}Error: curl is required but not installed.${NC}"
        exit 1
    fi
    
    # Show initial dashboard
    show_dashboard
    
    # Auto-refresh loop
    while true; do
        sleep "$REFRESH_INTERVAL"
        show_dashboard
    done
}

# Show help
show_help() {
    cat << EOF
Azure Governance Platform - Health Dashboard

Usage: ./scripts/health-dashboard.sh [options]

Options:
  --interval N    Set refresh interval to N seconds (default: 10)
  --no-details    Hide detailed component status
  --once          Run once and exit (no auto-refresh)
  --help          Show this help message

Environment Variables:
  REFRESH_INTERVAL    Auto-refresh interval in seconds
  SHOW_DETAILS        Show detailed component status (true/false)

Examples:
  ./scripts/health-dashboard.sh              # Run with default settings
  ./scripts/health-dashboard.sh --interval 5 # Refresh every 5 seconds
  ./scripts/health-dashboard.sh --once       # Single check

Press Ctrl+C to exit the dashboard.
EOF
}

# Parse arguments
ONCE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --interval)
            REFRESH_INTERVAL="$2"
            shift 2
            ;;
        --no-details)
            SHOW_DETAILS=false
            shift
            ;;
        --once)
            ONCE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Run once or loop
if [ "$ONCE" == "true" ]; then
    show_dashboard
else
    main
fi
