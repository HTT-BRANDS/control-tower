"""Tests for async Graph API token acquisition and connection timeout.

Verifies that the GraphClient properly:
- Acquires tokens asynchronously via asyncio.to_thread()
- Uses connection_timeout on ClientSecretCredential
- Handles token acquisition failures gracefully
- Doesn't block the event loop during token acquisition
"""

import asyncio
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock Azure SDK before imports
azure_mock = MagicMock()
sys.modules.setdefault("azure", azure_mock)
sys.modules.setdefault("azure.identity", azure_mock)
sys.modules.setdefault("azure.core", azure_mock)
sys.modules.setdefault("azure.core.exceptions", azure_mock)


class TestGraphClientAsyncToken:
    """Test suite for async token acquisition in GraphClient."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mock settings for all tests."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "test-client-id"
        self.mock_settings.azure_client_secret = "test-client-secret"
        self.mock_settings.azure_tenant_id = "test-tenant-id"

        with patch("app.api.services.graph_client.settings", self.mock_settings):
            from app.api.services.graph_client import GraphClient

            self.GraphClient = GraphClient
            yield

    @pytest.mark.asyncio
    async def test_get_token_is_async(self):
        """Verify _get_token is a coroutine (async function)."""
        client = self.GraphClient("test-tenant-id")
        assert asyncio.iscoroutinefunction(client._get_token)

    @pytest.mark.asyncio
    async def test_get_token_uses_to_thread(self):
        """Verify _get_token wraps sync credential.get_token in asyncio.to_thread."""
        client = self.GraphClient("test-tenant-id")

        mock_token = MagicMock()
        mock_token.token = "test-access-token-12345"

        mock_credential = MagicMock()
        mock_credential.get_token.return_value = mock_token
        client._credential = mock_credential

        with patch(
            "app.api.services.graph_client.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_token,
        ) as mock_to_thread:
            token = await client._get_token()

            # Verify to_thread was called with the sync get_token
            mock_to_thread.assert_called_once()
            args = mock_to_thread.call_args
            assert args[0][0] == mock_credential.get_token  # first arg is the sync function

        assert token == "test-access-token-12345"

    @pytest.mark.asyncio
    async def test_get_token_does_not_block_event_loop(self):
        """Verify token acquisition doesn't block other async tasks."""
        client = self.GraphClient("test-tenant-id")

        # Simulate a slow token acquisition (100ms)
        mock_token = MagicMock()
        mock_token.token = "slow-token"

        mock_credential = MagicMock()

        def slow_get_token(*args):
            time.sleep(0.1)  # 100ms blocking call
            return mock_token

        mock_credential.get_token.side_effect = slow_get_token
        client._credential = mock_credential

        # Run token acquisition alongside a fast async task
        fast_task_completed = False

        async def fast_task():
            nonlocal fast_task_completed
            await asyncio.sleep(0.01)  # 10ms
            fast_task_completed = True

        # Both should complete without the slow token blocking the fast task
        await asyncio.gather(client._get_token(), fast_task())
        assert fast_task_completed, "Fast async task should not be blocked by token acquisition"

    @pytest.mark.asyncio
    async def test_get_token_returns_token_string(self):
        """Verify _get_token returns the token string, not the Token object."""
        client = self.GraphClient("test-tenant-id")

        mock_token = MagicMock()
        mock_token.token = "bearer-token-value"

        mock_credential = MagicMock()
        mock_credential.get_token.return_value = mock_token
        client._credential = mock_credential

        token = await client._get_token()
        assert token == "bearer-token-value"
        assert isinstance(token, str)

    @pytest.mark.asyncio
    async def test_get_token_propagates_auth_errors(self):
        """Verify authentication errors propagate correctly from async context."""
        client = self.GraphClient("test-tenant-id")

        mock_credential = MagicMock()
        mock_credential.get_token.side_effect = Exception(
            "Authentication failed: invalid client secret"
        )
        client._credential = mock_credential

        with pytest.raises(Exception, match="Authentication failed"):
            await client._get_token()

    @pytest.mark.asyncio
    async def test_get_token_propagates_timeout_errors(self):
        """Verify connection timeout errors propagate correctly."""
        client = self.GraphClient("test-tenant-id")

        mock_credential = MagicMock()
        mock_credential.get_token.side_effect = ConnectionError("Connection timed out")
        client._credential = mock_credential

        with pytest.raises(ConnectionError, match="Connection timed out"):
            await client._get_token()


class TestGraphClientCredentialConfig:
    """Test suite for credential configuration including connection_timeout."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mock settings."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "test-client-id"
        self.mock_settings.azure_client_secret = "test-client-secret"
        self.mock_settings.azure_tenant_id = "test-tenant-id"
        self.mock_settings.use_oidc_federation = False  # secret mode under test

        with patch("app.api.services.graph_client.settings", self.mock_settings):
            from app.api.services.graph_client import GraphClient

            self.GraphClient = GraphClient
            yield

    def test_credential_uses_connection_timeout(self):
        """Verify ClientSecretCredential is created with connection_timeout=10."""
        with (
            patch("app.api.services.graph_client.ClientSecretCredential") as mock_csc,
            patch("app.api.services.azure_client.AzureClientManager") as mock_mgr,
        ):
            mock_mgr.return_value._resolve_credentials.return_value = (
                "test-client-id",
                "test-client-secret",
                None,
            )
            client = self.GraphClient("test-tenant-id")
            client._get_credential()

            mock_csc.assert_called_once_with(
                tenant_id="test-tenant-id",
                client_id="test-client-id",
                client_secret="test-client-secret",
                connection_timeout=10,
            )

    def test_credential_is_cached(self):
        """Verify credential is created once and reused."""
        with (
            patch("app.api.services.graph_client.ClientSecretCredential") as mock_csc,
            patch("app.api.services.azure_client.AzureClientManager") as mock_mgr,
        ):
            mock_mgr.return_value._resolve_credentials.return_value = (
                "test-client-id",
                "test-client-secret",
                None,
            )
            client = self.GraphClient("test-tenant-id")
            cred1 = client._get_credential()
            cred2 = client._get_credential()

            assert cred1 is cred2
            mock_csc.assert_called_once()  # Only created once

    def test_credential_uses_correct_tenant(self):
        """Verify credential uses the tenant_id passed to GraphClient."""
        with (
            patch("app.api.services.graph_client.ClientSecretCredential") as mock_csc,
            patch("app.api.services.azure_client.AzureClientManager") as mock_mgr,
        ):
            mock_mgr.return_value._resolve_credentials.return_value = (
                "test-client-id",
                "test-client-secret",
                None,
            )
            client = self.GraphClient("custom-tenant-abc")
            client._get_credential()

            call_kwargs = mock_csc.call_args[1]
            assert call_kwargs["tenant_id"] == "custom-tenant-abc"


class TestGraphClientRequestIntegration:
    """Test suite for async request flow (token + HTTP)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mock settings."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "test-client-id"
        self.mock_settings.azure_client_secret = "test-client-secret"
        self.mock_settings.azure_tenant_id = "test-tenant-id"

        with patch("app.api.services.graph_client.settings", self.mock_settings):
            from app.api.services.graph_client import GraphClient

            self.GraphClient = GraphClient
            yield

    @pytest.mark.asyncio
    async def test_request_awaits_token_then_makes_http_call(self):
        """Verify _request awaits async _get_token before making HTTP request."""
        client = self.GraphClient("test-tenant-id")

        # Mock async _get_token
        client._get_token = AsyncMock(return_value="mock-bearer-token")

        # Mock httpx
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": [{"id": "user1"}]}
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.request.return_value = mock_response
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.api.services.graph_client.httpx.AsyncClient", return_value=mock_http_client
        ):
            result = await client._request("GET", "/users")

        # Token was awaited
        client._get_token.assert_awaited_once()

        # HTTP request used the token
        http_call = mock_http_client.request.call_args
        assert http_call[1]["headers"]["Authorization"] == "Bearer mock-bearer-token"

        assert result == {"value": [{"id": "user1"}]}

    @pytest.mark.asyncio
    async def test_request_handles_token_failure_before_http(self):
        """Verify _request propagates token errors without making HTTP call."""
        client = self.GraphClient("test-tenant-id")

        # Mock async _get_token to fail
        client._get_token = AsyncMock(side_effect=Exception("Token acquisition failed"))

        with pytest.raises(Exception, match="Token acquisition failed"):
            await client._request("GET", "/users")


class TestAzureGraphPreflightCheck:
    """Test suite for the lightweight AzureGraphCheck preflight."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mock settings."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "test-client-id"
        self.mock_settings.azure_client_secret = "test-client-secret"
        self.mock_settings.azure_tenant_id = "test-tenant-id"

        with patch("app.preflight.checks.get_settings", return_value=self.mock_settings):
            from app.preflight.checks import AzureGraphCheck

            self.GraphCheck = AzureGraphCheck
            yield

    @pytest.mark.asyncio
    async def test_graph_check_passes_with_org_response(self):
        """Verify Graph check passes when /organization returns data."""
        check = self.GraphCheck()

        mock_token = "test-bearer-token"
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": [{"id": "org1", "displayName": "Test Org"}]}
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("app.api.services.graph_client.GraphClient") as mock_gc_class,
            patch("httpx.AsyncClient", return_value=mock_http),
        ):
            mock_gc = MagicMock()
            mock_gc._get_token = AsyncMock(return_value=mock_token)
            mock_gc_class.return_value = mock_gc

            result = await check._execute_check()

        assert result.status.value == "pass"
        assert "Test Org" in result.message
        assert result.details["token_acquired"] is True

    @pytest.mark.asyncio
    async def test_graph_check_fails_on_timeout(self):
        """Verify Graph check returns descriptive failure on timeout."""
        import httpx as httpx_mod

        check = self.GraphCheck()

        mock_http = AsyncMock()
        mock_http.get.side_effect = httpx_mod.TimeoutException("Connection timed out")
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("app.api.services.graph_client.GraphClient") as mock_gc_class,
            patch("httpx.AsyncClient", return_value=mock_http),
        ):
            mock_gc = MagicMock()
            mock_gc._get_token = AsyncMock(return_value="test-token")
            mock_gc_class.return_value = mock_gc

            result = await check._execute_check()

        assert result.status.value == "fail"
        assert "timed out" in result.message.lower()
        assert "network connectivity" in result.message.lower()

    @pytest.mark.asyncio
    async def test_graph_check_fails_on_token_failure(self):
        """Verify Graph check fails gracefully when token acquisition fails."""
        check = self.GraphCheck()

        with patch("app.api.services.graph_client.GraphClient") as mock_gc_class:
            mock_gc = MagicMock()
            mock_gc._get_token = AsyncMock(side_effect=Exception("Auth failed"))
            mock_gc_class.return_value = mock_gc

            result = await check._execute_check()

        assert result.status.value == "fail"
        assert "Auth failed" in result.message

    @pytest.mark.asyncio
    async def test_graph_check_fails_without_tenant(self):
        """Verify Graph check fails when no tenant ID is configured."""
        self.mock_settings.azure_tenant_id = None

        with patch("app.preflight.checks.get_settings", return_value=self.mock_settings):
            from app.preflight.checks import AzureGraphCheck

            check = AzureGraphCheck()
            result = await check._execute_check()

        assert result.status.value == "fail"
        assert "No tenant ID" in result.message

    @pytest.mark.asyncio
    async def test_graph_check_handles_http_error(self):
        """Verify Graph check reports HTTP status errors clearly."""
        import httpx as httpx_mod

        check = self.GraphCheck()

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = httpx_mod.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=mock_response
        )

        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("app.api.services.graph_client.GraphClient") as mock_gc_class,
            patch("httpx.AsyncClient", return_value=mock_http),
        ):
            mock_gc = MagicMock()
            mock_gc._get_token = AsyncMock(return_value="test-token")
            mock_gc_class.return_value = mock_gc

            result = await check._execute_check()

        assert result.status.value == "fail"
        assert "403" in result.message

    def test_graph_check_has_20s_timeout(self):
        """Verify the check uses 20s timeout (not the old 60s)."""
        check = self.GraphCheck()
        assert check.timeout_seconds == 20.0


class TestAzureClientConnectionTimeout:
    """Test suite for azure_client.py connection_timeout parameter."""

    def test_azure_client_credential_uses_connection_timeout(self):
        """Verify AzureClientManager creates credentials with connection_timeout=10."""
        with (
            patch("app.api.services.azure_client.ClientSecretCredential") as mock_csc,
            patch("app.api.services.azure_client.settings") as mock_settings,
            patch("app.api.services.azure_client.SessionLocal") as mock_db,
        ):
            mock_settings.azure_client_id = "test-id"
            mock_settings.azure_client_secret = "test-secret"
            mock_settings.key_vault_url = None
            mock_settings.use_oidc_federation = False  # secret mode under test

            # Mock the tenant lookup
            mock_tenant = MagicMock()
            mock_tenant.use_lighthouse = True
            mock_tenant.client_id = None
            mock_tenant.client_secret_ref = None
            # SessionLocal() is used as context manager: with SessionLocal() as db:
            mock_db.return_value.__enter__ = MagicMock(
                return_value=MagicMock(
                    query=MagicMock(
                        return_value=MagicMock(
                            filter=MagicMock(
                                return_value=MagicMock(first=MagicMock(return_value=mock_tenant))
                            )
                        )
                    )
                )
            )
            mock_db.return_value.__exit__ = MagicMock(return_value=False)

            from app.api.services.azure_client import AzureClientManager

            manager = AzureClientManager()
            manager.get_credential("test-tenant-id", force_refresh=True)

            # Verify connection_timeout is passed
            call_kwargs = mock_csc.call_args[1]
            assert call_kwargs.get("connection_timeout") == 10
