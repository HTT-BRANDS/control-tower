"""Unit tests for `scripts/judge_repo_checks.py`.

Each check is exercised twice where possible:
- A happy-path assertion against the real repo (should pass right now)
- A failure-path assertion against a tampered tmp fixture (locks in the
  failure detail format so dashboards stay parseable)

These tests intentionally do NOT mock the filesystem for the happy path —
they're the same signal that judge.py would emit, run in CI so we notice
the second a check would start to fail in production.
"""

from __future__ import annotations

from scripts.judge_repo_checks import (
    check_changelog_current,
    check_dockerfile_non_root,
    check_focus_visible_uses_brand_token,
    check_no_focus_outline_none,
    check_no_handrolled_badges,
    check_no_invisible_text,
    check_role_enum_lockstep,
    check_session_handoff_fresh,
    check_status_md_fresh,
)


# ---------------------------------------------------------------------------
# Happy path — checks pass against the real repo today
# ---------------------------------------------------------------------------
class TestHappyPathAgainstRealRepo:
    """If these start failing in CI, the repo state regressed — investigate the
    underlying file, don't 'fix' the test."""

    def test_no_invisible_text(self):
        ok, detail = check_no_invisible_text()
        assert ok, f"text-gray-100 reappeared: {detail}"

    def test_no_focus_outline_none(self):
        ok, detail = check_no_focus_outline_none()
        assert ok, f"unringed focus:outline-none reappeared: {detail}"

    def test_focus_visible_uses_brand_token(self):
        ok, detail = check_focus_visible_uses_brand_token()
        assert ok, f"hard-coded focus ring colour reappeared: {detail}"

    def test_status_md_fresh(self):
        ok, detail = check_status_md_fresh()
        assert ok, f"STATUS.md gone stale: {detail}"

    def test_changelog_current(self):
        ok, detail = check_changelog_current()
        assert ok, f"CHANGELOG.md has no recent dated entry: {detail}"

    def test_session_handoff_fresh(self):
        ok, detail = check_session_handoff_fresh()
        assert ok, f"SESSION_HANDOFF.md gone stale: {detail}"

    def test_role_enum_lockstep(self):
        ok, detail = check_role_enum_lockstep()
        assert ok, f"Role enum / _ROLE_DESCRIPTIONS drift: {detail}"

    def test_dockerfile_non_root(self):
        ok, detail = check_dockerfile_non_root()
        assert ok, f"Dockerfile runs as root: {detail}"

    def test_no_handrolled_badges(self):
        ok, detail = check_no_handrolled_badges()
        assert ok, f"hand-rolled badge spans reappeared in Jinja templates: {detail}"


# ---------------------------------------------------------------------------
# Failure path — synthetic fixtures verify the failure detail format
# ---------------------------------------------------------------------------
class TestFailureDetailFormat:
    """Lock in the human-readable failure strings — judge dashboards parse them."""

    def test_status_md_missing_returns_clear_detail(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, detail = mod.check_status_md_fresh()
        assert ok is False
        assert "missing" in detail

    def test_status_md_stale_returns_age(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        stale = tmp_path / "STATUS.md"
        stale.write_text("stale")
        # Force mtime to 30 days ago
        import os
        import time
        thirty_days_ago = time.time() - 30 * 86400
        os.utime(stale, (thirty_days_ago, thirty_days_ago))

        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, detail = mod.check_status_md_fresh()
        assert ok is False
        assert "mtime age" in detail and "threshold" in detail

    def test_changelog_missing(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, detail = mod.check_changelog_current()
        assert ok is False and "missing" in detail

    def test_changelog_only_ancient_entries(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        (tmp_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## v1.0.0 - 2019-01-01\n- ancient release\n"
        )
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, detail = mod.check_changelog_current()
        assert ok is False
        assert "no entry within" in detail

    def test_changelog_with_recent_entry_passes(self, tmp_path, monkeypatch):
        from datetime import date

        from scripts import judge_repo_checks as mod

        recent = date.today().isoformat()
        (tmp_path / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## v2.5.99 - {recent}\n- fresh entry\n"
        )
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, detail = mod.check_changelog_current()
        assert ok is True
        assert recent in detail

    def test_focus_outline_none_flags_unringed(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        templates = tmp_path / "app" / "templates"
        templates.mkdir(parents=True)
        (templates / "bad.html").write_text(
            '<button class="focus:outline-none">click</button>\n'
        )
        # No static dir is fine — the function tolerates missing globs
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, detail = mod.check_no_focus_outline_none()
        assert ok is False
        assert "unringed" in detail

    def test_focus_outline_none_accepts_ring_pair(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        templates = tmp_path / "app" / "templates"
        templates.mkdir(parents=True)
        (templates / "good.html").write_text(
            '<button class="focus:outline-none focus:ring-2 ring-primary">click</button>\n'
        )
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, detail = mod.check_no_focus_outline_none()
        assert ok is True

    def test_no_invisible_text_flags_gray_100(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        templates = tmp_path / "app" / "templates"
        templates.mkdir(parents=True)
        (templates / "bad.html").write_text('<p class="text-gray-100">whoops</p>\n')
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, detail = mod.check_no_invisible_text()
        assert ok is False
        assert "occurrence" in detail

    def test_handrolled_badge_flagged(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        templates = tmp_path / "app" / "templates"
        templates.mkdir(parents=True)
        (templates / "bad.html").write_text(
            '<span class="px-2 py-1 text-xs rounded bg-red-500 text-white">P0</span>\n'
        )
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, detail = mod.check_no_handrolled_badges()
        assert ok is False
        assert "hand-rolled" in detail

    def test_handrolled_badge_daisyui_passes(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        templates = tmp_path / "app" / "templates"
        templates.mkdir(parents=True)
        # DaisyUI badge — should NOT be flagged despite text-xs rounded px-
        (templates / "good.html").write_text(
            '<span class="badge badge-error badge-sm">P0</span>\n'
        )
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, _ = mod.check_no_handrolled_badges()
        assert ok is True

    def test_handrolled_badge_js_template_literal_skipped(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        templates = tmp_path / "app" / "templates"
        templates.mkdir(parents=True)
        # JS template literal context — tracked separately (ct-ofx follow-up)
        (templates / "js.html").write_text(
            "<script>\n"
            "const html = `\n"
            '<span class="px-2 py-1 text-xs rounded bg-red-500 text-white">${name}</span>\n'
            "`;\n"
            "</script>\n"
        )
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, _ = mod.check_no_handrolled_badges()
        assert ok is True


# ---------------------------------------------------------------------------
# xpassed check — soft-pass semantics (don't penalise empty caches)
# ---------------------------------------------------------------------------
class TestXpassed:
    def test_no_cache_passes_with_explanation(self, tmp_path, monkeypatch):
        from scripts import judge_repo_checks as mod

        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        ok, detail = mod.check_no_xpassed()
        assert ok is True
        assert "no pytest cache" in detail
