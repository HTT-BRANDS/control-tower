# ROUND 1 — Frontend / Design-System / A11y Audit
## HTT Control Tower

**Auditor:** Experience Architect 🎨 (`experience-architect-9a5353`)
**Date:** 2026-05-19
**Scope:** 49 Jinja templates under `app/templates/`, design tokens, CSS bundle, login flow, privacy surfaces, ct-59n cleanup verification
**Method:** Static template analysis (live server on `:8080` was wedged for curl — IPv6-only socket accepting connections then closing without response; bd `ct-boh` may be the root cause). All findings cite `file:line` receipts.
**Standard:** WCAG 2.2 Level AA + GDPR/CCPA/GPC privacy-by-design

---

## 1. Executive Summary

1. **ct-0b1 is REAL and worse than the bd description.** The dev-login form ships in the HTML to every environment (`app/templates/login.html:60`), hidden only by a CSS class that's removed via client-side JS when `/health` returns `environment === 'development'`. **An attacker in prod can flip `display:hidden` in DevTools and POST to `/api/v1/auth/login`.** This must be a server-side `{% if %}` gate, not a client-side classList toggle.
2. **ct-59n cleanup is INCOMPLETE.** `app/templates/pages/dashboard.html:96` still renders an `<a href="/onboarding/">Onboard a Tenant</a>` button in the "no tenants configured" empty state. The route was deleted — this will 404 the only call-to-action on the empty dashboard.
3. **The documented design system is stale.** `docs/design-system.md` lists HTT primary as `#000000` and accent as `#007CBA`. The actual `app/static/css/design-tokens.css:24-31` ships `#500711` (burgundy) primary and `#FFC957` (gold) accent. The doc-vs-code drift means new contributors will pick the wrong colors. **Drift score: 6/10.**
4. **The login page is an accessibility void.** Bypasses `base.html` entirely, so it has: zero landmarks (`<main>`/`<header>`/`<footer>` missing), no skip links, no `role="alert"` on the error region, no favicon, no meta description, no OG tags, no `data-brand` attribute for theming. Wrong product name in `<title>`. ct-tdu captures most but not all of this.
5. **Privacy/GPC plumbing is solid; cookie banner is well-built.** `base.html:5` injects `<meta name="gpc-enabled">`, `components/consent_banner.html` honors GPC by suppressing the banner, has proper dialog ARIA, layered consent with granular categories, and Reject-All parity. Largest gap: banner is `role="dialog"` but doesn't trap focus and has no Escape-to-dismiss.

**Overall verdict:** The design-system foundation (tokens, macros, ARIA discipline in `macros/ds/*`) is genuinely good — better than typical 3-month-old internal tooling. The drift is concentrated in (a) the bypass templates (login.html) and (b) stale docs. ~80% of findings are <S effort.

---

## 2. Findings

### F1 — Dev login form ships hidden-but-present to production [ct-0b1]
- **Severity:** P0 BLOCKER (security + a11y)
- **Evidence:** `app/templates/login.html:60`
  ```html
  <form id="login-form" class="space-y-5 hidden" data-testid="login-dev-form">
  ```
  Page init JS at lines 290–301: `fetch('/health')` → `if (data.environment === 'development')` → `document.getElementById('login-form').classList.remove('hidden')`. The form, the inputs, and the submit handler are all on the page in every environment. A user can `document.getElementById('login-form').classList.remove('hidden')` in DevTools in prod and POST to `/api/v1/auth/login`. The server may 403, but it's an unguarded attack surface that doesn't need to exist.
- **WCAG SC:** 4.1.2 Name, Role, Value (Level A) — a `hidden` form that becomes visible via JS without notifying assistive tech is also an a11y smell.
- **Recommendation:** Gate the form server-side: `{% if settings.environment == 'development' %}<form>…</form>{% endif %}`. Remove the client-side `/health` poll. The divider element should be gated the same way.
- **Effort:** XS (10 minutes)

### F2 — Broken `/onboarding/` link in dashboard empty state [ct-59n residual]
- **Severity:** P1
- **Evidence:** `app/templates/pages/dashboard.html:96`
  ```html
  <a href="/onboarding/" class="btn-brand text-center">Onboard a Tenant</a>
  ```
  ct-59n closed 2026-05-19 deleted `/onboarding/`. This is the **primary CTA** on the empty state shown when `no_tenants_configured=true` — the worst place to break a link.
- **Recommendation:** Either restore an onboarding route or change the CTA to a documentation link / tenant-admin contact. Also `grep -r "/onboarding" app/` to confirm no other references survived.
- **Effort:** S

### F3 — Login page has no landmarks, no skip links, no favicon, wrong product name [ct-tdu superset]
- **Severity:** P1 (a11y) / P2 (polish)
- **Evidence:** `app/templates/login.html:1-15` declares its own `<head>` and skips `base.html` entirely:
  - **No `<main>`, `<header>`, `<footer>`** — fails WCAG 1.3.1 Info & Relationships, 2.4.1 Bypass Blocks (Level A)
  - **No `<link rel="icon">`** anywhere → `/favicon.ico` 404 noise (confirmed: grep returned zero `favicon` results in all templates)
  - **No `<meta name="description">`** anywhere in repo (grep confirmed)
  - **`<title>Login - Riverside Capital PE Governance</title>`** (line 5) — wrong brand. The app is HTT Control Tower; the footer on the same page reads "HTT Control Tower v{{ app_version }}" (line 75). Contradicts the rest of the app.
  - **No skip links** — fails WCAG 2.4.1
  - **Error div lacks `role="alert"` / `aria-live`** — `app/templates/login.html:71`:
    ```html
    <div id="error-message" data-testid="login-error-message" class="text-sm hidden …">
    ```
    Failed-login messages set `.textContent` then unhide via `.classList.remove('hidden')`. Screen readers will never hear authentication failures. **Fails WCAG 4.1.3 Status Messages (Level AA).**
  - **No `data-brand` / inline brand style** on `<html>` — login is the only page that doesn't theme via the `ThemeMiddleware`. Multi-brand support is broken here.
- **WCAG SC:** 1.3.1 (A), 2.4.1 (A), 4.1.3 (AA), 2.4.2 Page Titled (A)
- **Recommendation:** Make `login.html` extend `base.html` (with an optional `{% block nav %}{% endblock %}` to suppress nav) or copy in the landmarks + skip links + favicon link + meta description + `data-brand` attribute + `role="alert"` on the error region. Fix the `<title>` to `"Sign In — HTT Control Tower"`.
- **Effort:** S–M

### F4 — Error message announcements are silent across the app
- **Severity:** P1 (a11y)
- **Evidence:** Repo-wide grep for `role="alert"` returned **zero matches** in `app/templates/`. The only live regions are:
  - `app/templates/base.html:56` — generic `#page-announcer` (`aria-live="polite"`)
  - `app/templates/partials/data_health.html:13` — data-health badge
  - `app/templates/components/consent_banner.html` — `role="dialog"` (not alert)
  
  Form validation, sync failures, HTMX swap errors → none are wired through the announcer or have inline `role="alert"`. A blind user filling out the consent preferences, the tenant filter, the admin user search, or the login form gets no audible feedback when something fails.
- **WCAG SC:** 4.1.3 Status Messages (Level AA)
- **Recommendation:** (a) Add `role="alert"` / `aria-live="assertive"` to every error-display div in: `login.html`, `consent_banner.html`, `admin_dashboard.html` user-search, dashboard tenant filter HTMX errors. (b) Wire HTMX `htmx:responseError` to write into `#page-announcer`.
- **Effort:** M

### F5 — Heading hierarchy skip in DMARC dashboard
- **Severity:** P2 (a11y)
- **Evidence:** `app/templates/pages/dmarc_dashboard.html:77`:
  ```html
  <h3 class="text-lg font-semibold text-primary-theme">Email Authentication Compliance Trends</h3>
  ```
  Under `ds_page_shell` (which renders `<h1>`), the first major section heading should be `<h2>`, not `<h3>`. Several other ds_card sections on this page also open with `<h3>`. (Note: `ds_table` macro emits its own internal heading — needs inspection — but the standalone Chart card definitely skips a level.)
- **WCAG SC:** 1.3.1 Info & Relationships (Level A); also 2.4.6 Headings & Labels (Level AA) implications.
- **Recommendation:** Audit every `<h3>` in `pages/*` and demote/promote so hierarchy is contiguous. Consider lint rule: `tests/architecture/test_heading_hierarchy.py`.
- **Effort:** S

### F6 — Documented design system DRIFTS from implementation
- **Severity:** P2
- **Evidence:**
  - `docs/design-system.md:18` claims HTT primary = `#000000`, accent = `#007CBA`, heading font = Montserrat
  - `app/static/css/design-tokens.css:24,31` actually ships primary = `#500711` (burgundy), accent = `#FFC957` (gold)
  - `app/templates/base.html:15` body font fallback is Inter, not Open Sans as docs imply
  - The doc's "Architecture Pipeline" diagram still references `app/templates/macros/ui.html` — that file doesn't exist; the real path is `app/templates/macros/ds.html` + `app/templates/macros/ds/*`
  - Doc says "Phase 5 of the WIGGUM roadmap"; the repo is now on a different roadmap entirely
- **Recommendation:** Rewrite `docs/design-system.md` from the current tokens file. Add a CI fitness test: parse the doc's color table, assert each value matches `design-tokens.css`. Otherwise it'll re-drift in 3 weeks.
- **Effort:** S (rewrite) + M (CI guard)

### F7 — Hardcoded hex colors in two page templates
- **Severity:** P3
- **Evidence:**
  - `app/templates/pages/topology.html:75-78` — `style="background:#f0abfc;color:#3b0764"` and `style="border:2px solid #ef4444"`. Documented (lines 71-74) as "must match Mermaid's external palette" — defensible but bypasses the no-hardcoded-hex fitness function.
  - `app/templates/pages/design_system.html:271,276,281` — inline styles with fallback hex (`#f9fafb`, `#f3f4f6`, `rgba(243,244,246,0.7)`). These are the showcase page itself, so probably intentional, but token vars should not need hex fallbacks if the design-tokens.css load order is guaranteed.
- **Recommendation:** Add `--mermaid-callout-bg`, `--mermaid-callout-text`, `--mermaid-callout-prod-border` tokens to design-tokens.css; reference them in topology.html. Drop the fallbacks in design_system.html.
- **Effort:** XS

### F8 — Inline `style="height: 300px"` for chart containers
- **Severity:** P3
- **Evidence:** `app/templates/pages/dashboard.html:248,275` — `<div style="height: 300px;">`. Magic number, not responsive, ignores reduced-zoom users.
- **Recommendation:** Promote to `.chart-container` utility class in `design-utilities.css` with `aspect-ratio` or `min-height` + `max-height` tokens.
- **Effort:** XS

### F9 — Theme toggle button violates 24×24 target-size minimum
- **Severity:** P2 (a11y)
- **Evidence:** `app/templates/base.html:80` — `<button id="theme-toggle-btn" class="text-sm px-2 py-1 rounded …">🌓</button>`. Computed: `text-sm` line-height ≈ 20px + `py-1` (4px × 2) = **28px tall** ✓ but `px-2` (8px × 2) + emoji glyph width ≈ **24-26px wide**, right at the floor. Adjacent `mobile-menu-btn` (`p-2` on a `w-6 h-6` SVG = ~40×40 ✓). The theme toggle is borderline.
- **WCAG SC:** 2.5.8 Target Size Minimum (Level AA, new in 2.2)
- **Recommendation:** Bump to `px-3 py-2` (40×32) or wrap glyph in a `w-6 h-6` span. Same audit pass needed on `<button id="consent-customize">` chain in the consent banner.
- **Effort:** XS

### F10 — Mobile menu duplicates desktop nav, drifts from `partials/nav.html`
- **Severity:** P2 (consistency)
- **Evidence:** `app/templates/base.html:90-100` hard-codes the mobile menu link list. `app/templates/partials/nav.html` (desktop) has admin gating, persona-aware visibility (`visible_pages`), `aria-current="page"`, and the riverside HTMX badge. Mobile has none of these. **A non-admin opening the mobile menu sees the same links as a full-admin desktop user.**
- **Recommendation:** Refactor `partials/nav.html` to accept a `display="mobile"` param that swaps classes, then `{% include 'partials/nav.html' with display='mobile' %}` in the mobile menu block. Single source of truth.
- **Effort:** M

### F11 — Mobile menu toggle has no focus trap, no Escape handler, no outside-click close
- **Severity:** P2 (a11y)
- **Evidence:** `app/templates/base.html:83-87` — hamburger button has `aria-expanded="false"` and `aria-controls="mobile-menu"` ✓ but `app/static/js/mobileMenu.js` (referenced at line 138) is not inspected here. **Manual test required** to confirm.
- **WCAG SC:** 2.1.2 No Keyboard Trap (A) inverted — *needs* trap when open; 2.4.11 Focus Not Obscured (AA, new in 2.2).
- **Recommendation:** **MANUAL CHECKLIST ITEM** — keyboard-only walk-through: open menu via keyboard, Tab cycles only within menu, Esc closes, focus returns to hamburger. Add to `docs/accessibility/MANUAL_TESTING_CHECKLIST.md`.
- **Effort:** S (if missing)

### F12 — Consent banner is `role="dialog"` but is not modal
- **Severity:** P2 (a11y + UX)
- **Evidence:** `app/templates/components/consent_banner.html:11-14`:
  ```html
  <div id="consent-banner" class="fixed bottom-0 …" role="dialog" aria-labelledby="consent-title" …>
  ```
  No `aria-modal="true"`, no focus trap, no inert background, no Escape handler. Users can Tab past it into the underlying page (which they shouldn't be able to interact with until they've consented). Conversely, Tabbing INTO the banner is awkward — focus order will visit the page first.
- **WCAG SC:** 2.4.11 Focus Not Obscured (AA, new 2.2); also 1.3.1 — claiming `role="dialog"` without modal semantics misleads AT.
- **Recommendation:** Either (a) remove `role="dialog"` and treat it as a `role="region"` banner (matches reality), OR (b) make it truly modal — `aria-modal="true"`, focus trap, Escape closes, inert siblings. Option (a) is faster and arguably more honest.
- **Effort:** XS (option a) / M (option b)

### F13 — GPC handling: server reads header, but UI shows no confirmation
- **Severity:** P3 (UX + legal hygiene)
- **Evidence:** `app/templates/base.html:5` exposes `<meta name="gpc-enabled" content="…">` and `consent_banner.html:85` correctly suppresses the banner when GPC=true. However: there is **no user-visible feedback** that the GPC signal was received and honored. A California user who sent GPC cannot tell whether the site honored their opt-out. CCPA does not require a visible badge, but CPRA enforcement guidance recommends it.
- **Recommendation:** When `gpc_enabled=true`, render a small badge in the footer: "We honor your Global Privacy Control signal" linking to `/privacy#gpc`. Provides legal receipts.
- **Effort:** XS

### F14 — No `<meta name="description">`, no OG, no Twitter card, no theme-color, no PWA manifest [ct-tdu]
- **Severity:** P3
- **Evidence:** Repo-wide grep returned zero matches for `<meta name="description"`, `og:title`, `twitter:card`, `theme-color`, `manifest`. Login + every dashboard page is share-blind.
- **Recommendation:** Add to `base.html` head:
  ```html
  <meta name="description" content="{% block meta_description %}HTT Control Tower — multi-brand Azure governance for HTT Brands.{% endblock %}">
  <meta name="theme-color" content="#500711">
  <meta property="og:title" content="{% block og_title %}{% block title %}{% endblock %}{% endblock %}">
  <link rel="icon" href="/static/favicon.ico">
  <link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
  ```
- **Effort:** XS

### F15 — External Google Fonts call from login.html bypasses brand font config
- **Severity:** P3 (perf + design system)
- **Evidence:** `app/templates/login.html:9` hard-codes Inter from Google Fonts. `base.html:12-16` conditionally swaps `brand.google_fonts_url` per brand — login can't because it doesn't extend base. This means a Lash Lounge user on `/login` sees Inter, not Playfair Display.
- **Recommendation:** Resolved by F3 (login extends base).
- **Effort:** N/A (rolled into F3)

### F16 — Empty/Loading/Error states inconsistent across data dashboards
- **Severity:** P2 (UX + consistency)
- **Evidence:** Spot-check of the major dashboards:
  - `dashboard.html` — has 3 well-designed empty states (`no_tenants_configured`, `not has_any_data`, plus an "all set" hydrated state) ✓
  - `riverside_dashboard.html` — chart bars init to `style="width: 0%"` (lines 98, 120, 142, 164) with no `aria-busy="true"` and no skeleton. **If the JS that hydrates them fails, the user sees a permanent zero state with no indication anything is wrong.** This appears to match the symptom Tyler reported ("stale skeleton/empty states that never get hydrated").
  - `dmarc_dashboard.html` — stat cards init with `value="--"`, four tenant score divs are empty `<div id="tenant-scores">` populated by JS. Same risk.
  - `costs.html`, `compliance.html`, `resources.html` — need same audit.
- **WCAG SC:** 4.1.3 Status Messages (AA)
- **Recommendation:** Add `aria-busy="true"` + visible skeleton on every JS-hydrated container. On `fetch()` catch, render an error tile (with `role="alert"`) that tells the user the data load failed and offers a retry. **This is likely the largest UX win in the audit.**
- **Effort:** M

### F17 — `<button>` elements in tenant filter pills use color-only state indicator
- **Severity:** P2 (a11y)
- **Evidence:** `app/templates/pages/dmarc_dashboard.html:62-69` — filter pills change between `bg-brand-primary-5 text-brand-primary` (active) and `bg-surface-tertiary text-secondary-theme` (inactive). No `aria-pressed`, no underline/icon distinction, no `aria-current`. Users with color vision deficiency relying on color alone cannot tell which filter is active.
- **WCAG SC:** 1.4.1 Use of Color (Level A); 4.1.2 Name, Role, Value (A)
- **Recommendation:** Add `aria-pressed="true|false"` to each button, and add a non-color indicator (a checkmark `aria-hidden` glyph, or a bottom border).
- **Effort:** XS

### F18 — Three external CDN scripts loaded without preconnect / consideration of offline
- **Severity:** P3 (perf + privacy)
- **Evidence:** `app/templates/base.html:25` HTMX from unpkg, `:28` Chart.js from jsdelivr, `topology.html:7` Mermaid from jsdelivr. Each triggers a DNS + TLS handshake for a third-party origin on every page load. Also: third-party CDN calls without explicit user consent may be argued under GDPR (IP address is PII; cloudflare-fronted CDNs see it).
- **Recommendation:** Self-host these three libs under `app/static/vendor/` (they all have permissive licenses + SRI hashes already declared). Removes the third-party data leak vector, halves the TLS handshake count for first-load.
- **Effort:** S

### F19 — `prefers-reduced-motion` is honored in CSS but not in HTMX swap animations
- **Severity:** P3 (a11y)
- **Evidence:** `app/static/css/design-utilities.css:380,495` — `@media (prefers-reduced-motion: reduce)` blocks exist ✓. But `app/templates/base.html:58` declares `hx-swap="outerHTML settle:150ms"` globally on nav. The 150ms settle transition runs regardless of user preference.
- **Recommendation:** Use HTMX's `hx-swap-settle` only when motion is allowed: add a JS shim that reads `window.matchMedia('(prefers-reduced-motion: reduce)').matches` and sets `htmx.config.defaultSettleDelay = 0`.
- **Effort:** XS

### F20 — No automated WCAG CI gate on rendered pages
- **Severity:** P2 (governance)
- **Evidence:** `tests/unit/test_wcag_accessibility.py` (per `docs/a11y/wcag-2.2-audit.md`) is static analysis of tokens + token-level contrast — solid foundation, but doesn't run axe-core on the actual rendered DOM. `tests/e2e/test_headless_full_audit.py` exists but its purpose appears focused on login (line 53/66 reference `#login-form`).
- **Recommendation:** Add Pa11y 9.1.1 to CI, scanning rendered output of `/dashboard`, `/login`, `/privacy`, `/admin`, `/topology`, `/riverside`, `/dmarc-dashboard`. Wire into the existing Playwright session fixture mentioned in `docs/plans/ci-browser-gate-and-prod-sync-plan-2026-04-24.md`. axe-core 4.11.1 catches ~57% of WCAG issues; remaining 43% stays manual (see Section 5).
- **Effort:** M

### F21 — 49 templates, but no documented component inventory
- **Severity:** P3 (governance)
- **Evidence:** `docs/design-system.md` lists 10 macros under "Jinja2 UI Macros" but the actual `macros/ds/*` exports 17 macros (`ds_page_shell`, `ds_card`, `ds_card_grid`, `ds_stats_row`, `ds_toolbar`, `ds_stat_card`, `ds_alert`, `ds_badge`, `ds_table`, `ds_static_table`, `ds_modal`, `ds_button`, `ds_form_field`, `ds_tabs`, `ds_tab_panel`, …). The README points to a `master-hub-infra` React showcase that an HTT-internal dev may not be able to read.
- **Recommendation:** `/design-system` page (which already exists at `pages/design_system.html`) is the live showcase — link it from the docs and the footer. Add a one-line per-macro inventory table to `docs/design-system.md`.
- **Effort:** S

### F22 — Page weight: three CSS bundles loaded uncompressed (~57KB before gzip)
- **Severity:** P3 (perf)
- **Evidence:** `app/static/css/` contains design-tokens.css (10.8KB) + design-utilities.css (21.1KB) + tailwind-output.css (25.4KB) = **57.3KB** of CSS, loaded on every page including `/login`. Tailwind output likely has significant unused-class waste (no PurgeCSS step verified).
- **Recommendation:** (a) Confirm `tailwind.config.cjs` `content:` globs cover every template (run `npx tailwindcss --content "app/templates/**/*.html"` and diff against current bundle). (b) Verify gzip/brotli is enabled in FastAPI (`GZipMiddleware` or upstream nginx). (c) Consider critical CSS extraction for `/login` (it uses ~5% of the utilities).
- **Effort:** S

### F23 — Login page uses `class="bg-brand-primary"` but never sets brand context
- **Severity:** P3 (design system)
- **Evidence:** `app/templates/login.html:18` body uses `bg-surface-secondary` (token) ✓ but line 23 uses `bg-brand-primary` — and `<html>` has no `data-brand` attribute (line 2: `<html lang="en">` only). The CSS variable falls back to the `:root` defaults in `design-tokens.css` (HTT colors), which works **only** because HTT is the default. A Lash Lounge user reaching `/login` directly via marketing link will see HTT burgundy.
- **Recommendation:** Resolved by F3 + F15 if login extends base.html (which sets `data-brand` from `ThemeMiddleware`).
- **Effort:** N/A (rolled into F3)

### F24 — Privacy preference modal does not surface DSAR controls (Right to Know/Delete/Correct/Limit)
- **Severity:** P2 (privacy + legal)
- **Evidence:** `app/templates/components/consent_banner.html` only surfaces cookie category toggles (necessary/functional/analytics/marketing). The privacy policy at `app/templates/pages/privacy.html:49-82` documents the rights (GDPR Art. 15-22, CCPA 1798.100-135) and mentions GPC. But there is no in-UI "Request my data" / "Delete my account" / "Correct my info" affordance. Per CCPA, the request mechanism must be "clearly described" — text in the policy is the minimum, but a button in the preference center is best practice.
- **WCAG SC:** N/A (legal, not a11y)
- **Recommendation:** Add a "Privacy controls" tab to the consent preference panel with four buttons that POST to `/api/v1/privacy/dsar/{know,delete,correct,limit}` (per consent receipts pattern). Add consent-receipt download. Coordinate with Security Auditor — DSAR endpoints need rate-limiting + identity verification.
- **Effort:** M (UI) + L (backend if endpoints missing)

### F25 — `target="_blank"` audit: zero matches → no `rel="noopener"` risk
- **Severity:** ✅ PASS
- **Evidence:** Repo-wide grep for `target="_blank"` returned **zero matches** in `app/templates/`. No `tabnabbing` exposure surface. Keep it that way.

### F26 — Dragging movements (WCAG 2.5.7): not applicable
- **Severity:** ✅ PASS
- **Evidence:** Repo-wide grep for `draggable`, `onmousedown`, `drag` returned only one match: a comment in `macros/ds/navigation.html:26` stating "Non-dragging interaction only — 2.5.7 Dragging Movements (n/a)". Confirmed.

---

## 3. Design System Drift Score: **6/10**

| Dimension | Score | Notes |
|---|---|---|
| Token usage (color, spacing, typography) | 8/10 | Only 2 templates have raw hex; both rationalized. Magic-number heights in 2 places. |
| Macro reuse | 8/10 | `ds_page_shell` + `ds_card` etc. are used consistently in `/pages/*`. login.html is the rebel. |
| Doc-vs-code parity | 3/10 | `docs/design-system.md` describes a hypothetical state, not the real one. Brand colors wrong; macro paths wrong; macro count incomplete. |
| Component coverage | 7/10 | Empty/loading/success states well-handled on dashboard; missing on riverside/dmarc/admin. |
| Cross-template consistency | 5/10 | login.html bypasses everything. Mobile menu re-implements desktop nav. |
| A11y discipline | 7/10 | sr-only labels, `<caption>`, `aria-label` used consistently in macros; landmark gap on login is the big miss. |
| **Aggregate** | **6/10** | Solid foundation, concentrated drift in 2 places (login + docs). |

> 1 = green-field, perfect adherence. 10 = abandoned design system, every page a snowflake. **6/10 means there's a real design system being followed in most places, but the documented spec has materially drifted from the running code, and one critical surface (login) bypasses the system entirely.**

---

## 4. A11y Compliance Snapshot — WCAG 2.2 Level AA

**Method:** Static template analysis (no axe-core runtime). Live server was wedged for curl during this audit. Manual screen-reader testing **NOT** performed.

| Category | SC Count | Likely PASS | Likely FAIL | Cannot Determine Without Live Test |
|---|---|---|---|---|
| Perceivable (1.x) | 16 | 12 | 1 (1.4.3 — login error states) | 3 (1.4.10 reflow, 1.4.11 non-text — needs live render) |
| Operable (2.x) | 22 | 14 | 3 (2.4.1 login, 2.4.6 dmarc, 2.5.8 theme toggle) | 5 (2.4.11 focus obscure — needs live, 2.4.13 focus appearance, 2.1.2 menu trap, 2.4.7 visible focus on every interactive, 2.5.5 target size on all) |
| Understandable (3.x) | 11 | 9 | 1 (3.3.1 login error not announced — 4.1.3 overlaps) | 1 (3.2.6 consistent help — depends on nav consistency mobile-vs-desktop, F10) |
| Robust (4.x) | 6 | 4 | 2 (4.1.3 status messages app-wide, 4.1.2 filter pill state) | 0 |
| **Total (WCAG 2.2 AA)** | **55** | **39 (71%)** | **7 (13%)** | **9 (16%) — manual** |

### ⚠️ Critical caveat
axe-core covers ~57% of WCAG. The remaining ~43% **requires manual testing**. Specifically, these 7 SC cannot be automated and MUST be manually tested before any release claim of "WCAG 2.2 AA":

| SC | Title | Status in Control Tower |
|---|---|---|
| 2.4.11 | Focus Not Obscured (Minimum) | **NOT TESTED** — consent banner is sticky-bottom + nav is sticky-top. Manual scroll test required. |
| 2.4.12 | Focus Not Obscured (Enhanced) — AAA | Not targeted. |
| 2.4.13 | Focus Appearance | **NOT TESTED** — need to inspect `:focus-visible` rule's outline contrast & thickness. |
| 2.5.7 | Dragging Movements | ✅ PASS (no drag in app — F26) |
| 2.5.8 | Target Size (24×24) | **PARTIAL FAIL** — F9 theme toggle borderline; needs site-wide button audit. |
| 3.2.6 | Consistent Help | ⚠️ Footer "Accessibility" link is consistent across all pages that extend `base.html`. Login bypasses base — inconsistent. |
| 3.3.7 | Redundant Entry | ✅ Spot-checked — admin user form doesn't re-ask known fields. |
| 3.3.8 | Accessible Authentication | ✅ PASS — Azure AD SSO primary, no CAPTCHA. Per `docs/a11y/wcag-2.2-audit.md` confirmed. |

### Headline metric
**~71% of WCAG 2.2 AA criteria likely pass via static analysis. The 13% failing are concentrated in (a) the login page and (b) the lack of `role="alert"` on dynamic error states. Manual testing of the remaining 9 criteria (16%) is REQUIRED before any compliance claim.**

---

## 5. Manual A11y Audit Checklist (REQUIRED before claiming WCAG 2.2 AA)

This checklist covers the 7 WCAG 2.2 criteria that cannot be automated, plus the manual gaps surfaced by this audit. Run these against the live app once the curl-wedge in `bd:ct-boh` is resolved.

- [ ] **2.4.11 Focus Not Obscured (Min):** Tab through `/dashboard` — does the sticky `<nav>` (h-16) ever cover the focused element? Resize browser to 768px — does the consent banner cover the bottom row of any form?
- [ ] **2.4.13 Focus Appearance:** Inspect `:focus-visible` outline. Must be (a) ≥2 CSS px thick, (b) contrast ≥3:1 against adjacent colors, (c) enclose the entire focused element.
- [ ] **2.5.7 Dragging Movements:** Confirmed via grep — no drag UI. ✅
- [ ] **2.5.8 Target Size (24×24):** Walk every page measuring every interactive element. Theme toggle (F9), consent buttons, filter pills (F17), mobile nav links.
- [ ] **3.2.6 Consistent Help:** Footer "Accessibility" + "Privacy Policy" links present in same order on all pages? Check `/login` — currently bypasses base, so probably fails (F3).
- [ ] **3.3.7 Redundant Entry:** Admin "create user" form — does it pre-fill known fields? Tenant onboarding (once route restored) — does it remember partial completion?
- [ ] **3.3.8 Accessible Authentication:** Azure AD SSO is the primary path — confirmed accessible (no cognitive function test). Dev login form (when shown) — is autofill respected? `name="username"` ✓, `name="password"` ✓ — looks OK.
- [ ] **Screen reader sweep:** NVDA (Windows) or VoiceOver (macOS) — read `/dashboard`, `/login`, `/privacy`, `/admin`, then trigger a failed login. Does the error get announced? (F4 says no.)
- [ ] **Keyboard-only walkthrough:** Unplug mouse. Complete: log in, switch tenant scope, run a sync, customize cookie preferences, log out.
- [ ] **prefers-reduced-motion:** Enable in OS — does the nav HTMX swap still animate? (F19)
- [ ] **400% zoom (1.4.10 Reflow):** Test at 320 CSS px width — does anything horizontally scroll except intentional code blocks?
- [ ] **Dark mode contrast:** Manually inspect — `tests/unit/test_wcag_accessibility.py::TestDarkModeContrast` covers tokens; verify rendered borders + text on every page.

---

## 6. Cross-Agent Coordination Recommendations

- **Solutions Architect 🏛️ (`solutions-architect`):** F1 (server-side login form gating) is half-frontend, half-API-contract. F2 needs the API-side `/onboarding/` story decided (restore? redirect? telemetry-only stub?). F24 DSAR endpoints likely don't exist yet — needs API design.
- **Security Auditor / Release Gate Arbiter:** F1, F12, F24 are all privacy-touching and need security sign-off before merge. The hidden dev login form (F1) is a P0 that should land in the next release cycle, not next sprint.
- **QA Kitten 🐱:** F11, F16, the entire Section 5 manual checklist needs Playwright + axe-core + visual regression. Once `:8080` is unwedged, fire Pa11y 9.1.1 against all 14 routable pages.

---

## 7. Recommended bd issue updates

| bd ID | Action | Why |
|---|---|---|
| ct-0b1 | **Re-scope: P1 → P0 BLOCKER.** Update description to make clear this is server-side gating, not just a hidden-form polish. | F1 |
| ct-tdu | **Expand acceptance criteria:** add `role="alert"` on error div (F3); add `meta description`, `theme-color`, OG tags (F14); add `data-brand` attribute (F23). Lighthouse a11y ≥ 95 target stays. | F3, F14 |
| **NEW** | File: "frontend: `/onboarding/` link broken in dashboard empty-state CTA" — P1 | F2 |
| **NEW** | File: "docs: rewrite design-system.md from current tokens + add CI parity guard" — P2 | F6 |
| **NEW** | File: "a11y: site-wide `role='alert'` audit on error/status regions" — P1 | F4 |
| **NEW** | File: "a11y: heading hierarchy audit + lint rule" — P2 | F5 |
| **NEW** | File: "frontend: extract mobile nav from base.html into `partials/nav.html`" — P2 | F10 |
| **NEW** | File: "ux: hydration error states + `aria-busy` on every JS-populated container" — P2 | F16 |
| **NEW** | File: "ci: add Pa11y 9.1.1 + axe-core 4.11.1 against rendered routes" — P2 | F20 |
| **NEW** | File: "privacy: add DSAR controls + GPC honored badge" — P2 | F13, F24 |
| **NEW** | File: "perf: self-host HTMX/Chart.js/Mermaid, drop CDN" — P3 | F18 |

---

**End of Round 1 audit. Receipts attached, no fluff added. — Experience Architect 🎨 (`experience-architect-9a5353`)**
