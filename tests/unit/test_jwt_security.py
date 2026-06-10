"""JWT hardening tests.

Closes the audit gap: the internal JWT manager (`app.core.auth.JWTTokenManager`)
had token *creation* tested but not adversarial *decode* behaviour. These tests
attack the decoder the way a real attacker would.

STRIDE coverage: S1 (impersonation via forged token), T (payload tampering),
E1 (privilege escalation by editing the roles claim).
"""

from __future__ import annotations

import datetime as dt

import jwt as pyjwt
import pytest
from fastapi import HTTPException

from app.core.auth import jwt_manager
from app.core.config import get_settings

settings = get_settings()


def _valid_token(**overrides) -> str:
    """Mint a genuine token via the production code path."""
    kwargs = {
        "user_id": "user-1",
        "email": "u@example.com",
        "roles": ["viewer"],
    }
    kwargs.update(overrides)
    return jwt_manager.create_access_token(**kwargs)


def test_valid_token_decodes() -> None:
    payload = jwt_manager.decode_token(_valid_token())
    assert payload["sub"] == "user-1"
    assert "viewer" in payload["roles"]


def test_tampered_payload_is_rejected() -> None:
    """Flip a byte in the payload segment -> signature must fail."""
    token = _valid_token()
    header, payload, sig = token.split(".")
    # Corrupt the payload but keep it base64-ish
    bad_payload = payload[:-2] + ("AA" if payload[-2:] != "AA" else "BB")
    forged = f"{header}.{bad_payload}.{sig}"
    with pytest.raises(HTTPException) as exc:
        jwt_manager.decode_token(forged)
    assert exc.value.status_code == 401


def test_alg_none_is_rejected() -> None:
    """The classic 'alg: none' downgrade must not be accepted."""
    forged = pyjwt.encode(
        {
            "sub": "attacker",
            "roles": ["admin"],
            "aud": "azure-governance-api",
            "iss": "azure-governance-api",
        },
        key="",
        algorithm="none",
    )
    with pytest.raises(HTTPException) as exc:
        jwt_manager.decode_token(forged)
    assert exc.value.status_code == 401


def test_token_signed_with_wrong_secret_is_rejected() -> None:
    """An attacker who guesses structure but not the secret is locked out."""
    forged = pyjwt.encode(
        {
            "sub": "attacker",
            "roles": ["admin"],
            "aud": "azure-governance-api",
            "iss": "azure-governance-api",
            "exp": dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
        },
        key="not-the-real-secret-value-12345",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(HTTPException):
        jwt_manager.decode_token(forged)


def test_expired_token_is_rejected() -> None:
    expired = pyjwt.encode(
        {
            "sub": "user-1",
            "roles": ["viewer"],
            "aud": "azure-governance-api",
            "iss": "azure-governance-api",
            "exp": dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1),
        },
        key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(HTTPException) as exc:
        jwt_manager.decode_token(expired)
    assert exc.value.status_code == 401


def test_wrong_audience_is_rejected() -> None:
    """A token minted for another audience must not be honoured here."""
    other_aud = pyjwt.encode(
        {
            "sub": "user-1",
            "roles": ["viewer"],
            "aud": "some-other-api",
            "iss": "azure-governance-api",
            "exp": dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
        },
        key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(HTTPException):
        jwt_manager.decode_token(other_aud)


def test_untrusted_issuer_is_rejected() -> None:
    """Issuer allowlist enforcement (decode checks ACCEPTED_INTERNAL_JWT_ISSUERS)."""
    bad_iss = pyjwt.encode(
        {
            "sub": "user-1",
            "roles": ["admin"],
            "aud": "azure-governance-api",
            "iss": "https://evil.example.com/",
            "exp": dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
        },
        key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(HTTPException):
        jwt_manager.decode_token(bad_iss)


def test_garbage_token_is_rejected() -> None:
    for junk in ("", "not-a-token", "a.b", "..", "Bearer x"):
        with pytest.raises(HTTPException):
            jwt_manager.decode_token(junk)
