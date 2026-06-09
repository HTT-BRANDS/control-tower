"""API documentation exposure is environment-gated.

Closes STRIDE I1 (schema disclosure). The OpenAPI surface (/docs, /redoc,
/openapi.json) is intentionally open in dev/staging for developer velocity, but
in production it must require a valid bearer token. This pins that contract so a
config refactor cannot silently expose the schema in prod.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.core.auth import jwt_manager
from app.main_docs import _production_docs_auth_error


def _request(auth: str | None = None, cookie: str | None = None):
    headers = {}
    if auth:
        headers["Authorization"] = auth
    cookies = {"access_token": cookie} if cookie else {}
    return SimpleNamespace(headers=headers, cookies=cookies)


def _settings(is_production: bool):
    return SimpleNamespace(is_production=is_production)


def test_non_production_docs_are_open() -> None:
    """Dev/staging: no auth gate (returns None == allow)."""
    assert _production_docs_auth_error(_request(), _settings(False), jwt_manager) is None


def test_production_docs_require_a_token() -> None:
    err = _production_docs_auth_error(_request(), _settings(True), jwt_manager)
    assert err is not None
    assert err.status_code == 401


def test_production_docs_reject_invalid_token() -> None:
    bad = _request(auth="Bearer not-a-real-token")
    err = _production_docs_auth_error(bad, _settings(True), jwt_manager)
    assert err is not None
    assert err.status_code == 401


def test_production_docs_accept_valid_token() -> None:
    token = jwt_manager.create_access_token(user_id="u1", roles=["viewer"])
    ok = _request(auth=f"Bearer {token}")
    assert _production_docs_auth_error(ok, _settings(True), jwt_manager) is None


def test_production_docs_accept_valid_cookie_token() -> None:
    """The gate also honours the access_token cookie (browser session)."""
    token = jwt_manager.create_access_token(user_id="u1", roles=["viewer"])
    ok = _request(cookie=token)
    assert _production_docs_auth_error(ok, _settings(True), jwt_manager) is None
