"""Unit tests for onboarding API routes.

Covers the self-service onboarding flow:
- Landing page (HTML/HTMX)
- ARM template generation (HTML + JSON)
- Delegation verification & tenant creation
- Onboarding status checks
- Validation, error handling, and async behaviour
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.tenant import Tenant
from app.services.lighthouse_client import LighthouseDelegationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides) -> MagicMock:
    """Build a fake Settings object with sane defaults for template tests."""
    settings = MagicMock()
    settings.azure_ad_tenant_id = overrides.get("azure_ad_tenant_id", "msp-tenant-123")
    settings.azure_tenant_id = overrides.get("azure_tenant_id", "msp-tenant-123")
    settings.managed_identity_object_id = overrides.get(
        "managed_identity_object_id", "principal-456"
    )
    settings.lighthouse_enabled = overrides.get("lighthouse_enabled", True)
    return settings


def _valid_form_data(**overrides) -> dict[str, str]:
    """Return valid verify-onboarding form data."""
    defaults: dict[str, str] = {
        "tenant_name": "Test Tenant",
        "tenant_id": str(uuid.uuid4()),
        "subscription_id": str(uuid.uuid4()),
        "description": "Test description",
    }
    defaults.update(overrides)
    return defaults


def _create_tenant(db_session, **overrides) -> Tenant:
    """Insert a Tenant into the test DB and return the refreshed instance."""
    defaults: dict = {
        "id": str(uuid.uuid4()),
        "name": "Test Tenant",
        "tenant_id": f"azure-tid-{uuid.uuid4().hex[:8]}",
        "is_active": True,
        "use_lighthouse": True,
    }
    defaults.update(overrides)
    tenant = Tenant(**defaults)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _patch_settings():
    """Convenience context-manager that patches ``get_settings``."""
    return patch(
        "app.api.routes.onboarding.get_settings",
        return_value=_make_settings(),
    )


def _patch_lighthouse(delegation_return=None, side_effect=None):
    """Convenience context-manager that patches ``LighthouseAzureClient``.

    Returns the *mock class* so callers can inspect ``mock_cls.return_value``.
    """
    ctx = patch("app.api.routes.onboarding.LighthouseAzureClient")
    # We store extra info so the caller can set up the mock after entering.
    ctx._delegation_return = delegation_return  # type: ignore[attr-defined]
    ctx._side_effect = side_effect  # type: ignore[attr-defined]
    return ctx


# ===========================================================================
# 1. Landing page
# ===========================================================================


class TestOnboardingLandingPage:
    """GET /onboarding/ – HTML landing page."""

    def test_returns_landing_page(self, client):
        """Landing page responds 200 with HTMX-powered HTML."""
        response = client.get("/onboarding/")

        assert response.status_code == 200
        assert "Azure Governance Platform" in response.text
        assert "hx-" in response.text  # HTMX attributes present

    def test_content_type_is_html(self, client):
        """Landing page serves text/html."""
        response = client.get("/onboarding/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "onboard" in response.text.lower()


# ===========================================================================
# 2. Generate template (HTML)
# ===========================================================================


class TestGenerateTemplate:
    """POST /onboarding/generate-template – HTML response with ARM template."""

    def test_success(self, client):
        """Generates an ARM template and returns success HTML."""
        with _patch_settings():
            response = client.post(
                "/onboarding/generate-template",
                data={"org_name": "Test Org"},
            )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Template Generated Successfully" in response.text
        assert "managedByTenantId" in response.text
        assert "resources" in response.text

    def test_org_name_appears_in_response(self, client):
        """Supplied org name is echoed back in the generated HTML."""
        with _patch_settings():
            response = client.post(
                "/onboarding/generate-template",
                data={"org_name": "Custom Organization"},
            )

        assert response.status_code == 200
        assert "Custom Organization" in response.text

    def test_empty_org_name_defaults_gracefully(self, client):
        """An empty org_name still produces a valid template."""
        with _patch_settings():
            response = client.post(
                "/onboarding/generate-template",
                data={"org_name": ""},
            )

        assert response.status_code == 200
        assert "Template Generated Successfully" in response.text


# ===========================================================================
# 3. Generate template (JSON API)
# ===========================================================================


class TestGenerateTemplateJSON:
    """GET /onboarding/api/template – JSON ARM template."""

    def test_returns_template_with_metadata(self, client):
        """JSON endpoint returns template + metadata."""
        with _patch_settings():
            response = client.get("/onboarding/api/template?org_name=TestCorp")

        assert response.status_code == 200
        body = response.json()
        assert "template" in body
        assert "metadata" in body
        assert "$schema" in body["template"]
        assert "resources" in body["template"]
        assert "parameters" in body["template"]


# ===========================================================================
# 4. Verify onboarding (HTML)
# ===========================================================================


class TestVerifyOnboarding:
    """POST /onboarding/verify – delegation verification & tenant creation."""

    def test_success_creates_tenant(self, client, db_session):
        """Successful delegation → 201, HTML confirmation, tenant in DB."""
        form = _valid_form_data()

        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_cls:
            inst = AsyncMock()
            inst.verify_delegation.return_value = {
                "is_delegated": True,
                "display_name": "Test Subscription",
                "subscription_id": form["subscription_id"],
            }
            mock_cls.return_value = inst

            response = client.post("/onboarding/verify", data=form)

        assert response.status_code == 201
        assert "text/html" in response.headers.get("content-type", "")
        assert "Tenant Created Successfully" in response.text
        assert form["tenant_name"] in response.text

        # DB round-trip check
        tenant = (
            db_session.query(Tenant)
            .filter(Tenant.tenant_id == form["tenant_id"].lower())
            .first()
        )
        assert tenant is not None
        assert tenant.name == form["tenant_name"]
        assert tenant.use_lighthouse is True
        assert tenant.is_active is True

    def test_delegation_failed_returns_400(self, client):
        """When is_delegated is False the endpoint returns 400 HTML."""
        form = _valid_form_data()

        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_cls:
            inst = AsyncMock()
            inst.verify_delegation.return_value = {
                "is_delegated": False,
                "error": "Subscription not found or not delegated",
            }
            mock_cls.return_value = inst

            response = client.post("/onboarding/verify", data=form)

        assert response.status_code == 400
        assert "Delegation Verification Failed" in response.text

    def test_tenant_persisted_to_database(self, client, db_session):
        """Tenant record appears in DB after successful verify."""
        form = _valid_form_data()

        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_cls:
            inst = AsyncMock()
            inst.verify_delegation.return_value = {
                "is_delegated": True,
                "display_name": "Sub",
            }
            mock_cls.return_value = inst

            response = client.post("/onboarding/verify", data=form)

        assert response.status_code == 201

        tenant = (
            db_session.query(Tenant)
            .filter(Tenant.tenant_id == form["tenant_id"].lower())
            .first()
        )
        assert tenant is not None
        assert tenant.use_lighthouse is True

    def test_missing_required_fields_returns_422(self, client):
        """Omitting required Form fields (tenant_id, subscription_id) → 422."""
        response = client.post(
            "/onboarding/verify",
            data={"tenant_name": "Test Tenant"},
        )
        assert response.status_code == 422

    def test_duplicate_tenant_returns_409(self, client, db_session):
        """Attempting to onboard an already-registered tenant → 409."""
        form = _valid_form_data()

        existing = Tenant(
            id=str(uuid.uuid4()),
            name=form["tenant_name"],
            tenant_id=form["tenant_id"],
            is_active=True,
            use_lighthouse=True,
        )
        db_session.add(existing)
        db_session.commit()

        with patch("app.api.routes.onboarding.LighthouseAzureClient"):
            response = client.post("/onboarding/verify", data=form)

        assert response.status_code == 409
        assert "Already Exists" in response.text


# ===========================================================================
# 5. Onboarding status
# ===========================================================================


class TestOnboardingStatus:
    """GET /onboarding/status/{tenant_id} – JSON status response."""

    def test_active_tenant(self, client, db_session):
        """Active Lighthouse tenant returns full status payload."""
        tenant = _create_tenant(db_session)

        response = client.get(f"/onboarding/status/{tenant.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["tenant"]["id"] == tenant.id
        assert data["tenant"]["name"] == tenant.name
        assert data["tenant"]["use_lighthouse"] is True
        assert data["onboarding_complete"] is True

    def test_not_found(self, client):
        """Non-existent tenant ID returns 404 with descriptive message."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/onboarding/status/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "not_found"
        assert fake_id in data["message"]

    def test_any_string_accepted_as_id(self, client):
        """Route accepts arbitrary strings — no UUID validation."""
        response = client.get("/onboarding/status/not-a-uuid")

        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "not_found"

    def test_inactive_tenant(self, client, db_session):
        """Inactive tenant → status "inactive", onboarding_complete False."""
        tenant = _create_tenant(db_session, is_active=False)

        response = client.get(f"/onboarding/status/{tenant.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "inactive"
        assert data["tenant"]["is_active"] is False
        assert data["onboarding_complete"] is False

    def test_non_lighthouse_tenant(self, client, db_session):
        """Tenant without Lighthouse → onboarding_complete False."""
        tenant = _create_tenant(db_session, use_lighthouse=False)

        response = client.get(f"/onboarding/status/{tenant.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["tenant"]["use_lighthouse"] is False
        assert data["onboarding_complete"] is False


# ===========================================================================
# 6. Error scenarios
# ===========================================================================


class TestOnboardingErrorScenarios:
    """Assorted error-handling and edge-case coverage."""

    def test_missing_fields_returns_422(self, client):
        """POST /verify with missing required Form fields → 422."""
        response = client.post(
            "/onboarding/verify",
            data={"tenant_name": "Test"},  # tenant_id + subscription_id omitted
        )
        assert response.status_code == 422

    def test_invalid_payload_returns_422(self, client):
        """Non-form payload on a Form-only endpoint → 422."""
        response = client.post(
            "/onboarding/verify",
            content=b"not valid data",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_method_not_allowed(self, client):
        """Wrong HTTP methods are rejected with 405."""
        assert client.put("/onboarding/verify").status_code == 405
        assert client.delete("/onboarding/generate-template").status_code == 405

    def test_lighthouse_delegation_error(self, client):
        """LighthouseDelegationError during verify → 400 with error HTML."""
        form = _valid_form_data()

        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_cls:
            inst = AsyncMock()
            inst.verify_delegation.side_effect = LighthouseDelegationError(
                form["subscription_id"], "Auth failed"
            )
            mock_cls.return_value = inst

            response = client.post("/onboarding/verify", data=form)

        assert response.status_code == 400
        assert "Lighthouse Delegation Error" in response.text


# ===========================================================================
# 7. Input validation
# ===========================================================================


class TestOnboardingValidation:
    """Validation rules enforced by POST /onboarding/verify."""

    def test_empty_tenant_name_rejected(self, client):
        """Whitespace-only tenant_name → 400."""
        form = _valid_form_data(tenant_name="   ")

        response = client.post("/onboarding/verify", data=form)

        assert response.status_code == 400
        assert "required" in response.text.lower()

    def test_invalid_tenant_id_format(self, client):
        """tenant_id that isn't 32 hex chars (sans dashes) → 400."""
        form = _valid_form_data(tenant_id="not-a-valid-uuid")

        response = client.post("/onboarding/verify", data=form)

        assert response.status_code == 400
        assert "Invalid" in response.text

    def test_invalid_subscription_id_format(self, client):
        """subscription_id that isn't 32 hex chars (sans dashes) → 400."""
        form = _valid_form_data(subscription_id="invalid-sub")

        response = client.post("/onboarding/verify", data=form)

        assert response.status_code == 400
        assert "Invalid" in response.text


# ===========================================================================
# 8. Async operations
# ===========================================================================


class TestOnboardingAsyncOperations:
    """Verify async call-through behaviour."""

    def test_verify_delegation_called_with_correct_args(self, client):
        """verify_delegation receives the exact subscription_id from the form."""
        form = _valid_form_data()

        with patch("app.api.routes.onboarding.LighthouseAzureClient") as mock_cls:
            inst = AsyncMock()
            inst.verify_delegation.return_value = {
                "is_delegated": True,
                "display_name": "Test Sub",
            }
            mock_cls.return_value = inst

            response = client.post("/onboarding/verify", data=form)

        assert response.status_code == 201
        inst.verify_delegation.assert_called_once_with(form["subscription_id"])

    async def test_async_resource_listing_mock(self):
        """Mocked LighthouseAzureClient.list_resources works async."""
        mock_client = AsyncMock()
        mock_client.list_resources.return_value = {
            "success": True,
            "resources": [],
            "count": 0,
        }

        result = await mock_client.list_resources("sub-12345")

        mock_client.list_resources.assert_awaited_once_with("sub-12345")
        assert result["success"] is True
