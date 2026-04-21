"""Design system compliance tests — prevent raw Tailwind color regressions.

These tests scan every template and JS file to ensure they ONLY use design
system tokens (brand-*, wm-*, bg-surface-*, text-*-theme, etc.) and never
bypass them with raw Tailwind palette classes like bg-red-600 or text-blue-500.

If a test here fails, it means someone added a raw color that bypasses the
design system. Fix it by using the appropriate token from theme.src.css.

Guards the work done in commit 23bbd71:
  "fix: WCAG 2.2 AA design system hardening — zero raw Tailwind violations"
"""

import re
from pathlib import Path

import pytest

# ── Paths ───────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent
TEMPLATES_DIR = ROOT / "app" / "templates"
STATIC_JS_DIR = ROOT / "app" / "static" / "js"

# Phase 1 (ADR-0005): design system split into 3 files.
#   design-tokens.css       — :root vars, dark mode, brand ramps
#   tailwind-output.css     — generated, not human-edited
#   design-utilities.css    — brand helpers, components, a11y, skip links
#
# These tests treat the (tokens + utilities) pair as the canonical "theme".
DESIGN_TOKENS_CSS = ROOT / "app" / "static" / "css" / "design-tokens.css"
DESIGN_UTILITIES_CSS = ROOT / "app" / "static" / "css" / "design-utilities.css"


class _Concat:
    """Path-like façade that read_text()s multiple files concatenated.

    Lets legacy assertions keep using THEME_SRC.read_text() without caring
    that the design system was split into multiple files in Phase 1.
    """

    def __init__(self, *paths):
        self._paths = paths

    def exists(self):
        return all(p.exists() for p in self._paths)

    def read_text(self):
        return "\n".join(p.read_text() for p in self._paths)


# Token-only (used by tests that assert about :root variables)
THEME_SRC = _Concat(DESIGN_TOKENS_CSS, DESIGN_UTILITIES_CSS)

# A11y patterns moved into design-utilities.css in Phase 1
ACCESSIBILITY_CSS = DESIGN_UTILITIES_CSS

# ── Banned Patterns ─────────────────────────────────────────────
# Raw Tailwind palette colors that should NEVER appear in templates or JS.
# These bypass the design system and break dark mode, tenant branding, and WCAG.
#
# Allowed exceptions:
#   - CSS dark mode fallback selectors (e.g., `.dark .bg-gray-50`)
#   - Gradient classes on hero banners (from-indigo-600, to-blue-800) — intentional brand gradient
#   - Comments explaining the design system
BANNED_COLOR_PATTERN = re.compile(
    r"""(?<![\w-])           # Not preceded by word char or hyphen (avoid matching wm-blue-100)
    (?:bg|text|border|ring|divide|from|to|via)-  # Tailwind utility prefix
    (?:red|green|blue|yellow|orange|purple|pink|indigo|teal|cyan|emerald|amber|lime|rose|fuchsia|violet|sky|slate|stone|zinc|neutral)  # Raw palette name
    -\d{1,3}                # Shade number (50-950)
    (?![\w-])               # Not followed by word char or hyphen
    """,
    re.VERBOSE,
)

# Gray is special — theme.src.css has intentional dark mode fallback selectors
# like `.dark .bg-gray-50`. We ban grays everywhere EXCEPT theme.src.css.
BANNED_GRAY_PATTERN = re.compile(
    r"""(?<![\w-])
    (?:bg|text|border|ring|divide)-gray-\d{1,3}
    (?![\w-])
    """,
    re.VERBOSE,
)

# focus:outline-none without a ring replacement — kills native focus indicators
BANNED_FOCUS_OUTLINE_NONE = re.compile(r"focus:outline-none")

# border-theme is a ghost class — not defined in design-utilities.css, not a
# Tailwind color key (no "theme" in tailwind.config.cjs). It gets silently
# dropped by Tailwind, causing elements to fall back to the default border
# color, which DIVERGES from --border-default in dark mode (#e5e7eb vs
# #6B7280). Discovered via cwxu audit (2026-04); 21 sites fixed in 9v9u.
BANNED_BORDER_THEME_PATTERN = re.compile(r"\bborder-theme\b")

# Hardcoded hex colors in inline styles (bypasses design system)
INLINE_HEX_PATTERN = re.compile(
    r"""style\s*=\s*["'][^"']*
    (?:color|background(?:-color)?|border(?:-color)?)\s*:\s*\#[0-9a-fA-F]{3,8}
    """,
    re.VERBOSE,
)

# ── Helpers ─────────────────────────────────────────────────────
GRADIENT_EXCEPTIONS = {"from-indigo-600", "to-blue-800", "from-blue-600"}


def _collect_files(directory: Path, extension: str) -> list[Path]:
    """Collect all files with given extension, excluding node_modules."""
    if not directory.exists():
        return []
    return [
        f
        for f in directory.rglob(f"*{extension}")
        if "node_modules" not in str(f) and "__pycache__" not in str(f)
    ]


def _find_violations(
    filepath: Path, pattern: re.Pattern, skip_comments: bool = True
) -> list[tuple[int, str, str]]:
    """Find pattern violations in a file. Returns [(line_num, match, line_text)]."""
    violations = []
    content = filepath.read_text(encoding="utf-8")
    for i, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        # Skip HTML/JS/CSS comments
        if skip_comments and (
            stripped.startswith("//")
            or stripped.startswith("/*")
            or stripped.startswith("*")
            or stripped.startswith("<!--")
        ):
            continue
        for match in pattern.finditer(line):
            matched = match.group()
            # Allow gradient exceptions on hero banners
            if matched in GRADIENT_EXCEPTIONS:
                continue
            violations.append((i, matched, stripped))
    return violations


# ── Template Tests ──────────────────────────────────────────────
class TestTemplateColorCompliance:
    """Ensure HTML templates use only design system tokens."""

    @pytest.fixture
    def html_files(self):
        return _collect_files(TEMPLATES_DIR, ".html")

    def test_templates_exist(self, html_files):
        """Sanity: we have templates to test."""
        assert len(html_files) > 0, "No HTML templates found!"

    def test_no_raw_tailwind_colors_in_templates(self, html_files):
        """No raw Tailwind palette colors (red-500, blue-600, etc.) in any template."""
        all_violations = []
        for f in html_files:
            violations = _find_violations(f, BANNED_COLOR_PATTERN)
            for line_num, matched, _line_text in violations:
                all_violations.append(f"  {f.relative_to(ROOT)}:{line_num} — {matched}")

        assert not all_violations, (
            f"Found {len(all_violations)} raw Tailwind color(s) in templates.\n"
            "Use design system tokens (brand-*, wm-*, bg-surface-*, text-success, etc.) instead.\n"
            + "\n".join(all_violations[:20])  # Show first 20
        )

    def test_no_raw_gray_in_templates(self, html_files):
        """No raw bg-gray-*, text-gray-* in templates (use surface/theme tokens)."""
        all_violations = []
        for f in html_files:
            violations = _find_violations(f, BANNED_GRAY_PATTERN)
            for line_num, matched, _line_text in violations:
                all_violations.append(f"  {f.relative_to(ROOT)}:{line_num} — {matched}")

        assert not all_violations, (
            f"Found {len(all_violations)} raw gray class(es) in templates.\n"
            "Use bg-surface-primary/secondary/tertiary or text-primary/secondary/muted-theme instead.\n"
            + "\n".join(all_violations[:20])
        )

    def test_no_focus_outline_none_in_templates(self, html_files):
        """No focus:outline-none which kills native focus indicators (WCAG 2.4.7)."""
        all_violations = []
        for f in html_files:
            violations = _find_violations(f, BANNED_FOCUS_OUTLINE_NONE)
            for line_num, _matched, _line_text in violations:
                all_violations.append(f"  {f.relative_to(ROOT)}:{line_num}")

        assert not all_violations, (
            f"Found {len(all_violations)} focus:outline-none in templates.\n"
            "This suppresses native focus indicators (WCAG 2.4.7 violation).\n"
            "Use focus-visible:ring-2 or let accessibility.css handle focus styles.\n"
            + "\n".join(all_violations[:20])
        )

    def test_no_ghost_border_theme_class_in_templates(self, html_files):
        """No `border-theme` class — it is not defined anywhere (9v9u).

        `theme` is NOT a Tailwind color key (checked tailwind.config.cjs) and
        `.border-theme` is NOT a rule in design-utilities.css. Templates that
        use it get silently dropped by Tailwind, falling back to its default
        border color — which coincides with --border-default in LIGHT mode but
        diverges in DARK mode (fallback stays light while border-default
        becomes #6B7280). Using `border-default` gives theme-aware behavior.

        Guards the 9v9u normalization sweep (20 sites across 5 files).
        """
        all_violations = []
        for f in html_files:
            violations = _find_violations(f, BANNED_BORDER_THEME_PATTERN)
            for line_num, _matched, _line_text in violations:
                all_violations.append(f"  {f.relative_to(ROOT)}:{line_num}")

        assert not all_violations, (
            f"Found {len(all_violations)} `border-theme` ghost-class use(s) in templates.\n"
            "`border-theme` is not defined (not a Tailwind color, not a utility rule). "
            "Use `border-default` for theme-aware borders that honor dark mode.\n"
            + "\n".join(all_violations[:20])
        )


# ── JavaScript Tests ────────────────────────────────────────────
class TestJavaScriptColorCompliance:
    """Ensure JS files use only design system tokens."""

    @pytest.fixture
    def js_files(self):
        files = _collect_files(STATIC_JS_DIR, ".js")
        # Exclude the bundle since source files cover it
        return [f for f in files if ".bundle." not in f.name]

    def test_js_files_exist(self, js_files):
        assert len(js_files) > 0, "No JS files found!"

    def test_no_raw_tailwind_colors_in_js(self, js_files):
        """No raw Tailwind palette colors in JavaScript template literals."""
        all_violations = []
        for f in js_files:
            violations = _find_violations(f, BANNED_COLOR_PATTERN)
            for line_num, matched, _line_text in violations:
                all_violations.append(f"  {f.relative_to(ROOT)}:{line_num} — {matched}")

        assert not all_violations, (
            f"Found {len(all_violations)} raw Tailwind color(s) in JS files.\n"
            + "\n".join(all_violations[:20])
        )

    def test_no_raw_gray_in_js(self, js_files):
        """No raw gray classes in JavaScript."""
        all_violations = []
        for f in js_files:
            violations = _find_violations(f, BANNED_GRAY_PATTERN)
            for line_num, matched, _line_text in violations:
                all_violations.append(f"  {f.relative_to(ROOT)}:{line_num} — {matched}")

        assert not all_violations, (
            f"Found {len(all_violations)} raw gray class(es) in JS files.\n"
            + "\n".join(all_violations[:20])
        )


# ── CSS Tests ───────────────────────────────────────────────────
class TestCSSDesignSystem:
    """Verify CSS files follow the design system correctly."""

    def test_theme_src_exists(self):
        assert THEME_SRC.exists(), "theme.src.css not found!"

    def test_accessibility_css_exists(self):
        assert ACCESSIBILITY_CSS.exists(), "accessibility.css not found!"

    def test_accessibility_css_uses_brand_token_for_focus(self):
        """accessibility.css must use var(--brand-primary) for focus-visible, not hardcoded blue."""
        content = ACCESSIBILITY_CSS.read_text()
        assert "var(--brand-primary" in content, (
            "accessibility.css must use var(--brand-primary) for focus-visible outlines"
        )
        # Must NOT have hardcoded Walmart blue
        assert "#0053e2" not in content.lower(), (
            "accessibility.css still has hardcoded #0053e2 (Walmart blue). "
            "Use var(--brand-primary, #500711) instead."
        )

    def test_accessibility_css_has_forced_colors(self):
        """accessibility.css must support forced-colors (Windows High Contrast)."""
        content = ACCESSIBILITY_CSS.read_text()
        assert "forced-colors" in content, (
            "accessibility.css must include @media (forced-colors: active) for HC mode"
        )

    def test_accessibility_css_has_reduced_motion(self):
        """accessibility.css must respect prefers-reduced-motion."""
        content = ACCESSIBILITY_CSS.read_text()
        assert "prefers-reduced-motion" in content, (
            "accessibility.css must include @media (prefers-reduced-motion: reduce)"
        )

    def test_accessibility_css_has_skip_link(self):
        """accessibility.css must define .skip-link for keyboard navigation."""
        content = ACCESSIBILITY_CSS.read_text()
        assert ".skip-link" in content, "accessibility.css must define .skip-link"

    def test_btn_brand_focus_uses_outline(self):
        """btn-brand:focus-visible must use outline (not just box-shadow) for HC mode."""
        content = THEME_SRC.read_text()
        # Find the btn-brand:focus-visible block
        focus_block_match = re.search(r"\.btn-brand:focus-visible\s*\{([^}]+)\}", content)
        assert focus_block_match, "btn-brand:focus-visible rule not found in theme.src.css"

        block = focus_block_match.group(1)
        assert "outline:" in block, (
            "btn-brand:focus-visible must use 'outline:' (not just box-shadow) "
            "for Windows High Contrast Mode compatibility"
        )
        # Must not have outline: none
        assert "outline: none" not in block, "btn-brand:focus-visible must NOT use 'outline: none'"

    def test_text_muted_meets_wcag_aa(self):
        """--text-muted must have >= 4.5:1 contrast ratio on white (WCAG AA)."""
        content = THEME_SRC.read_text()
        # Find --text-muted value in the :root block
        match = re.search(r"--text-muted:\s*(#[0-9a-fA-F]{6})", content)
        assert match, "--text-muted not found in theme.src.css"

        hex_color = match.group(1)
        ratio = _contrast_ratio(hex_color, "#FFFFFF")
        assert ratio >= 4.5, (
            f"--text-muted ({hex_color}) has only {ratio:.2f}:1 contrast on white. "
            f"WCAG AA requires >= 4.5:1. Darken the color."
        )

    def test_theme_defines_all_semantic_tokens(self):
        """theme.src.css must define all required semantic color tokens."""
        content = THEME_SRC.read_text()
        required_tokens = [
            "--color-success",
            "--color-warning",
            "--color-error",
            "--color-info",
            "--text-primary",
            "--text-secondary",
            "--text-muted",
            "--bg-primary",
            "--bg-secondary",
            "--bg-tertiary",
            "--border-color",
            "--brand-primary",
        ]
        for token in required_tokens:
            assert token in content, f"Required token {token} not found in theme.src.css"

    def test_theme_defines_utility_classes(self):
        """theme.src.css must define semantic utility classes."""
        content = THEME_SRC.read_text()
        required_classes = [
            ".bg-surface-primary",
            ".bg-surface-secondary",
            ".bg-surface-tertiary",
            ".text-primary-theme",
            ".text-secondary-theme",
            ".text-muted-theme",
            ".bg-success",
            ".bg-warning",
            ".bg-danger",
            ".text-success",
            ".text-warning",
            ".text-danger",
        ]
        for cls in required_classes:
            assert cls in content, f"Required utility class {cls} not found in theme.src.css"


# ── Base Template Tests ─────────────────────────────────────────
class TestBaseTemplate:
    """Verify base.html has required accessibility and design system features."""

    @pytest.fixture
    def base_html(self):
        path = TEMPLATES_DIR / "base.html"
        assert path.exists(), "base.html not found!"
        return path.read_text()

    def test_skip_link_present(self, base_html):
        """base.html must have a skip-to-main-content link."""
        assert "skip-link" in base_html, "base.html must include a .skip-link element"
        assert "#main-content" in base_html, "Skip link must target #main-content"

    def test_main_content_landmark(self, base_html):
        """base.html must have a <main> element with id for skip link."""
        assert 'id="main-content"' in base_html, "base.html must have <main id='main-content'>"

    def test_lang_attribute(self, base_html):
        """base.html must have lang attribute on <html>."""
        assert 'lang="en"' in base_html, "base.html <html> must have lang='en'"

    def test_viewport_meta(self, base_html):
        """base.html must have responsive viewport meta tag."""
        assert "viewport" in base_html, "base.html must include viewport meta tag"

    def test_loads_design_system_css(self, base_html):
        """base.html must load the 3-file design system stack (ADR-0005).

        Phase 1 split the old monolithic theme/accessibility CSS into:
          design-tokens.css     (CSS custom properties + dark mode)
          tailwind-output.css   (generated utility classes)
          design-utilities.css  (brand helpers, components, a11y, skip links)
        """
        for css_file in (
            "design-tokens.css",
            "tailwind-output.css",
            "design-utilities.css",
        ):
            assert css_file in base_html, f"base.html must load {css_file}"

    def test_page_announcer_for_spa(self, base_html):
        """base.html must have an aria-live region for SPA page changes."""
        assert "aria-live" in base_html, "base.html must include an aria-live announcer region"

    def test_nav_has_aria_label(self, base_html):
        """Navigation must have aria-label for screen readers."""
        assert "aria-label=" in base_html, "Navigation must have aria-label"


# ── Login Template Tests ────────────────────────────────────────
class TestLoginTemplate:
    """Verify login.html uses design system tokens."""

    @pytest.fixture
    def login_html(self):
        path = TEMPLATES_DIR / "login.html"
        assert path.exists(), "login.html not found!"
        return path.read_text()

    def test_no_inline_hex_colors(self, login_html):
        """login.html must not use hardcoded hex colors in inline styles."""
        # Check for style="...color: #..." or style="...background-color: #..."
        violations = INLINE_HEX_PATTERN.findall(login_html)
        assert not violations, (
            f"login.html has {len(violations)} inline hex color(s). "
            "Use design system classes (bg-brand-primary, text-muted-theme, etc.) instead."
        )

    def test_uses_design_tokens(self, login_html):
        """login.html must use brand-primary and muted-theme tokens."""
        assert "bg-brand-primary" in login_html or "btn-brand" in login_html, (
            "login.html must use brand-primary or btn-brand for the brand accent"
        )
        assert "text-muted-theme" in login_html, (
            "login.html must use text-muted-theme for secondary text"
        )


# ── Contrast Ratio Helper ──────────────────────────────────────
def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #RRGGBB to (R, G, B)."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(r: int, g: int, b: int) -> float:
    """WCAG 2.x relative luminance calculation."""

    def linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _contrast_ratio(color1: str, color2: str) -> float:
    """Calculate WCAG contrast ratio between two hex colors."""
    l1 = _relative_luminance(*_hex_to_rgb(color1))
    l2 = _relative_luminance(*_hex_to_rgb(color2))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ── Structural invariants (hbvt) ────────────────────────────────
# These aren't "color compliance" strictly — they guard template-level
# invariants where a visual regression isn't caught by type checks or route
# tests. Placed here because the file already encodes "prevent silent
# template drift" (banned colors, banned gray, ghost classes).


class TestAdminDashboardUsersTable:
    """Guards the admin_dashboard users-table (intentionally bespoke per hbvt).

    Because the table is NOT rendered via the ds_table macro, nothing else
    checks that the three places defining its column shape stay in sync:

      1. <thead> in pages/admin_dashboard.html       ← the visual contract
      2. Skeleton <tr> (animate-pulse) same file     ← HTMX pre-load state
      3. Data <tr> in partials/admin_users_table_body.html  ← HTMX post-load

    If any of these drift out of alignment, the table "jumps" when HTMX
    swaps in real data — a visible, user-facing bug that's easy to miss
    in code review. This test makes the invariant explicit.
    """

    ADMIN_DASHBOARD = TEMPLATES_DIR / "pages" / "admin_dashboard.html"
    USERS_PARTIAL = TEMPLATES_DIR / "partials" / "admin_users_table_body.html"

    def test_admin_users_table_column_parity(self):
        """Thead <th>, skeleton <td>, and partial data <td> counts must match."""
        dash = self.ADMIN_DASHBOARD.read_text()
        partial = self.USERS_PARTIAL.read_text()

        # --- thead column count (the authoritative visual contract) ---
        thead_match = re.search(
            r'<table class="w-full text-sm" data-table="admin-users">.*?<thead>(.*?)</thead>',
            dash,
            re.DOTALL,
        )
        assert thead_match, "admin-users <thead> not found — did the table markup change?"
        thead_cols = len(re.findall(r"<th\b", thead_match.group(1)))

        # --- skeleton row (HTMX pre-load placeholder) ---
        skeleton_match = re.search(
            r'<tr class="border-b border-default animate-pulse">(.*?)</tr>',
            dash,
            re.DOTALL,
        )
        assert skeleton_match, "skeleton row not found — did the animate-pulse class change?"
        skeleton_cols = len(re.findall(r"<td\b", skeleton_match.group(1)))

        # --- data row in the HTMX partial (post-load) ---
        data_match = re.search(
            r'<tr class="border-b border-default hover:bg-surface-secondary[^"]*">(.*?)</tr>',
            partial,
            re.DOTALL,
        )
        assert data_match, "data row in users partial not found — did the row class change?"
        data_cols = len(re.findall(r"<td\b", data_match.group(1)))

        assert thead_cols == skeleton_cols == data_cols, (
            f"Column count mismatch in admin_dashboard users table — "
            f"the table will visibly jump on HTMX load:\n"
            f"  thead:   {thead_cols} <th>\n"
            f"  skeleton:{skeleton_cols} <td>\n"
            f"  data:    {data_cols} <td>\n"
            f"All three must match. Update all three when adding/removing columns."
        )
