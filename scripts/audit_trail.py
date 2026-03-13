#!/usr/bin/env python3
"""Audit trail callback hook for the /wiggum ralph protocol.

Logs agent actions to both a local JSONL file and bd issue comments,
providing a queryable audit trail with zero external dependencies.

Python 3.11+ | stdlib only (no external dependencies).

Usage:
    # Log a completed task
    python scripts/audit_trail.py --agent "Python Programmer 🐍" \
        --task 1.2.4 --action completed

    # Log with bd issue ID and file changes
    python scripts/audit_trail.py --agent "Python Programmer 🐍" \
        --task 1.2.4 --action completed \
        --issue-id azure-governance-platform-3gv \
        --files-changed scripts/audit_trail.py scripts/hooks.sh

    # Log a failure with a message
    python scripts/audit_trail.py --agent "QA Expert 🐾" \
        --task 2.1.1 --action failed --message "mypy strict found 3 errors"

    # Show recent audit trail entries
    python scripts/audit_trail.py --list
    python scripts/audit_trail.py --list --limit 5
    python scripts/audit_trail.py --list --task 1.2.4
    python scripts/audit_trail.py --list --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TextIO

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Audit log lives alongside other data artifacts
AUDIT_LOG_PATH = Path("data/audit_trail.jsonl")

# Valid actions an agent can report
ValidAction = Literal["completed", "failed", "reviewed", "started", "blocked"]
VALID_ACTIONS: frozenset[str] = frozenset({"completed", "failed", "reviewed", "started", "blocked"})

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Immutable record of a single agent action.

    Frozen + slotted for memory efficiency and hashability — because
    audit records should be as immutable as the history they capture.
    """

    timestamp: str
    agent: str
    task_id: str
    action: str
    issue_id: str = ""
    message: str = ""
    files_changed: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize to a compact JSON string (one line per entry)."""
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, line: str) -> AuditEntry:
        """Deserialize from a JSON string."""
        data = json.loads(line)
        return cls(**data)

    def to_display(self) -> str:
        """Human-friendly one-line summary for --list output."""
        ts = self.timestamp[:19].replace("T", " ")
        status_icon = _action_icon(self.action)
        parts = [f"{status_icon} [{ts}] {self.agent} — {self.action} task {self.task_id}"]
        if self.issue_id:
            parts.append(f"  (bd: {self.issue_id})")
        if self.message:
            parts.append(f"  💬 {self.message}")
        if self.files_changed:
            files_str = ", ".join(self.files_changed[:5])
            if len(self.files_changed) > 5:
                files_str += f" (+{len(self.files_changed) - 5} more)"
            parts.append(f"  📁 {files_str}")
        return "\n".join(parts)

    def to_bd_comment(self) -> str:
        """Format as a bd comment string."""
        icon = _action_icon(self.action)
        lines = [
            f"{icon} AUDIT: {self.agent} — {self.action} task {self.task_id}",
            f"  Timestamp: {self.timestamp}",
        ]
        if self.message:
            lines.append(f"  Message: {self.message}")
        if self.files_changed:
            lines.append(f"  Files: {', '.join(self.files_changed)}")
        return "\n".join(lines)


def _action_icon(action: str) -> str:
    """Map action to a visual icon for quick scanning."""
    icons: dict[str, str] = {
        "completed": "✅",
        "failed": "❌",
        "reviewed": "👀",
        "started": "🚀",
        "blocked": "🚫",
    }
    return icons.get(action, "📝")


# ---------------------------------------------------------------------------
# Core Operations
# ---------------------------------------------------------------------------


def append_entry(entry: AuditEntry, *, log_path: Path = AUDIT_LOG_PATH) -> None:
    """Append an audit entry to the JSONL log file.

    Creates the parent directory if it doesn't exist — because we
    shouldn't fail on first run just because `data/` is missing.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry.to_json() + "\n")


def read_entries(
    *,
    log_path: Path = AUDIT_LOG_PATH,
    task_filter: str | None = None,
    agent_filter: str | None = None,
    action_filter: str | None = None,
    limit: int | None = None,
) -> list[AuditEntry]:
    """Read and optionally filter audit trail entries.

    Returns entries in reverse-chronological order (most recent first)
    because that's what humans actually want to see.
    """
    if not log_path.exists():
        return []

    entries: list[AuditEntry] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = AuditEntry.from_json(line)
            except (json.JSONDecodeError, TypeError, KeyError):
                # Skip malformed lines — resilience over strictness for logs
                continue

            if task_filter and entry.task_id != task_filter:
                continue
            if agent_filter and agent_filter.lower() not in entry.agent.lower():
                continue
            if action_filter and entry.action != action_filter:
                continue

            entries.append(entry)

    # Reverse for most-recent-first
    entries.reverse()

    if limit is not None:
        entries = entries[:limit]

    return entries


def post_to_bd(entry: AuditEntry) -> bool:
    """Post audit comment to a bd issue.

    Returns True if the comment was posted successfully, False otherwise.
    Silently degrades if bd is unavailable — audit logging should never
    block the actual work.
    """
    if not entry.issue_id:
        return False

    comment = entry.to_bd_comment()
    try:
        result = subprocess.run(
            [
                "bd",
                "comments",
                "add",
                entry.issue_id,
                comment,
                "--author",
                entry.agent,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        print(f"⚠️  Could not post to bd: {exc}", file=sys.stderr)
        return False


def detect_git_changes() -> list[str]:
    """Auto-detect changed files from git status.

    This is a convenience for agents that forget to pass --files-changed.
    Returns modified/added files from the working tree.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with mutually exclusive modes."""
    parser = argparse.ArgumentParser(
        prog="audit_trail",
        description="Audit trail callback hook for agent actions.",
        epilog=(
            "Examples:\n"
            "  %(prog)s --agent 'Python Programmer 🐍' --task 1.2.4 --action completed\n"
            "  %(prog)s --list --limit 10\n"
            "  %(prog)s --list --task 1.2.4 --json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # --- Mode: Log an action ---
    log_group = parser.add_argument_group("log an action")
    log_group.add_argument(
        "--agent",
        type=str,
        help="Agent name/identifier (e.g., 'Python Programmer 🐍')",
    )
    log_group.add_argument(
        "--task",
        type=str,
        help="Task ID from WIGGUM_ROADMAP.md (e.g., '1.2.4')",
    )
    log_group.add_argument(
        "--action",
        type=str,
        choices=sorted(VALID_ACTIONS),
        help="Action type to log",
    )
    log_group.add_argument(
        "--issue-id",
        type=str,
        default="",
        help="bd issue ID for posting comment (e.g., 'azure-governance-platform-3gv')",
    )
    log_group.add_argument(
        "--message",
        "-m",
        type=str,
        default="",
        help="Optional message with details",
    )
    log_group.add_argument(
        "--files-changed",
        nargs="*",
        default=None,
        help="Files changed (auto-detects from git if omitted)",
    )
    log_group.add_argument(
        "--no-bd",
        action="store_true",
        help="Skip posting to bd (local log only)",
    )

    # --- Mode: List entries ---
    list_group = parser.add_argument_group("list audit trail")
    list_group.add_argument(
        "--list",
        action="store_true",
        help="Show recent audit trail entries",
    )
    list_group.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max entries to show (default: 20)",
    )
    list_group.add_argument(
        "--filter-agent",
        type=str,
        default=None,
        help="Filter by agent name (substring match)",
    )
    list_group.add_argument(
        "--filter-action",
        type=str,
        choices=sorted(VALID_ACTIONS),
        default=None,
        help="Filter by action type",
    )
    list_group.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON array",
    )

    return parser


def cmd_log(
    args: argparse.Namespace,
    *,
    out: TextIO = sys.stdout,
) -> int:
    """Handle the 'log an action' mode."""
    # Validate required fields
    missing = []
    if not args.agent:
        missing.append("--agent")
    if not args.task:
        missing.append("--task")
    if not args.action:
        missing.append("--action")
    if missing:
        print(f"❌ Missing required arguments: {', '.join(missing)}", file=sys.stderr)
        return 1

    # Auto-detect file changes from git if not explicitly provided
    files_changed: list[str] = (
        args.files_changed if args.files_changed is not None else detect_git_changes()
    )

    entry = AuditEntry(
        timestamp=datetime.now(UTC).isoformat(),
        agent=args.agent,
        task_id=args.task,
        action=args.action,
        issue_id=args.issue_id,
        message=args.message,
        files_changed=files_changed,
    )

    # 1. Always write to local JSONL log
    append_entry(entry)
    print(f"✅ Logged: {entry.agent} — {entry.action} task {entry.task_id}", file=out)

    # 2. Post to bd if we have an issue ID and --no-bd wasn't set
    if entry.issue_id and not args.no_bd:
        if post_to_bd(entry):
            print(f"📝 Posted comment to bd issue {entry.issue_id}", file=out)
        else:
            print(f"⚠️  Failed to post to bd issue {entry.issue_id} (logged locally)", file=out)

    return 0


def cmd_list(
    args: argparse.Namespace,
    *,
    out: TextIO = sys.stdout,
) -> int:
    """Handle the 'list entries' mode."""
    entries = read_entries(
        task_filter=args.task,
        agent_filter=args.filter_agent,
        action_filter=args.filter_action,
        limit=args.limit,
    )

    if not entries:
        print("📋 No audit trail entries found.", file=out)
        return 0

    if args.json_output:
        print(json.dumps([asdict(e) for e in entries], indent=2), file=out)
    else:
        print(f"📋 Audit Trail ({len(entries)} entries):\n", file=out)
        for entry in entries:
            print(entry.to_display(), file=out)
            print("", file=out)  # blank line separator

    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point — dispatches to the appropriate subcommand."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        return cmd_list(args)

    # If any log args are provided, assume log mode
    if args.agent or args.task or args.action:
        return cmd_log(args)

    # No mode selected — show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
