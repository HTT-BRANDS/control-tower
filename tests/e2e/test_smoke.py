"""Smoke tests for the Azure Governance Platform.

Placeholder suite for future browser-based E2E testing (e.g. Playwright).
For now, just ensures the app package is importable.
"""


def test_app_module_imports():
    """The app package should be importable without errors."""
    import app

    assert app is not None
