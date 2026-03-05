#!/usr/bin/env python3
"""Roadmap synchronization script for Azure Governance Platform.

This script solves the /wiggum ralph inefficiency where the loop wastes time
re-verifying already-completed tasks. It provides three modes:

1. --verify (default): Read-only check of roadmap vs. filesystem state
2. --update: Mark tasks as complete and update metadata
3. --report: Generate completion statistics and discrepancies

Usage:
    python scripts/sync_roadmap.py --verify --json
    python scripts/sync_roadmap.py --update --task 6.2.1 --reason "validation passed"
    python scripts/sync_roadmap.py --report
"""

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
ROADMAP_PATH = Path("WIGGUM_ROADMAP.md")
BACKUP_DIR = Path(".roadmap_backups")


@dataclass
class TaskMetadata:
    """Metadata for a single task."""
    task_id: str
    phase: int
    title: str
    completed: bool
    files: List[str]
    agent: Optional[str]
    validation_command: Optional[str]
    line_number: int  # Line number in the roadmap file


@dataclass
class RoadmapMetadata:
    """Metadata from the YAML frontmatter."""
    project: str
    version: str
    created: str
    last_updated: str
    loop_status: str
    current_phase: int
    total_phases: int
    completed_tasks: int
    total_tasks: int
    stop_condition: str


@dataclass
class SyncResult:
    """Result of sync operation."""
    status: str  # "ok" or "discrepancies_found"
    metadata: Dict
    next_task: Optional[Dict]
    discrepancies: List[Dict]
    timestamp: str


class RoadmapParser:
    """Parse the WIGGUM_ROADMAP.md file."""

    # Regex patterns
    TASK_PATTERN = re.compile(r'^- \[(.?)\] \*\*Task ([\d.]+)\*\*: (.+)$')
    YAML_START = re.compile(r'^```yaml\s*$')
    YAML_END = re.compile(r'^```\s*$')
    FILES_PATTERN = re.compile(r'\*\*Files\*\*: `([^`]+)`')
    AGENT_PATTERN = re.compile(r'\*\*Agent\*\*: `([^`]+)`')
    VALIDATION_PATTERN = re.compile(r'\*\*Validation\*\*: `([^`]+)`')

    def __init__(self, roadmap_path: Path):
        self.roadmap_path = roadmap_path
        self.lines = []
        self.metadata = None
        self.tasks = []

    def parse(self) -> Tuple[RoadmapMetadata, List[TaskMetadata]]:
        """Parse roadmap file and return metadata + tasks."""
        if not self.roadmap_path.exists():
            raise FileNotFoundError(f"Roadmap not found: {self.roadmap_path}")

        with open(self.roadmap_path, 'r', encoding='utf-8') as f:
            self.lines = f.readlines()

        self.metadata = self._parse_metadata()
        self.tasks = self._parse_tasks()

        return self.metadata, self.tasks

    def _parse_metadata(self) -> RoadmapMetadata:
        """Extract YAML metadata from roadmap."""
        in_yaml = False
        yaml_lines = []

        for line in self.lines:
            if self.YAML_START.match(line):
                in_yaml = True
                continue
            if in_yaml and self.YAML_END.match(line):
                break
            if in_yaml:
                yaml_lines.append(line.strip())

        # Parse YAML manually (avoid dependency on pyyaml)
        metadata_dict = {}
        for line in yaml_lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip().strip('"')
                metadata_dict[key] = value

        # Convert to RoadmapMetadata
        return RoadmapMetadata(
            project=metadata_dict.get('project', 'unknown'),
            version=metadata_dict.get('version', '0.0.0'),
            created=metadata_dict.get('created', ''),
            last_updated=metadata_dict.get('last_updated', ''),
            loop_status=metadata_dict.get('loop_status', 'UNKNOWN'),
            current_phase=int(metadata_dict.get('current_phase', 0)),
            total_phases=int(metadata_dict.get('total_phases', 0)),
            completed_tasks=int(metadata_dict.get('completed_tasks', 0)),
            total_tasks=int(metadata_dict.get('total_tasks', 0)),
            stop_condition=metadata_dict.get('stop_condition', '')
        )

    def _parse_tasks(self) -> List[TaskMetadata]:
        """Extract all tasks from roadmap."""
        tasks = []
        current_task = None
        task_content_lines = []

        for line_num, line in enumerate(self.lines, start=1):
            task_match = self.TASK_PATTERN.match(line)

            if task_match:
                # Save previous task if exists
                if current_task:
                    self._finalize_task(current_task, task_content_lines)
                    tasks.append(current_task)

                # Start new task
                completed = task_match.group(1).lower() == 'x'
                task_id = task_match.group(2)
                title = task_match.group(3)

                # Extract phase from task_id (e.g., "6.2.1" -> phase 6)
                phase = int(task_id.split('.')[0])

                current_task = TaskMetadata(
                    task_id=task_id,
                    phase=phase,
                    title=title,
                    completed=completed,
                    files=[],
                    agent=None,
                    validation_command=None,
                    line_number=line_num
                )
                task_content_lines = []
            elif current_task:
                # Accumulate lines for current task metadata
                task_content_lines.append(line)

        # Don't forget the last task
        if current_task:
            self._finalize_task(current_task, task_content_lines)
            tasks.append(current_task)

        return tasks

    def _finalize_task(self, task: TaskMetadata, content_lines: List[str]):
        """Extract file paths, agent, and validation from task content."""
        content = ''.join(content_lines)

        # Extract files - find all backtick-delimited paths in the Files line
        # Look for the line containing "**Files**:" and extract all `path` patterns
        files_line_match = re.search(r'\*\*Files\*\*:([^\n]+)', content)
        if files_line_match:
            files_line = files_line_match.group(1)
            # Find all backtick-delimited paths
            task.files = re.findall(r'`([^`]+)`', files_line)

        # Extract agent
        agent_match = self.AGENT_PATTERN.search(content)
        if agent_match:
            task.agent = agent_match.group(1).split(',')[0].strip()

        # Extract validation command
        validation_match = self.VALIDATION_PATTERN.search(content)
        if validation_match:
            task.validation_command = validation_match.group(1)


class RoadmapValidator:
    """Validate roadmap state against filesystem."""

    def __init__(self, tasks: List[TaskMetadata]):
        self.tasks = tasks
        self.discrepancies = []

    def validate(self) -> List[Dict]:
        """Check each task's files and validation."""
        self.discrepancies = []

        for task in self.tasks:
            if task.completed:
                # Task marked done - verify files exist
                self._check_completed_task(task)
            else:
                # Task not done - check if it should be marked complete
                self._check_incomplete_task(task)

        return self.discrepancies

    def _check_completed_task(self, task: TaskMetadata):
        """Verify completed task has required files."""
        for file_path in task.files:
            path = Path(file_path)
            if not path.exists():
                self.discrepancies.append({
                    "task": task.task_id,
                    "issue": f"marked [x] but file missing: {file_path}",
                    "severity": "high"
                })
            elif path.stat().st_size == 0:
                self.discrepancies.append({
                    "task": task.task_id,
                    "issue": f"marked [x] but file empty: {file_path}",
                    "severity": "medium"
                })

    def _check_incomplete_task(self, task: TaskMetadata):
        """Check if incomplete task actually has files and might be done."""
        if not task.files:
            return  # Can't check without file list

        all_files_exist = all(Path(f).exists() for f in task.files)
        all_files_have_content = all(
            Path(f).stat().st_size > 100 for f in task.files if Path(f).exists()
        )

        if all_files_exist and all_files_have_content:
            # Run validation command if available
            if task.validation_command:
                if self._run_validation(task.validation_command):
                    self.discrepancies.append({
                        "task": task.task_id,
                        "issue": "marked [ ] but files exist and validation passes",
                        "severity": "low",
                        "suggestion": "consider marking as complete"
                    })

    def _run_validation(self, command: str, timeout: int = 10) -> bool:
        """Run validation command and return True if it passes."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=timeout,
                text=True
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning(f"Validation timed out: {command}")
            return False
        except Exception as e:
            logger.warning(f"Validation failed: {command} - {e}")
            return False


class RoadmapUpdater:
    """Update roadmap file with new task statuses."""

    def __init__(self, roadmap_path: Path):
        self.roadmap_path = roadmap_path

    def backup(self):
        """Create timestamped backup of roadmap."""
        BACKUP_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"WIGGUM_ROADMAP_{timestamp}.md"
        shutil.copy2(self.roadmap_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        return backup_path

    def mark_task_complete(self, task_id: str) -> bool:
        """Mark a specific task as complete [x]."""
        self.backup()

        with open(self.roadmap_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        modified = False
        for i, line in enumerate(lines):
            if f'**Task {task_id}**' in line and '- [ ]' in line:
                lines[i] = line.replace('- [ ]', '- [x]')
                modified = True
                logger.info(f"Marked task {task_id} as complete")
                break

        if modified:
            with open(self.roadmap_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            return True
        else:
            logger.warning(f"Task {task_id} not found or already complete")
            return False

    def update_metadata(self, completed_count: int, current_phase: int):
        """Update YAML metadata block."""
        with open(self.roadmap_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        in_yaml = False
        yaml_start = -1
        yaml_end = -1

        # Find YAML block boundaries
        for i, line in enumerate(lines):
            if re.match(r'^```yaml\s*$', line):
                in_yaml = True
                yaml_start = i
            elif in_yaml and re.match(r'^```\s*$', line):
                yaml_end = i
                break

        if yaml_start == -1 or yaml_end == -1:
            logger.error("Could not find YAML metadata block")
            return False

        # Update metadata lines
        for i in range(yaml_start + 1, yaml_end):
            if lines[i].startswith('last_updated:'):
                lines[i] = f"last_updated: {datetime.now().strftime('%Y-%m-%d')}\n"
            elif lines[i].startswith('completed_tasks:'):
                lines[i] = f"completed_tasks: {completed_count}\n"
            elif lines[i].startswith('current_phase:'):
                lines[i] = f"current_phase: {current_phase}\n"

        with open(self.roadmap_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        logger.info(f"Updated metadata: {completed_count} tasks completed, phase {current_phase}")
        return True


class RoadmapSync:
    """Main orchestrator for roadmap synchronization."""

    def __init__(self):
        self.parser = RoadmapParser(ROADMAP_PATH)
        self.metadata = None
        self.tasks = []

    def load(self):
        """Load and parse roadmap."""
        self.metadata, self.tasks = self.parser.parse()
        logger.info(f"Loaded roadmap: {len(self.tasks)} tasks, {self.metadata.completed_tasks} complete")

    def verify(self) -> SyncResult:
        """Verify mode: check roadmap vs filesystem."""
        self.load()

        validator = RoadmapValidator(self.tasks)
        discrepancies = validator.validate()

        # Find next incomplete task
        next_task = self._find_next_task()

        # Calculate actual completion from roadmap
        actual_completed = sum(1 for t in self.tasks if t.completed)
        completion_pct = (actual_completed / len(self.tasks) * 100) if self.tasks else 0

        status = "ok" if not discrepancies else "discrepancies_found"

        return SyncResult(
            status=status,
            metadata={
                "completed_tasks": actual_completed,
                "total_tasks": len(self.tasks),
                "current_phase": self.metadata.current_phase,
                "completion_percentage": round(completion_pct, 1)
            },
            next_task=next_task,
            discrepancies=discrepancies,
            timestamp=datetime.now().isoformat()
        )

    def update(self, task_id: str, reason: str = "") -> bool:
        """Update mode: mark task as complete."""
        self.load()

        # Find the task
        task = next((t for t in self.tasks if t.task_id == task_id), None)
        if not task:
            logger.error(f"Task {task_id} not found")
            return False

        if task.completed:
            logger.info(f"Task {task_id} already marked complete")
            return True

        # Validate before marking complete
        if task.validation_command:
            validator = RoadmapValidator([task])
            if not validator._run_validation(task.validation_command):
                logger.error(f"Validation failed for task {task_id}")
                logger.error(f"Command: {task.validation_command}")
                return False

        # Mark complete
        updater = RoadmapUpdater(ROADMAP_PATH)
        success = updater.mark_task_complete(task_id)

        if success:
            # Recalculate metadata
            self.load()  # Reload to get updated counts
            actual_completed = sum(1 for t in self.tasks if t.completed)
            current_phase = max((t.phase for t in self.tasks if not t.completed), default=self.metadata.total_phases)

            updater.update_metadata(actual_completed, current_phase)

            logger.info(f"✅ Task {task_id} marked complete. Reason: {reason or 'N/A'}")

        return success

    def report(self) -> Dict:
        """Report mode: generate statistics."""
        self.load()

        validator = RoadmapValidator(self.tasks)
        discrepancies = validator.validate()

        # Calculate stats by phase
        phase_stats = {}
        for task in self.tasks:
            if task.phase not in phase_stats:
                phase_stats[task.phase] = {"total": 0, "completed": 0}
            phase_stats[task.phase]["total"] += 1
            if task.completed:
                phase_stats[task.phase]["completed"] += 1

        actual_completed = sum(1 for t in self.tasks if t.completed)
        completion_pct = (actual_completed / len(self.tasks) * 100) if self.tasks else 0

        return {
            "summary": {
                "total_tasks": len(self.tasks),
                "completed_tasks": actual_completed,
                "remaining_tasks": len(self.tasks) - actual_completed,
                "completion_percentage": round(completion_pct, 1),
                "current_phase": self.metadata.current_phase,
                "total_phases": self.metadata.total_phases
            },
            "phase_breakdown": phase_stats,
            "discrepancies": discrepancies,
            "next_task": self._find_next_task(),
            "timestamp": datetime.now().isoformat()
        }

    def _find_next_task(self) -> Optional[Dict]:
        """Find the next incomplete task."""
        for task in self.tasks:
            if not task.completed:
                # Check if files exist to determine readiness
                ready = all(Path(f).exists() for f in task.files) if task.files else False

                return {
                    "id": task.task_id,
                    "phase": task.phase,
                    "title": task.title[:80] + "..." if len(task.title) > 80 else task.title,
                    "files": task.files,
                    "validation_command": task.validation_command,
                    "ready_to_execute": not ready  # Ready if files DON'T exist (needs creation)
                }
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Roadmap synchronization for /wiggum ralph workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify roadmap state (default mode)'
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='Update roadmap (mark task complete)'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate completion report'
    )
    parser.add_argument(
        '--task',
        type=str,
        help='Task ID to update (e.g., "6.2.1")'
    )
    parser.add_argument(
        '--reason',
        type=str,
        default='',
        help='Reason for marking task complete'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON (for programmatic use)'
    )

    args = parser.parse_args()

    # Default to verify mode
    if not (args.verify or args.update or args.report):
        args.verify = True

    sync = RoadmapSync()

    try:
        if args.update:
            if not args.task:
                logger.error("--task required for --update mode")
                sys.exit(1)

            success = sync.update(args.task, args.reason)
            sys.exit(0 if success else 1)

        elif args.report:
            report = sync.report()

            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print("\n📊 ROADMAP SYNC REPORT")
                print("=" * 60)
                print(f"Total Tasks: {report['summary']['total_tasks']}")
                print(f"Completed: {report['summary']['completed_tasks']}")
                print(f"Remaining: {report['summary']['remaining_tasks']}")
                print(f"Progress: {report['summary']['completion_percentage']}%")
                print(f"Current Phase: {report['summary']['current_phase']} / {report['summary']['total_phases']}")

                if report['next_task']:
                    print(f"\n📋 Next Task: {report['next_task']['id']}")
                    print(f"   {report['next_task']['title']}")

                if report['discrepancies']:
                    print(f"\n⚠️  {len(report['discrepancies'])} Discrepancies Found:")
                    for d in report['discrepancies'][:5]:  # Show first 5
                        print(f"   [{d['severity'].upper()}] Task {d['task']}: {d['issue']}")

        else:  # verify mode
            result = sync.verify()

            if args.json:
                output = asdict(result)
                print(json.dumps(output, indent=2))
            else:
                print("\n✅ ROADMAP VERIFICATION")
                print("=" * 60)
                print(f"Status: {result.status}")
                print(f"Completed: {result.metadata['completed_tasks']} / {result.metadata['total_tasks']}")
                print(f"Progress: {result.metadata['completion_percentage']}%")

                if result.next_task:
                    print(f"\n📋 Next Task: {result.next_task['id']}")
                    print(f"   {result.next_task['title']}")
                    print(f"   Ready: {'Yes' if result.next_task['ready_to_execute'] else 'No'}")

                if result.discrepancies:
                    print(f"\n⚠️  {len(result.discrepancies)} Discrepancies:")
                    for d in result.discrepancies[:3]:
                        print(f"   [{d['severity'].upper()}] Task {d['task']}: {d['issue']}")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
