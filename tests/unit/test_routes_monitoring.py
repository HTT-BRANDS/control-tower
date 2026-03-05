"""Unit tests for monitoring API routes.

Tests monitoring endpoints:
- GET /api/v1/monitoring/performance
- GET /api/v1/monitoring/cache
- GET /api/v1/monitoring/sync-jobs
- GET /api/v1/monitoring/queries
- POST /api/v1/monitoring/reset
- GET /api/v1/monitoring/health
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import User
from app.core.database import get_db
from app.main import app
from app.models.tenant import Tenant, UserTenant


@pytest.fixture
def test_db_session(db_session):
    """Database session with test data."""
    tenant = Tenant(
        id=str(uuid.uuid4()),
        tenant_id="monitoring-tenant-123",
        name="Monitoring Test Tenant",
        subscription_id="sub-monitoring-123",
        is_active=True,
    )
    db_session.add(tenant)
    
    user_tenant = UserTenant(
        id=str(uuid.uuid4()),
        user_id="user:monitoring-admin",
        tenant_id=tenant.id,
        role="admin",
        is_active=True,
        can_view_costs=True,
        can_manage_resources=True,
        can_manage_compliance=True,
        granted_by="test",
        granted_at=datetime.utcnow(),
    )
    db_session.add(user_tenant)
    
    db_session.commit()
    return db_session


@pytest.fixture
def client_with_db(test_db_session):
    """Test client with database override."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    """Mock authenticated admin user."""
    return User(
        id="user-monitoring-admin",
        email="admin@monitoring.test",
        name="Monitoring Admin",
        roles=["admin"],
        tenant_ids=["monitoring-tenant-123"],
        is_active=True,
        auth_provider="azure_ad",
    )


def test_get_performance_metrics_success(client_with_db, mock_user):
    """Test getting comprehensive performance metrics."""
    mock_dashboard = {
        "cache": {
            "hit_rate_percent": 85.5,
            "total_hits": 1000,
            "total_misses": 150,
        },
        "sync_jobs": {
            "total_jobs": 42,
            "avg_duration_seconds": 12.5,
            "failed_jobs": 2,
        },
        "queries": {
            "total_queries": 5000,
            "slow_queries": 25,
            "avg_duration_ms": 45.2,
        },
    }
    
    with patch("app.api.routes.monitoring.get_current_user", return_value=mock_user):
        with patch("app.api.routes.monitoring.get_performance_dashboard", return_value=mock_dashboard):
            response = client_with_db.get("/api/v1/monitoring/performance")
    
    assert response.status_code == 200
    data = response.json()
    assert data["cache"]["hit_rate_percent"] == 85.5
    assert data["sync_jobs"]["total_jobs"] == 42
    assert data["queries"]["total_queries"] == 5000


def test_get_cache_metrics_success(client_with_db, mock_user):
    """Test getting cache metrics."""
    mock_cache_stats = {
        "hit_rate_percent": 82.3,
        "total_hits": 850,
        "total_misses": 183,
        "evictions": 12,
        "cache_size_mb": 256.5,
    }
    
    with patch("app.api.routes.monitoring.get_current_user", return_value=mock_user):
        with patch("app.api.routes.monitoring.get_cache_stats", return_value=mock_cache_stats):
            response = client_with_db.get("/api/v1/monitoring/cache")
    
    assert response.status_code == 200
    data = response.json()
    assert data["hit_rate_percent"] == 82.3
    assert data["total_hits"] == 850
    assert data["cache_size_mb"] == 256.5


def test_get_sync_job_metrics_all_jobs(client_with_db, mock_user):
    """Test getting all sync job metrics."""
    mock_sync_metrics = [
        {
            "job_id": "sync-1",
            "job_type": "resources",
            "tenant_id": "monitoring-tenant-123",
            "duration_seconds": 15.2,
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "job_id": "sync-2",
            "job_type": "costs",
            "tenant_id": "monitoring-tenant-123",
            "duration_seconds": 8.7,
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
        },
    ]
    
    with patch("app.api.routes.monitoring.get_current_user", return_value=mock_user):
        with patch("app.api.routes.monitoring.performance_monitor") as mock_monitor:
            mock_monitor.get_sync_metrics.return_value = mock_sync_metrics
            
            response = client_with_db.get("/api/v1/monitoring/sync-jobs")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["job_type"] == "resources"


def test_get_sync_job_metrics_with_filters(client_with_db, mock_user):
    """Test getting sync job metrics with filters."""
    mock_sync_metrics = [
        {
            "job_id": "sync-1",
            "job_type": "resources",
            "tenant_id": "monitoring-tenant-123",
            "duration_seconds": 15.2,
            "status": "completed",
        },
    ]
    
    with patch("app.api.routes.monitoring.get_current_user", return_value=mock_user):
        with patch("app.api.routes.monitoring.performance_monitor") as mock_monitor:
            mock_monitor.get_sync_metrics.return_value = mock_sync_metrics
            
            response = client_with_db.get(
                "/api/v1/monitoring/sync-jobs?job_type=resources&tenant_id=monitoring-tenant-123&limit=50"
            )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    mock_monitor.get_sync_metrics.assert_called_once_with("resources", "monitoring-tenant-123", 50)


def test_get_query_metrics_all(client_with_db, mock_user):
    """Test getting all query metrics."""
    mock_query_metrics = [
        {
            "query_id": "q-1",
            "query_type": "SELECT",
            "duration_ms": 25.5,
            "slow": False,
            "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "query_id": "q-2",
            "query_type": "JOIN",
            "duration_ms": 250.8,
            "slow": True,
            "timestamp": datetime.utcnow().isoformat(),
        },
    ]
    
    with patch("app.api.routes.monitoring.get_current_user", return_value=mock_user):
        with patch("app.api.routes.monitoring.performance_monitor") as mock_monitor:
            mock_monitor.get_query_metrics.return_value = mock_query_metrics
            
            response = client_with_db.get("/api/v1/monitoring/queries")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_query_metrics_slow_only(client_with_db, mock_user):
    """Test getting only slow query metrics."""
    mock_slow_queries = [
        {
            "query_id": "q-2",
            "query_type": "JOIN",
            "duration_ms": 250.8,
            "slow": True,
        },
    ]
    
    with patch("app.api.routes.monitoring.get_current_user", return_value=mock_user):
        with patch("app.api.routes.monitoring.performance_monitor") as mock_monitor:
            mock_monitor.get_query_metrics.return_value = mock_slow_queries
            
            response = client_with_db.get("/api/v1/monitoring/queries?slow_only=true&limit=50")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["slow"] is True
    mock_monitor.get_query_metrics.assert_called_once_with(True, 50)


def test_reset_performance_metrics_success(client_with_db, mock_user):
    """Test resetting performance metrics."""
    with patch("app.api.routes.monitoring.get_current_user", return_value=mock_user):
        with patch("app.api.routes.monitoring.reset_metrics") as mock_reset:
            response = client_with_db.post("/api/v1/monitoring/reset")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Metrics reset successfully"
    mock_reset.assert_called_once()


def test_health_check_good_cache(client_with_db, mock_user):
    """Test health check with good cache performance."""
    mock_cache_stats = {
        "hit_rate_percent": 88.5,
    }
    
    mock_perf_summary = {
        "sync_jobs": {
            "total_jobs": 100,
        },
        "queries": {
            "total_queries": 5000,
            "slow_queries": 10,
        },
    }
    
    with patch("app.api.routes.monitoring.get_current_user", return_value=mock_user):
        with patch("app.api.routes.monitoring.get_cache_stats", return_value=mock_cache_stats):
            with patch("app.api.routes.monitoring.get_performance_dashboard", return_value=mock_perf_summary):
                response = client_with_db.get("/api/v1/monitoring/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["cache_health"] == "good"  # > 80%
    assert data["cache_hit_rate"] == 88.5


def test_health_check_poor_cache(client_with_db, mock_user):
    """Test health check with poor cache performance."""
    mock_cache_stats = {
        "hit_rate_percent": 45.0,
    }
    
    mock_perf_summary = {
        "sync_jobs": {
            "total_jobs": 50,
        },
        "queries": {
            "total_queries": 1000,
            "slow_queries": 100,
        },
    }
    
    with patch("app.api.routes.monitoring.get_current_user", return_value=mock_user):
        with patch("app.api.routes.monitoring.get_cache_stats", return_value=mock_cache_stats):
            with patch("app.api.routes.monitoring.get_performance_dashboard", return_value=mock_perf_summary):
                response = client_with_db.get("/api/v1/monitoring/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["cache_health"] == "poor"  # < 50%
    assert data["slow_queries"] == 100
