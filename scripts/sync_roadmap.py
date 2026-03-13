#!/usr/bin/env python3
"""Roadmap synchronization script for the /wiggum ralph protocol.

Parses WIGGUM_ROADMAP.md — the single source of truth for task tracking —
and provides verification, update, and status reporting capabilities.

Python 3.11+ | stdlib only (no external dependencies).

Usage:
    python scripts/sync_roadmap.py --verify
    python scripts/sync_roadmap.py --verify --json
    python scripts/sync_roadmap.py --update --task 1.2.3
    python scripts/sync_roadmap.py --status
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TextIO

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROADMAP_PATH = Path("WIGGUM_ROADMAP.md")

# A task line looks like:
#   - [x] 1.1.1 Create Solutions Architect JSON agent (Agent Creator 🏗️)
#   - [ ] 2.1.3 MCP trust boundary audit (Security Auditor 🛡️)
#
# Capture groups:
#   1: checkbox content  ("x" or " ")
#   2: task ID           ("1.1.1")
#   3: description       ("Create Solutions Architect JSON agent")
#   4: owner agent       ("Agent Creator 🏗️")
TASK_RE = re.compile(
    r"^- \[([ xX])\]\s+"  # checkbox
    r"(\d+\.\d+\.\d+)\s+"  # task ID  (X.Y.Z)
    r"(.+?)\s*"  # description (lazy)
    r"\(([^)]+)\)\s*$"  # (owner agent)
)

# Progress Summary table row, e.g.:
# | Phase 1: Foundation | 7 | 4 | 3 | 🔄 In Progress |
TABLE_ROW_RE = re.compile(
    r"^\|\s*Phase\s+(\d+)\b[^|]*\|"  # phase number
    r"\s*(\d+)\s*\|"  # total
    r"\s*(\d+)\s*\|"  # completed
    r"\s*(\d+)\s*\|"  # remaining
    r"\s*([^|]+?)\s*\|$"  # status emoji/text
)

# TOTAL row
TABLE_TOTAL_RE = re.compile(
    r"^\|\s*\*\*TOTAL\*\*\s*\|"
    r"\s*\*\*(\d+)\*\*\s*\|"
    r"\s*\*\*(\d+)\*\*\s*\|"
    r"\s*\*\*(\d+)\*\*\s*\|"
    r"\s*\*\*([^|]+?)\*\*\s*\|$"
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Task:
    """A single parsed task from the roadmap."""

    task_id: str
    description: str
    owner: str
    completed: bool
    line_number: int  # 1-based

    @property
    def phase(self) -> int:
        """Extract phase number from task ID (e.g. '2.1.3' -> 2)."""
        return int(self.task_id.split(".")[0])


@dataclass
class ValidationIssue:
    """A single validation issue found during --verify."""

    line_number: int
    line_content: str
    message: str


@dataclass
class PhaseStats:
    """Per-phase completion statistics."""

    phase: int
    total: int = 0
    completed: int = 0

    @property
    def remaining(self) -> int:
        return self.total - self.completed

    @property
    def status_emoji(self) -> str:
        if self.completed == self.total:
            return "✅ Complete"
        if self.completed > 0:
            return "🔄 In Progress"
        return "⬜ Not Started"


@dataclass
class VerifyResult:
    """Result of --verify operation."""

    valid: bool
    total_tasks: int
    completed_tasks: int
    remaining_tasks: int
    phases: dict[int, dict[str, int | str]] = field(default_factory=dict)
    issues: list[dict[str, str | int]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_tasks(lines: list[str]) -> list[Task]:
    """Parse all task lines from the roadmap content.

    Args:
        lines: Raw lines from WIGGUM_ROADMAP.md.

    Returns:
        List of parsed Task objects.
    """
    tasks: list[Task] = []
    for line_num, line in enumerate(lines, start=1):
        m = TASK_RE.match(line.rstrip("\n"))
        if m:
            checkbox, task_id, description, owner = m.groups()
            tasks.append(
                Task(
                    task_id=task_id,
                    description=description.strip(),
                    owner=owner.strip(),
                    completed=checkbox.lower() == "x",
                    line_number=line_num,
                )
            )
    return tasks


def compute_phase_stats(tasks: list[Task]) -> dict[int, PhaseStats]:
    """Aggregate tasks into per-phase statistics."""
    stats: dict[int, PhaseStats] = {}
    for t in tasks:
        if t.phase not in stats:
            stats[t.phase] = PhaseStats(phase=t.phase)
        stats[t.phase].total += 1
        if t.completed:
            stats[t.phase].completed += 1
    return dict(sorted(stats.items()))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_verify(
    roadmap: Path,
    as_json: bool,
    out: TextIO = sys.stdout,
) -> int:
    """Verify roadmap format. Exit 0 if valid, 1 if invalid."""
    if not roadmap.exists():
        _emit_error(f"Roadmap file not found: {roadmap}", as_json, out)
        return 1

    lines = roadmap.read_text(encoding="utf-8").splitlines(keepends=True)
    tasks = parse_tasks(lines)
    issues: list[ValidationIssue] = []

    if not tasks:
        issues.append(
            ValidationIssue(
                line_number=0,
                line_content="",
                message="No tasks found in roadmap. Expected lines matching "
                "'- [ ] X.Y.Z Description (Owner)'.",
            )
        )

    # Check for duplicate task IDs
    seen_ids: dict[str, int] = {}
    for t in tasks:
        if t.task_id in seen_ids:
            issues.append(
                ValidationIssue(
                    line_number=t.line_number,
                    line_content=lines[t.line_number - 1].rstrip("\n"),
                    message=f"Duplicate task ID '{t.task_id}' "
                    f"(first seen at line {seen_ids[t.task_id]}).",
                )
            )
        else:
            seen_ids[t.task_id] = t.line_number

    # Scan for lines that look like tasks but don't fully match
    # (e.g. missing owner in parens, malformed checkbox)
    _partial_task_re = re.compile(r"^- \[.?\]\s+\d+\.\d+\.\d+\s")
    for line_num, line in enumerate(lines, start=1):
        stripped = line.rstrip("\n")
        if _partial_task_re.match(stripped) and not TASK_RE.match(stripped):
            issues.append(
                ValidationIssue(
                    line_number=line_num,
                    line_content=stripped,
                    message="Line looks like a task but doesn't match expected format. "
                    "Expected: '- [ ] X.Y.Z Description (Owner Agent)'",
                )
            )

    phase_stats = compute_phase_stats(tasks)
    total = len(tasks)
    completed = sum(1 for t in tasks if t.completed)
    valid = len(issues) == 0

    result = VerifyResult(
        valid=valid,
        total_tasks=total,
        completed_tasks=completed,
        remaining_tasks=total - completed,
        phases={
            p: {
                "total": s.total,
                "completed": s.completed,
                "remaining": s.remaining,
                "status": s.status_emoji,
            }
            for p, s in phase_stats.items()
        },
        issues=[
            {
                "line": i.line_number,
                "content": i.line_content,
                "message": i.message,
            }
            for i in issues
        ],
    )

    if as_json:
        out.write(json.dumps(asdict(result), indent=2, ensure_ascii=False) + "\n")
    else:
        if valid:
            out.write(
                f"✅ Roadmap is valid. {total} tasks found "
                f"({completed} completed, {total - completed} remaining).\n"
            )
        else:
            out.write(f"❌ Roadmap has {len(issues)} issue(s):\n")
            for i in issues:
                out.write(f"  Line {i.line_number}: {i.message}\n")
                if i.line_content:
                    out.write(f"    > {i.line_content}\n")
        # Phase breakdown
        out.write("\nPhase breakdown:\n")
        for p, s in phase_stats.items():
            out.write(f"  Phase {p}: {s.completed}/{s.total} ({s.status_emoji})\n")

    return 0 if valid else 1


def cmd_update(roadmap: Path, task_id: str) -> int:
    """Mark task X.Y.Z as complete and update the Progress Summary table.

    Returns 0 on success, 1 on failure.
    """
    if not roadmap.exists():
        print(f"❌ Roadmap file not found: {roadmap}", file=sys.stderr)
        return 1

    text = roadmap.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # --- Step 1: Find and toggle the task checkbox -------------------------
    task_found = False
    already_done = False

    for idx, line in enumerate(lines):
        m = TASK_RE.match(line.rstrip("\n"))
        if m and m.group(2) == task_id:
            task_found = True
            if m.group(1).lower() == "x":
                already_done = True
                print(f"ℹ️  Task {task_id} is already marked complete.")
                break
            # Replace '- [ ]' with '- [x]'
            lines[idx] = line.replace("- [ ]", "- [x]", 1)
            print(f"✅ Marked task {task_id} as complete.")
            break

    if not task_found:
        print(f"❌ Task {task_id} not found in {roadmap}.", file=sys.stderr)
        return 1

    if already_done:
        return 0

    # --- Step 2: Reparse to get fresh stats --------------------------------
    tasks = parse_tasks(lines)
    phase_stats = compute_phase_stats(tasks)
    total_all = len(tasks)
    completed_all = sum(1 for t in tasks if t.completed)

    # --- Step 3: Update the Progress Summary table -------------------------
    for idx, line in enumerate(lines):
        stripped = line.rstrip("\n")

        # Phase rows
        row_m = TABLE_ROW_RE.match(stripped)
        if row_m:
            phase_num = int(row_m.group(1))
            if phase_num in phase_stats:
                s = phase_stats[phase_num]
                # Reconstruct the row, preserving the phase label
                # Extract full phase label from original line
                label_end = stripped.index("|", 1)  # second pipe
                phase_label = stripped[1:label_end].strip()
                lines[idx] = (
                    f"| {phase_label} | {s.total} | {s.completed} "
                    f"| {s.remaining} | {s.status_emoji} |\n"
                )
            continue

        # TOTAL row
        total_m = TABLE_TOTAL_RE.match(stripped)
        if total_m:
            remaining_all = total_all - completed_all
            # Determine overall status
            if completed_all == total_all:
                overall_status = "✅ Complete"
            elif completed_all > 0:
                overall_status = "🔄 In Progress"
            else:
                overall_status = "⬜ Not Started"
            lines[idx] = (
                f"| **TOTAL** | **{total_all}** | **{completed_all}** "
                f"| **{remaining_all}** | **{overall_status}** |\n"
            )

    # --- Step 4: Write back ------------------------------------------------
    roadmap.write_text("".join(lines), encoding="utf-8")
    print(f"📊 Progress Summary table updated ({completed_all}/{total_all} tasks complete).")
    return 0


def cmd_status(roadmap: Path, as_json: bool, out: TextIO = sys.stdout) -> int:
    """Print a summary of completed vs remaining tasks."""
    if not roadmap.exists():
        _emit_error(f"Roadmap file not found: {roadmap}", as_json, out)
        return 1

    lines = roadmap.read_text(encoding="utf-8").splitlines(keepends=True)
    tasks = parse_tasks(lines)
    phase_stats = compute_phase_stats(tasks)

    total = len(tasks)
    completed = sum(1 for t in tasks if t.completed)
    remaining = total - completed
    pct = (completed / total * 100) if total else 0.0

    if as_json:
        data = {
            "total_tasks": total,
            "completed_tasks": completed,
            "remaining_tasks": remaining,
            "completion_percentage": round(pct, 1),
            "phases": {
                str(p): {
                    "total": s.total,
                    "completed": s.completed,
                    "remaining": s.remaining,
                    "status": s.status_emoji,
                }
                for p, s in phase_stats.items()
            },
            "remaining_task_ids": [t.task_id for t in tasks if not t.completed],
        }
        out.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    else:
        out.write("\n📊 WIGGUM ROADMAP STATUS\n")
        out.write("=" * 55 + "\n")
        out.write(f"Total tasks:   {total}\n")
        out.write(f"Completed:     {completed}\n")
        out.write(f"Remaining:     {remaining}\n")
        out.write(f"Progress:      {pct:.1f}%\n")
        out.write("\n")

        # Phase breakdown
        out.write(f"{'Phase':<10} {'Done':>5} {'Total':>6} {'Status'}\n")
        out.write("-" * 40 + "\n")
        for p, s in phase_stats.items():
            out.write(f"Phase {p:<4} {s.completed:>5}/{s.total:<5} {s.status_emoji}\n")

        # Remaining tasks
        remaining_tasks = [t for t in tasks if not t.completed]
        if remaining_tasks:
            out.write("\n📋 Next up:\n")
            for t in remaining_tasks[:5]:
                out.write(f"  [ ] {t.task_id} {t.description} ({t.owner})\n")
            if len(remaining_tasks) > 5:
                out.write(f"  ... and {len(remaining_tasks) - 5} more\n")

    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit_error(
    message: str,
    as_json: bool,
    out: TextIO = sys.stdout,
) -> None:
    """Emit an error in plain text or JSON format."""
    if as_json:
        out.write(json.dumps({"valid": False, "error": message}, indent=2) + "\n")
    else:
        print(f"❌ {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser with full help text."""
    parser = argparse.ArgumentParser(
        prog="sync_roadmap",
        description=(
            "Synchronize and manage the WIGGUM_ROADMAP.md task roadmap.\n\n"
            "This script is the backbone of the /wiggum ralph protocol,\n"
            "providing verification, task updates, and status reporting."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --verify              Validate roadmap format\n"
            "  %(prog)s --verify --json        Validate and output JSON\n"
            "  %(prog)s --update --task 1.2.3  Mark task 1.2.3 done\n"
            "  %(prog)s --status               Show completion summary\n"
            "  %(prog)s --status --json        Summary as JSON\n"
        ),
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--verify",
        action="store_true",
        help="Parse and validate roadmap format. Exit 0 if valid, 1 if not.",
    )
    mode.add_argument(
        "--update",
        action="store_true",
        help="Mark a task as complete (requires --task).",
    )
    mode.add_argument(
        "--status",
        action="store_true",
        help="Print a summary of completed vs remaining tasks.",
    )

    parser.add_argument(
        "--task",
        type=str,
        metavar="X.Y.Z",
        help="Task ID to update (e.g. 1.2.3). Required with --update.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output results as JSON to stdout.",
    )
    parser.add_argument(
        "--roadmap",
        type=Path,
        default=ROADMAP_PATH,
        help=f"Path to roadmap file (default: {ROADMAP_PATH}).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Default to --verify when no mode specified
    if not (args.verify or args.update or args.status):
        args.verify = True

    if args.update:
        if not args.task:
            parser.error("--update requires --task X.Y.Z")
        # Validate task ID format
        if not re.fullmatch(r"\d+\.\d+\.\d+", args.task):
            parser.error(f"Invalid task ID '{args.task}'. Expected format: X.Y.Z (e.g. 1.2.3)")
        return cmd_update(args.roadmap, args.task)

    if args.status:
        return cmd_status(args.roadmap, args.as_json)

    # --verify (default)
    return cmd_verify(args.roadmap, args.as_json)


if __name__ == "__main__":
    sys.exit(main())
