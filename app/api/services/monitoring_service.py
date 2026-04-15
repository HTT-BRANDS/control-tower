"""Monitoring and observability service for sync jobs."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.notifications import (
    Notification,
    NotificationChannel,
    Severity,
    create_dashboard_url,
    create_retry_url,
    record_notification_sent,
    send_notification,
    should_notify,
)
from app.models.monitoring import Alert, SyncJobLog, SyncJobMetrics
from app.models.notifications import NotificationLog

logger = logging.getLogger(__name__)

# Configuration for alert thresholds
ALERT_THRESHOLDS = {
    "stale_sync_multiplier": 2.0,  # Alert if sync hasn't run in 2x expected interval
    "error_rate_threshold": 0.3,  # Alert if error rate > 30%
    "zero_records_threshold": 3,  # Alert after 3 consecutive zero-record runs
}


def _expected_sync_intervals() -> dict[str, int]:
    """Return expected sync intervals from settings (configurable via env)."""
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "costs": settings.cost_sync_interval_hours,
        "compliance": settings.compliance_sync_interval_hours,
        "resources": settings.resource_sync_interval_hours,
        "identity": settings.identity_sync_interval_hours,
    }


class MonitoringService:
    """Service for monitoring sync job execution and health."""

    def __init__(self, db: Session):
        self.db = db

    # ==========================================================================
    # Sync Job Log Operations
    # ==========================================================================

    def cleanup_ghost_jobs(self, stale_minutes: int = 30) -> int:
        """Mark stale "running" jobs as failed to prevent ghost jobs.

        A ghost job is a sync job stuck in "running" status for longer than
        ``stale_minutes`` — typically caused by a process crash or OOM kill
        that never called ``complete_sync_job()``.

        Args:
            stale_minutes: How many minutes a job can be "running" before
                it is considered ghostly.  Defaults to 30.

        Returns:
            Number of ghost jobs cleaned up.
        """
        cutoff = datetime.now(UTC) - timedelta(minutes=stale_minutes)
        ghost_jobs = (
            self.db.query(SyncJobLog)
            .filter(
                SyncJobLog.status == "running",
                SyncJobLog.started_at < cutoff,
            )
            .all()
        )

        for job in ghost_jobs:
            job.status = "failed"
            job.ended_at = datetime.now(UTC)
            job.error_message = (
                f"Ghost job: still running after {stale_minutes} min — likely crashed or OOM-killed"
            )
            if job.started_at:
                started_at = job.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=UTC)
                job.duration_ms = int((job.ended_at - started_at).total_seconds() * 1000)
            logger.warning(
                f"Cleaned up ghost job: {job.job_type} (id={job.id}, "
                f"started={job.started_at.isoformat()})"
            )

        if ghost_jobs:
            self.db.commit()

        return len(ghost_jobs)

    def start_sync_job(
        self, job_type: str, tenant_id: str | None = None, details: dict | None = None
    ) -> SyncJobLog:
        """Create a new sync job log entry at the start of execution.

        Cleans up ghost jobs before creating the new entry so that stale
        "running" entries don't block monitoring dashboards.

        Args:
            job_type: Type of sync job (costs, compliance, resources, identity)
            tenant_id: Optional tenant ID (None for all tenants)
            details: Optional JSON-serializable details dict

        Returns:
            The created SyncJobLog entry
        """
        # Nuke ghost jobs before we start a new one
        ghost_count = self.cleanup_ghost_jobs()
        if ghost_count:
            logger.info(f"Cleaned up {ghost_count} ghost job(s) before starting {job_type} sync")

        log_entry = SyncJobLog(
            job_type=job_type,
            tenant_id=tenant_id,
            status="running",
            started_at=datetime.now(UTC),
            records_processed=0,
            records_created=0,
            records_updated=0,
            errors_count=0,
            details_json=json.dumps(details) if details else None,
        )
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        logger.info(f"Started {job_type} sync job (log_id={log_entry.id})")
        return log_entry

    def update_sync_progress(
        self,
        log_id: int,
        records_processed: int | None = None,
        records_created: int | None = None,
        records_updated: int | None = None,
        errors_count: int | None = None,
    ) -> SyncJobLog:
        """Update sync job progress during execution.

        Args:
            log_id: ID of the sync job log entry
            records_processed: Optional new records_processed count
            records_created: Optional new records_created count
            records_updated: Optional new records_updated count
            errors_count: Optional new errors_count

        Returns:
            The updated SyncJobLog entry
        """
        log_entry = self.db.query(SyncJobLog).filter(SyncJobLog.id == log_id).first()
        if not log_entry:
            raise ValueError(f"Sync job log with id {log_id} not found")

        if records_processed is not None:
            log_entry.records_processed = records_processed
        if records_created is not None:
            log_entry.records_created = records_created
        if records_updated is not None:
            log_entry.records_updated = records_updated
        if errors_count is not None:
            log_entry.errors_count = errors_count

        self.db.commit()
        self.db.refresh(log_entry)
        return log_entry

    def complete_sync_job(
        self,
        log_id: int,
        status: str = "completed",
        error_message: str | None = None,
        final_records: dict | None = None,
    ) -> SyncJobLog:
        """Mark a sync job as completed or failed.

        Args:
            log_id: ID of the sync job log entry
            status: Final status (completed or failed)
            error_message: Optional error message if failed
            final_records: Optional dict with final record counts
                (records_processed, records_created, records_updated, errors_count)

        Returns:
            The updated SyncJobLog entry
        """
        log_entry = self.db.query(SyncJobLog).filter(SyncJobLog.id == log_id).first()
        if not log_entry:
            raise ValueError(f"Sync job log with id {log_id} not found")

        log_entry.status = status
        log_entry.ended_at = datetime.now(UTC)

        if log_entry.started_at:
            started_at = log_entry.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            duration = log_entry.ended_at - started_at
            log_entry.duration_ms = int(duration.total_seconds() * 1000)

        if error_message:
            log_entry.error_message = error_message

        if final_records:
            log_entry.records_processed = final_records.get(
                "records_processed", log_entry.records_processed
            )
            log_entry.records_created = final_records.get(
                "records_created", log_entry.records_created
            )
            log_entry.records_updated = final_records.get(
                "records_updated", log_entry.records_updated
            )
            log_entry.errors_count = final_records.get("errors_count", log_entry.errors_count)

        self.db.commit()
        self.db.refresh(log_entry)

        # Update metrics and check for alerts
        self._update_metrics_for_job_type(log_entry.job_type)
        self._check_for_alerts_after_completion(log_entry)

        logger.info(
            f"Completed {log_entry.job_type} sync job (log_id={log_id}) "
            f"with status={status}, duration_ms={log_entry.duration_ms}"
        )
        return log_entry

    # ==========================================================================
    # Sync Job Metrics Operations
    # ==========================================================================

    def _update_metrics_for_job_type(self, job_type: str) -> SyncJobMetrics:
        """Recalculate and update metrics for a job type."""
        # Get or create metrics record
        metrics = self.db.query(SyncJobMetrics).filter(SyncJobMetrics.job_type == job_type).first()
        if not metrics:
            metrics = SyncJobMetrics(job_type=job_type)
            self.db.add(metrics)

        # Calculate metrics from logs
        logs_query = self.db.query(SyncJobLog).filter(SyncJobLog.job_type == job_type)

        # Total runs
        metrics.total_runs = logs_query.count()

        # Successful and failed runs
        metrics.successful_runs = logs_query.filter(SyncJobLog.status == "completed").count()
        metrics.failed_runs = logs_query.filter(SyncJobLog.status == "failed").count()

        # Success rate
        if metrics.total_runs > 0:
            metrics.success_rate = metrics.successful_runs / metrics.total_runs

        # Duration stats (only completed/failed jobs with duration)
        duration_query = logs_query.filter(SyncJobLog.duration_ms.isnot(None))
        durations = [log.duration_ms for log in duration_query.all() if log.duration_ms]

        if durations:
            metrics.avg_duration_ms = sum(durations) / len(durations)
            metrics.min_duration_ms = min(durations)
            metrics.max_duration_ms = max(durations)

        # Records stats
        metrics.total_records_processed = sum(
            log.records_processed or 0 for log in logs_query.all()
        )
        metrics.total_errors = sum(log.errors_count or 0 for log in logs_query.all())

        if metrics.total_runs > 0:
            metrics.avg_records_processed = metrics.total_records_processed / metrics.total_runs

        # Last execution info
        last_run = logs_query.order_by(SyncJobLog.started_at.desc()).first()
        if last_run:
            metrics.last_run_at = last_run.started_at
            if last_run.status == "completed":
                metrics.last_success_at = last_run.started_at
            elif last_run.status == "failed":
                metrics.last_failure_at = last_run.started_at
                metrics.last_error_message = last_run.error_message

        metrics.calculated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(metrics)
        return metrics

    def get_metrics(self, job_type: str | None = None) -> list[SyncJobMetrics]:
        """Get metrics for sync jobs.

        Args:
            job_type: Optional specific job type to filter by

        Returns:
            List of SyncJobMetrics
        """
        query = self.db.query(SyncJobMetrics)
        if job_type:
            query = query.filter(SyncJobMetrics.job_type == job_type)
        return query.all()

    def get_recent_logs(
        self, job_type: str | None = None, limit: int = 50, include_running: bool = False
    ) -> list[SyncJobLog]:
        """Get recent sync job logs.

        Args:
            job_type: Optional specific job type to filter by
            limit: Maximum number of logs to return
            include_running: Whether to include currently running jobs

        Returns:
            List of SyncJobLog entries
        """
        query = self.db.query(SyncJobLog)
        if job_type:
            query = query.filter(SyncJobLog.job_type == job_type)
        if not include_running:
            query = query.filter(SyncJobLog.status != "running")
        return query.order_by(SyncJobLog.started_at.desc()).limit(limit).all()

    # ==========================================================================
    # Alert Operations
    # ==========================================================================

    def _check_for_alerts_after_completion(self, log_entry: SyncJobLog) -> list[Alert]:
        """Check and create alerts after a sync job completes."""
        alerts = []

        # Alert on failure
        if log_entry.status == "failed":
            alert = self.create_alert(
                alert_type="sync_failure",
                severity="error",
                job_type=log_entry.job_type,
                tenant_id=log_entry.tenant_id,
                title=f"{log_entry.job_type.title()} sync failed",
                message=f"Sync job failed after {log_entry.duration_seconds or 0:.1f}s",
                details={
                    "log_id": log_entry.id,
                    "error_message": log_entry.error_message,
                    "records_processed": log_entry.records_processed,
                },
            )
            alerts.append(alert)

        # Alert on zero records (potential auth issue)
        if log_entry.status == "completed" and log_entry.records_processed == 0:
            # Check if this is consecutive
            recent_zeros = (
                self.db.query(SyncJobLog)
                .filter(
                    SyncJobLog.job_type == log_entry.job_type,
                    SyncJobLog.status == "completed",
                    SyncJobLog.records_processed == 0,
                )
                .order_by(SyncJobLog.started_at.desc())
                .limit(ALERT_THRESHOLDS["zero_records_threshold"])
                .count()
            )

            if recent_zeros >= ALERT_THRESHOLDS["zero_records_threshold"]:
                alert = self.create_alert(
                    alert_type="no_records",
                    severity="warning",
                    job_type=log_entry.job_type,
                    tenant_id=log_entry.tenant_id,
                    title=f"{log_entry.job_type.title()} sync processing zero records",
                    message=f"Last {recent_zeros} runs processed zero records - possible auth issue",
                    details={
                        "log_id": log_entry.id,
                        "consecutive_zero_runs": recent_zeros,
                    },
                )
                alerts.append(alert)

        # Check high error rate
        if log_entry.errors_count > 0:
            # Calculate error rate for recent runs
            recent_logs = (
                self.db.query(SyncJobLog)
                .filter(
                    SyncJobLog.job_type == log_entry.job_type,
                    SyncJobLog.status != "running",
                )
                .order_by(SyncJobLog.started_at.desc())
                .limit(10)
                .all()
            )

            if recent_logs:
                total_errors = sum(log.errors_count or 0 for log in recent_logs)
                total_records = sum(log.records_processed or 0 for log in recent_logs)

                if total_records > 0:
                    error_rate = total_errors / total_records
                    if error_rate > ALERT_THRESHOLDS["error_rate_threshold"]:
                        alert = self.create_alert(
                            alert_type="high_error_rate",
                            severity="warning",
                            job_type=log_entry.job_type,
                            title=f"{log_entry.job_type.title()} sync has high error rate",
                            message=f"Error rate is {error_rate:.1%} over last {len(recent_logs)} runs",
                            details={
                                "error_rate": error_rate,
                                "total_errors": total_errors,
                                "total_records": total_records,
                            },
                        )
                        alerts.append(alert)

        return alerts

    def check_stale_syncs(self) -> list[Alert]:
        """Check for sync jobs that haven't run in expected time.

        Returns:
            List of created alerts
        """
        alerts = []

        for job_type, expected_hours in _expected_sync_intervals().items():
            metrics = (
                self.db.query(SyncJobMetrics).filter(SyncJobMetrics.job_type == job_type).first()
            )

            if not metrics or not metrics.last_run_at:
                # Never run - create alert
                alert = self.create_alert(
                    alert_type="stale_sync",
                    severity="warning",
                    job_type=job_type,
                    title=f"{job_type.title()} sync has never run",
                    message=f"Expected interval: {expected_hours}h, but no runs found",
                )
                alerts.append(alert)
                continue

            # Check if stale
            expected_interval = timedelta(
                hours=expected_hours * ALERT_THRESHOLDS["stale_sync_multiplier"]
            )
            last_run_at = metrics.last_run_at
            if last_run_at.tzinfo is None:
                last_run_at = last_run_at.replace(tzinfo=UTC)
            since_last_run = datetime.now(UTC) - last_run_at

            if since_last_run > expected_interval:
                # Check if alert already exists
                existing = (
                    self.db.query(Alert)
                    .filter(
                        Alert.alert_type == "stale_sync",
                        Alert.job_type == job_type,
                        Alert.is_resolved == 0,
                    )
                    .first()
                )

                if not existing:
                    hours_overdue = since_last_run.total_seconds() / 3600
                    alert = self.create_alert(
                        alert_type="stale_sync",
                        severity="error" if hours_overdue > expected_hours * 3 else "warning",
                        job_type=job_type,
                        title=f"{job_type.title()} sync is stale",
                        message=f"Last run was {hours_overdue:.1f} hours ago (expected: {expected_hours}h)",
                        details={
                            "last_run_at": metrics.last_run_at.isoformat(),
                            "expected_hours": expected_hours,
                            "hours_overdue": hours_overdue,
                        },
                    )
                    alerts.append(alert)

        return alerts

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        job_type: str | None = None,
        tenant_id: str | None = None,
        details: dict | None = None,
    ) -> Alert:
        """Create a new alert.

        Args:
            alert_type: Type of alert
            severity: Alert severity (info, warning, error, critical)
            title: Short alert title
            message: Detailed alert message
            job_type: Optional related job type
            tenant_id: Optional related tenant
            details: Optional JSON-serializable details

        Returns:
            The created Alert
        """
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            job_type=job_type,
            tenant_id=tenant_id,
            title=title,
            message=message,
            details_json=json.dumps(details) if details else None,
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        logger.warning(f"Created alert: {alert_type} - {title}")

        # Send notification for critical alerts — fire-and-forget async call
        # Pass only the alert_id (not the ORM object) to avoid DetachedInstanceError
        # when the session closes before the async task runs.
        if severity in ("error", "critical"):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(send_alert_notification(alert.id))
            except RuntimeError:
                # No running event loop (e.g. CLI/sync context) — notification skipped
                logger.debug("No running event loop; skipping alert notification for %s", alert.id)

        return alert

    def resolve_alert(self, alert_id: int, resolved_by: str | None = None) -> Alert:
        """Mark an alert as resolved.

        Args:
            alert_id: ID of the alert to resolve
            resolved_by: Optional user/system that resolved the alert

        Returns:
            The resolved Alert
        """
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert with id {alert_id} not found")

        alert.is_resolved = True
        alert.resolved_at = datetime.now(UTC)
        alert.resolved_by = resolved_by
        self.db.commit()
        self.db.refresh(alert)
        logger.info(f"Resolved alert {alert_id}")
        return alert

    def get_active_alerts(
        self, job_type: str | None = None, severity: str | None = None
    ) -> list[Alert]:
        """Get active (unresolved) alerts.

        Args:
            job_type: Optional filter by job type
            severity: Optional filter by severity

        Returns:
            List of active Alert entries
        """
        query = self.db.query(Alert).filter(Alert.is_resolved == 0)

        if job_type:
            query = query.filter(Alert.job_type == job_type)
        if severity:
            query = query.filter(Alert.severity == severity)

        return query.order_by(Alert.created_at.desc()).all()

    def get_alert_stats(self) -> dict[str, Any]:
        """Get summary statistics for alerts.

        Returns:
            Dict with alert statistics
        """
        total_alerts = self.db.query(Alert).count()
        active_alerts = self.db.query(Alert).filter(Alert.is_resolved == 0).count()
        resolved_alerts = total_alerts - active_alerts

        # By severity
        severity_counts = (
            self.db.query(Alert.severity, func.count(Alert.id))
            .filter(Alert.is_resolved == 0)
            .group_by(Alert.severity)
            .all()
        )

        # By type
        type_counts = (
            self.db.query(Alert.alert_type, func.count(Alert.id))
            .filter(Alert.is_resolved == 0)
            .group_by(Alert.alert_type)
            .all()
        )

        return {
            "total": total_alerts,
            "active": active_alerts,
            "resolved": resolved_alerts,
            "by_severity": dict(severity_counts),
            "by_type": dict(type_counts),
        }

    # ==========================================================================
    # Overall Status
    # ==========================================================================

    def get_overall_status(self) -> dict[str, Any]:
        """Get overall sync system status.

        Returns:
            Dict with overall status summary
        """
        # Check for stale syncs
        stale_alerts = self.check_stale_syncs()

        # Get metrics for all job types
        all_metrics = self.get_metrics()
        metrics_by_type = {m.job_type: m for m in all_metrics}

        # Build status for each expected job type
        job_statuses = {}
        for job_type in _expected_sync_intervals():
            metrics = metrics_by_type.get(job_type)

            if not metrics:
                job_statuses[job_type] = {
                    "status": "unknown",
                    "last_run": None,
                    "success_rate": None,
                }
            elif metrics.last_failure_at and (
                not metrics.last_success_at or metrics.last_failure_at > metrics.last_success_at
            ):
                job_statuses[job_type] = {
                    "status": "degraded",
                    "last_run": metrics.last_run_at.isoformat() if metrics.last_run_at else None,
                    "last_success": metrics.last_success_at.isoformat()
                    if metrics.last_success_at
                    else None,
                    "last_failure": metrics.last_failure_at.isoformat()
                    if metrics.last_failure_at
                    else None,
                    "success_rate": metrics.success_rate,
                }
            else:
                job_statuses[job_type] = {
                    "status": "healthy",
                    "last_run": metrics.last_run_at.isoformat() if metrics.last_run_at else None,
                    "last_success": metrics.last_success_at.isoformat()
                    if metrics.last_success_at
                    else None,
                    "success_rate": metrics.success_rate,
                }

        # Count active alerts
        active_alerts = self.get_active_alerts()
        critical_alerts = [a for a in active_alerts if a.severity == "critical"]
        error_alerts = [a for a in active_alerts if a.severity == "error"]

        # Determine overall status
        overall_status = "healthy"
        if critical_alerts:
            overall_status = "critical"
        elif error_alerts or stale_alerts:
            overall_status = "degraded"

        return {
            "status": overall_status,
            "jobs": job_statuses,
            "alerts": {
                "total_active": len(active_alerts),
                "critical": len(critical_alerts),
                "error": len(error_alerts),
            },
            "last_updated": datetime.now(UTC).isoformat(),
        }

    # ==========================================================================
    # Notification Log Operations
    # ==========================================================================

    def get_notification_logs(
        self,
        alert_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[NotificationLog]:
        """Get notification history.

        Args:
            alert_id: Optional filter by specific alert
            status: Optional filter by status (pending, sent, failed, retrying)
            limit: Maximum number of logs to return

        Returns:
            List of NotificationLog entries
        """
        query = self.db.query(NotificationLog)

        if alert_id:
            query = query.filter(NotificationLog.alert_id == alert_id)
        if status:
            query = query.filter(NotificationLog.status == status)

        return query.order_by(NotificationLog.sent_at.desc()).limit(limit).all()

    def get_notification_stats(self) -> dict[str, Any]:
        """Get notification delivery statistics.

        Returns:
            Dict with notification statistics
        """
        total = self.db.query(NotificationLog).count()
        sent = self.db.query(NotificationLog).filter(NotificationLog.status == "sent").count()
        failed = self.db.query(NotificationLog).filter(NotificationLog.status == "failed").count()
        pending = self.db.query(NotificationLog).filter(NotificationLog.status == "pending").count()

        # By channel
        channel_counts = (
            self.db.query(NotificationLog.channel, func.count(NotificationLog.id))
            .group_by(NotificationLog.channel)
            .all()
        )

        # Recent failures (last 24h)
        recent_failures = (
            self.db.query(NotificationLog)
            .filter(
                NotificationLog.status == "failed",
                NotificationLog.sent_at >= datetime.now(UTC) - timedelta(hours=24),
            )
            .count()
        )

        return {
            "total": total,
            "sent": sent,
            "failed": failed,
            "pending": pending,
            "success_rate": sent / total if total > 0 else 0.0,
            "by_channel": dict(channel_counts),
            "recent_failures_24h": recent_failures,
        }


# ==========================================================================
# Module-level async notification — uses its own session
# ==========================================================================


async def send_alert_notification(alert_id: int) -> NotificationLog | None:
    """Send notification for an alert and log the attempt.

    This is a standalone async function (not a MonitoringService method) so it
    can open its own DB session via get_db_context(). This avoids the
    DetachedInstanceError that occurs when a fire-and-forget asyncio task
    outlives the session that created the Alert object.

    Args:
        alert_id: ID of the alert to notify about

    Returns:
        NotificationLog entry or None if skipped
    """
    with get_db_context() as db:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            logger.error(f"Alert {alert_id} not found for notification")
            return None

        settings = get_settings()

        # Check if notifications are enabled
        if not settings.notification_enabled:
            logger.debug(f"Notifications disabled, skipping alert {alert.id}")
            return None

        # Check deduplication cooldown
        if not should_notify(alert.alert_type, alert.job_type):
            logger.debug(f"Notification for {alert.alert_type}/{alert.job_type} in cooldown")
            return None

        # Create notification log entry
        log_entry = NotificationLog(
            channel=NotificationChannel.TEAMS.value,
            severity=alert.severity,
            alert_id=alert.id,
            job_type=alert.job_type,
            tenant_id=alert.tenant_id,
            title=alert.title,
            message=alert.message,
            status="pending",
            sent_at=datetime.now(UTC),
            metadata_json=json.dumps(
                {
                    "alert_type": alert.alert_type,
                    "details": alert.details_json,
                }
            ),
        )
        db.add(log_entry)
        db.commit()

        # Build notification with actionable links
        error_message = None
        if alert.details_json:
            try:
                details = json.loads(alert.details_json)
                error_message = details.get("error_message")
            except json.JSONDecodeError:
                pass

        notification = Notification(
            title=alert.title,
            message=alert.message,
            severity=Severity(alert.severity),
            channel=NotificationChannel.TEAMS,
            alert_id=alert.id,
            job_type=alert.job_type,
            tenant_id=alert.tenant_id,
            error_message=error_message,
            dashboard_url=create_dashboard_url(alert.job_type),
            retry_url=create_retry_url(alert.job_type or "resources", alert.tenant_id),
            metadata={
                "alert_type": alert.alert_type,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            },
        )

        # Send the notification
        result = await send_notification(notification)

        # Update log entry with result
        log_entry.status = "sent" if result.get("success") else "failed"
        log_entry.response_status = str(result.get("status_code", ""))
        log_entry.response_body = result.get("error") or json.dumps(result)

        if result.get("success"):
            log_entry.delivered_at = datetime.now(UTC)
            record_notification_sent(alert.alert_type, alert.job_type)
            logger.info(f"Notification sent for alert {alert.id}: {alert.title}")
        else:
            logger.error(f"Notification failed for alert {alert.id}: {result.get('error')}")

        db.commit()
        return log_entry
