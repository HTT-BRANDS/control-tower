"""Architecture fitness tests — security constraints.

These tests verify that security invariants hold across the codebase.
They should run in CI and fail fast if security boundaries are violated.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
APP_DIR = PROJECT_ROOT / "app"
TEMPLATES_DIR = APP_DIR / "templates"
CSS_DIR = APP_DIR / "static" / "css"
INFRA_DIR = PROJECT_ROOT / "infrastructure"


# ============================================================================
# SEC-1: No secrets in source code
# ============================================================================

SECRETS_PATTERNS = [
    (r"(?i)(password|secret|api.?key)\s*=\s*['\"][^'\"]{8,}['\"]", "hardcoded secret"),
    (r"(?i)AKIA[0-9A-Z]{16}", "AWS access key"),
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI/Stripe secret key"),
]


class TestNoHardcodedSecrets:
    """Source code must not contain hardcoded secrets or API keys."""

    @pytest.fixture
    def python_files(self):
        return list(APP_DIR.rglob("*.py"))

    def test_no_secrets_in_python(self, python_files):
        violations = []
        for f in python_files:
            content = f.read_text(errors="ignore")
            for pattern, label in SECRETS_PATTERNS:
                for match in re.finditer(pattern, content):
                    # Skip test files, comments, and well-known false positives
                    line = content[: match.start()].count("\n") + 1
                    context = match.group()
                    if any(
                        fp in context.lower()
                        for fp in ("example", "placeholder", "changeme", "xxx", "test")
                    ):
                        continue
                    violations.append(f"{f.relative_to(PROJECT_ROOT)}:{line} — {label}")

        assert not violations, "Potential secrets found:\n" + "\n".join(violations)


# ============================================================================
# SEC-2: Infrastructure network defaults must be Deny
# ============================================================================


class TestInfraNetworkDefaults:
    """Bicep/ARM templates must not use defaultAction: Allow."""

    def test_no_allow_default_in_bicep(self):
        violations = []
        for f in INFRA_DIR.rglob("*.bicep"):
            content = f.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                if "defaultAction" in line and "'Allow'" in line:
                    violations.append(f"{f.relative_to(PROJECT_ROOT)}:{i}")

        assert not violations, (
            "Infrastructure has defaultAction: 'Allow' (must be 'Deny'):\n" + "\n".join(violations)
        )

    def test_no_allow_default_in_arm(self):
        violations = []
        for f in INFRA_DIR.rglob("*.json"):
            content = f.read_text()
            for i, line in enumerate(content.splitlines(), 1):
                if '"defaultAction"' in line and '"Allow"' in line:
                    violations.append(f"{f.relative_to(PROJECT_ROOT)}:{i}")

        assert not violations, "ARM template has defaultAction: Allow:\n" + "\n".join(violations)


# ============================================================================
# SEC-3: No listKeys() in Bicep (leaks secrets to ARM deployment history)
# ============================================================================


class TestNoListKeysInBicep:
    """Bicep must not use listKeys() without #nosec annotation."""

    def test_no_untracked_listkeys(self):
        violations = []
        for f in INFRA_DIR.rglob("*.bicep"):
            for i, line in enumerate(f.read_text().splitlines(), 1):
                stripped = line.strip()
                # Skip comments — only flag actual code usage
                if stripped.startswith("//"):
                    continue
                if "listKeys()" in line and "#nosec" not in line:
                    violations.append(f"{f.relative_to(PROJECT_ROOT)}:{i}: {stripped}")

        assert not violations, (
            "listKeys() without #nosec found (leaks secrets to deployment history):\n"
            + "\n".join(violations)
        )


# ============================================================================
# SEC-4: Auth middleware on all API routes
# ============================================================================


class TestAuthMiddleware:
    """All API route files must import auth dependencies."""

    PUBLIC_ROUTES = {"auth.py", "health.py", "privacy.py", "accessibility.py", "onboarding.py", "__init__.py"}

    def test_api_routes_require_auth(self):
        """Every data-bearing API route must reference get_current_user or require_roles.

        A route file that only uses Depends(get_db) is NOT protected.
        """
        routes_dir = APP_DIR / "api" / "routes"
        if not routes_dir.exists():
            pytest.skip("Routes directory not found")

        unprotected = []
        for f in routes_dir.glob("*.py"):
            if f.name in self.PUBLIC_ROUTES:
                continue
            content = f.read_text()
            has_auth = "get_current_user" in content or "require_roles" in content
            if not has_auth:
                unprotected.append(f.name)

        assert not unprotected, (
            f"Routes without authentication (get_current_user / require_roles): "
            f"{unprotected}. Add dependencies=[Depends(get_current_user)] to the router."
        )


# ============================================================================
# SEC-5: WCAG contrast — no invisible text classes
# ============================================================================


class TestWCAGContrast:
    """Templates must not use CSS classes that produce invisible text."""

    FORBIDDEN_CLASSES = [
        "text-gray-100",  # #F3F4F6 on white = 1.04:1
        "text-gray-160",  # doesn't exist — dead class
        "text-gray-50",  # #F9FAFB on white = 1.01:1
    ]

    def test_no_invisible_text_classes(self):
        if not TEMPLATES_DIR.exists():
            pytest.skip("Templates directory not found")

        violations = []
        for f in TEMPLATES_DIR.rglob("*.html"):
            content = f.read_text()
            for cls in self.FORBIDDEN_CLASSES:
                if cls in content:
                    violations.append(f"{f.relative_to(PROJECT_ROOT)}: uses '{cls}'")

        assert not violations, (
            "Templates use invisible/dead text classes (WCAG fail):\n" + "\n".join(violations)
        )

    def test_text_muted_meets_wcag_aa(self):
        """--text-muted must have >= 4.5:1 contrast on white."""
        css_file = CSS_DIR / "theme.src.css"
        if not css_file.exists():
            pytest.skip("theme.src.css not found")

        content = css_file.read_text()
        # WCAG-failing values for --text-muted
        failing_values = ["#9CA3AF", "#D1D5DB", "#E5E7EB", "#F3F4F6"]
        for val in failing_values:
            assert val not in content.split("dark")[0], (
                f"--text-muted set to {val} which fails WCAG AA (< 4.5:1 on white)"
            )
