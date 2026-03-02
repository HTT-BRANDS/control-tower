"""Core module initialization."""

from app.core.cache import (
    cache_manager,
    cached,
    delete_cached,
    get_cached,
    get_cache_ttl,
    invalidate_on_sync_completion,
    set_cached,
)
from app.core.config import Settings, get_settings
from app.core.database import (
    Base,
    batch_query,
    bulk_insert_chunks,
    eager_load_options,
    get_db,
    get_db_bulk_context,
    get_db_context,
    get_db_stats,
    init_db,
    query_with_timing,
)
from app.core.monitoring import (
    PerformanceMonitor,
    SyncJobMetrics,
    get_cache_stats,
    get_performance_dashboard,
    performance_monitor,
    reset_metrics,
    track_query,
    track_sync_job,
)
from app.core.notifications import (
    Notification,
    NotificationChannel,
    Severity,
    create_dashboard_url,
    create_retry_url,
    format_sync_alert,
    record_notification_sent,
    send_notification,
    send_teams_notification,
    severity_meets_threshold,
    should_notify,
)
from app.core.rate_limit import (
    RateLimitConfig,
    RateLimitStrategy,
    rate_limit,
    rate_limiter,
)
from app.core.scheduler import get_scheduler, init_scheduler, trigger_manual_sync
from app.core.tenant_context import (
    BrandColors,
    DEFAULT_BRAND,
    get_all_brand_palettes,
    get_brand_colors,
    get_brand_colors_by_code,
    get_brand_context_for_request,
    get_brand_css_variables,
    get_template_context,
    get_tenant_brand_from_request,
    register_template_filters,
    TenantContextMiddleware,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    # Database
    "Base",
    "get_db",
    "get_db_context",
    "get_db_bulk_context",
    "init_db",
    "eager_load_options",
    "query_with_timing",
    "batch_query",
    "bulk_insert_chunks",
    "get_db_stats",
    # Cache
    "cache_manager",
    "cached",
    "get_cached",
    "set_cached",
    "delete_cached",
    "get_cache_ttl",
    "invalidate_on_sync_completion",
    # Monitoring
    "PerformanceMonitor",
    "SyncJobMetrics",
    "performance_monitor",
    "track_query",
    "track_sync_job",
    "get_performance_dashboard",
    "get_cache_stats",
    "reset_metrics",
    # Rate Limiting
    "RateLimitConfig",
    "RateLimitStrategy",
    "rate_limit",
    "rate_limiter",
    # Scheduler
    "get_scheduler",
    "init_scheduler",
    "trigger_manual_sync",
    # Notifications
    "Notification",
    "NotificationChannel",
    "Severity",
    "should_notify",
    "send_notification",
    "send_teams_notification",
    "format_sync_alert",
    "record_notification_sent",
    "severity_meets_threshold",
    "create_dashboard_url",
    "create_retry_url",
    # Tenant Context
    "BrandColors",
    "DEFAULT_BRAND",
    "TenantContextMiddleware",
    "get_brand_colors",
    "get_brand_colors_by_code",
    "get_all_brand_palettes",
    "get_tenant_brand_from_request",
    "get_brand_css_variables",
    "get_template_context",
    "get_brand_context_for_request",
    "register_template_filters",
]
