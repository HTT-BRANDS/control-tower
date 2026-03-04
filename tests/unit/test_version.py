"""Tests for version consistency."""
import re
import pytest

class TestVersionConsistency:
    def test_init_version_is_semver(self):
        from app import __version__
        assert re.match(r"^\d+\.\d+\.\d+", __version__)

    def test_config_version_matches_init(self):
        from app import __version__
        from app.core.config import Settings
        s = Settings()
        assert s.app_version == __version__

    def test_pyproject_version_matches_init(self):
        from app import __version__
        with open("pyproject.toml") as f:
            c = f.read()
        m = re.search(r'^version\s*=\s*"([^"]+)"', c, re.MULTILINE)
        assert m and m.group(1) == __version__

    def test_health_returns_correct_version(self, client):
        from app import __version__
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["version"] == __version__

    def test_health_detailed_returns_correct_version(self, client):
        from app import __version__
        r = client.get("/health/detailed")
        assert r.status_code == 200
        assert r.json()["version"] == __version__

    def test_version_not_old_hardcoded(self):
        from app import __version__
        assert __version__ != "0.1.0"
