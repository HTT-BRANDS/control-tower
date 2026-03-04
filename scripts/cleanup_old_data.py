#!/usr/bin/env python3
"""Data retention cleanup script (P6: 6ty).

Run manually or via cron to purge stale time-series data::

    python scripts/cleanup_old_data.py
"""

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.retention_service import run_retention_cleanup  # noqa: E402


def main() -> None:
    results = run_retention_cleanup()
    print("Retention cleanup results:")
    for table, count in results.items():
        print(f"  {table}: {count} records deleted")
    print(f"Total: {sum(results.values())} records deleted")


if __name__ == "__main__":
    main()
