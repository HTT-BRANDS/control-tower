"""Unit tests for QuotaService — RM-007."""

from unittest.mock import MagicMock, patch


class TestQuotaItem:
    def test_utilization_pct_normal(self):
        from app.api.services.quota_service import QuotaItem

        item = QuotaItem(name="cores", current_value=50, limit=100)
        assert item.utilization_pct == 50.0

    def test_utilization_pct_zero_limit(self):
        from app.api.services.quota_service import QuotaItem

        item = QuotaItem(name="cores", current_value=0, limit=0)
        assert item.utilization_pct == 0.0

    def test_status_ok(self):
        from app.api.services.quota_service import QuotaItem

        item = QuotaItem(name="cores", current_value=10, limit=100)
        assert item.status == "ok"

    def test_status_warning_at_75_pct(self):
        from app.api.services.quota_service import QuotaItem

        item = QuotaItem(name="cores", current_value=75, limit=100)
        assert item.status == "warning"

    def test_status_critical_at_90_pct(self):
        from app.api.services.quota_service import QuotaItem

        item = QuotaItem(name="cores", current_value=90, limit=100)
        assert item.status == "critical"

    def test_status_critical_at_100_pct(self):
        from app.api.services.quota_service import QuotaItem

        item = QuotaItem(name="cores", current_value=100, limit=100)
        assert item.status == "critical"

    def test_available_calculation(self):
        from app.api.services.quota_service import QuotaItem

        item = QuotaItem(name="cores", current_value=30, limit=100)
        assert item.available == 70

    def test_available_never_negative(self):
        from app.api.services.quota_service import QuotaItem

        item = QuotaItem(name="cores", current_value=110, limit=100)
        assert item.available == 0

    def test_to_dict_structure(self):
        from app.api.services.quota_service import QuotaItem

        item = QuotaItem(
            name="vCPUs",
            current_value=5,
            limit=20,
            provider="compute",
            location="eastus",
        )
        d = item.to_dict()
        assert d["name"] == "vCPUs"
        assert d["utilization_pct"] == 25.0
        assert d["status"] == "ok"
        assert "available" in d


class TestQuotaSummary:
    def _make_summary(self, sub="sub-1", tenant="t-1", quotas=None):
        from app.api.services.quota_service import QuotaSummary

        s = QuotaSummary(subscription_id=sub, tenant_id=tenant, location="eastus")
        if quotas:
            s.quotas = quotas
        return s

    def test_overall_status_ok_with_empty_quotas(self):
        s = self._make_summary()
        assert s.overall_status == "ok"

    def test_overall_status_critical(self):
        from app.api.services.quota_service import QuotaItem

        s = self._make_summary()
        s.quotas = [QuotaItem(name="cores", current_value=92, limit=100)]
        assert s.overall_status == "critical"
        assert s.critical_count == 1

    def test_overall_status_warning(self):
        from app.api.services.quota_service import QuotaItem

        s = self._make_summary()
        s.quotas = [QuotaItem(name="cores", current_value=77, limit=100)]
        assert s.overall_status == "warning"
        assert s.warning_count == 1

    def test_overall_status_error(self):
        s = self._make_summary()
        s.error = "Permission denied"
        assert s.overall_status == "error"

    def test_to_dict_structure(self):
        s = self._make_summary()
        d = s.to_dict()
        assert "subscription_id" in d
        assert "overall_status" in d
        assert "quotas" in d
        assert isinstance(d["quotas"], list)


class TestQuotaServiceComputeQuotas:
    def test_get_compute_quotas_not_installed(self):
        """Should return error summary when azure-mgmt-compute not installed."""
        from app.api.services.quota_service import QuotaService

        svc = QuotaService(credential=MagicMock())
        # Patch the module-level name to None (simulates missing SDK)
        with patch("app.api.services.quota_service.ComputeManagementClient", None):
            summary = svc.get_compute_quotas("sub-1", "tenant-1")
        assert summary.subscription_id == "sub-1"
        assert summary.error is not None

    def test_get_compute_quotas_api_exception(self):
        """Should return error summary when Azure API raises."""
        from app.api.services.quota_service import QuotaService

        mock_client_cls = MagicMock(side_effect=Exception("API down"))
        svc = QuotaService(credential=MagicMock())
        with patch("app.api.services.quota_service.ComputeManagementClient", mock_client_cls):
            summary = svc.get_compute_quotas("sub-1", "tenant-1")
        assert summary.error is not None

    def test_get_compute_quotas_success(self):
        """Should return populated QuotaSummary when Azure API succeeds."""
        from app.api.services.quota_service import QuotaService

        mock_usage = MagicMock()
        mock_usage.current_value = 10
        mock_usage.limit = 100
        mock_usage.unit = "Count"
        mock_usage.name.localized_value = "Virtual Machines"
        mock_usage.name.value = "virtualMachines"

        mock_client = MagicMock()
        mock_client.usage.list.return_value = [mock_usage]
        mock_client_cls = MagicMock(return_value=mock_client)

        svc = QuotaService(credential=MagicMock())
        with patch("app.api.services.quota_service.ComputeManagementClient", mock_client_cls):
            summary = svc.get_compute_quotas("sub-1", "tenant-1", "eastus")

        assert len(summary.quotas) == 1
        assert summary.quotas[0].name == "Virtual Machines"
        assert summary.quotas[0].current_value == 10
        assert summary.quotas[0].limit == 100

    def test_get_compute_quotas_skips_null_values(self):
        """Usage entries with None current_value or limit should be skipped."""
        from app.api.services.quota_service import QuotaService

        mock_usage = MagicMock()
        mock_usage.current_value = None
        mock_usage.limit = 100

        mock_client = MagicMock()
        mock_client.usage.list.return_value = [mock_usage]
        mock_client_cls = MagicMock(return_value=mock_client)

        svc = QuotaService(credential=MagicMock())
        with patch("app.api.services.quota_service.ComputeManagementClient", mock_client_cls):
            summary = svc.get_compute_quotas("sub-1", "tenant-1")

        assert len(summary.quotas) == 0

    def test_get_network_quotas_not_installed(self):
        """Should return error summary when azure-mgmt-network not installed."""
        from app.api.services.quota_service import QuotaService

        svc = QuotaService(credential=MagicMock())
        with patch("app.api.services.quota_service.NetworkManagementClient", None):
            summary = svc.get_network_quotas("sub-1", "tenant-1")
        assert summary.error is not None


class TestQuotaServiceAggregate:
    def test_aggregate_quotas_empty(self):
        from app.api.services.quota_service import QuotaService

        svc = QuotaService(credential=MagicMock())
        result = svc.aggregate_quotas([])
        assert result["overall_status"] == "ok"
        assert result["subscriptions_checked"] == 0

    def test_aggregate_quotas_critical_surfaces(self):
        from app.api.services.quota_service import QuotaItem, QuotaService, QuotaSummary

        svc = QuotaService(credential=MagicMock())
        s = QuotaSummary(subscription_id="sub-crit", tenant_id="t-1", location="eastus")
        s.quotas = [QuotaItem(name="cores", current_value=95, limit=100)]
        result = svc.aggregate_quotas([s])
        assert result["overall_status"] == "critical"
        assert "sub-crit" in result["critical_subscriptions"]

    def test_aggregate_quotas_warning_surfaces(self):
        from app.api.services.quota_service import QuotaItem, QuotaService, QuotaSummary

        svc = QuotaService(credential=MagicMock())
        s = QuotaSummary(subscription_id="sub-warn", tenant_id="t-1", location="eastus")
        s.quotas = [QuotaItem(name="cores", current_value=80, limit=100)]
        result = svc.aggregate_quotas([s])
        assert result["overall_status"] == "warning"
        assert "sub-warn" in result["warning_subscriptions"]

    def test_aggregate_quotas_top_sorted_by_utilization(self):
        from app.api.services.quota_service import QuotaItem, QuotaService, QuotaSummary

        svc = QuotaService(credential=MagicMock())
        s = QuotaSummary(subscription_id="sub-1", tenant_id="t-1", location="eastus")
        s.quotas = [
            QuotaItem(name="cores", current_value=20, limit=100),
            QuotaItem(name="vms", current_value=80, limit=100),
        ]
        result = svc.aggregate_quotas([s])
        # Highest utilization first
        assert result["top_quotas_by_utilization"][0]["name"] == "vms"

    def test_aggregate_total_quota_metrics(self):
        from app.api.services.quota_service import QuotaItem, QuotaService, QuotaSummary

        svc = QuotaService(credential=MagicMock())
        s = QuotaSummary(subscription_id="sub-1", tenant_id="t-1", location="eastus")
        s.quotas = [
            QuotaItem(name="a", current_value=1, limit=10),
            QuotaItem(name="b", current_value=2, limit=10),
            QuotaItem(name="c", current_value=3, limit=10),
        ]
        result = svc.aggregate_quotas([s])
        assert result["total_quota_metrics"] == 3


class TestQuotaRoutes:
    def test_quota_route_registered(self, client):
        """GET /api/v1/resources/quotas must be mounted (not 404)."""
        response = client.get("/api/v1/resources/quotas")
        assert response.status_code != 404

    def test_quota_route_requires_auth(self, client):
        response = client.get("/api/v1/resources/quotas")
        assert response.status_code in (401, 403)

    def test_quota_summary_route_registered(self, client):
        response = client.get("/api/v1/resources/quotas/summary")
        assert response.status_code != 404

    def test_quota_route_authenticated(self, authed_client):
        response = authed_client.get("/api/v1/resources/quotas")
        assert response.status_code == 200

    def test_quota_summary_authenticated(self, authed_client):
        response = authed_client.get("/api/v1/resources/quotas/summary")
        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert "subscriptions_checked" in data
