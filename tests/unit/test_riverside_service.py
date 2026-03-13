"""Unit tests for RiversideService.

Tests the RiversideService class from the package
app/api/services/riverside_service/__init__.py which delegates
to query functions and sync operations.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.api.services.riverside_service import (
    RIVERSIDE_DEADLINE,
    TARGET_MATURITY_SCORE,
    RiversideService,
)
from app.api.services.riverside_service.constants import FINANCIAL_RISK


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def service(mock_db):
    """Create a RiversideService instance with mock db."""
    return RiversideService(db=mock_db)


@pytest.fixture(autouse=True)
def disable_cache():
    """Disable caching so query functions are always called."""
    with patch("app.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.cache_enabled = False
        yield


class TestRiversideServiceInit:
    """Test RiversideService initialization."""

    def test_initialization(self, mock_db):
        """Test RiversideService initializes correctly with database session."""
        svc = RiversideService(db=mock_db)
        assert svc.db is mock_db

    def test_riverside_deadline_constant(self):
        """Test that Riverside deadline constant is set correctly."""
        from datetime import date

        assert RIVERSIDE_DEADLINE == date(2026, 7, 8)

    def test_target_maturity_score_constant(self):
        """Test that target maturity score constant is set correctly."""
        assert TARGET_MATURITY_SCORE == 3.0

    def test_financial_risk_constant(self):
        """Test that financial risk constant is set correctly."""
        assert FINANCIAL_RISK == "$4M"


class TestRiversideServiceQueries:
    """Test RiversideService query methods."""

    @pytest.mark.asyncio
    async def test_get_riverside_summary(self, service):
        """Test get_riverside_summary delegates to query function."""
        expected = {"days_until_deadline": 365, "financial_risk": "$4M"}
        with patch(
            "app.api.services.riverside_service.get_riverside_summary",
            return_value=expected,
        ) as mock_query:
            result = await service.get_riverside_summary()
            mock_query.assert_called_once_with(service.db)
            assert result == expected

    @pytest.mark.asyncio
    async def test_get_mfa_status(self, service):
        """Test get_mfa_status delegates to query function."""
        expected = {"summary": {"total_users": 100}, "tenants": []}
        with patch(
            "app.api.services.riverside_service.get_mfa_status",
            return_value=expected,
        ) as mock_query:
            result = await service.get_mfa_status()
            mock_query.assert_called_once_with(service.db)
            assert result == expected

    @pytest.mark.asyncio
    async def test_get_maturity_scores(self, service):
        """Test get_maturity_scores delegates to query function."""
        expected = {"summary": {"overall_average": 2.5}, "tenants": []}
        with patch(
            "app.api.services.riverside_service.get_maturity_scores",
            return_value=expected,
        ) as mock_query:
            result = await service.get_maturity_scores()
            mock_query.assert_called_once_with(service.db)
            assert result == expected

    def test_get_requirements_no_filters(self, service):
        """Test get_requirements with no filters."""
        expected = {"requirements": [], "stats": {"total": 0}}
        with patch(
            "app.api.services.riverside_service.get_requirements",
            return_value=expected,
        ) as mock_query:
            result = service.get_requirements()
            mock_query.assert_called_once_with(service.db, None, None, None)
            assert result == expected

    def test_get_requirements_with_filters(self, service):
        """Test get_requirements with category, priority, status filters."""
        expected = {"requirements": [], "stats": {"total": 0}}
        with patch(
            "app.api.services.riverside_service.get_requirements",
            return_value=expected,
        ) as mock_query:
            result = service.get_requirements(category="IAM", priority="P0", status="not_started")
            mock_query.assert_called_once_with(service.db, "IAM", "P0", "not_started")
            assert result == expected

    @pytest.mark.asyncio
    async def test_get_gaps(self, service):
        """Test get_gaps delegates to query function."""
        expected = {"summary": {"total_gaps": 0}, "immediate_action": []}
        with patch(
            "app.api.services.riverside_service.get_gaps",
            return_value=expected,
        ) as mock_query:
            result = await service.get_gaps()
            mock_query.assert_called_once_with(service.db)
            assert result == expected


class TestRiversideServiceSync:
    """Test RiversideService sync methods."""

    @pytest.mark.asyncio
    async def test_sync_all(self, service):
        """Test sync_all runs all sync operations."""
        with (
            patch.object(
                service, "sync_riverside_mfa", new_callable=AsyncMock, return_value={"status": "ok"}
            ),
            patch.object(
                service,
                "sync_riverside_device_compliance",
                new_callable=AsyncMock,
                return_value={"status": "ok"},
            ),
            patch.object(
                service,
                "sync_riverside_requirements",
                new_callable=AsyncMock,
                return_value={"status": "ok"},
            ),
            patch.object(
                service,
                "sync_riverside_maturity_scores",
                new_callable=AsyncMock,
                return_value={"status": "ok"},
            ),
        ):
            result = await service.sync_all()
            assert "mfa" in result
            assert "device_compliance" in result
            assert "requirements" in result
            assert "maturity_scores" in result
