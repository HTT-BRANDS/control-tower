#!/bin/bash
# =============================================================================
# Monitor Dev Environment Health
# =============================================================================
# Continuous monitoring script for the dev environment.
# Displays health status every 30 seconds with colored output.
#
# Usage: ./scripts/monitor-dev.sh
# Press Ctrl+C to stop monitoring
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_URL="https://app-governance-dev-001.azurewebsites.net"
HEALTH_ENDPOINT="${APP_URL}/health"
INTERVAL_SECONDS=30

# Counters
SUCCESS_COUNT=0
FAILURE_COUNT=0
START_TIME=$(date +%s)

# Functions
print_header() {
    clear
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     Azure Governance Platform - Dev Health Monitor         ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Target:${NC}  ${APP_URL}"
    echo -e "${BLUE}Started:${NC} $(date -r $START_TIME '+%Y-%m-%d %H:%M:%S')"
    echo -e "${BLUE}Interval:${NC} ${INTERVAL_SECONDS}s"
    echo ""
    echo -e "${CYAN}────────────────────────────────────────────────────────────${NC}"
    printf "%-20s %-10s %-8s %s\n" "Timestamp" "Status" "Code" "Response Time"
    echo -e "${CYAN}────────────────────────────────────────────────────────────${NC}"
}

print_summary() {
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    echo ""
    echo -e "${CYAN}────────────────────────────────────────────────────────────${NC}"
    echo -e "${BLUE}Monitoring stopped${NC}"
    echo ""
    echo -e "${BLUE}Session Summary:${NC}"
    echo -e "  Duration:      ${minutes}m ${seconds}s"
    echo -e "  Total Checks:  $((SUCCESS_COUNT + FAILURE_COUNT))"
    echo -e "  ${GREEN}Success:${NC}       $SUCCESS_COUNT"
    echo -e "  ${RED}Failures:${NC}      $FAILURE_COUNT"
    
    if [ $SUCCESS_COUNT -gt 0 ] || [ $FAILURE_COUNT -gt 0 ]; then
        local success_rate=$(( SUCCESS_COUNT * 100 / (SUCCESS_COUNT + FAILURE_COUNT) ))
        if [ $success_rate -ge 95 ]; then
            echo -e "  Success Rate:  ${GREEN}${success_rate}%${NC}"
        elif [ $success_rate -ge 80 ]; then
            echo -e "  Success Rate:  ${YELLOW}${success_rate}%${NC}"
        else
            echo -e "  Success Rate:  ${RED}${success_rate}%${NC}"
        fi
    fi
    echo ""
}

# Handle Ctrl+C
trap print_summary EXIT

# Main monitoring loop
print_header

while true; do
    TIMESTAMP=$(date '+%H:%M:%S')
    
    # Perform health check with timing
    START_CHECK=$(date +%s%N)
    
    # Capture response details
    HTTP_RESPONSE=$(curl -s -w "\n%{http_code}\n%{time_total}" \
        -o /tmp/health_response.json \
        "$HEALTH_ENDPOINT" 2>/dev/null || echo -e "\n000\n0")
    
    END_CHECK=$(date +%s%N)
    
    # Parse response
    HTTP_BODY=$(head -n 1 /tmp/health_response.json 2>/dev/null || echo "")
    HTTP_CODE=$(sed -n '2p' <<< "$HTTP_RESPONSE" 2>/dev/null || echo "000")
    RESPONSE_TIME=$(sed -n '3p' <<< "$HTTP_RESPONSE" 2>/dev/null || echo "0")
    
    # Format response time
    if command -v bc &> /dev/null; then
        RESPONSE_TIME_MS=$(echo "$RESPONSE_TIME * 1000" | bc 2>/dev/null | cut -d'.' -f1)
    else
        RESPONSE_TIME_MS="N/A"
    fi
    
    # Determine status
    if [ "$HTTP_CODE" == "200" ]; then
        STATUS="✅ Healthy"
        COLOR="$GREEN"
        ((SUCCESS_COUNT++)) || true
    elif [ "$HTTP_CODE" == "000" ]; then
        STATUS="❌ No Response"
        COLOR="$RED"
        ((FAILURE_COUNT++)) || true
    elif [ "$HTTP_CODE" == "503" ]; then
        STATUS="❌ Service Unavailable"
        COLOR="$RED"
        ((FAILURE_COUNT++)) || true
    else
        STATUS="⚠️  Error $HTTP_CODE"
        COLOR="$YELLOW"
        ((FAILURE_COUNT++)) || true
    fi
    
    # Print result
    printf "${COLOR}%-20s${NC} %-10s ${COLOR}%-8s${NC} %s\n" \
        "$TIMESTAMP" "$STATUS" "$HTTP_CODE" "${RESPONSE_TIME_MS}ms"
    
    # Log detailed response for failures
    if [ "$HTTP_CODE" != "200" ] && [ -f /tmp/health_response.json ]; then
        echo -e "${YELLOW}  Response: ${HTTP_BODY:0:100}${NC}"
    fi
    
    # Check for terminal resize and reprint header if needed
    if [ ${#TIMESTAMP} -eq 0 ]; then
        print_header
    fi
    
    sleep $INTERVAL_SECONDS
done
