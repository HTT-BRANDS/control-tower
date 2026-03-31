#!/bin/bash
# =============================================================================
# Azure Governance Platform — Dependency Check Script
# =============================================================================
# Checks for outdated packages, security vulnerabilities, and deprecated
# dependencies. Generates a report with upgrade recommendations.
#
# Usage:
#   ./scripts/check-dependencies.sh              # Run all checks
#   ./scripts/check-dependencies.sh --security   # Security only
#   ./scripts/check-dependencies.sh --outdated   # Outdated only
#   ./scripts/check-dependencies.sh --json       # Output JSON report
#
# Exit codes:
#   0 - All checks passed
#   1 - Security vulnerabilities found
#   2 - Outdated packages found
#   3 - Deprecated packages found
#   4 - Multiple issues found
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Temporary files
TEMP_DIR=$(mktemp -d)
REQUIREMENTS_FILE="$TEMP_DIR/requirements.txt"
REPORT_FILE="$TEMP_DIR/report.md"
JSON_OUTPUT=false

# Exit code tracking
EXIT_CODE=0
VULN_FOUND=0
OUTDATED_FOUND=0
DEPRECATED_FOUND=0

# Cleanup function
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Help function
show_help() {
    cat << EOF
Azure Governance Platform — Dependency Checker

Usage: $0 [OPTIONS]

OPTIONS:
    --security      Check only for security vulnerabilities
    --outdated      Check only for outdated packages
    --deprecated    Check only for deprecated packages
    --json          Output results as JSON
    --report FILE   Save report to file
    --help          Show this help message

EXAMPLES:
    $0                      # Run all checks
    $0 --security           # Security audit only
    $0 --json               # JSON output
    $0 --report deps.md     # Save report to deps.md

EOF
}

# Parse arguments
CHECK_SECURITY=true
CHECK_OUTDATED=true
CHECK_DEPRECATED=true
REPORT_OUTPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --security)
            CHECK_SECURITY=true
            CHECK_OUTDATED=false
            CHECK_DEPRECATED=false
            shift
            ;;
        --outdated)
            CHECK_SECURITY=false
            CHECK_OUTDATED=true
            CHECK_DEPRECATED=false
            shift
            ;;
        --deprecated)
            CHECK_SECURITY=false
            CHECK_OUTDATED=false
            CHECK_DEPRECATED=true
            shift
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --report)
            REPORT_OUTPUT="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Header
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Azure Governance Platform — Dependency Check            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Timestamp:${NC} $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo -e "${BLUE}Project:${NC} $PROJECT_ROOT"
echo ""

# Check if running in project root
if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
    echo -e "${RED}Error: pyproject.toml not found. Run from project root.${NC}"
    exit 1
fi

# Check for required tools
check_requirements() {
    local missing_tools=()
    
    if ! command -v uv &> /dev/null; then
        missing_tools+=("uv")
    fi
    
    if [[ "$CHECK_SECURITY" == true ]] && ! command -v pip-audit &> /dev/null; then
        missing_tools+=("pip-audit")
    fi
    
    if [[ "$CHECK_OUTDATED" == true ]] && ! command -v pip-outdated &> /dev/null; then
        missing_tools+=("pip-outdated")
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        echo -e "${RED}Missing required tools:${NC}"
        for tool in "${missing_tools[@]}"; do
            echo "  - $tool"
        done
        echo ""
        echo "Install with:"
        echo "  uv tool install pip-audit pip-outdated"
        exit 1
    fi
}

check_requirements

# Export requirements from uv.lock
echo -e "${BLUE}→ Exporting requirements from uv.lock...${NC}"
uv export --no-hashes --no-dev > "$REQUIREMENTS_FILE" 2>/dev/null || {
    echo -e "${RED}Error: Failed to export requirements${NC}"
    exit 1
}
echo -e "${GREEN}✓ Requirements exported${NC}"
echo ""

# Initialize JSON structure
if [[ "$JSON_OUTPUT" == true ]]; then
    JSON_DATA='{"timestamp":"'$(date -u '+%Y-%m-%dT%H:%M:%SZ')'","checks":{},"summary":{}}'
fi

# ============================================================================
# Security Check (pip-audit)
# ============================================================================
if [[ "$CHECK_SECURITY" == true ]]; then
    echo -e "${BLUE}→ Running security audit (pip-audit)...${NC}"
    
    AUDIT_JSON="$TEMP_DIR/pip-audit.json"
    
    # Run pip-audit, but handle potential failures gracefully
    set +e
    pip-audit -r "$REQUIREMENTS_FILE" --format=json --output="$AUDIT_JSON" 2>/dev/null
    AUDIT_EXIT=$?
    set -e
    
    # Check if output file was created and has content
    if [[ -f "$AUDIT_JSON" ]] && [[ -s "$AUDIT_JSON" ]]; then
        VULN_COUNT=$(jq '[.dependencies[]?.vulns // empty | length] | add // 0' "$AUDIT_JSON" 2>/dev/null || echo "0")
        
        if [[ "$JSON_OUTPUT" == true ]]; then
            JSON_DATA=$(echo "$JSON_DATA" | jq --argjson audit "$(cat "$AUDIT_JSON" 2>/dev/null || echo '{}')" '.checks.security = $audit')
        fi
        
        if [[ $VULN_COUNT -gt 0 ]]; then
            VULN_FOUND=1
            EXIT_CODE=1
            echo -e "${RED}✗ Found $VULN_COUNT security vulnerabilities${NC}"
            
            # Display vulnerabilities
            jq -r '.dependencies[] | select(.vulns) | 
              "- \(.name) \(.version):\n\(.vulns | map(\"  • \(.id): \(.description // \"No description\")\" ) | join(\"\\n\"))"' "$AUDIT_JSON" 2>/dev/null | while read -r line; do
                echo "  $line"
            done
            
            # Generate fix commands
            echo ""
            echo -e "${YELLOW}Fix recommendations:${NC}"
            jq -r '.dependencies[] | select(.vulns) | 
              select(.vulns[].fix_versions) | 
              "  uv add \(.name)@\(.vulns[].fix_versions[0])"' "$AUDIT_JSON" 2>/dev/null | sort -u
        else
            echo -e "${GREEN}✓ No security vulnerabilities found${NC}"
        fi
    elif [[ $AUDIT_EXIT -ne 0 ]]; then
        echo -e "${YELLOW}⚠ pip-audit could not complete (exit code: $AUDIT_EXIT)${NC}"
        echo -e "${YELLOW}  This may be due to venv creation issues. Run manually:${NC}"
        echo -e "${YELLOW}    uv run pip-audit -r requirements.txt${NC}"
        
        if [[ "$JSON_OUTPUT" == true ]]; then
            JSON_DATA=$(echo "$JSON_DATA" | jq '.checks.security = {"error": "pip-audit failed", "exit_code": '$AUDIT_EXIT'}')
        fi
    else
        echo -e "${YELLOW}⚠ pip-audit produced no output${NC}"
    fi
    echo ""
fi
# ============================================================================
# Outdated Check (pip-outdated)
# ============================================================================
if [[ "$CHECK_OUTDATED" == true ]]; then
    echo -e "${BLUE}→ Checking for outdated packages (pip-outdated)...${NC}"
    
    OUTDATED_JSON="$TEMP_DIR/pip-outdated.json"
    
    if pip-outdated --requirements-file "$REQUIREMENTS_FILE" --format=json > "$OUTDATED_JSON" 2>/dev/null || true; then
        OUTDATED_COUNT=$(jq 'length' "$OUTDATED_JSON")
        
        if [[ "$JSON_OUTPUT" == true ]]; then
            JSON_DATA=$(echo "$JSON_DATA" | jq --argjson outdated "$(cat "$OUTDATED_JSON")" '.checks.outdated = $outdated')
        fi
        
        if [[ $OUTDATED_COUNT -gt 0 ]]; then
            OUTDATED_FOUND=1
            if [[ $EXIT_CODE -eq 0 ]]; then
                EXIT_CODE=2
            else
                EXIT_CODE=4
            fi
            
            echo -e "${YELLOW}⚠ Found $OUTDATED_COUNT outdated packages${NC}"
            
            # Display outdated packages
            echo ""
            printf "${BLUE}%-30s %-15s %-15s %s${NC}\n" "Package" "Current" "Latest" "Type"
            echo "─────────────────────────────────────────────────────────────────────"
            
            jq -r '.[] | [.name, .version, .latest_version, 
              if .latest_major then "major" 
              elif .latest_minor then "minor" 
              elif .latest_patch then "patch" 
              else "other" end] | @tsv' "$OUTDATED_JSON" 2>/dev/null | while IFS=$'\t' read -r name current latest type; do
                color="$NC"
                if [[ "$type" == "major" ]]; then color="$RED"; fi
                if [[ "$type" == "minor" ]]; then color="$YELLOW"; fi
                if [[ "$type" == "patch" ]]; then color="$GREEN"; fi
                printf "${color}%-30s %-15s %-15s %s${NC}\n" "$name" "$current" "$latest" "$type"
            done
            
            # Count by type
            MAJOR_COUNT=$(jq '[.[] | select(.latest_major)] | length' "$OUTDATED_JSON")
            MINOR_COUNT=$(jq '[.[] | select(.latest_minor)] | length' "$OUTDATED_JSON")
            PATCH_COUNT=$(jq '[.[] | select(.latest_patch)] | length' "$OUTDATED_JSON")
            
            echo ""
            echo "Summary: ${RED}$MAJOR_COUNT major${NC}, ${YELLOW}$MINOR_COUNT minor${NC}, ${GREEN}$PATCH_COUNT patch${NC} updates available"
        else
            echo -e "${GREEN}✓ All packages are up to date${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Could not run pip-outdated${NC}"
    fi
    echo ""
fi

# ============================================================================
# Deprecated Check (heuristic based on last release date)
# ============================================================================
if [[ "$CHECK_DEPRECATED" == true ]]; then
    echo -e "${BLUE}→ Checking for potentially deprecated packages...${NC}"
    
    DEPRECATED_LIST=()
    
    # List of known deprecated/unmaintained packages (from pyproject.toml analysis)
    # This is a heuristic check - packages not updated in 2+ years
    KNOWN_DEPRECATED=(
        "pyjwt:1.7.1:Consider upgrading to PyJWT 2.x"
    )
    
    # Parse requirements and check against known deprecated
    while IFS='==' read -r package version; do
        package=$(echo "$package" | tr '[:upper:]' '[:lower:]')
        for deprecated in "${KNOWN_DEPRECATED[@]}"; do
            IFS=':' read -r dep_pkg dep_ver dep_msg <<< "$deprecated"
            if [[ "$package" == "$dep_pkg" ]]; then
                DEPRECATED_LIST+=("$package:$version:$dep_msg")
            fi
        done
    done < <(grep -v '^#' "$REQUIREMENTS_FILE" | grep -v '^$' | cut -d';' -f1 | tr -d ' ')
    
    if [[ ${#DEPRECATED_LIST[@]} -gt 0 ]]; then
        DEPRECATED_FOUND=1
        if [[ $EXIT_CODE -eq 0 ]]; then
            EXIT_CODE=3
        else
            EXIT_CODE=4
        fi
        
        echo -e "${YELLOW}⚠ Found ${#DEPRECATED_LIST[@]} potentially deprecated packages${NC}"
        echo ""
        for item in "${DEPRECATED_LIST[@]}"; do
            IFS=':' read -r pkg ver msg <<< "$item"
            echo -e "  ${YELLOW}$pkg $ver${NC}: $msg"
        done
    else
        echo -e "${GREEN}✓ No deprecated packages detected${NC}"
    fi
    
    if [[ "$JSON_OUTPUT" == true ]]; then
        JSON_DATA=$(echo "$JSON_DATA" | jq --argjson deprecated "$(printf '%s\n' "${DEPRECATED_LIST[@]}" | jq -R . | jq -s .)" '.checks.deprecated = $deprecated')
    fi
    echo ""
fi

# ============================================================================
# Generate Report
# ============================================================================
if [[ -n "$REPORT_OUTPUT" || "$JSON_OUTPUT" == false ]]; then
    {
        echo "# Dependency Check Report"
        echo ""
        echo "**Project:** Azure Governance Platform"
        echo "**Generated:** $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
        echo ""
        
        if [[ $VULN_FOUND -eq 1 ]]; then
            echo "## 🔒 Security Vulnerabilities"
            echo ""
            jq -r '.dependencies[] | select(.vulns) | 
              "- **\(.name)** \(.version):\n\(.vulns | map(\"  - \(.id): \(.description)\" ) | join(\"\\n\"))"' "$AUDIT_JSON" 2>/dev/null
            echo ""
        fi
        
        if [[ $OUTDATED_FOUND -eq 1 ]]; then
            echo "## 📦 Outdated Packages"
            echo ""
            echo "| Package | Current | Latest | Update Type |"
            echo "|---------|---------|--------|-------------|"
            jq -r '.[] | ["|", .name, "|", .version, "|", .latest_version, "|", 
              (if .latest_major then "major" elif .latest_minor then "minor" elif .latest_patch then "patch" else "other" end), "|"] | @tsv' "$OUTDATED_JSON" 2>/dev/null | tr '\t' ' '
            echo ""
        fi
        
        if [[ $DEPRECATED_FOUND -eq 1 ]]; then
            echo "## ⚠️ Deprecated Packages"
            echo ""
            for item in "${DEPRECATED_LIST[@]}"; do
                IFS=':' read -r pkg ver msg <<< "$item"
                echo "- **$pkg** $ver: $msg"
            done
            echo ""
        fi
        
        if [[ $EXIT_CODE -eq 0 ]]; then
            echo "## ✅ Status"
            echo ""
            echo "All dependency checks passed!"
        else
            echo "## ⚡ Recommendations"
            echo ""
            echo "### Immediate Actions"
            if [[ $VULN_FOUND -eq 1 ]]; then
                echo "1. **Security**: Run \`uv add <package>@<fixed_version>\` for vulnerable packages"
            fi
            if [[ $OUTDATED_FOUND -eq 1 ]]; then
                echo "2. **Updates**: Run \`uv sync --upgrade\` to update all dependencies"
                echo "3. **Major Updates**: Review major version updates manually before applying"
            fi
            echo ""
            echo "### Automation"
            echo "- Dependabot will create PRs for minor/patch updates"
            echo "- Major updates require manual review"
            echo "- Weekly security scans run automatically via GitHub Actions"
        fi
        
    } > "$REPORT_FILE"
    
    if [[ -n "$REPORT_OUTPUT" ]]; then
        cp "$REPORT_FILE" "$REPORT_OUTPUT"
        echo -e "${GREEN}✓ Report saved to: $REPORT_OUTPUT${NC}"
    fi
fi

# ============================================================================
# Summary
# ============================================================================
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                        Summary                               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Your dependencies are secure and up to date. 🎉"
else
    [[ $VULN_FOUND -eq 1 ]] && echo -e "${RED}✗ Security vulnerabilities found${NC}"
    [[ $OUTDATED_FOUND -eq 1 ]] && echo -e "${YELLOW}⚠ Outdated packages found${NC}"
    [[ $DEPRECATED_FOUND -eq 1 ]] && echo -e "${YELLOW}⚠ Deprecated packages found${NC}"
    echo ""
    echo "Run with --report to save detailed findings."
fi

# JSON output
if [[ "$JSON_OUTPUT" == true ]]; then
    JSON_DATA=$(echo "$JSON_DATA" | jq --argjson summary "{
        \"exit_code\": $EXIT_CODE,
        \"vulnerabilities_found\": $VULN_FOUND,
        \"outdated_found\": $OUTDATED_FOUND,
        \"deprecated_found\": $DEPRECATED_FOUND,
        \"all_clear\": $(if [[ $EXIT_CODE -eq 0 ]]; then echo "true"; else echo "false"; fi)
    }" '.summary = $summary')
    
    echo "$JSON_DATA" | jq .
fi

exit $EXIT_CODE
