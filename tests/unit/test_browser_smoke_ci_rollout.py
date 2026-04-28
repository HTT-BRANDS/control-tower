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
        assert "timeout-minutes: 15" in content

    def test_browser_smoke_job_is_a_blocking_gate(self):
        """After the soak ended, browser-smoke must NOT be best-effort.

        We pin this so accidentally re-introducing ``continue-on-error: true``
        in the browser-smoke job (or anywhere else in the workflow) trips a
        loud test instead of silently re-demoting the gate.
        """
        content = CI_WORKFLOW.read_text()
        assert "continue-on-error: true" not in content
        # The workflow advertises its blocking status in the step summary so
        # operators see the current rollout mode in every run.
        assert "blocking CI gate" in content

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

    def test_rollout_doc_describes_current_blocking_gate(self):
        """The rollout doc must reflect the *current* mode, not historic soak.

        After promotion, the doc must clearly state the gate is blocking, that
        the soak has ended, and what to do if the gate goes flaky. We also
        keep asserting the artifact-policy guardrails so a future edit can't
        accidentally re-allow cookies/storage-state in failure artifacts.
        """
        content = ROLLOUT_DOC.read_text()
        assert "blocking CI gate" in content
        assert "soak" in content.lower()
        assert "branch protection or rulesets" in content
        # Demotion / flake handling must be documented, not implicit.
        assert "flake threshold" in content
        # Artifact policy must keep prohibiting auth-bearing material.
        assert "cookie dumps" in content
        assert "storage state files" in content
