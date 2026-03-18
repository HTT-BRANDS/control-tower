"""Database configuration and session management — supports SQLite and Azure SQL Server.

Dialect-aware: SQLite pragmas and path setup only activate when DATABASE_URL
starts with "sqlite". Azure SQL (mssql+pyodbc) uses connection pooling.

Features:
- Connection pooling with configurable settings
- Query performance monitoring and slow query logging
- Database indexes for common queries
- Eager loading helpers to prevent N+1 queries
"""

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Index, create_engine, event, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_IS_SQLITE = settings.database_url.startswith("sqlite")

# Ensure data directory exists for SQLite (not needed for remote DBs)
if _IS_SQLITE:
    db_path = settings.database_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# Build engine kwargs — SQLite and SQL Server need different configs
_engine_args: dict[str, Any] = {
    "echo": settings.debug and settings.enable_query_logging,
}

if _IS_SQLITE:
    # SQLite: single-file, needs thread safety override
    _engine_args["connect_args"] = {"check_same_thread": False}
else:
    # SQL Server / PostgreSQL: use connection pool
    _engine_args.update(
        {
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_timeout": settings.database_pool_timeout,
            "pool_pre_ping": True,  # Verify connections before using
            "pool_recycle": 3600,  # Recycle connections after 1 hour
        }
    )

# Lazy engine: pyodbc is NOT imported until first actual DB use.
# This prevents ImportError: libodbc.so.2 at module load time.
_engine_instance = None


def _get_engine():
    """Return (or create) the singleton SQLAlchemy engine."""
    global _engine_instance
    if _engine_instance is None:
        eng = create_engine(settings.database_url, **_engine_args)

        # Query performance monitoring
        @event.listens_for(eng, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault("query_start_time", [])
            conn.info["query_start_time"].append(time.perf_counter())

        @event.listens_for(eng, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            start_time = conn.info["query_start_time"].pop()
            total_time = (time.perf_counter() - start_time) * 1000
            if total_time > settings.slow_query_threshold_ms:
                logger.warning(f"Slow query detected ({total_time:.2f}ms): {statement[:200]}...")
            if settings.debug and settings.enable_query_logging:
                logger.debug(f"Query executed in {total_time:.2f}ms: {statement[:100]}...")

        # SQLite WAL mode — skip for SQL Server
        if _IS_SQLITE:
            @event.listens_for(eng, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA mmap_size=30000000000")
                cursor.close()

        _engine_instance = eng
    return _engine_instance


class _LazyEngine:
    """Transparent proxy so code that imports `engine` directly keeps working."""
    def __getattr__(self, name: str):
        return getattr(_get_engine(), name)

    def __call__(self, *a, **kw):
        return _get_engine()(*a, **kw)


engine = _LazyEngine()


# _session_factory is built lazily so _get_engine() is not invoked at
# module-import time.
_session_factory = None


def SessionLocal():
    """Return a new SQLAlchemy Session bound to the real engine."""
    global _session_factory
    if _session_factory is None:
        from sqlalchemy.orm import sessionmaker as _sm
        _session_factory = _sm(autocommit=False, autoflush=False, bind=_get_engine())
    return _session_factory()

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database sessions (for background jobs)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_bulk_context() -> Generator[Session, None, None]:
    """Optimized context manager for bulk operations.

    Disables autoflush for better performance during bulk inserts.
    """
    db = SessionLocal()
    db.autoflush = False
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables.

    For SQLite (local dev / test): create_all() creates the full schema.
    For all other dialects (Azure SQL, PostgreSQL…): skip create_all and let
    Alembic manage the schema.  The entrypoint runs `alembic upgrade head`
    immediately after init_db(), so there is no gap.  Calling create_all
    against a live Azure SQL database that already has the schema causes
    42S01 'object already exists' errors that crash the process.
    """
    from app import models  # noqa: F401  — registers all models with Base

    if _IS_SQLITE:
        Base.metadata.create_all(_get_engine(), checkfirst=True)

    try:
        _create_indexes()
    except Exception as exc:  # pragma: no cover
        # Index creation is a performance optimisation only — never fatal.
        # A transient DB connectivity issue at startup must not prevent the
        # application from coming up; Alembic manages correctness separately.
        logger.warning(
            "Index creation skipped during startup (will be retried on next deploy): %s",
            exc,
        )


def _create_indexes() -> None:
    """Create database indexes for common query patterns."""
    indexes = [
        # Cost snapshots - frequently queried by date and tenant
        Index("idx_cost_snapshots_date", "cost_snapshots", "date"),
        Index("idx_cost_snapshots_tenant_date", "cost_snapshots", "tenant_id", "date"),
        Index("idx_cost_snapshots_service", "cost_snapshots", "service_name"),
        # Cost anomalies - frequently queried by acknowledgment status
        Index("idx_cost_anomalies_acknowledged", "cost_anomalies", "is_acknowledged"),
        Index("idx_cost_anomalies_detected", "cost_anomalies", "detected_at"),
        Index("idx_cost_anomalies_tenant", "cost_anomalies", "tenant_id"),
        # Resources - frequently queried by tenant and type
        Index("idx_resources_tenant", "resources", "tenant_id"),
        Index("idx_resources_type", "resources", "resource_type"),
        Index("idx_resources_orphaned", "resources", "is_orphaned"),
        Index("idx_resources_synced", "resources", "synced_at"),
        # Idle resources - frequently filtered by review status
        Index("idx_idle_resources_reviewed", "idle_resources", "is_reviewed"),
        Index("idx_idle_resources_tenant", "idle_resources", "tenant_id"),
        Index("idx_idle_resources_savings", "idle_resources", "estimated_monthly_savings"),
        # Compliance snapshots
        Index("idx_compliance_snapshots_tenant", "compliance_snapshots", "tenant_id"),
        Index("idx_compliance_snapshots_date", "compliance_snapshots", "snapshot_date"),
        # Policy states
        Index("idx_policy_states_compliance", "policy_states", "compliance_state"),
        Index("idx_policy_states_tenant", "policy_states", "tenant_id"),
        # Identity snapshots
        Index("idx_identity_snapshots_tenant", "identity_snapshots", "tenant_id"),
        Index("idx_identity_snapshots_date", "identity_snapshots", "snapshot_date"),
        # Privileged users
        Index("idx_privileged_users_tenant", "privileged_users", "tenant_id"),
        Index("idx_privileged_users_role", "privileged_users", "role_name"),
        # Resource tags
        Index("idx_resource_tags_resource", "resource_tags", "resource_id"),
        Index("idx_resource_tags_name", "resource_tags", "tag_name"),
        # Tenants
        Index("idx_tenants_active", "tenants", "is_active"),
        # Sync jobs
        Index("idx_sync_jobs_status", "sync_jobs", "status"),
        Index("idx_sync_jobs_tenant", "sync_jobs", "tenant_id"),
    ]

    with engine.connect() as conn:
        for index in indexes:
            try:
                index.create(conn, checkfirst=True)
            except Exception as e:
                logger.debug(f"Index creation skipped (may already exist): {e}")
        conn.commit()


# Query optimization helpers


def eager_load_options(*relationships: str) -> list[Any]:
    """Create eager load options for relationships to prevent N+1 queries.

    Usage:
        from sqlalchemy.orm import joinedload
        query = db.query(Model).options(*eager_load_options("tenant", "tags"))
    """
    from sqlalchemy.orm import joinedload

    return [joinedload(r) for r in relationships]


def query_with_timing(db: Session, query, description: str = "Query"):
    """Execute query with timing and logging.

    Usage:
        results = query_with_timing(db, db.query(Model), "Fetch models")
    """
    start = time.perf_counter()
    try:
        result = query.all()
        elapsed = (time.perf_counter() - start) * 1000
        logger.debug(f"{description} completed in {elapsed:.2f}ms")
        return result
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error(f"{description} failed after {elapsed:.2f}ms: {e}")
        raise


def batch_query(db: Session, query, batch_size: int | None = None):
    """Iterate over query results in batches to reduce memory usage.

    Usage:
        for batch in batch_query(db, db.query(LargeTable), 1000):
            process_batch(batch)
    """
    if batch_size is None:
        batch_size = settings.sync_chunk_size

    offset = 0
    while True:
        batch = query.limit(batch_size).offset(offset).all()
        if not batch:
            break
        yield batch
        offset += batch_size


def bulk_insert_chunks(
    db: Session,
    model_class,
    items: list[dict],
    batch_size: int | None = None,
) -> int:
    """Perform bulk insert in chunks to avoid memory issues.

    Args:
        db: Database session
        model_class: SQLAlchemy model class
        items: List of dictionaries to insert
        batch_size: Number of items per batch

    Returns:
        Total number of items inserted
    """
    if batch_size is None:
        batch_size = settings.bulk_batch_size

    total_inserted = 0

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        db.bulk_insert_mappings(model_class, batch)
        db.commit()
        total_inserted += len(batch)
        logger.debug(f"Bulk inserted {len(batch)} {model_class.__name__} records")

    return total_inserted


def get_db_stats(db: Session) -> dict[str, Any]:
    """Get database statistics for monitoring."""
    stats = {}

    # Table counts
    tables = [
        "resources",
        "cost_snapshots",
        "cost_anomalies",
        "compliance_snapshots",
        "policy_states",
        "identity_snapshots",
        "privileged_users",
        "sync_jobs",
        "tenants",
    ]

    for table in tables:
        try:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            stats[f"{table}_count"] = result.scalar()
        except Exception:
            stats[f"{table}_count"] = None

    # Database size (SQLite only)
    if settings.database_url.startswith("sqlite"):
        try:
            result = db.execute(
                text("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
            )
            stats["db_size_bytes"] = result.scalar()
        except Exception:
            stats["db_size_bytes"] = None

    return stats
