#!/bin/bash
# =============================================================================
# HTT Control Tower - Dispatch Development Deployment Workflow
# =============================================================================
# Usage:
#   ./scripts/gh-deploy-dev.sh [options]
#
# Options:
#   -w, --watch          Watch deployment progress (default)
#   --no-watch           Dispatch and exit
#   --skip-tests         Dispatch workflow with run_tests=false
#   --ref <ref>          Branch/tag/SHA to deploy (default: current branch)
#   --tag-suffix <text>  Optional image tag suffix
#   -h, --help           Show help
#
# This script intentionally dispatches .github/workflows/deploy-dev.yml. It no
# longer pushes/merges a dev branch; that old path had no active workflow and
# was basically CI/CD cosplay.
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

WATCH=true
RUN_TESTS=true
DEPLOY_REF=""
TAG_SUFFIX=""
WORKFLOW="deploy-dev.yml"
REPO="HTT-BRANDS/control-tower"

show_help() {
    sed -n '2,28p' "$0"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -w|--watch)
            WATCH=true
            shift
            ;;
        --no-watch)
            WATCH=false
            shift
            ;;
        --skip-tests)
            RUN_TESTS=false
            shift
            ;;
        --ref)
            DEPLOY_REF="${2:-}"
            if [ -z "$DEPLOY_REF" ]; then
                echo -e "${RED}--ref requires a value${NC}" >&2
                exit 1
            fi
            shift 2
            ;;
        --tag-suffix)
            TAG_SUFFIX="${2:-}"
            if [ -z "$TAG_SUFFIX" ]; then
                echo -e "${RED}--tag-suffix requires a value${NC}" >&2
                exit 1
            fi
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            show_help
            exit 1
            ;;
    esac
done

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo -e "${RED}❌ Not in a git repository${NC}" >&2
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    echo -e "${RED}❌ gh CLI not found. Install: https://cli.github.com/${NC}" >&2
    exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
    echo -e "${RED}❌ Not logged in to GitHub. Run: gh auth login${NC}" >&2
    exit 1
fi

if ! gh workflow view "$WORKFLOW" --repo "$REPO" >/dev/null 2>&1; then
    echo -e "${RED}❌ Workflow $WORKFLOW not found in $REPO${NC}" >&2
    exit 1
fi

if [ -z "$DEPLOY_REF" ]; then
    DEPLOY_REF=$(git rev-parse --abbrev-ref HEAD)
fi

if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}❌ Working tree has uncommitted changes. Commit or stash before deploying dev.${NC}" >&2
    git status --short
    exit 1
fi

if ! git ls-remote --exit-code --heads origin "$DEPLOY_REF" >/dev/null 2>&1; then
    if ! git ls-remote --exit-code --tags origin "$DEPLOY_REF" >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠ Ref '$DEPLOY_REF' was not found as a remote branch/tag. Dispatch may still work for a SHA if GitHub can resolve it.${NC}"
    fi
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 Dispatching development deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Repo:       $REPO"
echo "Workflow:   $WORKFLOW"
echo "Ref:        $DEPLOY_REF"
echo "Run tests:  $RUN_TESTS"
echo "Tag suffix: ${TAG_SUFFIX:-<none>}"
echo ""

gh workflow run "$WORKFLOW" \
    --repo "$REPO" \
    --ref "$DEPLOY_REF" \
    -f run_tests="$RUN_TESTS" \
    -f image_tag_suffix="$TAG_SUFFIX"

echo -e "${GREEN}✓ Workflow dispatched${NC}"

if [ "$WATCH" != true ]; then
    echo "Monitor with: gh run list --workflow=$WORKFLOW --repo $REPO --limit 5"
    exit 0
fi

# Give GitHub a moment to create the run.
sleep 5

run_id=""
for _ in $(seq 1 12); do
    run_id=$(gh run list \
        --workflow "$WORKFLOW" \
        --repo "$REPO" \
        --limit 10 \
        --json databaseId,headBranch,status \
        -q ".[] | select(.headBranch == \"$DEPLOY_REF\") | .databaseId" \
        | head -n 1)
    if [ -n "$run_id" ]; then
        break
    fi
    sleep 5
done

if [ -z "$run_id" ]; then
    echo -e "${YELLOW}⚠ Could not find the new workflow run yet.${NC}"
    echo "Check: gh run list --workflow=$WORKFLOW --repo $REPO --limit 5"
    exit 0
fi

echo -e "${CYAN}Watching run: $run_id${NC}"
gh run watch "$run_id" --repo "$REPO"

conclusion=$(gh run view "$run_id" --repo "$REPO" --json conclusion -q '.conclusion')
if [ "$conclusion" != "success" ]; then
    echo -e "${RED}❌ Dev deployment workflow concluded: $conclusion${NC}" >&2
    echo "Logs: gh run view $run_id --repo $REPO --log-failed"
    exit 1
fi

echo -e "${GREEN}✅ Development deployment workflow succeeded${NC}"
echo "URL: https://app-governance-dev-001.azurewebsites.net"
