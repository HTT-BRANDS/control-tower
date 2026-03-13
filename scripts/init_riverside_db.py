#!/usr/bin/env python3
"""Initialize Riverside database tables.

This script creates all Riverside-related database tables using SQLAlchemy's
create_all() method. It verifies table creation by querying sqlite_master.

Usage:
    python scripts/init_riverside_db.py
"""

import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text  # noqa: E402

from app.core.database import engine, init_db  # noqa: E402

# Riverside tables to verify
RIVERSIDE_TABLES = [
    "riverside_compliance",
    "riverside_mfa",
    "riverside_requirements",
    "riverside_device_compliance",
    "riverside_threat_data",
]


def get_existing_tables() -> set[str]:
    """Query sqlite_master to get existing tables."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        return {row[0] for row in result}


def verify_riverside_tables() -> dict[str, bool]:
    """Verify all Riverside tables exist in the database."""
    existing = get_existing_tables()
    return {table: table in existing for table in RIVERSIDE_TABLES}


def main() -> int:
    """Initialize database and verify Riverside tables."""
    print("=" * 60)
    print("Riverside Database Initialization")
    print("=" * 60)
    print()

    # Check for existing tables before initialization
    print("Step 1: Checking existing tables...")
    existing_before = get_existing_tables()
    riverside_existing = existing_before & set(RIVERSIDE_TABLES)
    if riverside_existing:
        print(f"  Found existing Riverside tables: {', '.join(sorted(riverside_existing))}")
    else:
        print("  No existing Riverside tables found")
    print()

    # Step 2: Initialize database (creates all tables)
    print("Step 2: Initializing database...")
    try:
        init_db()
        print("  ✓ Database initialization complete")
    except Exception as e:
        print(f"  ✗ Database initialization failed: {e}")
        return 1
    print()

    # Step 3: Verify tables
    print("Step 3: Verifying Riverside tables...")
    verification = verify_riverside_tables()

    all_created = True
    for table in RIVERSIDE_TABLES:
        status = "✓" if verification[table] else "✗"
        print(f"  {status} {table}")
        if not verification[table]:
            all_created = False
    print()

    # Step 4: Final summary
    print("=" * 60)
    if all_created:
        print("SUCCESS: All Riverside tables created/verified!")
        print("=" * 60)
        return 0
    else:
        print("ERROR: Some Riverside tables are missing!")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
