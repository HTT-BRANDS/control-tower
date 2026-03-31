#!/usr/bin/env python3
"""Database backup script for Azure Governance Platform.

Supports PostgreSQL, SQL Server/Azure SQL, and SQLite.
Compresses backups with gzip for storage efficiency.

Usage:
    python scripts/backup_database.py --type full --output backup.sql.gz
    python scripts/backup_database.py --type schema-only --output schema.sql.gz
    python scripts/backup_database.py --type data-only --output data.sql.gz

Environment Variables:
    DATABASE_URL: Database connection string
"""

import argparse
import gzip
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Backup database to compressed SQL file")
    parser.add_argument(
        "--type",
        choices=["full", "schema-only", "data-only"],
        default="full",
        help="Type of backup to create",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output file path (should end in .gz for compression)",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Database URL (defaults to DATABASE_URL env var)",
    )
    return parser.parse_args()


def get_database_type(url: str) -> str:
    """Determine database type from connection URL."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    if scheme.startswith("postgresql") or scheme.startswith("postgres"):
        return "postgresql"
    elif scheme.startswith("mssql") or scheme.startswith("sqlserver"):
        return "mssql"
    elif scheme.startswith("sqlite"):
        return "sqlite"
    else:
        raise ValueError(f"Unsupported database scheme: {scheme}")


def backup_postgresql(url: str, backup_type: str, output_path: str) -> None:
    """Create PostgreSQL backup using pg_dump."""
    parsed = urlparse(url)
    dbname = parsed.path.lstrip("/")

    # Build pg_dump command
    cmd = ["pg_dump", "-h", parsed.hostname, "-p", str(parsed.port or 5432)]

    if parsed.username:
        cmd.extend(["-U", parsed.username])

    if backup_type == "schema-only":
        cmd.append("--schema-only")
    elif backup_type == "data-only":
        cmd.append("--data-only")
    else:
        cmd.append("--verbose")

    cmd.extend(["-f", "-", dbname])  # Output to stdout

    # Set environment for password
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    logger.info(f"Running pg_dump for database: {dbname}")

    # Run pg_dump and compress
    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        for line in process.stdout:
            f.write(line)

        process.wait()

        if process.returncode != 0:
            stderr = process.stderr.read()
            raise RuntimeError(f"pg_dump failed: {stderr}")

    logger.info(f"✓ PostgreSQL backup saved to {output_path}")


def backup_mssql(url: str, backup_type: str, output_path: str) -> None:
    """Create SQL Server/Azure SQL backup using mssql-scripter or sqlpackage."""
    parsed = urlparse(url)
    dbname = parsed.path.lstrip("/")

    # Try mssql-scripter first (Python-based, easier to install)
    try:
        import subprocess

        cmd = [
            "python",
            "-m",
            "mssqlscripter",
            "-S",
            f"{parsed.hostname},{parsed.port or 1433}",
            "-d",
            dbname,
            "-U",
            parsed.username,
        ]

        if backup_type == "schema-only":
            cmd.append("--schema-only")
        elif backup_type == "data-only":
            cmd.append("--data-only")

        cmd.extend(["--script-create", "--script-drop", "--target-server-version", "AzureDB"])

        logger.info(f"Running mssql-scripter for database: {dbname}")

        with gzip.open(output_path, "wt", encoding="utf-8") as f:
            env = os.environ.copy()
            if parsed.password:
                env["MSSQLSCRIPTER_PASSWORD"] = parsed.password

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )

            for line in process.stdout:
                f.write(line)

            process.wait()

            if process.returncode != 0:
                stderr = process.stderr.read()
                raise RuntimeError(f"mssql-scripter failed: {stderr}")

        logger.info(f"✓ SQL Server backup saved to {output_path}")

    except FileNotFoundError:
        # Fallback: Use SQLAlchemy to generate schema script
        logger.warning("mssql-scripter not found, using SQLAlchemy fallback")
        backup_with_sqlalchemy(url, backup_type, output_path)


def backup_sqlite(url: str, backup_type: str, output_path: str) -> None:
    """Create SQLite backup."""
    parsed = urlparse(url)
    db_path = parsed.path

    if backup_type == "data-only":
        # Use .dump command for data only
        cmd = ["sqlite3", db_path, ".dump"]
    elif backup_type == "schema-only":
        # Schema only
        cmd = ["sqlite3", db_path, ".schema"]
    else:
        # Full backup
        cmd = ["sqlite3", db_path, ".backup", ":memory:"]

    logger.info(f"Creating SQLite backup: {db_path}")

    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        for line in process.stdout:
            f.write(line)

        process.wait()

        if process.returncode != 0:
            stderr = process.stderr.read()
            raise RuntimeError(f"sqlite3 failed: {stderr}")

    logger.info(f"✓ SQLite backup saved to {output_path}")


def backup_with_sqlalchemy(url: str, backup_type: str, output_path: str) -> None:
    """Fallback backup using SQLAlchemy introspection."""
    from sqlalchemy import MetaData, create_engine

    logger.info("Using SQLAlchemy for schema backup")

    engine = create_engine(url)
    metadata = MetaData()
    metadata.reflect(bind=engine)

    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        # Write header
        f.write(f"-- Backup generated at {datetime.now(UTC).isoformat()}\n")
        f.write(f"-- Type: {backup_type}\n")
        f.write(f"-- Database: {url.split('@')[-1]}\n")
        f.write("--\n\n")

        if backup_type in ("full", "schema-only"):
            # Generate CREATE TABLE statements
            from sqlalchemy.schema import CreateTable

            f.write("-- Schema\n")
            for table in metadata.sorted_tables:
                create_stmt = str(CreateTable(table).compile(engine))
                f.write(f"{create_stmt};\n\n")

        if backup_type in ("full", "data-only"):
            # Export data as INSERT statements
            f.write("-- Data\n")
            with engine.connect() as conn:
                for table in metadata.sorted_tables:
                    result = conn.execute(table.select())
                    for row in result:
                        values = []
                        for val in row:
                            if val is None:
                                values.append("NULL")
                            elif isinstance(val, str):
                                escaped = val.replace("'", "''")
                                values.append(f"'{escaped}'")
                            elif isinstance(val, int | float):
                                values.append(str(val))
                            elif isinstance(val, datetime):
                                values.append(f"'{val.isoformat()}'")
                            else:
                                values.append(f"'{str(val)}'")

                        columns = ", ".join(table.columns.keys())
                        vals = ", ".join(values)
                        f.write(f"INSERT INTO {table.name} ({columns}) VALUES ({vals});\n")
                    f.write("\n")

    logger.info(f"✓ SQLAlchemy backup saved to {output_path}")


def verify_backup(output_path: str) -> bool:
    """Verify backup file integrity."""
    if not os.path.exists(output_path):
        logger.error(f"Backup file not found: {output_path}")
        return False

    if os.path.getsize(output_path) == 0:
        logger.error("Backup file is empty")
        return False

    # Try to decompress and check first few lines
    try:
        with gzip.open(output_path, "rt", encoding="utf-8") as f:
            # Read first few lines to verify it's a valid SQL dump
            header = f.read(1000)
            if "CREATE" in header or "INSERT" in header or "PostgreSQL" in header:
                logger.info("✓ Backup file verified")
                return True
            else:
                logger.warning("Backup file may be corrupted (no SQL statements found)")
                return False
    except Exception as e:
        logger.error(f"Backup file verification failed: {e}")
        return False


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Validate database URL
    if not args.database_url:
        logger.error("DATABASE_URL not provided (use --database-url or set env var)")
        return 1

    try:
        # Determine database type
        db_type = get_database_type(args.database_url)
        logger.info(f"Detected database type: {db_type}")

        # Create output directory if needed
        output_dir = os.path.dirname(args.output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Perform backup
        if db_type == "postgresql":
            backup_postgresql(args.database_url, args.type, args.output)
        elif db_type == "mssql":
            backup_mssql(args.database_url, args.type, args.output)
        elif db_type == "sqlite":
            backup_sqlite(args.database_url, args.type, args.output)
        else:
            backup_with_sqlalchemy(args.database_url, args.type, args.output)

        # Verify backup
        if not verify_backup(args.output):
            logger.error("Backup verification failed")
            return 1

        # Print summary
        size_bytes = os.path.getsize(args.output)
        size_mb = size_bytes / (1024 * 1024)
        logger.info(f"Backup complete: {args.output} ({size_mb:.2f} MB)")

        return 0

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
