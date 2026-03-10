#!/usr/bin/env python3
"""Setup initial admin user for Azure Governance Platform.

Usage:
    uv run python scripts/setup_admin.py --email admin@example.com --name "Admin User"
    uv run python scripts/setup_admin.py --email admin@example.com --name "Admin User" --dry-run
    uv run python scripts/setup_admin.py --help
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Create an admin user for the Azure Governance Platform.",
        epilog="Example: uv run python scripts/setup_admin.py --email admin@example.com --name 'Admin User'",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Admin user email address",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Admin user display name",
    )
    parser.add_argument(
        "--role",
        default="admin",
        choices=["admin", "viewer", "operator"],
        help="Role to assign (default: admin)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    return parser.parse_args()


def main() -> int:
    """Create admin user."""
    args = parse_args()

    print("Azure Governance Platform — Admin User Setup")
    print("=" * 50)
    print(f"Email: {args.email}")
    print(f"Name:  {args.name}")
    print(f"Role:  {args.role}")
    print()

    if args.dry_run:
        print("[DRY RUN] Would create admin user with above settings.")
        print("[DRY RUN] No changes made.")
        return 0

    # Check database exists
    from app.core.config import get_settings

    settings = get_settings()

    db_path = settings.database_url.replace("sqlite:///", "")
    if db_path.startswith("./"):
        db_path = str(Path(db_path))

    if "sqlite" in settings.database_url and not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        print("Run 'uv run alembic upgrade head' first to create the database.")
        return 1

    # Import database session
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        # Check if user already exists
        from sqlalchemy import text

        result = db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": args.email},
        ).fetchone()

        if result:
            print(f"User '{args.email}' already exists (ID: {result[0]}). Skipping.")
            return 0

        # Create admin user
        import uuid
        from datetime import UTC, datetime

        user_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        db.execute(
            text(
                "INSERT INTO users (id, email, display_name, role, is_active, created_at, updated_at) "
                "VALUES (:id, :email, :name, :role, 1, :now, :now)"
            ),
            {
                "id": user_id,
                "email": args.email,
                "name": args.name,
                "role": args.role,
                "now": now,
            },
        )
        db.commit()

        print("✅ Admin user created successfully!")
        print(f"   ID:    {user_id}")
        print(f"   Email: {args.email}")
        print(f"   Role:  {args.role}")

    except Exception as e:
        print(f"ERROR: {e}")
        print()
        print("If the 'users' table doesn't exist, run 'uv run alembic upgrade head' first.")
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
