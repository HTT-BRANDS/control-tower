"""Unit tests for Riverside compliance scheduler.

Tests for the riverside_scheduler module covering:
- MFA compliance checks
- Deadline tracking
- Maturity regression detection
- Threat escalation monitoring
- Scheduled job wrappers
- Notification integration
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.alerts.deadline_alerts import AlertLevel, DeadlineAlert
from app.core.riverside_scheduler import (
    DEADLINE_ALERT_INTERVALS,
    MFA_ADMIN_TARGET_PERCENTAGE,
    MFA_USER_TARGET_PERCENTAGE,
    THREAT_SCORE_CRITICAL_THRESHOLD,
    THREAT_SCORE_HIGH_THRESHOLD,
    MaturityRegression,
    MFAComplianceResult,
    ThreatEscalation,
    check_maturity_regressions,
    check_mfa_compliance,
    check_requirement_deadlines,
    check_threat_escalations,
    init_riverside_scheduler,
    run_daily_compliance_report,
    run_deadline_check,
    run_maturity_regression_check,
    run_mfa_compliance_check,
    run_threat_escalation_check,
    send_deadline_alerts,
    send_maturity_regression_alerts,
    send_mfa_compliance_alerts,
    send_threat_escalation_alerts,
    trigger_manual_check,
)
from app.models.riverside import (
    RequirementStatus,
    RiversideCompliance,
    RiversideMFA,
    RiversideRequirement,
    RiversideThreatData,
)


class TestMFAComplianceResult:
    """Tests for MFAComplianceResult dataclass."""

    def test_creation(self):
        """Test creating MFAComplianceResult."""
        result = MFAComplianceResult(
            tenant_id="test-tenant",
            user_mfa_percentage=85.0,
            admin_mfa_percentage=95.0,
            user_target_met=False,
            admin_target_met=False,
            total_users=100,
            mfa_enrolled_users=85,
            admin_accounts_total=10,
            admin_accounts_mfa=9,
        )
        assert result.tenant_id == "test-tenant"
        assert result.user_mfa_percentage == 85.0
        assert not result.user_target_met
        assert not result.admin_target_met


class TestDeadlineAlert:
    """Tests for DeadlineAlert dataclass."""

    def test_overdue_alert(self):
        """Test creating overdue alert."""
        alert = DeadlineAlert(
            requirement_id="REQ-001",
            tenant_id="test-tenant",
            title="Test Requirement",
            days_until_deadline=-5,
            alert_level=AlertLevel.CRITICAL,
            is_overdue=True,
            alert_stage=None,
        )
        assert alert.is_overdue
        assert alert.days_until_deadline == -5
        assert alert.alert_stage is None

    def test_approaching_alert(self):
        """Test creating approaching deadline alert."""
        alert = DeadlineAlert(
            requirement_id="REQ-002",
            tenant_id="test-tenant",
            title="Test Requirement",
            days_until_deadline=7,
            alert_level=AlertLevel.CRITICAL,
            is_overdue=False,
            alert_stage=7,
        )
        assert not alert.is_overdue
        assert alert.days_until_deadline == 7
        assert alert.alert_stage == 7


class TestMaturityRegression:
    """Tests for MaturityRegression dataclass."""

    def test_creation(self):
        """Test creating MaturityRegression."""
        regression = MaturityRegression(
            tenant_id="test-tenant",
            previous_score=3.5,
            current_score=3.0,
            score_drop=0.5,
            last_assessment_date=datetime.utcnow(),
        )
        assert regression.tenant_id == "test-tenant"
        assert regression.previous_score == 3.5
        assert regression.current_score == 3.0
        assert regression.score_drop == 0.5


class TestThreatEscalation:
    """Tests for ThreatEscalation dataclass."""

    def test_critical_threat(self):
        """Test creating critical threat escalation."""
        escalation = ThreatEscalation(
            tenant_id="test-tenant",
            threat_score=9.5,
            vulnerability_count=50,
            malicious_domain_alerts=5,
            is_critical=True,
            snapshot_date=datetime.utcnow(),
        )
        assert escalation.is_critical
        assert escalation.threat_score == 9.5

    def test_high_threat(self):
        """Test creating high (non-critical) threat escalation."""
        escalation = ThreatEscalation(
            tenant_id="test-tenant",
            threat_score=7.5,
            vulnerability_count=20,
            malicious_domain_alerts=2,
            is_critical=False,
            snapshot_date=datetime.utcnow(),
        )
        assert not escalation.is_critical
        assert escalation.threat_score == 7.5


class TestConstants:
    """Tests for scheduler constants."""

    def test_mfa_thresholds(self):
        """Test MFA threshold constants."""
        assert MFA_USER_TARGET_PERCENTAGE == 95.0
        assert MFA_ADMIN_TARGET_PERCENTAGE == 100.0

    def test_threat_thresholds(self):
        """Test threat score thresholds."""
        assert THREAT_SCORE_HIGH_THRESHOLD == 7.0
        assert THREAT_SCORE_CRITICAL_THRESHOLD == 9.0

    def test_deadline_intervals(self):
        """Test deadline alert intervals."""
        assert DEADLINE_ALERT_INTERVALS == [90, 60, 30, 14, 7, 1]


class TestCheckMFACompliance:
    """Tests for check_mfa_compliance function."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.mark.asyncio
    async def test_no_violations(self, mock_db):
        """Test when all tenants meet MFA targets."""
        # Create mock MFA records that meet targets
        mfa_record = MagicMock(spec=RiversideMFA)
        mfa_record.tenant_id = "tenant-1"
        mfa_record.mfa_coverage_percentage = 96.0  # Above 95%
        mfa_record.admin_mfa_percentage = 100.0  # At 100%
        mfa_record.total_users = 100
        mfa_record.mfa_enrolled_users = 96
        mfa_record.admin_accounts_total = 5
        mfa_record.admin_accounts_mfa = 5

        # Setup mock query chain
        mock_subquery = MagicMock()
        mock_subquery.c = MagicMock()

        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = mock_subquery
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = [mfa_record]

        mock_db.query.return_value = mock_query

        results = await check_mfa_compliance(mock_db)

        # Should return empty list since targets are met
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_user_mfa_violation(self, mock_db):
        """Test detection of user MFA below threshold."""
        mfa_record = MagicMock(spec=RiversideMFA)
        mfa_record.tenant_id = "tenant-1"
        mfa_record.mfa_coverage_percentage = 85.0  # Below 95%
        mfa_record.admin_mfa_percentage = 100.0  # At 100%
        mfa_record.total_users = 100
        mfa_record.mfa_enrolled_users = 85
        mfa_record.admin_accounts_total = 5
        mfa_record.admin_accounts_mfa = 5

        mock_subquery = MagicMock()
        mock_subquery.c = MagicMock()

        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = mock_subquery
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = [mfa_record]

        mock_db.query.return_value = mock_query

        results = await check_mfa_compliance(mock_db)

        assert len(results) == 1
        assert results[0].tenant_id == "tenant-1"
        assert not results[0].user_target_met
        assert results[0].admin_target_met

    @pytest.mark.asyncio
    async def test_admin_mfa_violation(self, mock_db):
        """Test detection of admin MFA below threshold."""
        mfa_record = MagicMock(spec=RiversideMFA)
        mfa_record.tenant_id = "tenant-1"
        mfa_record.mfa_coverage_percentage = 96.0  # Above 95%
        mfa_record.admin_mfa_percentage = 80.0  # Below 100%
        mfa_record.total_users = 100
        mfa_record.mfa_enrolled_users = 96
        mfa_record.admin_accounts_total = 5
        mfa_record.admin_accounts_mfa = 4

        mock_subquery = MagicMock()
        mock_subquery.c = MagicMock()

        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = mock_subquery
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = [mfa_record]

        mock_db.query.return_value = mock_query

        results = await check_mfa_compliance(mock_db)

        assert len(results) == 1
        assert results[0].tenant_id == "tenant-1"
        assert results[0].user_target_met
        assert not results[0].admin_target_met

    @pytest.mark.asyncio
    async def test_multiple_tenants(self, mock_db):
        """Test checking multiple tenants with mixed compliance."""
        # Tenant 1: compliant
        mfa1 = MagicMock(spec=RiversideMFA)
        mfa1.tenant_id = "tenant-1"
        mfa1.mfa_coverage_percentage = 96.0
        mfa1.admin_mfa_percentage = 100.0
        mfa1.total_users = 100
        mfa1.mfa_enrolled_users = 96
        mfa1.admin_accounts_total = 5
        mfa1.admin_accounts_mfa = 5

        # Tenant 2: non-compliant
        mfa2 = MagicMock(spec=RiversideMFA)
        mfa2.tenant_id = "tenant-2"
        mfa2.mfa_coverage_percentage = 85.0
        mfa2.admin_mfa_percentage = 90.0
        mfa2.total_users = 100
        mfa2.mfa_enrolled_users = 85
        mfa2.admin_accounts_total = 10
        mfa2.admin_accounts_mfa = 9

        mock_subquery = MagicMock()
        mock_subquery.c = MagicMock()

        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = mock_subquery
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = [mfa1, mfa2]

        mock_db.query.return_value = mock_query

        results = await check_mfa_compliance(mock_db)

        # Only tenant-2 should be in results
        assert len(results) == 1
        assert results[0].tenant_id == "tenant-2"


class TestCheckRequirementDeadlines:
    """Tests for check_requirement_deadlines function."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.mark.asyncio
    async def test_no_requirements(self, mock_db):
        """Test when there are no requirements."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        overdue, approaching = await check_requirement_deadlines(mock_db)

        assert len(overdue) == 0
        assert len(approaching) == 0

    @pytest.mark.asyncio
    async def test_overdue_requirement(self, mock_db):
        """Test detection of overdue requirements."""
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "REQ-001"
        req.tenant_id = "tenant-1"
        req.title = "Test Requirement"
        req.status = RequirementStatus.IN_PROGRESS
        req.due_date = date.today() - timedelta(days=5)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [req]
        mock_db.query.return_value = mock_query

        overdue, approaching = await check_requirement_deadlines(mock_db)

        assert len(overdue) == 1
        assert len(approaching) == 0
        assert overdue[0].requirement_id == "REQ-001"
        assert overdue[0].is_overdue
        assert overdue[0].days_until_deadline == -5

    @pytest.mark.asyncio
    async def test_approaching_deadlines(self, mock_db):
        """Test detection of approaching deadlines at alert intervals."""
        # Create requirements at different alert intervals
        requirements = []
        for days in [7, 14, 30]:
            req = MagicMock(spec=RiversideRequirement)
            req.requirement_id = f"REQ-{days}"
            req.tenant_id = "tenant-1"
            req.title = f"Requirement due in {days} days"
            req.status = RequirementStatus.IN_PROGRESS
            req.due_date = date.today() + timedelta(days=days)
            requirements.append(req)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = requirements
        mock_db.query.return_value = mock_query

        overdue, approaching = await check_requirement_deadlines(mock_db)

        assert len(overdue) == 0
        assert len(approaching) == 3
        alert_days = [a.days_until_deadline for a in approaching]
        assert 7 in alert_days
        assert 14 in alert_days
        assert 30 in alert_days

    @pytest.mark.asyncio
    async def test_non_alert_interval_ignored(self, mock_db):
        """Test that non-alert intervals are ignored."""
        # 25 days is not in DEADLINE_ALERT_INTERVALS
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "REQ-025"
        req.tenant_id = "tenant-1"
        req.title = "Requirement due in 25 days"
        req.status = RequirementStatus.IN_PROGRESS
        req.due_date = date.today() + timedelta(days=25)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [req]
        mock_db.query.return_value = mock_query

        overdue, approaching = await check_requirement_deadlines(mock_db)

        assert len(overdue) == 0
        assert len(approaching) == 0

    @pytest.mark.asyncio
    async def test_completed_requirement_ignored(self, mock_db):
        """Test that completed requirements are ignored."""
        # Completed requirements should be filtered out by the database query
        # Since we mock the query chain, we simulate an empty result after filtering
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []  # Empty after filtering out completed
        mock_db.query.return_value = mock_query

        overdue, approaching = await check_requirement_deadlines(mock_db)

        assert len(overdue) == 0
        assert len(approaching) == 0


class TestCheckMaturityRegressions:
    """Tests for check_maturity_regressions function."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.mark.asyncio
    async def test_no_regressions(self, mock_db):
        """Test when no regressions exist."""
        # Create records showing improvement
        comp1 = MagicMock(spec=RiversideCompliance)
        comp1.tenant_id = "tenant-1"
        comp1.overall_maturity_score = 3.5
        comp1.last_assessment_date = datetime.utcnow()

        comp2 = MagicMock(spec=RiversideCompliance)
        comp2.tenant_id = "tenant-1"
        comp2.overall_maturity_score = 3.0
        comp2.last_assessment_date = datetime.utcnow() - timedelta(days=7)

        mock_query = MagicMock()
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [comp1, comp2]
        mock_db.query.return_value = mock_query

        results = await check_maturity_regressions(mock_db)

        # No regressions - scores improved
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_regression_detected(self, mock_db):
        """Test detection of maturity regression."""
        # Current score is lower than previous
        current = MagicMock(spec=RiversideCompliance)
        current.tenant_id = "tenant-1"
        current.overall_maturity_score = 2.5
        current.last_assessment_date = datetime.utcnow()

        previous = MagicMock(spec=RiversideCompliance)
        previous.tenant_id = "tenant-1"
        previous.overall_maturity_score = 3.0
        previous.last_assessment_date = datetime.utcnow() - timedelta(days=7)

        mock_query = MagicMock()
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [current, previous]
        mock_db.query.return_value = mock_query

        results = await check_maturity_regressions(mock_db)

        assert len(results) == 1
        assert results[0].tenant_id == "tenant-1"
        assert results[0].previous_score == 3.0
        assert results[0].current_score == 2.5
        assert results[0].score_drop == 0.5

    @pytest.mark.asyncio
    async def test_multiple_tenants_regression(self, mock_db):
        """Test detecting regressions across multiple tenants."""
        # Tenant 1: regression
        t1_current = MagicMock(spec=RiversideCompliance)
        t1_current.tenant_id = "tenant-1"
        t1_current.overall_maturity_score = 2.0
        t1_current.last_assessment_date = datetime.utcnow()

        t1_previous = MagicMock(spec=RiversideCompliance)
        t1_previous.tenant_id = "tenant-1"
        t1_previous.overall_maturity_score = 3.0
        t1_previous.last_assessment_date = datetime.utcnow() - timedelta(days=7)

        # Tenant 2: no regression
        t2_current = MagicMock(spec=RiversideCompliance)
        t2_current.tenant_id = "tenant-2"
        t2_current.overall_maturity_score = 4.0
        t2_current.last_assessment_date = datetime.utcnow()

        t2_previous = MagicMock(spec=RiversideCompliance)
        t2_previous.tenant_id = "tenant-2"
        t2_previous.overall_maturity_score = 3.5
        t2_previous.last_assessment_date = datetime.utcnow() - timedelta(days=7)

        mock_query = MagicMock()
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [t1_current, t1_previous, t2_current, t2_previous]
        mock_db.query.return_value = mock_query

        results = await check_maturity_regressions(mock_db)

        # Only tenant-1 should be in results
        assert len(results) == 1
        assert results[0].tenant_id == "tenant-1"

    @pytest.mark.asyncio
    async def test_single_record_per_tenant(self, mock_db):
        """Test that tenants with single records don't cause regressions."""
        comp = MagicMock(spec=RiversideCompliance)
        comp.tenant_id = "tenant-1"
        comp.overall_maturity_score = 3.0
        comp.last_assessment_date = datetime.utcnow()

        mock_query = MagicMock()
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [comp]
        mock_db.query.return_value = mock_query

        results = await check_maturity_regressions(mock_db)

        # No comparison possible with single record
        assert len(results) == 0


class TestCheckThreatEscalations:
    """Tests for check_threat_escalations function."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.mark.asyncio
    async def test_no_threats(self, mock_db):
        """Test when no high threats exist."""
        mock_subquery = MagicMock()
        mock_subquery.c = MagicMock()

        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = mock_subquery
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        results = await check_threat_escalations(mock_db)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_high_threat_detected(self, mock_db):
        """Test detection of high (non-critical) threat."""
        threat = MagicMock(spec=RiversideThreatData)
        threat.tenant_id = "tenant-1"
        threat.threat_score = 7.5  # Above HIGH threshold, below CRITICAL
        threat.vulnerability_count = 25
        threat.malicious_domain_alerts = 3
        threat.snapshot_date = datetime.utcnow()

        mock_subquery = MagicMock()
        mock_subquery.c = MagicMock()

        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = mock_subquery
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [threat]
        mock_db.query.return_value = mock_query

        results = await check_threat_escalations(mock_db)

        assert len(results) == 1
        assert results[0].tenant_id == "tenant-1"
        assert results[0].threat_score == 7.5
        assert not results[0].is_critical

    @pytest.mark.asyncio
    async def test_critical_threat_detected(self, mock_db):
        """Test detection of critical threat."""
        threat = MagicMock(spec=RiversideThreatData)
        threat.tenant_id = "tenant-1"
        threat.threat_score = 9.5  # Above CRITICAL threshold
        threat.vulnerability_count = 50
        threat.malicious_domain_alerts = 10
        threat.snapshot_date = datetime.utcnow()

        mock_subquery = MagicMock()
        mock_subquery.c = MagicMock()

        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = mock_subquery
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [threat]
        mock_db.query.return_value = mock_query

        results = await check_threat_escalations(mock_db)

        assert len(results) == 1
        assert results[0].is_critical
        assert results[0].threat_score == 9.5

    @pytest.mark.asyncio
    async def test_low_threat_ignored(self, mock_db):
        """Test that low threats are ignored."""
        threat = MagicMock(spec=RiversideThreatData)
        threat.tenant_id = "tenant-1"
        threat.threat_score = 5.0  # Below HIGH threshold
        threat.vulnerability_count = 10
        threat.malicious_domain_alerts = 1
        threat.snapshot_date = datetime.utcnow()

        mock_subquery = MagicMock()
        mock_subquery.c = MagicMock()

        mock_query = MagicMock()
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = mock_subquery
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        results = await check_threat_escalations(mock_db)

        assert len(results) == 0


class TestSendAlerts:
    """Tests for alert sending functions."""

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.should_notify")
    @patch("app.core.riverside_scheduler.send_notification")
    @patch("app.core.riverside_scheduler.record_notification_sent")
    async def test_send_mfa_compliance_alerts(self, mock_record, mock_send, mock_should_notify):
        """Test sending MFA compliance alerts."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": True}

        non_compliant = [
            MFAComplianceResult(
                tenant_id="tenant-1",
                user_mfa_percentage=85.0,
                admin_mfa_percentage=100.0,
                user_target_met=False,
                admin_target_met=True,
                total_users=100,
                mfa_enrolled_users=85,
                admin_accounts_total=5,
                admin_accounts_mfa=5,
            )
        ]

        results = await send_mfa_compliance_alerts(non_compliant)

        assert len(results) == 1
        assert results[0]["success"] is True
        mock_send.assert_called_once()
        mock_record.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.should_notify")
    @patch("app.core.riverside_scheduler.send_notification")
    async def test_send_mfa_alerts_deduplication(self, mock_send, mock_should_notify):
        """Test that MFA alerts respect deduplication."""
        mock_should_notify.return_value = False  # In cooldown

        non_compliant = [
            MFAComplianceResult(
                tenant_id="tenant-1",
                user_mfa_percentage=85.0,
                admin_mfa_percentage=100.0,
                user_target_met=False,
                admin_target_met=True,
                total_users=100,
                mfa_enrolled_users=85,
                admin_accounts_total=5,
                admin_accounts_mfa=5,
            )
        ]

        results = await send_mfa_compliance_alerts(non_compliant)

        # No notifications sent due to deduplication
        assert len(results) == 0
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.should_notify")
    @patch("app.core.riverside_scheduler.send_notification")
    @patch("app.core.riverside_scheduler.record_notification_sent")
    async def test_send_deadline_alerts(self, mock_record, mock_send, mock_should_notify):
        """Test sending deadline alerts."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": True}

        overdue = [
            DeadlineAlert(
                requirement_id="REQ-001",
                tenant_id="tenant-1",
                title="Overdue Req",
                days_until_deadline=-5,
                alert_level=AlertLevel.CRITICAL,
                is_overdue=True,
                alert_stage=None,
            )
        ]
        approaching = [
            DeadlineAlert(
                requirement_id="REQ-002",
                tenant_id="tenant-1",
                title="Approaching Req",
                days_until_deadline=7,
                alert_level=AlertLevel.CRITICAL,
                is_overdue=False,
                alert_stage=7,
            )
        ]

        results = await send_deadline_alerts(overdue, approaching)

        # Should send 2 notifications (1 overdue + 1 approaching)
        assert len(results) == 2
        assert mock_send.call_count == 2

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.should_notify")
    @patch("app.core.riverside_scheduler.send_notification")
    @patch("app.core.riverside_scheduler.record_notification_sent")
    async def test_send_maturity_regression_alerts(
        self, mock_record, mock_send, mock_should_notify
    ):
        """Test sending maturity regression alerts."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": True}

        regressions = [
            MaturityRegression(
                tenant_id="tenant-1",
                previous_score=3.5,
                current_score=3.0,
                score_drop=0.5,
                last_assessment_date=datetime.utcnow(),
            )
        ]

        results = await send_maturity_regression_alerts(regressions)

        assert len(results) == 1
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.should_notify")
    @patch("app.core.riverside_scheduler.send_notification")
    @patch("app.core.riverside_scheduler.record_notification_sent")
    async def test_send_threat_escalation_alerts(self, mock_record, mock_send, mock_should_notify):
        """Test sending threat escalation alerts."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": True}

        escalations = [
            ThreatEscalation(
                tenant_id="tenant-1",
                threat_score=9.5,
                vulnerability_count=50,
                malicious_domain_alerts=5,
                is_critical=True,
                snapshot_date=datetime.utcnow(),
            )
        ]

        results = await send_threat_escalation_alerts(escalations)

        assert len(results) == 1
        assert results[0]["success"] is True


class TestRunScheduledJobs:
    """Tests for scheduled job wrapper functions."""

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.check_mfa_compliance")
    @patch("app.core.riverside_scheduler.send_mfa_compliance_alerts")
    async def test_run_mfa_compliance_check_success(self, mock_send, mock_check):
        """Test successful MFA compliance check run."""
        mock_check.return_value = [
            MFAComplianceResult(
                tenant_id="tenant-1",
                user_mfa_percentage=85.0,
                admin_mfa_percentage=100.0,
                user_target_met=False,
                admin_target_met=True,
                total_users=100,
                mfa_enrolled_users=85,
                admin_accounts_total=5,
                admin_accounts_mfa=5,
            )
        ]
        mock_send.return_value = [{"success": True}]

        result = await run_mfa_compliance_check()

        assert result["success"] is True
        assert result["violations_found"] == 1
        assert result["notifications_sent"] == 1
        assert "tenant-1" in result["tenants"]

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.check_mfa_compliance")
    async def test_run_mfa_compliance_check_error(self, mock_check):
        """Test MFA compliance check handles errors gracefully."""
        mock_check.side_effect = Exception("Database error")

        result = await run_mfa_compliance_check()

        assert result["success"] is False
        assert "error" in result
        assert result["violations_found"] == 0

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.check_requirement_deadlines")
    @patch("app.core.riverside_scheduler.send_deadline_alerts")
    async def test_run_deadline_check_success(self, mock_send, mock_check):
        """Test successful deadline check run."""
        overdue = [
            DeadlineAlert(
                requirement_id="REQ-001",
                tenant_id="tenant-1",
                title="Overdue",
                days_until_deadline=-5,
                alert_level=AlertLevel.CRITICAL,
                is_overdue=True,
                alert_stage=None,
            )
        ]
        approaching = [
            DeadlineAlert(
                requirement_id="REQ-002",
                tenant_id="tenant-1",
                title="Approaching",
                days_until_deadline=7,
                alert_level=AlertLevel.CRITICAL,
                is_overdue=False,
                alert_stage=7,
            )
        ]
        mock_check.return_value = (overdue, approaching)
        mock_send.return_value = [{"success": True}, {"success": True}]

        result = await run_deadline_check()

        assert result["success"] is True
        assert result["overdue_count"] == 1
        assert result["approaching_count"] == 1
        assert result["notifications_sent"] == 2

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.check_maturity_regressions")
    @patch("app.core.riverside_scheduler.send_maturity_regression_alerts")
    async def test_run_maturity_check_success(self, mock_send, mock_check):
        """Test successful maturity regression check run."""
        mock_check.return_value = [
            MaturityRegression(
                tenant_id="tenant-1",
                previous_score=3.5,
                current_score=3.0,
                score_drop=0.5,
                last_assessment_date=datetime.utcnow(),
            )
        ]
        mock_send.return_value = [{"success": True}]

        result = await run_maturity_regression_check()

        assert result["success"] is True
        assert result["regressions_found"] == 1
        assert "tenant-1" in result["regressed_tenants"]

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.check_threat_escalations")
    @patch("app.core.riverside_scheduler.send_threat_escalation_alerts")
    async def test_run_threat_check_success(self, mock_send, mock_check):
        """Test successful threat escalation check run."""
        mock_check.return_value = [
            ThreatEscalation(
                tenant_id="tenant-1",
                threat_score=9.5,
                vulnerability_count=50,
                malicious_domain_alerts=5,
                is_critical=True,
                snapshot_date=datetime.utcnow(),
            )
        ]
        mock_send.return_value = [{"success": True}]

        result = await run_threat_escalation_check()

        assert result["success"] is True
        assert result["escalations_found"] == 1
        assert len(result["threats"]) == 1
        assert result["threats"][0]["critical"] is True

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.run_mfa_compliance_check")
    @patch("app.core.riverside_scheduler.run_deadline_check")
    @patch("app.core.riverside_scheduler.run_maturity_regression_check")
    @patch("app.core.riverside_scheduler.run_threat_escalation_check")
    async def test_run_daily_compliance_report(
        self, mock_threat, mock_maturity, mock_deadline, mock_mfa
    ):
        """Test daily compliance report runs all checks."""
        mock_mfa.return_value = {"success": True, "violations_found": 1}
        mock_deadline.return_value = {
            "success": True,
            "overdue_count": 0,
            "approaching_count": 2,
        }
        mock_maturity.return_value = {"success": True, "regressions_found": 0}
        mock_threat.return_value = {"success": True, "escalations_found": 1}

        result = await run_daily_compliance_report()

        assert result["success"] is True
        assert result["total_issues"] == 4  # 1 + 0 + 2 + 0 + 1
        assert "mfa_check" in result
        assert "deadline_check" in result
        assert "maturity_check" in result
        assert "threat_check" in result


class TestSchedulerInitialization:
    """Tests for scheduler initialization."""

    def test_init_riverside_scheduler(self):
        """Test scheduler initialization creates jobs."""
        scheduler = init_riverside_scheduler()

        assert scheduler is not None

        # Check that all expected jobs are scheduled
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "riverside_mfa_check" in job_ids
        assert "riverside_daily_report" in job_ids
        assert "riverside_weekly_deadlines" in job_ids
        assert "riverside_weekly_maturity" in job_ids
        assert "riverside_weekly_threats" in job_ids


class TestTriggerManualCheck:
    """Tests for manual check triggering."""

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.run_mfa_compliance_check")
    async def test_trigger_mfa_check(self, mock_run):
        """Test triggering MFA check manually."""
        mock_run.return_value = {"success": True, "violations_found": 0}

        result = await trigger_manual_check("mfa")

        assert result["success"] is True
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.run_deadline_check")
    async def test_trigger_deadlines_check(self, mock_run):
        """Test triggering deadlines check manually."""
        mock_run.return_value = {"success": True, "overdue_count": 0}

        result = await trigger_manual_check("deadlines")

        assert result["success"] is True
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.run_maturity_regression_check")
    async def test_trigger_maturity_check(self, mock_run):
        """Test triggering maturity check manually."""
        mock_run.return_value = {"success": True, "regressions_found": 0}

        result = await trigger_manual_check("maturity")

        assert result["success"] is True
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.run_threat_escalation_check")
    async def test_trigger_threats_check(self, mock_run):
        """Test triggering threats check manually."""
        mock_run.return_value = {"success": True, "escalations_found": 0}

        result = await trigger_manual_check("threats")

        assert result["success"] is True
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.core.riverside_scheduler.run_daily_compliance_report")
    async def test_trigger_daily_check(self, mock_run):
        """Test triggering daily report manually."""
        mock_run.return_value = {"success": True, "total_issues": 0}

        result = await trigger_manual_check("daily")

        assert result["success"] is True
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_invalid_check_type(self):
        """Test triggering invalid check type returns error."""
        result = await trigger_manual_check("invalid")

        assert result["success"] is False
        assert "error" in result
        assert "valid_types" in result
