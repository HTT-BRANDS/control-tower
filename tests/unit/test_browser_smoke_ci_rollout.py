"""Contract checks for browser-smoke CI rollout wiring."""

from pathlib import Path

CI_WORKFLOW = Path(".github/workflows/ci.yml")
ROLLOUT_DOC = Path("docs/testing/browser_smoke_ci_rollout.md")


class TestBrowserSmokeCiWorkflow:
    def test_ci_workflow_contains_browser_smoke_job(self):
        content = CI_WORKFLOW.read_text()
        assert "browser-smoke:" in content
        assert "name: Browser Smoke" in content
        assert "needs: lint-and-test" in content
        assert "continue-on-error: true" in content
        assert "timeout-minutes: 15" in content

    def test_ci_workflow_pins_browser_runtime_and_readiness(self):
        content = CI_WORKFLOW.read_text()
        assert "uv run playwright install chromium --with-deps" in content
        assert "uv run python scripts/wait_for_url.py" in content
        assert "/api/v1/health" in content
        assert "tests/e2e/test_browser_smoke.py" in content

    def test_ci_workflow_uploads_failure_only_sanitized_artifacts(self):
        content = CI_WORKFLOW.read_text()
        assert "Upload sanitized browser-smoke failure artifacts" in content
        assert "if: failure()" in content
        assert "tests/e2e/screenshots/" in content
        assert "artifacts/browser-smoke/pytest.log" in content
        assert "retention-days: 7" in content


class TestBrowserSmokeCiDocs:
    def test_rollout_doc_exists(self):
        assert ROLLOUT_DOC.exists()

    def test_rollout_doc_covers_soak_and_branch_protection(self):
        content = ROLLOUT_DOC.read_text()
        assert "non-blocking (`continue-on-error: true`)" in content
        assert "10 consecutive green `browser-smoke` runs" in content
        assert "branch protection or rulesets" in content
        assert (
            "no cookies, storage state files, auth headers" in content or "cookie dumps" in content
        )
