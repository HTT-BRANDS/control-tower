"""Unit tests for RiversideService.

Basic unit tests that verify the RiversideService class structure
and basic functionality without requiring complex database mocking.
"""

from datetime import date
from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.orm import Session

from app.api.services.riverside_service import (
    RIVERSIDE_DEADLINE,
    TARGET_MATURITY_SCORE,
    RiversideService,
)


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return create_autospec(Session, instance=True)


@pytest.fixture
def riverside_service(mock_db):
    """Create a RiversideService instance with mock db."""
    return RiversideService(db=mock_db)


class TestRiversideService:
    """Test suite for RiversideService."""

    def test_initialization(self, mock_db):
        """Test RiversideService initializes correctly with database session."""
        service = RiversideService(db=mock_db)
        assert service.db is mock_db

    def test_riverside_deadline_constant(self):
        """Test that Riverside deadline constant is set correctly."""
        assert RIVERSIDE_DEADLINE == date(2026, 7, 8)
        assert isinstance(RIVERSIDE_DEADLINE, date)

    def test_target_maturity_score_constant(self):
        """Test that target maturity score constant is set correctly."""
        assert TARGET_MATURITY_SCORE == 3.0
        assert isinstance(TARGET_MATURITY_SCORE, float)

    def test_get_compliance_summary_basic(self, riverside_service, mock_db):
        """Test get_compliance_summary method exists and queries database."""
        # Setup mock to return empty list
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        # Call the method - should not raise error
        result = riverside_service.get_compliance_summary()

        # Assert query was made
        mock_db.query.assert_called_once()
        assert result == []

    def test_get_compliance_summary_with_tenant_filter(self, riverside_service, mock_db):
        """Test get_compliance_summary with tenant filter."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        # Call with tenant_id filter
        result = riverside_service.get_compliance_summary(tenant_id="test-tenant")

        # Assert filter was applied
        mock_query.filter.assert_called_once()
        assert result == []

    def test_get_mfa_stats_basic(self, riverside_service, mock_db):
        """Test get_mfa_stats method exists and queries database."""
        # Setup mock for subquery pattern
        mock_query = MagicMock()
        mock_subquery = MagicMock()
        mock_subquery.c = MagicMock()

        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = mock_subquery
        mock_query.join.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        mock_db.query.return_value = mock_query

        # Call the method - should not raise error
        result = riverside_service.get_mfa_stats()

        # Assert query was made
        mock_db.query.assert_called()
        assert result == []

    def test_get_mfa_stats_with_tenant_filter(self, riverside_service, mock_db):
        """Test get_mfa_stats with tenant filter."""
        mock_query = MagicMock()
        mock_subquery = MagicMock()
        mock_subquery.c = MagicMock()

        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = mock_subquery
        mock_query.join.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        mock_db.query.return_value = mock_query

        # Call with tenant_id filter
        result = riverside_service.get_mfa_stats(tenant_id="test-tenant")

        # Assert query was made
        mock_db.query.assert_called()
        assert result == []

    def test_get_dashboard_data_empty_tenants(self, riverside_service, mock_db):
        """Test get_dashboard_data handles no tenants gracefully."""
        # Setup mock to return empty tenant list
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        # Call the method
        from app.schemas.riverside import RiversideDashboardSummary
        result = riverside_service.get_dashboard_data()

        # Assert
        assert result is not None
        assert isinstance(result, RiversideDashboardSummary)
        assert result.total_tenants == 0
