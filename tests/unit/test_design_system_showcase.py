"""Smoke tests for the /design-system showcase page.

These tests protect the ds-template Phase 2 work (ADR-0005):
  - Every macro in `macros/ds.html` must render on the showcase page
  - The showcase template must not raise Jinja undefined errors
  - The route must be registered on the FastAPI app
  - The SWA glassmorphism tokens must be present in design-tokens.css

We deliberately render the template via Jinja2 directly (not through a
live server) so these tests stay fast and don't depend on auth, DB, or
network. The auth-gated HTTP path is covered separately by e2e tests.

See: bd issue azure-governance-platform-oxfd
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent.parent.parent
TEMPLATES_DIR = ROOT / "app" / "templates"
DS_MACROS = TEMPLATES_DIR / "macros" / "ds.html"
DS_CONCERN_DIR = TEMPLATES_DIR / "macros" / "ds"
SHOWCASE_HTML = TEMPLATES_DIR / "pages" / "design_system.html"
DESIGN_TOKENS_CSS = ROOT / "app" / "static" / "css" / "design-tokens.css"


# ── Fixtures ────────────────────────────────────────────────────
@pytest.fixture
def jinja_env():
    """A Jinja env mirroring app.core.templates for smoke rendering.

    The test suite relies on asserting specific output strings appear in the
    rendered HTML — typos in macro variable names would show up as missing
    output, not silent passes.
    """
    # Use Jinja's default Undefined (matches app.core.templates.templates) so
    # unrelated partials (nav, brand injection) can render without us having
    # to mock every persona/auth variable.
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


@pytest.fixture
def rendered_showcase(jinja_env):
    """Render pages/design_system.html end-to-end with a fake request/brand."""

    class _FakeState:
        csp_nonce = "test-nonce-xyz"
        gpc_enabled = False

    class _FakeRequest:
        state = _FakeState()

    tmpl = jinja_env.get_template("pages/design_system.html")
    return tmpl.render(
        request=_FakeRequest(),
        brand=SimpleNamespace(
            key="httbrands",
            inline_style="",
            google_fonts_url="https://fonts.googleapis.com/css2?family=Inter&display=swap",
            css_variables={},
        ),
    )


# ── File-layer invariants ──────────────────────────────────────
class TestFilesExist:
    def test_ds_macros_file_exists(self):
        assert DS_MACROS.exists(), "app/templates/macros/ds.html missing"

    def test_showcase_page_exists(self):
        assert SHOWCASE_HTML.exists(), "app/templates/pages/design_system.html missing"

    def test_ds_facade_is_thin(self):
        """ADR-0005 cohesion budget — the re-export facade stays tiny.

        Phase 4b-i (bd py7u.2.1) split the monolithic ds.html into
        cohesion-based concern files (layout/display/forms) and turned
        ds.html into a thin re-export facade. The facade should only
        contain import+alias plumbing and a short docblock; new primitives
        belong in the concern files, not here.
        """
        n = len(DS_MACROS.read_text().splitlines())
        assert n < 50, f"ds.html facade is {n} lines — target <50 (see py7u.2.1)"

    def test_ds_concern_files_exist(self):
        """Phase 4b-i: the 3 cohesion-based concern files must exist."""
        for fname in ("layout.html", "display.html", "forms.html"):
            fpath = DS_CONCERN_DIR / fname
            assert fpath.exists(), f"missing concern file: macros/ds/{fname}"

    def test_ds_concern_files_within_budget(self):
        """ADR-0005 per-file cohesion budget for the split primitive library.

        Each concern file holds a coherent slice of the ds-template library.
        The budget is <250L per file — well under the 600-line project
        ceiling and tight enough that any single concern fits on a couple
        of screens. If a concern file crosses 250, split it further (e.g.
        display → display + data) rather than bumping the number.

        Note: the raw content of the existing byte-for-byte preserved
        macro docstrings puts display.html in the 210-230L range; that is
        expected and why the budget is 250, not 200. When adding new
        primitives under py7u.2.2-.6, respect the 250 cap by slicing.
        """
        budget = 250
        for fpath in sorted(DS_CONCERN_DIR.glob("*.html")):
            n = len(fpath.read_text().splitlines())
            assert n < budget, (
                f"macros/ds/{fpath.name} is {n} lines — target <{budget} per ADR-0005"
            )


# ── Macro declaration invariants ───────────────────────────────
class TestMacroDeclarations:
    """Every canonical ds-template primitive must be defined."""

    REQUIRED_MACROS = [
        "ds_page_shell",
        "ds_card",
        "ds_stat_card",
        "ds_alert",
        "ds_button",
        "ds_card_grid",
        "ds_stats_row",
    ]

    @pytest.mark.parametrize("macro_name", REQUIRED_MACROS)
    def test_macro_is_defined(self, macro_name):
        """Every required primitive must be defined in one of the concern files.

        After py7u.2.1 the monolithic ds.html was split into layout/display/
        forms concern files and ds.html became a re-export facade. The macro
        definition lives in exactly one concern file; this test walks all of
        them to find it.
        """
        needle = f"macro {macro_name}("
        hits = [fpath for fpath in DS_CONCERN_DIR.glob("*.html") if needle in fpath.read_text()]
        assert hits, f"Macro {macro_name} not defined in any macros/ds/*.html concern file"
        assert len(hits) == 1, f"Macro {macro_name} defined in multiple concern files: {hits}"

    @pytest.mark.parametrize("macro_name", REQUIRED_MACROS)
    def test_macro_is_exported_via_facade(self, macro_name):
        """Every required primitive must be reachable through the ds.html facade.

        Callers depend on ``{% from "macros/ds.html" import ds_card, ... %}``.
        After the py7u.2.1 split, ds.html re-exports macros from the concern
        files via ``{% set ds_foo = _ns.ds_foo %}``. This test verifies the
        re-export actually publishes each macro on the facade's module
        namespace (Jinja's ``{% from ... import %}`` and ``{% include %}`` both
        silently fail to re-export -- hence the alias pattern).
        """
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        module = env.get_template("macros/ds.html").module
        assert hasattr(module, macro_name), (
            f"{macro_name} is not exported by macros/ds.html (facade broken)"
        )


# ── Render-layer invariants ─────────────────────────────────────
class TestShowcaseRenders:
    """Render the full page and verify every primitive shows up."""

    def test_renders_without_error(self, rendered_showcase):
        """Full render produces a non-trivial HTML page."""
        assert len(rendered_showcase) > 1000, "Showcase rendered suspiciously small"

    def test_page_shell_emitted(self, rendered_showcase):
        """ds_page_shell emits a recognizable wrapper with our title block."""
        assert "Design System" in rendered_showcase
        # breadcrumb
        assert 'aria-label="Breadcrumb"' in rendered_showcase
        # title block
        assert "<h1" in rendered_showcase

    def test_all_button_variants_rendered(self, rendered_showcase):
        """Every button variant must appear at least once on the page."""
        for label in ("Primary", "Secondary", "Danger", "Ghost"):
            assert label in rendered_showcase, f"Button variant {label!r} missing from showcase"

    def test_all_alert_severities_rendered(self, rendered_showcase):
        """4 alert severities × their identifying text must render."""
        # The showcase uses severity-specific copy — check for those.
        markers = ("Plain info alert", "Sync complete", "Heads up", "Sync failed")
        for m in markers:
            assert m in rendered_showcase, f"Alert marker {m!r} missing"

        # Also confirm role="alert" appears (a11y)
        assert rendered_showcase.count('role="alert"') >= 4

    def test_stat_card_renders_all_four(self, rendered_showcase):
        """The showcase puts 4 stat cards in a stats row."""
        for label in ("Tenants", "Total Spend", "Active Users", "Compliance %"):
            assert label in rendered_showcase, f"Stat card {label!r} missing"

    def test_disabled_button_has_a11y_attrs(self, rendered_showcase):
        assert "disabled" in rendered_showcase
        assert 'aria-disabled="true"' in rendered_showcase

    def test_link_button_mode_renders_anchor(self, rendered_showcase):
        """ds_button(href=...) should emit <a>, not <button>."""
        assert 'href="/dashboard"' in rendered_showcase


# ── Design-tokens invariants ────────────────────────────────────
class TestSWATokens:
    """Phase 2 adds SWA glassmorphism tokens to design-tokens.css."""

    @pytest.fixture
    def tokens_css(self):
        return DESIGN_TOKENS_CSS.read_text()

    @pytest.mark.parametrize(
        "token",
        [
            "--surface:",
            "--surface-2:",
            "--surface-glass:",
            "--bg-gradient:",
            "--swa-radius:",
            "--swa-shadow:",
            "--swa-transition:",
            "--sidebar-width:",
            "--min-target-size:",
        ],
    )
    def test_swa_token_defined(self, tokens_css, token):
        assert token in tokens_css, f"SWA token {token!r} missing from design-tokens.css"

    def test_swa_glass_only_in_dark(self, tokens_css):
        """Glassmorphism surface tokens must live under .dark (not :root)."""
        # Find the .dark block
        dark_start = tokens_css.find(".dark {")
        dark_end = tokens_css.find("}", dark_start)
        assert dark_start != -1, ".dark block missing"
        dark_block = tokens_css[dark_start:dark_end]
        assert "--surface:" in dark_block, "--surface must live in .dark"
        assert "--surface-glass:" in dark_block, "--surface-glass must live in .dark"

    def test_swa_transition_shared(self, tokens_css):
        """--swa-transition is motion — lives in :root so light mode has it too."""
        root_start = tokens_css.find(":root {")
        dark_start = tokens_css.find(".dark {")
        root_block = tokens_css[root_start:dark_start]
        assert "--swa-transition:" in root_block, "--swa-transition must be in :root"


# ── Route wiring invariants ─────────────────────────────────────
class TestRouteRegistered:
    def test_router_importable(self):
        from app.api.routes import design_system_router

        assert design_system_router is not None

    def test_route_mounted_on_app(self):
        from app.main import app

        paths = {route.path for route in app.routes if hasattr(route, "path")}
        assert "/design-system" in paths, "/design-system not mounted"


# ── Phase 3 Migration Tests ─────────────────────────────────────
class TestMigratedPages:
    """Pages migrated in Phase 3 must import + exercise ds macros."""

    @pytest.mark.parametrize(
        "page,required_macros",
        [
            ("pages/dashboard.html", ["ds_stat_card", "ds_card"]),
            (
                "pages/costs.html",
                ["ds_page_shell", "ds_stat_card", "ds_card", "ds_table", "ds_button"],
            ),
            (
                "pages/compliance.html",
                ["ds_page_shell", "ds_stat_card", "ds_card", "ds_table", "ds_button"],
            ),
            (
                "pages/resources.html",
                ["ds_page_shell", "ds_stat_card", "ds_card", "ds_table", "ds_button"],
            ),
            (
                "pages/identity.html",
                ["ds_page_shell", "ds_stat_card", "ds_card", "ds_table", "ds_button"],
            ),
            (
                "pages/preflight.html",
                ["ds_page_shell", "ds_stat_card", "ds_card", "ds_button", "ds_badge"],
            ),
        ],
    )
    def test_page_imports_ds_macros(self, page, required_macros):
        """Every migrated page imports the ds macros it uses."""
        content = (TEMPLATES_DIR / page).read_text()
        assert 'from "macros/ds.html" import' in content, f"{page} must import macros/ds.html"
        for macro in required_macros:
            assert macro in content, (
                f"{page} expected to use macro {macro} but does not reference it"
            )

    def test_dashboard_no_bespoke_stat_cards(self):
        """After migration, dashboard.html should not reassemble stat cards inline.

        Symptom of un-migrated card: the original inline pattern
        `<p class="text-3xl font-bold text-primary-theme">` immediately
        after a `p-6 border-l-4` wrapper. All stat cards now go through
        `ds_stat_card`, which renders that markup from the macro body.
        """
        content = (TEMPLATES_DIR / "pages/dashboard.html").read_text()
        # Level-2 summary cards used to inline this pattern 4 times.
        assert 'border-l-4" style="border-color: var(--color-' not in content, (
            'Bespoke border-l-4 + style="border-color" pattern still present — '
            "migrate to ds_stat_card(border_accent=...)"
        )
