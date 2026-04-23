"""Browser-backed regression tests for sync status card theme contrast."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import Page

from app.core.templates import templates

CSS_FILES = [
    Path("app/static/css/design-tokens.css"),
    Path("app/static/css/tailwind-output.css"),
    Path("app/static/css/design-utilities.css"),
]


def _load_theme_css() -> str:
    """Load the same CSS stack used by the app for local browser rendering."""
    return "\n".join(path.read_text() for path in CSS_FILES)


def _render_sync_status_card() -> str:
    """Render the real sync status card template with representative job states."""
    template = templates.env.get_template("components/sync/sync_status_card.html")
    return template.render(
        status={
            "status": "degraded",
            "alerts": {"total_active": 3, "critical": 1, "error": 2},
            "jobs": {
                "costs": {
                    "status": "degraded",
                    "last_run": "2026-04-23T18:57:00Z",
                    "success_rate": 0.0,
                },
                "compliance": {
                    "status": "healthy",
                    "last_run": "2026-04-23T14:59:00Z",
                    "success_rate": 0.38,
                },
                "resources": {
                    "status": "healthy",
                    "last_run": "2026-04-23T18:01:00Z",
                    "success_rate": 0.79,
                },
                "identity": {
                    "status": "idle",
                    "last_run": "2026-04-22T19:03:00Z",
                    "success_rate": 0.82,
                },
            },
        },
        last_refresh=datetime.now(UTC),
    )


def _mount_template_in_browser(page: Page) -> None:
    """Render the sync status card into a standalone browser page."""
    css = _load_theme_css()
    html = _render_sync_status_card()
    page.set_content(
        f"""
        <!doctype html>
        <html class="dark">
          <head>
            <meta charset="utf-8">
            <style>{css}</style>
          </head>
          <body>
            <main class="p-8 bg-surface-primary">
              {html}
            </main>
          </body>
        </html>
        """
    )
    page.wait_for_timeout(100)


class TestSyncStatusDarkMode:
    """Dark mode regressions for sync status UI."""

    def test_job_labels_remain_legible_against_soft_status_surfaces(self, page: Page):
        """Job labels should maintain readable contrast in dark mode."""
        _mount_template_in_browser(page)

        card_metrics = page.locator("[data-sync-job-card]").evaluate_all(
            r"""
            (cards) => {
                const parseRgb = (value) => {
                    const match = value.match(/\d+(?:\.\d+)?/g);
                    return match ? match.slice(0, 3).map(Number) : [0, 0, 0];
                };
                const luminance = ([r, g, b]) => {
                    const toLinear = (channel) => {
                        const normalized = channel / 255;
                        return normalized <= 0.03928
                            ? normalized / 12.92
                            : ((normalized + 0.055) / 1.055) ** 2.4;
                    };
                    const [lr, lg, lb] = [r, g, b].map(toLinear);
                    return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb;
                };
                const contrast = (fg, bg) => {
                    const [lighter, darker] = [luminance(fg), luminance(bg)].sort((a, b) => b - a);
                    return (lighter + 0.05) / (darker + 0.05);
                };

                return cards.map((card) => {
                    const label = card.querySelector('[data-sync-job-label]');
                    const cardStyle = getComputedStyle(card);
                    const labelStyle = label ? getComputedStyle(label) : null;
                    const labelText = label ? label.textContent.trim() : '';
                    const ratio = labelStyle
                        ? contrast(parseRgb(labelStyle.color), parseRgb(cardStyle.backgroundColor))
                        : 0;

                    return {
                        labelText,
                        ratio,
                        backgroundColor: cardStyle.backgroundColor,
                        labelColor: labelStyle ? labelStyle.color : null,
                    };
                });
            }
            """
        )

        assert card_metrics, "Expected sync job cards to render"
        for metric in card_metrics:
            assert metric["labelText"], f"Missing label text for card: {metric}"
            assert metric["ratio"] >= 4.5, (
                f"Dark-mode label contrast too low for {metric['labelText']}: "
                f"{metric['ratio']:.2f} (fg={metric['labelColor']}, bg={metric['backgroundColor']})"
            )
