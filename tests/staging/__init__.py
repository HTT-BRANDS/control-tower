"""Staging validation tests.

Run against a live staging environment:

    pytest tests/staging/ --staging-url=https://app-governance-staging-xnczpwyv.azurewebsites.net

Or via environment variable:

    STAGING_URL=https://... pytest tests/staging/

These tests require no database or local server — they hit the real endpoint.
"""
