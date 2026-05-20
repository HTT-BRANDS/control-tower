"""Regression tests for ct-0b1: dev login form must be server-side gated.

The hidden dev login `<form id="login-form">` used to ship in HTML to every
environment — gated only by client-side JS that probed `/health` for
`environment === 'development'`. An attacker in prod could open DevTools,
un-hide the form, and POST credentials. Backend rejects the submission,
but the form being there at all is an info-disclosure + brand-trust hit.

Fix: ``app/api/routes/dashboard.py::_login_context`` passes ``is_dev`` based
on ``settings.environment``, and ``login.html`` wraps the dev form in
``{% if is_dev %}``.

These tests assert the form (and its inputs) physically do not appear in
the rendered HTML when environment != "development".
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from jinja2 import Environment, FileSystemLoader


@pytest.fixture(scope="module")
def login_template():
    env = Environment(loader=FileSystemLoader("app/templates"))
    return env.get_template("login.html")


@pytest.fixture
def fake_request():
    return MagicMock(state=MagicMock(brand="htt"))


def _render(template, *, is_dev: bool, request) -> str:
    return template.render(is_dev=is_dev, request=request)


def test_dev_form_present_in_development(login_template, fake_request):
    html = _render(login_template, is_dev=True, request=fake_request)
    assert "login-dev-form" in html, "dev form must be present in development"
    assert 'id="username"' in html
    assert 'type="password"' in html


@pytest.mark.parametrize("is_dev", [False])
def test_dev_form_absent_when_not_development(login_template, fake_request, is_dev):
    """ct-0b1 regression — must never ship dev login form to staging or prod."""
    html = _render(login_template, is_dev=is_dev, request=fake_request)
    assert "login-dev-form" not in html, "ct-0b1: dev form leaked to non-dev env"
    assert 'id="username"' not in html, "ct-0b1: username input leaked to non-dev env"
    assert 'id="password"' not in html, "ct-0b1: password input leaked to non-dev env"


def test_dev_form_gating_saves_bytes(login_template, fake_request):
    """Sanity: prod HTML is meaningfully smaller (form is actually removed)."""
    html_dev = _render(login_template, is_dev=True, request=fake_request)
    html_prod = _render(login_template, is_dev=False, request=fake_request)
    # The dev form block is ~1.5 KB. If the difference shrinks below 1 KB,
    # something has likely been refactored that re-included the form.
    assert len(html_dev) - len(html_prod) > 1000, (
        "PROD html unexpectedly close in size to DEV — gating may have regressed"
    )


def test_error_region_has_alert_role(login_template, fake_request):
    """F4 from Round 1 design audit — error region must be announced (WCAG 4.1.3)."""
    html = _render(login_template, is_dev=False, request=fake_request)
    assert 'role="alert"' in html, "login error region must have role=alert for screen reader users"
