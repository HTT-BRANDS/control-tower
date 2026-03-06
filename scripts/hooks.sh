#!/usr/bin/env bash
# hooks.sh — Shell wrapper for audit trail integration.
#
# Source this file in agent scripts to auto-log actions to bd issues.
#
# Usage:
#   source scripts/hooks.sh
#
#   # Then call helper functions:
#   audit_started  "Python Programmer 🐍" 1.2.4 azure-governance-platform-3gv
#   audit_completed "Python Programmer 🐍" 1.2.4 azure-governance-platform-3gv "All tests pass"
#   audit_failed   "Python Programmer 🐍" 1.2.4 azure-governance-platform-3gv "mypy found 3 errors"
#   audit_reviewed  "Code Reviewer 🛡️" 1.2.4 azure-governance-platform-3gv "LGTM"
#   audit_list      # Show recent entries
#   audit_list_task 1.2.4  # Show entries for a specific task

set -euo pipefail

# Resolve the project root (where this script lives is scripts/)
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$HOOKS_DIR")"
AUDIT_SCRIPT="${PROJECT_ROOT}/scripts/audit_trail.py"

# Verify the audit trail script exists
if [[ ! -f "$AUDIT_SCRIPT" ]]; then
    echo "❌ audit_trail.py not found at $AUDIT_SCRIPT" >&2
    echo "   Are you running from the project root?" >&2
    return 1 2>/dev/null || exit 1
fi

# ---------------------------------------------------------------------------
# Helper: run audit_trail.py with proper Python
# ---------------------------------------------------------------------------
_audit_run() {
    python3 "$AUDIT_SCRIPT" "$@"
}

# ---------------------------------------------------------------------------
# Public API: One function per action type
# ---------------------------------------------------------------------------

# audit_started <agent> <task_id> [issue_id] [message]
audit_started() {
    local agent="${1:?Usage: audit_started <agent> <task_id> [issue_id] [message]}"
    local task="${2:?Usage: audit_started <agent> <task_id> [issue_id] [message]}"
    local issue_id="${3:-}"
    local message="${4:-}"

    local args=(--agent "$agent" --task "$task" --action started)
    [[ -n "$issue_id" ]] && args+=(--issue-id "$issue_id")
    [[ -n "$message" ]] && args+=(-m "$message")

    _audit_run "${args[@]}"
}

# audit_completed <agent> <task_id> [issue_id] [message] [files...]
audit_completed() {
    local agent="${1:?Usage: audit_completed <agent> <task_id> [issue_id] [message] [files...]}"
    local task="${2:?Usage: audit_completed <agent> <task_id> [issue_id] [message] [files...]}"
    local issue_id="${3:-}"
    local message="${4:-}"
    shift 4 2>/dev/null || true
    local files=("$@")

    local args=(--agent "$agent" --task "$task" --action completed)
    [[ -n "$issue_id" ]] && args+=(--issue-id "$issue_id")
    [[ -n "$message" ]] && args+=(-m "$message")
    [[ ${#files[@]} -gt 0 ]] && args+=(--files-changed "${files[@]}")

    _audit_run "${args[@]}"
}

# audit_failed <agent> <task_id> [issue_id] [message]
audit_failed() {
    local agent="${1:?Usage: audit_failed <agent> <task_id> [issue_id] [message]}"
    local task="${2:?Usage: audit_failed <agent> <task_id> [issue_id] [message]}"
    local issue_id="${3:-}"
    local message="${4:-}"

    local args=(--agent "$agent" --task "$task" --action failed)
    [[ -n "$issue_id" ]] && args+=(--issue-id "$issue_id")
    [[ -n "$message" ]] && args+=(-m "$message")

    _audit_run "${args[@]}"
}

# audit_reviewed <agent> <task_id> [issue_id] [message]
audit_reviewed() {
    local agent="${1:?Usage: audit_reviewed <agent> <task_id> [issue_id] [message]}"
    local task="${2:?Usage: audit_reviewed <agent> <task_id> [issue_id] [message]}"
    local issue_id="${3:-}"
    local message="${4:-}"

    local args=(--agent "$agent" --task "$task" --action reviewed)
    [[ -n "$issue_id" ]] && args+=(--issue-id "$issue_id")
    [[ -n "$message" ]] && args+=(-m "$message")

    _audit_run "${args[@]}"
}

# audit_list [limit]
audit_list() {
    local limit="${1:-20}"
    _audit_run --list --limit "$limit"
}

# audit_list_task <task_id> [limit]
audit_list_task() {
    local task="${1:?Usage: audit_list_task <task_id> [limit]}"
    local limit="${2:-20}"
    _audit_run --list --task "$task" --limit "$limit"
}

# ---------------------------------------------------------------------------
# Auto-hook: wrap bd close to automatically log completion
# ---------------------------------------------------------------------------
# If BD_AUDIT_AGENT is set, auto-log when bd close is called.
if [[ -n "${BD_AUDIT_AGENT:-}" ]]; then
    bd_close_with_audit() {
        local issue_id="${1:?Usage: bd_close_with_audit <issue_id> [task_id]}"
        local task_id="${2:-unknown}"

        # Log the completion
        audit_completed "$BD_AUDIT_AGENT" "$task_id" "$issue_id" "Issue closed via bd"

        # Actually close the issue
        bd close "$issue_id"
    }
    echo "🔗 Audit hooks loaded for agent: $BD_AUDIT_AGENT"
fi

echo "✅ Audit trail hooks loaded. Functions available:"
echo "   audit_started, audit_completed, audit_failed, audit_reviewed"
echo "   audit_list, audit_list_task"
