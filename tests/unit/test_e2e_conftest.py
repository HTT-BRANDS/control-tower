"""Unit tests for the shared E2E auth/session fixtures."""

from unittest.mock import MagicMock

import httpx
import pytest

from tests.e2e.conftest import (
    _assert_fresh_context,
    _assert_issued_cookies_present,
    _assert_login_cookie_contract,
    _issued_playwright_cookies,
)


def _login_response(*set_cookie_headers: str) -> httpx.Response:
    request = httpx.Request("POST", "http://127.0.0.1:8099/api/v1/auth/login")
    return httpx.Response(
        200,
        request=request,
        headers=[("set-cookie", header) for header in set_cookie_headers],
        json={"cookies_set": True, "token_type": "bearer", "expires_in": 1800},
    )


def test_login_cookie_contract_requires_expected_cookie_flags():
    response = _login_response(
        "access_token=abc; HttpOnly; Path=/; SameSite=Lax",
        "refresh_token=def; HttpOnly; Path=/; SameSite=Lax",
    )

    _assert_login_cookie_contract(response)


def test_login_cookie_contract_fails_closed_when_cookie_flags_missing():
    response = _login_response(
        "access_token=abc; Path=/; SameSite=Lax",
        "refresh_token=def; HttpOnly; Path=/; SameSite=Lax",
    )

    with pytest.raises(AssertionError, match="HttpOnly"):
        _assert_login_cookie_contract(response)


def test_issued_playwright_cookies_preserve_server_issued_cookie_names():
    response = _login_response(
        "access_token=abc; HttpOnly; Path=/; SameSite=Lax",
        "refresh_token=def; HttpOnly; Path=/; SameSite=Lax",
    )

    cookies = _issued_playwright_cookies(response, "http://127.0.0.1:8099")

    assert [cookie["name"] for cookie in cookies] == ["access_token", "refresh_token"]
    assert all(cookie["domain"] == "127.0.0.1" for cookie in cookies)
    assert all(cookie["path"] == "/" for cookie in cookies)
    assert all(cookie["httpOnly"] is True for cookie in cookies)
    assert all(cookie["sameSite"] == "Lax" for cookie in cookies)


def test_assert_fresh_context_rejects_unexpected_shared_state():
    context = MagicMock()
    context.cookies.return_value = [{"name": "access_token", "value": "leaked"}]

    with pytest.raises(AssertionError, match="Expected fresh browser context"):
        _assert_fresh_context(context)


def test_assert_issued_cookies_present_requires_access_and_refresh_tokens():
    context = MagicMock()
    context.cookies.return_value = [{"name": "access_token"}]

    with pytest.raises(AssertionError, match="Expected issued auth cookies"):
        _assert_issued_cookies_present(context)
