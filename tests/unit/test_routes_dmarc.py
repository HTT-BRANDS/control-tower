"""Unit tests for DMARC/DKIM API routes.

Tests all DMARC endpoints with FastAPI TestClient:
- GET /api/v1/dmarc/summary
- GET /api/v1/dmarc/records
- GET /api/v1/dmarc/dkim
- GET /api/v1/dmarc/score
- GET /api/v1/dmarc/trends
- GET /api/v1/dmarc/alerts
- POST /api/v1/dmarc/alerts/{alert_id}/acknowledge
- POST /api/v1/dmarc/sync
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.dmarc import DMARCAlert, DMARCRecord, DKIMRecord


@pytest.fixture
def test_db_session(db_session):
    """Database session with test DMARC data."""
    # Create test DMARC record
    dmarc_record = DMARCRecord(
        id=str(uuid.uuid4()),
        tenant_id="dmarc-tenant-123",
        domain="example.com",
        policy="quarantine",
        pct=100,
        rua="mailto:dmarc@example.com",
        adkim="r",
        aspf="r",
        is_valid=True,
        synced_at=datetime.utcnow(),
    )
    db_session.add(dmarc_record)
    
    # Create test DKIM record
    dkim_record = DKIMRecord(
        id=str(uuid.uuid4()),
        tenant_id="dmarc-tenant-123",
        domain="example.com",
        selector="selector1",
        is_enabled=True,
        key_size=2048,
        key_type="rsa",
        is_aligned=True,
        last_rotated=datetime.utcnow() - timedelta(days=90),
        synced_at=datetime.utcnow(),
    )
    db_session.add(dkim_record)
    
    # Create test alert
    alert = DMARCAlert(
        id=str(uuid.uuid4()),
        tenant_id="dmarc-tenant-123",
        alert_type="policy_change",
        severity="warning",
        domain="example.com",
        message="DMARC policy changed from reject to quarantine",
        is_acknowledged=False,
        created_at=datetime.utcnow(),
    )
    db_session.add(alert)
    
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
def mock_dmarc_service():
    """Mock DMARCService with common responses."""
    service = MagicMock()
    service.get_dmarc_summary.return_value = {
        "total_domains": 15,
        "dmarc_enabled": 12,
        "dmarc_policy_reject": 8,
        "dmarc_policy_quarantine": 3,
        "dmarc_policy_none": 1,
        "dkim_enabled": 10,
        "average_security_score": 78.5,
        "total_alerts": 3,
        "critical_alerts": 1,
    }
    service.get_domain_security_score.return_value = 85.0
    service.get_compliance_trends.return_value = [
        {"date": "2024-01-01", "compliance_rate": 95.5, "messages_total": 10000},
        {"date": "2024-01-02", "compliance_rate": 96.2, "messages_total": 12000},
    ]
    service.acknowledge_alert.return_value = MagicMock(
        id="alert-123",
        is_acknowledged=True,
        acknowledged_by="admin@example.com",
        acknowledged_at=datetime.utcnow(),
    )
    service.sync_dmarc_records.return_value = [{"domain": "example.com"}]
    service.sync_dkim_records.return_value = [{"domain": "example.com"}]
    service.sync_dmarc_reports.return_value = [{"report_id": "rep-123"}]
    service.invalidate_cache.return_value = None
    return service


# ============================================================================
# GET /api/v1/dmarc/summary Tests
# ============================================================================

class TestDMARCSummaryEndpoint:
    """Tests for GET /api/v1/dmarc/summary endpoint."""
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_summary_returns_aggregated_stats(self, mock_service_cls, client_with_db, mock_dmarc_service):
        """Summary endpoint returns aggregated DMARC/DKIM statistics."""
        mock_service_cls.return_value = mock_dmarc_service
        
        response = client_with_db.get("/api/v1/dmarc/summary")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_domains"] == 15
        assert data["dmarc_enabled"] == 12
        assert data["average_security_score"] == 78.5
        assert data["total_alerts"] == 3
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_summary_accepts_tenant_filter(self, mock_service_cls, client_with_db, mock_dmarc_service):
        """Summary endpoint accepts tenant_id query parameter."""
        mock_service_cls.return_value = mock_dmarc_service
        
        response = client_with_db.get("/api/v1/dmarc/summary?tenant_id=test-123")
        
        assert response.status_code == 200
        # Service should be called with tenant_id parameter
        mock_dmarc_service.get_dmarc_summary.assert_called_once_with("test-123")


# ============================================================================
# GET /api/v1/dmarc/records Tests
# ============================================================================

class TestDMARCRecordsEndpoint:
    """Tests for GET /api/v1/dmarc/records endpoint."""
    
    def test_records_returns_dmarc_configs(self, client_with_db):
        """Records endpoint returns DMARC DNS records for tenant."""
        response = client_with_db.get("/api/v1/dmarc/records?tenant_id=dmarc-tenant-123")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        record = data[0]
        assert "domain" in record
        assert "policy" in record
        assert record["domain"] == "example.com"
        assert record["policy"] == "quarantine"
    
    def test_records_requires_tenant_id(self, client_with_db):
        """Records endpoint returns 400 when tenant_id is missing."""
        response = client_with_db.get("/api/v1/dmarc/records")
        
        assert response.status_code == 400
        assert "tenant_id is required" in response.json()["detail"]
    
    def test_records_validates_empty_tenant_id(self, client_with_db):
        """Records endpoint validates non-empty tenant_id."""
        response = client_with_db.get("/api/v1/dmarc/records?tenant_id=")
        
        assert response.status_code == 400


# ============================================================================
# GET /api/v1/dmarc/dkim Tests
# ============================================================================

class TestDKIMRecordsEndpoint:
    """Tests for GET /api/v1/dmarc/dkim endpoint."""
    
    def test_dkim_returns_signing_configs(self, client_with_db):
        """DKIM endpoint returns DKIM signing configurations."""
        response = client_with_db.get("/api/v1/dmarc/dkim?tenant_id=dmarc-tenant-123")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        record = data[0]
        assert "domain" in record
        assert "selector" in record
        assert "is_enabled" in record
        assert record["key_size"] == 2048
        assert record["is_aligned"] is True
    
    def test_dkim_includes_rotation_info(self, client_with_db):
        """DKIM endpoint includes key rotation information."""
        response = client_with_db.get("/api/v1/dmarc/dkim?tenant_id=dmarc-tenant-123")
        
        assert response.status_code == 200
        data = response.json()
        record = data[0]
        assert "is_stale" in record
        assert "days_since_rotation" in record
        assert "next_rotation_due" in record


# ============================================================================
# GET /api/v1/dmarc/score Tests
# ============================================================================

class TestDomainSecurityScoreEndpoint:
    """Tests for GET /api/v1/dmarc/score endpoint."""
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_score_returns_security_rating(self, mock_service_cls, client_with_db, mock_dmarc_service):
        """Score endpoint returns calculated security score."""
        mock_service_cls.return_value = mock_dmarc_service
        
        response = client_with_db.get("/api/v1/dmarc/score?tenant_id=test-123")
        
        assert response.status_code == 200
        data = response.json()
        assert "security_score" in data
        assert "grade" in data
        assert "status" in data
        assert data["security_score"] == 85.0
        assert data["grade"] == "B"
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_score_includes_recommendations(self, mock_service_cls, client_with_db, mock_dmarc_service):
        """Score endpoint includes actionable recommendations."""
        mock_service_cls.return_value = mock_dmarc_service
        
        response = client_with_db.get("/api/v1/dmarc/score?tenant_id=test-123")
        
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)


# ============================================================================
# GET /api/v1/dmarc/trends Tests
# ============================================================================

class TestComplianceTrendsEndpoint:
    """Tests for GET /api/v1/dmarc/trends endpoint."""
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_trends_returns_historical_data(self, mock_service_cls, client_with_db, mock_dmarc_service):
        """Trends endpoint returns historical compliance data."""
        mock_service_cls.return_value = mock_dmarc_service
        
        response = client_with_db.get("/api/v1/dmarc/trends?days=30")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["compliance_rate"] == 95.5
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_trends_validates_days_parameter(self, mock_service_cls, client_with_db, mock_dmarc_service):
        """Trends endpoint validates days parameter range."""
        mock_service_cls.return_value = mock_dmarc_service
        
        # Valid range: 1-90 days
        response = client_with_db.get("/api/v1/dmarc/trends?days=100")
        
        # Should be rejected by FastAPI validation
        assert response.status_code == 422


# ============================================================================
# GET /api/v1/dmarc/alerts Tests
# ============================================================================

class TestDMARCAlertsEndpoint:
    """Tests for GET /api/v1/dmarc/alerts endpoint."""
    
    def test_alerts_returns_security_alerts(self, client_with_db):
        """Alerts endpoint returns active DMARC/DKIM alerts."""
        response = client_with_db.get("/api/v1/dmarc/alerts")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        alert = data[0]
        assert "alert_type" in alert
        assert "severity" in alert
        assert "message" in alert
    
    def test_alerts_filters_by_tenant(self, client_with_db):
        """Alerts endpoint filters by tenant_id parameter."""
        response = client_with_db.get("/api/v1/dmarc/alerts?tenant_id=dmarc-tenant-123")
        
        assert response.status_code == 200
        data = response.json()
        # All alerts should be for the specified tenant
        for alert in data:
            assert alert["tenant_id"] == "dmarc-tenant-123"
    
    def test_alerts_filters_by_severity(self, client_with_db):
        """Alerts endpoint filters by severity parameter."""
        response = client_with_db.get("/api/v1/dmarc/alerts?severity=warning")
        
        assert response.status_code == 200
        data = response.json()
        for alert in data:
            assert alert["severity"] == "warning"


# ============================================================================
# POST /api/v1/dmarc/alerts/{alert_id}/acknowledge Tests
# ============================================================================

class TestAcknowledgeAlertEndpoint:
    """Tests for POST /api/v1/dmarc/alerts/{alert_id}/acknowledge endpoint."""
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_acknowledge_marks_alert_as_acknowledged(self, mock_service_cls, client_with_db, mock_dmarc_service):
        """Acknowledge endpoint marks alert as acknowledged."""
        mock_service_cls.return_value = mock_dmarc_service
        
        response = client_with_db.post(
            "/api/v1/dmarc/alerts/alert-123/acknowledge?user=admin@example.com"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_acknowledged"] is True
        assert data["acknowledged_by"] == "admin@example.com"
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_acknowledge_returns_404_for_nonexistent_alert(self, mock_service_cls, client_with_db):
        """Acknowledge endpoint returns 404 for nonexistent alert."""
        service = MagicMock()
        service.acknowledge_alert.return_value = None
        mock_service_cls.return_value = service
        
        response = client_with_db.post(
            "/api/v1/dmarc/alerts/nonexistent-id/acknowledge?user=admin@example.com"
        )
        
        assert response.status_code == 404


# ============================================================================
# POST /api/v1/dmarc/sync Tests
# ============================================================================

class TestDMARCSyncEndpoint:
    """Tests for POST /api/v1/dmarc/sync endpoint."""
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_sync_triggers_dmarc_data_refresh(self, mock_service_cls, client_with_db, mock_dmarc_service):
        """Sync endpoint triggers manual data synchronization."""
        mock_service_cls.return_value = mock_dmarc_service
        
        response = client_with_db.post(
            "/api/v1/dmarc/sync?tenant_id=test-123&sync_type=all"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["sync_type"] == "all"
        assert "records_synced" in data
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_sync_supports_selective_sync_types(self, mock_service_cls, client_with_db, mock_dmarc_service):
        """Sync endpoint supports selective sync types (dmarc, dkim, reports)."""
        mock_service_cls.return_value = mock_dmarc_service
        
        # Sync only DKIM records
        response = client_with_db.post(
            "/api/v1/dmarc/sync?tenant_id=test-123&sync_type=dkim"
        )
        
        assert response.status_code == 200
        # Should only call sync_dkim_records, not others
        mock_dmarc_service.sync_dkim_records.assert_called_once()
    
    @patch("app.api.routes.dmarc.DMARCService")
    def test_sync_invalidates_cache_after_completion(self, mock_service_cls, client_with_db, mock_dmarc_service):
        """Sync endpoint invalidates cache after successful sync."""
        mock_service_cls.return_value = mock_dmarc_service
        
        response = client_with_db.post(
            "/api/v1/dmarc/sync?tenant_id=test-123&sync_type=all"
        )
        
        assert response.status_code == 200
        # Cache should be invalidated
        mock_dmarc_service.invalidate_cache.assert_called_once_with("test-123")
    
    def test_sync_requires_tenant_id(self, client_with_db):
        """Sync endpoint returns 400 when tenant_id is missing."""
        response = client_with_db.post("/api/v1/dmarc/sync")
        
        assert response.status_code == 400
