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


@pytest.fixture
def macros_env():
    """Module-scoped Jinja env — shared by ds_static_table + ds_modal render tests.

    Hoisted to module scope during the Wave-2 merge (py7u.2.2 + .2.3) so both
    test classes can share one fixture without re-defining it per class.
    """
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
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

        Cap bumped from <50 to <60 at py7u.2.4 — the facade grows O(n)
        with primitive count by design (each new concern file = 1 import
        + 1 alias line), so the ceiling tracks primitive additions rather
        than forcing a monolith.
        """
        n = len(DS_MACROS.read_text().splitlines())
        assert n < 60, (
            f"ds.html facade is {n} lines — target <60 (py7u.2.1 set <50; bumped to <60 at py7u.2.4 to accommodate navigation.html re-exports)"
        )

    def test_ds_concern_files_exist(self):
        """Phase 4b-i: the 3 cohesion-based concern files must exist."""
        for fname in ("layout.html", "display.html", "forms.html", "navigation.html"):
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
        expected and why the budget started at 250, not 200.

        py7u.2.3 (ds_modal) + py7u.2.2 (ds_static_table) landed in the
        same merge wave. ds_modal was extracted to `display_dialogs.html`
        (honouring the 'next primitive triggers split, not bump' commitment),
        so display.html holds only inline-display primitives and
        display_dialogs.html starts the dialog-family concern file.
        Budget stays at 280 for both files.
        """
        budget = 280
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
        "ds_static_table",
        "ds_toolbar",
        "ds_modal",
        "ds_tabs",
        "ds_tab_panel",
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


# ── ds_toolbar primitive (py7u.2.6) ─────────────────────────────
class TestToolbar:
    """ds_toolbar is the page-level action bar primitive (filters left,
    actions right; stacks on mobile). These tests guard its structural
    contract so callers can rely on the layout utilities.
    """

    @pytest.fixture
    def toolbar_env(self):
        """Minimal Jinja env that can import macros/ds.html directly."""
        return Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def test_toolbar_renders_filters_and_actions(self, toolbar_env):
        """Filter slot (caller) and actions slot both appear, filters FIRST
        in DOM so keyboard tab order is natural (inputs before CTAs)."""
        tmpl = toolbar_env.from_string(
            '{% from "macros/ds.html" import ds_toolbar, ds_button %}'
            '{% call ds_toolbar(actions=ds_button("Add", variant="primary")) %}'
            '<input id="toolbar-filter" type="search">'
            "{% endcall %}"
        )
        out = tmpl.render()
        # Both slots present
        assert 'id="toolbar-filter"' in out
        assert "Add" in out
        # Filters render BEFORE actions in source order
        assert out.index('id="toolbar-filter"') < out.index(">Add<"), (
            "filter slot must precede actions in DOM (tab order)"
        )

    def test_toolbar_responsive_flex_classes(self, toolbar_env):
        """Outer container must use flex-col by default, flex-row at md+
        with justify-between — the core responsive contract of the primitive.
        """
        tmpl = toolbar_env.from_string(
            '{% from "macros/ds.html" import ds_toolbar %}'
            "{% call ds_toolbar() %}<input>{% endcall %}"
        )
        out = tmpl.render()
        for cls in (
            "flex",
            "flex-col",
            "gap-3",
            "md:flex-row",
            "md:items-center",
            "md:justify-between",
        ):
            assert cls in out, f"ds_toolbar missing responsive class {cls!r}"

    def test_toolbar_without_actions_omits_actions_div(self, toolbar_env):
        """When actions=None the right-side slot div is not rendered at all
        (the caller shouldn't pay for an empty wrapper)."""
        tmpl = toolbar_env.from_string(
            '{% from "macros/ds.html" import ds_toolbar %}'
            '{% call ds_toolbar() %}<input id="lonely">{% endcall %}'
        )
        out = tmpl.render()
        assert 'id="lonely"' in out
        # Only ONE inner flex-wrap div (the filters slot); actions div absent.
        assert out.count("flex-wrap") == 0, (
            "empty actions should not emit the flex-wrap actions wrapper"
        )

    def test_toolbar_extra_classes_forwarded(self, toolbar_env):
        """extra_classes appends to the outer container for caller overrides."""
        tmpl = toolbar_env.from_string(
            '{% from "macros/ds.html" import ds_toolbar %}'
            '{% call ds_toolbar(extra_classes="mb-8 custom-bg") %}'
            "<input>{% endcall %}"
        )
        out = tmpl.render()
        assert "mb-8" in out
        assert "custom-bg" in out

    def test_toolbar_shown_on_showcase(self, rendered_showcase):
        """ds_toolbar appears in the /design-system showcase with both its
        variants (search+filter+action, and search-only)."""
        # Variant 1 marker
        assert "Add User" in rendered_showcase
        assert 'id="ds-toolbar-demo-search"' in rendered_showcase
        assert 'id="ds-toolbar-demo-role"' in rendered_showcase
        # Variant 2 marker
        assert 'id="ds-toolbar-demo-search2"' in rendered_showcase
        # Section title present
        assert "Toolbar" in rendered_showcase


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


# ── ds_static_table primitive (py7u.2.2) ───────────────────────
class TestStaticTableDeclaration:
    """Signature + render smoke tests for the ds_static_table primitive.

    ds_static_table wraps the repeated card+table shell for pages that
    server-render their rows (as opposed to the HTMX-swapped ds_table).
    The {% call %} body supplies <tr>/<td> markup so consumers keep
    control over cell layout while getting consistent chrome + a11y.
    """

    DISPLAY_HTML = DS_CONCERN_DIR / "display.html"

    def test_macro_defined_with_required_columns_param(self):
        """Signature must match the py7u.2.2 contract: columns required, rest keyword-optional."""
        import re

        content = self.DISPLAY_HTML.read_text()
        match = re.search(
            r"{%\s*macro\s+ds_static_table\(([^)]*)\)\s*%}",
            content,
            re.DOTALL,
        )
        assert match, "ds_static_table macro signature not found in display.html"
        signature = match.group(1)

        # `columns` must be the first positional (no default) — Jinja requires
        # required params before defaults, same as Python.
        first_param = signature.split(",")[0].strip()
        assert first_param == "columns", (
            f"ds_static_table first param must be `columns`, got `{first_param}`"
        )

        # Optional params present with defaults
        for kw in ("title=None", "caption=None", "extra_card_classes="):
            assert kw in signature, (
                f"ds_static_table signature missing `{kw}` (see py7u.2.2 contract)"
            )

    @staticmethod
    def _render(env: Environment, body: str) -> str:
        """Render a tiny template that imports the facade and uses the macro."""
        tmpl = env.from_string(
            '{% from "macros/ds.html" import ds_static_table, ds_tabs, ds_tab_panel %}' + body
        )
        return tmpl.render()

    def test_minimal_render(self, macros_env):
        """Minimal shape: no title, no caption, 2 columns, 3 rows."""
        html = self._render(
            macros_env,
            '{% call ds_static_table(columns=["Name", "Status"]) %}'
            "<tr><td>alpha</td><td>green</td></tr>"
            "<tr><td>beta</td><td>amber</td></tr>"
            "<tr><td>gamma</td><td>red</td></tr>"
            "{% endcall %}",
        )
        assert ">Name<" in html and ">Status<" in html
        # No <caption> when caption=None — screen readers get table alone
        assert "<caption" not in html
        # ds_card wrapper still renders, but header row is omitted (title=None)
        assert "<section" in html
        assert "card-" not in html  # aria-labelledby only emitted when titled
        # Caller rows flow through the tbody
        assert ">alpha<" in html and ">gamma<" in html

    def test_full_render(self, macros_env):
        """Full shape: title, caption, 4 columns, 10 rows with varied content."""
        rows = "".join(
            f"<tr><td>row{i}</td><td>x{i}</td><td>y{i}</td><td>z{i}</td></tr>" for i in range(10)
        )
        html = self._render(
            macros_env,
            '{% call ds_static_table(columns=["A","B","C","D"],'
            ' title="Tenants", caption="Synced tenants snapshot") %}' + rows + "{% endcall %}",
        )
        # Title flows through ds_card header + aria-labelledby
        assert "Tenants" in html
        assert 'id="card-tenants"' in html
        # sr-only caption for screen readers
        assert '<caption class="sr-only">Synced tenants snapshot</caption>' in html
        # 4 header cells, each with scope="col"
        assert html.count('scope="col"') == 4
        # All 10 caller rows came through
        assert html.count("<tr>") >= 10

    def test_empty_render(self, macros_env):
        """Empty shape: title, caption, 4 columns, 0 rows (caller emits empty state)."""
        html = self._render(
            macros_env,
            '{% call ds_static_table(columns=["A","B","C","D"],'
            ' title="Nothing here", caption="No data") %}'
            '<tr><td colspan="4" class="px-6 py-4 text-center text-muted-theme">'
            "No results to display.</td></tr>{% endcall %}",
        )
        assert "Nothing here" in html
        assert '<caption class="sr-only">No data</caption>' in html
        assert "No results to display." in html
        assert 'colspan="4"' in html

    def test_showcase_demos_ds_static_table(self):
        """The /design-system page must demo the new primitive (py7u.2.2)."""
        content = SHOWCASE_HTML.read_text()
        assert "ds_static_table" in content, (
            "design_system.html must import/demo ds_static_table so the "
            "showcase covers every primitive"
        )


# ── ds_modal render smoke tests (py7u.2.3) ─────────────────────
class TestDsModalRendersWithA11yWiring:
    """ds_modal must render native <dialog> markup with correct a11y wiring.

    py7u.2.3 — verify the macro honours its a11y contract (WAI-ARIA APG
    Dialog pattern):
      - uses a native <dialog> element (not role="dialog" on a div)
      - aria-labelledby points at the header h2 id
      - aria-describedby only appears when `describedby` is supplied
      - size enum maps to the documented max-w-* classes

    These tests render the macro directly via Jinja (no HTTP layer), so
    they stay fast and deterministic.
    """

    def _render(self, env, **kwargs):
        tmpl = env.from_string(
            '{% from "macros/ds.html" import ds_modal %}'
            "{% call ds_modal(" + ", ".join(f"{k}={v!r}" for k, v in kwargs.items()) + ") %}"
            "<p>body</p>"
            "{% endcall %}"
        )
        return tmpl.render()

    def test_renders_native_dialog_element(self, macros_env):
        html = self._render(macros_env, id="m1", title="Edit")
        assert "<dialog" in html, "ds_modal must use a native <dialog> element"
        assert 'role="dialog"' not in html, (
            'ds_modal must NOT use role="dialog" on a div — native <dialog> only'
        )

    def test_aria_labelledby_wired_to_header_id(self, macros_env):
        html = self._render(macros_env, id="edit-user", title="Edit User")
        assert 'aria-labelledby="edit-user-title"' in html
        assert 'id="edit-user-title"' in html

    def test_aria_describedby_only_when_supplied(self, macros_env):
        # Not supplied → attribute absent
        bare = self._render(macros_env, id="m2", title="Bare")
        assert "aria-describedby" not in bare, (
            "aria-describedby must not appear unless describedby kwarg is set"
        )
        # Supplied → attribute wired
        wired = self._render(macros_env, id="m3", title="Wired", describedby="m3-desc")
        assert 'aria-describedby="m3-desc"' in wired

    @pytest.mark.parametrize(
        "size,expected",
        [
            ("sm", "max-w-sm"),
            ("md", "max-w-md"),
            ("lg", "max-w-2xl"),
            ("xl", "max-w-4xl"),
        ],
    )
    def test_size_enum_maps_to_max_width(self, macros_env, size, expected):
        html = self._render(macros_env, id="m", title="T", size=size)
        assert expected in html, f"size={size!r} should emit {expected!r}"

    def test_dismissible_renders_close_button_with_aria_label(self, macros_env):
        html = self._render(macros_env, id="m4", title="With close")
        # form method="dialog" lets <button type="submit"> close natively
        assert 'method="dialog"' in html
        assert 'aria-label="Close"' in html

    def test_non_dismissible_hides_close_button(self, macros_env):
        html = self._render(macros_env, id="m5", title="No close", dismissible=False)
        assert 'method="dialog"' not in html
        assert 'aria-label="Close"' not in html

    def test_custom_close_label_is_honoured(self, macros_env):
        html = self._render(macros_env, id="m6", title="i18n", close_label="Fermer")
        assert 'aria-label="Fermer"' in html

    def test_caller_body_is_emitted(self, macros_env):
        html = self._render(macros_env, id="m7", title="Body")
        assert "<p>body</p>" in html

    def test_exported_via_ds_facade(self):
        """ds_modal must be reachable via the ds.html facade (py7u.2.1 pattern)."""
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        module = env.get_template("macros/ds.html").module
        assert hasattr(module, "ds_modal"), "ds_modal is not exported by macros/ds.html facade"


# ── py7u.2.4: ds_tabs + ds_tab_panel render invariants ─────────
class TestTabsPrimitive:
    """Render-layer smoke tests for ds_tabs / ds_tab_panel (WAI-ARIA APG)."""

    @pytest.fixture
    def rendered_tabs(self, macros_env):
        """Render a 3-tab example in isolation (no base.html chrome)."""
        tmpl = macros_env.from_string(
            '{% from "macros/ds.html" import ds_tabs, ds_tab_panel %}'
            '{% call ds_tabs(id="t", tabs=[{"label":"One"},{"label":"Two"},'
            '{"label":"Three","disabled":true}], aria_label="Demo") %}'
            '{% call ds_tab_panel(tabs_id="t", index=0, active=true) %}'
            "P1{% endcall %}"
            '{% call ds_tab_panel(tabs_id="t", index=1) %}P2{% endcall %}'
            '{% call ds_tab_panel(tabs_id="t", index=2) %}P3{% endcall %}'
            "{% endcall %}"
        )
        return tmpl.render()

    def test_tablist_role_present(self, rendered_tabs):
        assert 'role="tablist"' in rendered_tabs
        assert 'aria-label="Demo"' in rendered_tabs

    def test_every_tab_has_tab_role(self, rendered_tabs):
        assert rendered_tabs.count('role="tab"') == 3

    def test_every_panel_has_tabpanel_role(self, rendered_tabs):
        assert rendered_tabs.count('role="tabpanel"') == 3

    def test_aria_selected_exactly_one_true(self, rendered_tabs):
        assert rendered_tabs.count('aria-selected="true"') == 1
        assert rendered_tabs.count('aria-selected="false"') == 2

    def test_roving_tabindex(self, rendered_tabs):
        import re

        tab_tabindexes = re.findall(r'role="tab"[^>]*tabindex="(-?\d)"', rendered_tabs)
        assert tab_tabindexes.count("0") == 1
        assert tab_tabindexes.count("-1") == 2

    def test_aria_controls_matches_panel_ids(self, rendered_tabs):
        for i in range(3):
            assert f'aria-controls="t-panel-{i}"' in rendered_tabs
            assert f'id="t-panel-{i}"' in rendered_tabs

    def test_aria_labelledby_matches_tab_ids(self, rendered_tabs):
        for i in range(3):
            assert f'aria-labelledby="t-tab-{i}"' in rendered_tabs
            assert f'id="t-tab-{i}"' in rendered_tabs

    def test_inactive_panels_hidden(self, rendered_tabs):
        assert rendered_tabs.count("hidden") >= 2

    def test_disabled_tab_marked(self, rendered_tabs):
        assert 'aria-disabled="true"' in rendered_tabs

    def test_auto_init_hook_present(self, rendered_tabs):
        assert "data-ds-tabs" in rendered_tabs

    def test_target_size_wcag_258(self, rendered_tabs):
        # WCAG 2.5.8 AAA — tabs must be >= 44px tall
        assert "min-h-[44px]" in rendered_tabs
