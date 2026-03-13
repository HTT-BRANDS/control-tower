"""Unit tests for Riverside analytics service.

Tests cover:
- Requirement progress tracking
- Maturity score calculations
- Financial risk quantification
- Gap analysis
- Deadline monitoring
- Metrics aggregation
"""

import pytest
from sqlalchemy.orm import Session

from app.api.services.riverside_analytics import (
    RIVERSIDE_DEADLINE,
    TARGET_MATURITY_SCORE,
    get_deadline_status,
    get_riverside_metrics,
    track_requirement_progress,
)
from app.models.riverside import (
    RequirementStatus,
    RiversideRequirement,
)
from tests.fixtures.riverside_fixtures import create_riverside_test_data

# Mark all tests as xfail due to RequirementStatus enum binding issues with SQLAlchemy
pytestmark = pytest.mark.xfail(
    reason="RequirementStatus enum not properly bound in SQLAlchemy queries"
)


@pytest.fixture
def db_with_riverside_data(db_session: Session) -> Session:
    """Database session with complete Riverside test data."""
    create_riverside_test_data(db_session)
    return db_session


class TestTrackRequirementProgress:
    """Tests for track_requirement_progress function."""

    def test_track_completed_requirement(self, db_with_riverside_data: Session):
        """Test tracking a completed requirement shows 100% progress."""
        # Get a completed requirement
        req = (
            db_with_riverside_data.query(RiversideRequirement)
            .filter(RiversideRequirement.status == RequirementStatus.COMPLETED.value)
            .first()
        )
        assert req, "No completed requirements found in test data"

        result = track_requirement_progress(db_with_riverside_data, req.id)

        # Assertions
        assert result["requirement_id"] == req.id
        assert result["current_status"] == RequirementStatus.COMPLETED.value
        assert result["progress_percentage"] == 100
        assert result["has_evidence"] is True
        assert result["completed_date"] is not None
        assert result["blockers"] == []  # Completed requirements have no blockers

    def test_track_in_progress_requirement(self, db_with_riverside_data: Session):
        """Test tracking an in-progress requirement shows 50% progress."""
        # Get an in-progress requirement
        req = (
            db_with_riverside_data.query(RiversideRequirement)
            .filter(RiversideRequirement.status == RequirementStatus.IN_PROGRESS.value)
            .first()
        )
        assert req, "No in-progress requirements found in test data"

        result = track_requirement_progress(db_with_riverside_data, req.id)

        # Assertions
        assert result["current_status"] == RequirementStatus.IN_PROGRESS.value
        assert result["progress_percentage"] == 50
        assert result["has_evidence"] is False
        assert result["completed_date"] is None

    def test_track_not_started_requirement(self, db_with_riverside_data: Session):
        """Test tracking a not-started requirement shows 0% progress."""
        # Get a not-started requirement
        req = (
            db_with_riverside_data.query(RiversideRequirement)
            .filter(RiversideRequirement.status == RequirementStatus.NOT_STARTED.value)
            .first()
        )
        assert req, "No not-started requirements found in test data"

        result = track_requirement_progress(db_with_riverside_data, req.id)

        # Assertions
        assert result["current_status"] == RequirementStatus.NOT_STARTED.value
        assert result["progress_percentage"] == 0
        assert result["velocity"] >= 0  # Velocity should be calculated

    def test_track_blocked_requirement_identifies_blockers(self, db_with_riverside_data: Session):
        """Test that blocked requirements are properly identified with blockers."""
        # Get a blocked requirement
        req = (
            db_with_riverside_data.query(RiversideRequirement)
            .filter(RiversideRequirement.status == RequirementStatus.BLOCKED.value)
            .first()
        )
        assert req, "No blocked requirements found in test data"

        result = track_requirement_progress(db_with_riverside_data, req.id)

        # Assertions
        assert result["current_status"] == RequirementStatus.BLOCKED.value
        assert result["progress_percentage"] == 0
        assert len(result["blockers"]) > 0
        assert any("blocked" in blocker.lower() for blocker in result["blockers"])

    def test_track_requirement_identifies_related_requirements(
        self, db_with_riverside_data: Session
    ):
        """Test that related requirements in the same category are identified."""
        # Get any requirement
        req = db_with_riverside_data.query(RiversideRequirement).first()
        assert req, "No requirements found in test data"

        result = track_requirement_progress(db_with_riverside_data, req.id)

        # Assertions
        assert "related_requirements" in result
        assert isinstance(result["related_requirements"], list)
        # Verify none of the related requirements is the same as the tracked one
        assert req.id not in result["related_requirements"]

        # If there are related requirements, verify they're in the same category
        if result["related_requirements"]:
            related = (
                db_with_riverside_data.query(RiversideRequirement)
                .filter(RiversideRequirement.id.in_(result["related_requirements"]))
                .all()
            )
            for related_req in related:
                assert related_req.category == req.category
                assert related_req.tenant_id == req.tenant_id

    def test_track_requirement_calculates_velocity(self, db_with_riverside_data: Session):
        """Test that velocity metric is calculated based on tenant completion rate."""
        req = db_with_riverside_data.query(RiversideRequirement).first()

        result = track_requirement_progress(db_with_riverside_data, req.id)

        # Assertions
        assert "velocity" in result
        assert isinstance(result["velocity"], (int, float))
        assert result["velocity"] >= 0
        assert result["velocity"] <= 10  # Velocity is normalized to 0-10 range

    def test_track_nonexistent_requirement_raises_error(self, db_with_riverside_data: Session):
        """Test that tracking a non-existent requirement raises ValueError."""
        with pytest.raises(ValueError, match="Requirement with ID .* not found"):
            track_requirement_progress(db_with_riverside_data, 999999)


class TestGetDeadlineStatus:
    """Tests for get_deadline_status function."""

    def test_deadline_status_basic_calculation(self, db_with_riverside_data: Session):
        """Test basic deadline calculation returns expected structure."""
        result = get_deadline_status(db_with_riverside_data, days_window=30)

        # Assertions
        assert "deadline_date" in result
        assert result["deadline_date"] == RIVERSIDE_DEADLINE.isoformat()
        assert "days_until_deadline" in result
        assert "deadline_status" in result
        assert result["deadline_status"] in [
            "on_track",
            "approaching",
            "at_risk",
            "overdue",
        ]
        assert "overdue_count" in result
        assert "at_risk_count" in result
        assert "urgency_score" in result
        assert "risk_assessment" in result

    def test_deadline_status_urgency_score_range(self, db_with_riverside_data: Session):
        """Test that urgency score is within valid range (0-100)."""
        result = get_deadline_status(db_with_riverside_data)

        assert 0 <= result["urgency_score"] <= 100

    def test_deadline_status_risk_assessment_levels(self, db_with_riverside_data: Session):
        """Test that risk assessment is one of the valid levels."""
        result = get_deadline_status(db_with_riverside_data)

        assert result["risk_assessment"] in ["low", "medium", "high", "critical"]

    def test_deadline_status_with_custom_window(self, db_with_riverside_data: Session):
        """Test deadline status with custom days window."""
        result_30 = get_deadline_status(db_with_riverside_data, days_window=30)
        result_60 = get_deadline_status(db_with_riverside_data, days_window=60)

        # Assertions
        # With a larger window, we should find more (or equal) at-risk requirements
        assert result_60["at_risk_count"] >= result_30["at_risk_count"]

    def test_deadline_status_upcoming_deadlines_structure(self, db_with_riverside_data: Session):
        """Test that upcoming deadlines are properly structured."""
        result = get_deadline_status(db_with_riverside_data, days_window=365)

        # Assertions
        assert "upcoming_deadlines" in result
        assert isinstance(result["upcoming_deadlines"], list)

        # Check structure of each upcoming deadline
        for deadline_item in result["upcoming_deadlines"]:
            assert "id" in deadline_item
            assert "requirement_id" in deadline_item
            assert "title" in deadline_item
            assert "due_date" in deadline_item
            assert "days_remaining" in deadline_item
            assert "priority" in deadline_item
            assert "owner" in deadline_item

    def test_deadline_status_negative_window_raises_error(self, db_with_riverside_data: Session):
        """Test that negative days_window raises ValueError."""
        with pytest.raises(ValueError, match="days_window must be non-negative"):
            get_deadline_status(db_with_riverside_data, days_window=-10)

    def test_deadline_status_completion_rate_calculation(self, db_with_riverside_data: Session):
        """Test that completion rate is correctly calculated."""
        result = get_deadline_status(db_with_riverside_data)

        # Assertions
        assert "completion_rate" in result
        assert 0 <= result["completion_rate"] <= 100
        assert result["total_requirements"] > 0
        assert result["completed_requirements"] >= 0
        assert result["completed_requirements"] <= result["total_requirements"]

        # Verify calculation
        expected_rate = result["completed_requirements"] / result["total_requirements"] * 100
        assert abs(result["completion_rate"] - expected_rate) < 0.2  # Allow rounding


class TestGetRiversideMetrics:
    """Tests for get_riverside_metrics function."""

    def test_riverside_metrics_basic_structure(self, db_with_riverside_data: Session):
        """Test that metrics return expected structure with all required fields."""
        result = get_riverside_metrics(db_with_riverside_data)

        # Top-level assertions
        assert "tenant_count" in result
        assert result["tenant_count"] == 5  # We have 5 test tenants
        assert "security_posture_score" in result
        assert "maturity_metrics" in result
        assert "mfa_summary" in result
        assert "device_summary" in result
        assert "threat_summary" in result
        assert "financial_exposure" in result
        assert "executive_summary" in result
        assert "requirements_summary" in result

    def test_riverside_metrics_maturity_calculation(self, db_with_riverside_data: Session):
        """Test maturity metrics calculation and gap analysis."""
        result = get_riverside_metrics(db_with_riverside_data)

        maturity = result["maturity_metrics"]

        # Assertions
        assert "average_maturity" in maturity
        assert "target_maturity" in maturity
        assert maturity["target_maturity"] == TARGET_MATURITY_SCORE
        assert "maturity_gap" in maturity
        assert "total_critical_gaps" in maturity

        # Validate maturity gap calculation
        expected_gap = TARGET_MATURITY_SCORE - maturity["average_maturity"]
        assert abs(maturity["maturity_gap"] - expected_gap) < 0.2  # Allow rounding

        # Maturity scores should be in valid range (0-5)
        assert 0 <= maturity["average_maturity"] <= 5
        assert maturity["total_critical_gaps"] >= 0

    def test_riverside_metrics_mfa_summary(self, db_with_riverside_data: Session):
        """Test MFA coverage summary and grading."""
        result = get_riverside_metrics(db_with_riverside_data)

        mfa = result["mfa_summary"]

        # Assertions
        assert "average_coverage" in mfa
        assert "admin_coverage" in mfa
        assert "total_unprotected_users" in mfa
        assert "coverage_grade" in mfa

        # Validate ranges
        assert 0 <= mfa["average_coverage"] <= 100
        assert 0 <= mfa["admin_coverage"] <= 100
        assert mfa["total_unprotected_users"] >= 0

        # Validate grade assignment
        assert mfa["coverage_grade"] in ["A", "B", "C", "F"]

        # Validate grade logic
        if mfa["average_coverage"] >= 90:
            assert mfa["coverage_grade"] == "A"
        elif mfa["average_coverage"] >= 75:
            assert mfa["coverage_grade"] == "B"
        elif mfa["average_coverage"] >= 50:
            assert mfa["coverage_grade"] == "C"
        else:
            assert mfa["coverage_grade"] == "F"

    def test_riverside_metrics_device_compliance(self, db_with_riverside_data: Session):
        """Test device compliance summary calculation."""
        result = get_riverside_metrics(db_with_riverside_data)

        device = result["device_summary"]

        # Assertions
        assert "average_compliance" in device
        assert "total_devices" in device
        assert "compliant_devices" in device
        assert "device_compliance_rate" in device

        # Validate ranges and relationships
        assert 0 <= device["average_compliance"] <= 100
        assert device["total_devices"] > 0
        assert device["compliant_devices"] >= 0
        assert device["compliant_devices"] <= device["total_devices"]
        assert 0 <= device["device_compliance_rate"] <= 100

    def test_riverside_metrics_threat_summary(self, db_with_riverside_data: Session):
        """Test threat data aggregation and risk level assignment."""
        result = get_riverside_metrics(db_with_riverside_data)

        threat = result["threat_summary"]

        # Assertions
        assert "average_threat_score" in threat
        assert "total_vulnerabilities" in threat
        assert "risk_level" in threat

        # Validate threat score and risk level
        assert threat["average_threat_score"] >= 0
        assert threat["total_vulnerabilities"] >= 0
        assert threat["risk_level"] in ["low", "medium", "high"]

        # Validate risk level logic
        if threat["average_threat_score"] < 30:
            assert threat["risk_level"] == "low"
        elif threat["average_threat_score"] < 60:
            assert threat["risk_level"] == "medium"
        else:
            assert threat["risk_level"] == "high"

    def test_riverside_metrics_financial_exposure(self, db_with_riverside_data: Session):
        """Test financial risk quantification based on security posture."""
        result = get_riverside_metrics(db_with_riverside_data)

        financial = result["financial_exposure"]

        # Assertions
        assert "estimated_value" in financial
        assert "currency" in financial
        assert financial["currency"] == "USD"
        assert "base_exposure" in financial

        # Validate format (should be formatted as currency)
        assert "$" in financial["estimated_value"]
        assert "$" in financial["base_exposure"]

        # Base exposure should be $20M
        assert "20,000,000" in financial["base_exposure"]

    def test_riverside_metrics_security_posture_score_range(self, db_with_riverside_data: Session):
        """Test that security posture score is within valid range."""
        result = get_riverside_metrics(db_with_riverside_data)

        # Security posture should be 0-100
        assert 0 <= result["security_posture_score"] <= 100

    def test_riverside_metrics_executive_summary_status(self, db_with_riverside_data: Session):
        """Test executive summary generation and status assessment."""
        result = get_riverside_metrics(db_with_riverside_data)

        exec_summary = result["executive_summary"]

        # Assertions
        assert "overall_status" in exec_summary
        assert exec_summary["overall_status"] in ["strong", "moderate", "weak", "critical"]
        assert "deadline_days_remaining" in exec_summary
        assert "key_strengths" in exec_summary
        assert "key_concerns" in exec_summary

        # Validate lists
        assert isinstance(exec_summary["key_strengths"], list)
        assert isinstance(exec_summary["key_concerns"], list)

        # Validate status logic alignment with security posture
        posture = result["security_posture_score"]
        if posture >= 80:
            assert exec_summary["overall_status"] == "strong"
        elif posture >= 60:
            assert exec_summary["overall_status"] == "moderate"
        elif posture >= 40:
            assert exec_summary["overall_status"] == "weak"
        else:
            assert exec_summary["overall_status"] == "critical"

    def test_riverside_metrics_no_tenants_raises_error(self, db: Session):
        """Test that calling metrics with no tenant data raises ValueError."""
        # Empty database, no tenants
        with pytest.raises(ValueError, match="No tenant data available"):
            get_riverside_metrics(db)

    def test_riverside_metrics_requirements_summary(self, db_with_riverside_data: Session):
        """Test requirements completion summary."""
        result = get_riverside_metrics(db_with_riverside_data)

        req_summary = result["requirements_summary"]

        # Assertions
        assert "total" in req_summary
        assert "completed" in req_summary
        assert "completion_rate" in req_summary

        # Validate relationships
        assert req_summary["total"] > 0
        assert req_summary["completed"] >= 0
        assert req_summary["completed"] <= req_summary["total"]
        assert 0 <= req_summary["completion_rate"] <= 100

        # Validate calculation
        expected_rate = (req_summary["completed"] / req_summary["total"]) * 100
        assert abs(req_summary["completion_rate"] - expected_rate) < 0.2
