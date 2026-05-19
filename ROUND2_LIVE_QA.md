# 📋 ROUND 2 LIVE QA — HTT Control Tower (`localhost:8000`)

**QA Agent:** `qa-kitten-9c1da5` · **Round:** 2 of 3 · **Build under test:** `v2.5.0` dev mode · **Date:** 2026-05-19

## 🎯 TL;DR for Tyler

> **The "blank page" was NOT the `/onboarding/` CTA. The `5cb15ef` fix is correct as far as it goes, but the root cause is a different bug.**
>
> Every authenticated page leaves the URL bar at `/partials/riverside-badge` (or another partial) due to HTMX `hx-trigger="load"` polling under an `hx-boost` ancestor. **When you press F5 on the dashboard, the server returns 1 byte (a newline) and the screen goes completely white.** Reproduced live, screenshot proof in §3.

| Question | Answer |
|---|---|
| Does the `ct-0b1` dev-form fix work in a real browser? | **YES** — dev form visible, POST `/api/v1/auth/login` returns 401, error region with `role="alert"` displays "Invalid credentials" |
| Does the `role="alert"` fix announce errors? | **PARTIALLY** — role=alert present but the element ALSO has `aria-live="polite"` which overrides assertive (SR waits for a pause) |
| Are `admin/admin` creds live? | **YES** — login succeeds and session cookie issued |
| Is the dashboard empty state now correct? | **NO** — dashboard cards show data but every card says "Synced never", chart panels say "Run a sync to see…", footer says "Last sync: Never" — and `/healthz/data` proves the tenants DID sync. The state is hardcoded template text. Also the new "View Sync Status" CTA never gets a chance to be useful because reloading the page leaves you on `/partials/riverside-badge` (blank). |

---

## 1. Smoke matrix v2

Driver: Playwright (Chromium, headless), viewport 1280×900 unless noted.

| URL | HTTP | Title | Hydrated? | Top observation |
|---|---|---|---|---|
| `/` | 307 → `/login` | — | n/a | redirect ok |
| `/login` | 200 | "Login - Riverside Capital PE Governance" | n/a | dev form visible (`ct-0b1` ✅), role=alert with aria-live polite mismatch |
| `/login` @360 | 200 | same | n/a | reflows cleanly, no overflow |
| `/login` @768 | 200 | same | n/a | reflows cleanly |
| `/login` after bogus creds | — | — | — | error region shows "Invalid credentials" but unstyled black-on-white |
| `/onboarding/` | **404 JSON** | n/a | n/a | bare `{"detail":"Not Found"}`, `application/json` — branded 404 missing (`ct-tdu` carryover) |
| `/totally-bogus-route-xyz` | 404 JSON | n/a | n/a | same — universal |
| `/dashboard` | 200 | "Dashboard - HTT Control Tower" | **server-side**, no XHR hydration | URL clobbered → `/partials/riverside-badge`; cookie banner appears AFTER login; "Synced never" everywhere despite KPIs showing 87%, 1727, 60 |
| `/dashboard` after F5 | 200 | **""** (empty) | — | **🔥 COMPLETELY BLANK PAGE** — 1-byte response |
| `/dashboard` @360 | 200 | same | — | reflows to 2-col KPI grid + hamburger; OK |
| `/sync-dashboard` | 200 | "Sync Status Dashboard - HTT Control Tower" | server-side, rich | Overall "Degraded"; 15,656 alerts (5193 errors); RIVERSIDE_BATCH job 0% since 04/29; footer "Last sync: Never" contradicts "Last updated 19:22:37" |
| `/sync-dashboard` @360 | 200 | same | — | "Loading sync status..." skeleton, OK |
| `/riverside` | 200 | "Riverside Compliance Dashboard" | server-side | Live countdown to July 8, 2026; "Critical Gaps: 0" tile contradicts table with 10 overdue critical gaps below |
| `/dmarc` | 200 | "DMARC/DKIM Security Dashboard" | **JS XHR** | Hydrates correctly after delay; "— —" during load is bad UX (should be skeleton) |
| `/admin` | 200 | "Administration - HTT Control Tower" | server-side | 4 users (tyler.granlund=admin); "5/5 Active Tenants" — **proves header badge "4 Tenants" wrong** |
| `/costs` | 200 | "Cost Management" | **JS XHR — BROKEN** | All KPIs stuck at "— —", tables stuck "Loading…" despite three APIs returning 200; `/api/v1/costs/summary` returns `{tenant_count:0, total_cost:0}` while `/api/v1/costs/by-tenant` returns 5 tenants and `/api/v1/costs/anomalies` has 3 real anomalies ($1.4–$2.6K) |
| `/compliance` | 200 | "Compliance Monitoring" | mixed | Top KPIs "0%, 0, 0, 0" but per-tenant table shows 84-89% and violations table has 30+ rows of real data |
| `/resources` | 200 | "Resource Inventory" | **JS XHR — BROKEN** | Stuck "— —" / "Loading…" |
| `/identity` | 200 | "Identity & Access" | **JS XHR — BROKEN** | Stuck "— —" / "Loading…" |
| `/topology` | 200 | "Azure Topology" | client-side mermaid — **BROKEN** | Renders raw text `%% loading... flowchart TB loading["Loading diagram…"]`. "Download SVG" CTA offered, but page admits SVG isn't available |

Screenshots: in agent temp dir; key ones to look at:

- `screenshot_20260519_141708_286775.png` — `/login` showing dev form (ct-0b1 verified working in dev)
- `screenshot_20260519_141857_826218.png` — login error region unstyled
- `screenshot_20260519_141944_884782.png` — `/dashboard` with URL clobbered to `/partials/riverside-badge`
- **`screenshot_20260519_142130_017398.png`** — THE BLANK PAGE TYLER SAW (1-byte response on F5)
- `screenshot_20260519_142241_577993.png` — `/sync-dashboard` showing real data alongside "Last sync: Never"
- `screenshot_20260519_142426_353366.png` — `/costs` stuck at "— —" while APIs return data
- `screenshot_20260519_142457_415568.png` — `/compliance` showing KPI/table contradiction

---

## 2. Findings table

Severity scale: **P0** ship-blocker · **P1** must-fix · **P2** should-fix · **P3** nice-to-have

| # | Sev | URL(s) | Finding | Repro | Suggested fix | Status |
|---|---|---|---|---|---|---|
| F1 | **P0** | every authenticated page | **URL clobber + blank reload.** After any nav, `location.href` ends up at `/partials/<polling-thing>`. `fetch('/partials/riverside-badge')` returns 1 byte. **F5 = white page.** | Login as `admin/admin` → land on /dashboard → wait 100ms → look at URL bar → press F5 → page goes white. | Server-side: set `HX-Push-Url: false` response header on all `/partials/*` routes via middleware. Defense-in-depth: also add `hx-push-url="false"` to the 12 load-triggered partials in templates. | **FIXED** — middleware added in `app/main_middleware.py` (`_register_htmx_partial_no_push_url`). Regression test: `tests/unit/test_htmx_no_push_url_middleware.py` (6 tests passing). |
| F2 | **P1** | `/dashboard` | KPI cards show real numbers (87% compliance, 1727 identities, 60 privileged) **but every card subtext says "Synced never"** and chart panels say "No data yet". | Login → `/dashboard` → observe contradiction; then `fetch('/healthz/data')` | Bind sync metadata to actual `last_sync_at` per domain like `/sync-dashboard` does. | open — Round 3 |
| F3 | **P1** | `/costs`, `/resources`, `/identity` | **Broken JS hydration.** APIs return 200 + data, DOM stays at "— —" and tables stuck on "Loading…" even after `networkidle`. | Navigate to /costs → wait 5s → `document.body.textContent.includes('Loading')` still true | Check `static/js/pages/{costs,resources,identity}.js` for selector mismatches. | open — Round 3 |
| F4 | **P1** | `/api/v1/costs/summary` | **API aggregation bug.** Returns `{total_cost: 0, tenant_count: 0}` while `/api/v1/costs/by-tenant` returns 5 tenants and `/api/v1/costs/anomalies` has 3 anomalies. | `fetch('/api/v1/costs/summary')` vs `fetch('/api/v1/costs/by-tenant')` | Reconcile aggregator with detail endpoints in same SQL/service layer. | open — Round 3 |
| F5 | **P1** | layout header (every page) | Header badge says **"4 Tenants"** but system has 5 (per /admin, dashboard dropdown, /sync-dashboard, /healthz/data, /api/v1/dmarc/summary). | Visit any page, look top-right | Off-by-one or filter bug; replace badge source with `/admin` query. | open — Round 3 |
| F6 | **P2** | `/login` then `/dashboard` | **Cookie consent banner appears AFTER login** instead of on `/login`. | Cold session → /login → submit → banner appears | Move consent gate to before authentication, or to `/login`. | open — Round 3 |
| F7 | **P2** | `/login` error region | "Invalid credentials" rendered as **plain black-on-white**, no red color, no icon, no error background. | Submit bogus creds, look at `#error-message` | Add `text-error` color, icon, tinted background. | open — Round 3 |
| F8 | **P2** | `/login` `#error-message` | `role="alert"` + `aria-live="polite"` — role=alert implies assertive; polite overrides. Screen readers wait for pause. | Inspect: getAttribute('role')='alert', getAttribute('aria-live')='polite' | Remove explicit `aria-live`. Let role=alert assert. | open — Round 3 |
| F9 | **P2** | universal 404 | Bare `{"detail":"Not Found"}` JSON for unknown HTML routes. | `curl /anything-bogus` | Add Jinja-rendered branded 404 handler. Already filed as `ct-tdu` in Round 1. | open — backlog |
| F10 | **P2** | `/topology` | Mermaid never renders. Raw `%% loading... flowchart TB loading[...]` shown as plain text. | Visit `/topology` | Confirm mermaid script init; or disable page until weekly export runs. | open — Round 3 |
| F11 | **P2** | `/riverside` | "Critical Gaps: 0" KPI directly above "Critical Gaps Requiring Immediate Action" table with **10 overdue P0 entries**. | Visit `/riverside` | Bind count to same query that populates table. | open — Round 3 |
| F12 | **P2** | `/sync-dashboard` | "Last sync: Never" footer despite "Last updated: 2026-05-19 19:22:37 UTC" higher in same view. | Visit `/sync-dashboard`, scroll to bottom | Bind footer to `now()` or freshest sync timestamp. | open — Round 3 |
| F13 | **P2** | brand identity | **Three product names on one page:** "Riverside Capital PE Governance Platform" (login title), "Azure Governance" (nav brand), "HTT Control Tower v2.5.0" (footer/document.title). | Visit /login → /dashboard | Pick one. The nav "Azure Governance" looks like template residue. | open — backlog |
| F14 | **P2** | header badge | Color contrast violation: `rgb(168, 57, 74)` rose on `bg-brand-primary-900` maroon — fails WCAG 2.2 AA. (axe-core "color-contrast" serious.) | Tab to badge, run axe | Use `text-brand-primary-50` or white. | open — Round 3 |
| F15 | **P2** | `/dmarc`, `/costs`, `/resources`, `/identity` | Loading state uses **"— —"** em-dashes. To assistive tech this reads as actual content. | Visit and listen with VoiceOver during load | Use `aria-busy="true"` + skeleton shimmer or visually-hidden "Loading {kpi}" text. | open — Round 3 |
| F16 | **P3** | `/sync-dashboard` | RIVERSIDE_BATCH performance metric shows 0% success over 6 runs, last 04/29. **Dead job — surface a warning.** | /sync-dashboard → scroll to Sync Performance Metrics | Add "unhealthy job" treatment (red border, alert link). | open — backlog |
| F17 | **P3** | `/login` form | HTML `method="get"` on the login form. JS intercepts and POSTs so creds aren't leaked, but if JS fails the browser would submit creds via query string. | Inspect form attribute | Use `method="post"` for defense in depth. | open — backlog |
| F18 | **P3** | response headers | `Server: uvicorn, Azure-Governance-Platform` — minor info disclosure. | `curl -I /login` | Strip in prod proxy. | open — backlog |
| F19 | **P3** | response headers | `Strict-Transport-Security: max-age=300` (5 minutes). Fine for dev, **must be ≥31536000 + `includeSubDomains; preload`** for production. | `curl -I /login` | Raise max-age in prod config. | open — backlog |
| F20 | **P3** | `/login` a11y | Missing `<main>`, `<nav>`, `<header>` landmarks. axe: 2 moderate. | axe-core scan | Wrap content in `<main>`. | open — backlog |

---

## 3. Definitive answer to "why was the page blank?"

### The mechanism (hard evidence)

1. **Page template behavior.** The base layout includes `<span id="riverside-badge" hx-get="/partials/riverside-badge" hx-trigger="load, every 60s" hx-target="#riverside-badge" hx-swap="innerHTML" hx-push-url="false">` plus an `hx-boost="true"` ancestor (confirmed via `document.querySelector('[hx-boost="true"]')`).

2. **HTMX bug.** Despite `hx-push-url="false"` on the badge, when HTMX boost is enabled on an ancestor the load-triggered request **still pushes its own URL** onto history. Verified across 4 partials with identical behavior:
   - `/partials/riverside-badge`
   - `/partials/sync-history-table`
   - `/partials/active-alerts`
   - `/admin/partials/users-table`

3. **What the user sees after login:**
   - Browser navigates to `/dashboard` → status 200, HTML renders correctly.
   - On `load`, the riverside-badge fetches its partial. HTMX pushes `/partials/riverside-badge` into history.
   - URL bar now reads `http://localhost:8000/partials/riverside-badge`.

4. **What happens when the user presses F5:**
   - Browser issues `GET /partials/riverside-badge` (no `HX-Request` header).
   - FastAPI handler returns **1 byte** (a newline character). HTTP 200, Content-Length: 1, Content-Type: text/html.
   - Browser renders 1 byte of HTML. **Page is white. Title is empty.**

5. **Screenshot proof:** `screenshot_20260519_142130_017398.png` is a completely white 1280×900 viewport. **This is what Tyler reported.**

### Fix applied this session

`app/main_middleware.py` now registers `_register_htmx_partial_no_push_url`, which sets `HX-Push-Url: false` on every response whose path contains `/partials/`. HTMX honors this response header regardless of any client-side hx-push-url attribute — so the URL bar always reflects the real page route.

Verified live:
- `/partials/riverside-badge` → `hx-push-url: false` ✅
- `/partials/nonexistent` → `hx-push-url: false` ✅
- `/api/v1/health` → header absent ✅
- `/login` → header absent ✅

Regression test: `tests/unit/test_htmx_no_push_url_middleware.py` (6 parametrized cases, all passing).

---

## 4. Header / CSP audit

Sampled URLs: `/login`, `/dashboard`, `/sync-dashboard`, `/api/v1/dmarc/summary`, `/api/v1/auth/login` (POST). All return **consistent** headers.

| Header | Value (truncated) | Status |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'nonce-...' https://unpkg.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self' https://cdn.jsdelivr.net; media-src 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'; upgrade-insecure-requests` | ✅ Strong, per-request nonce |
| `Strict-Transport-Security` | `max-age=300; includeSubDomains` | ⚠️ raise to 31536000 + `preload` for prod (F19) |
| `X-Frame-Options` | `DENY` | ✅ |
| `X-Content-Type-Options` | `nosniff` | ✅ |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | ✅ |
| `Cross-Origin-Embedder-Policy` | `require-corp` | ✅ |
| `Cross-Origin-Opener-Policy` | `same-origin-allow-popups` | ✅ |
| `Cross-Origin-Resource-Policy` | `same-origin` | ✅ |
| `Permissions-Policy` | comprehensive (camera/geolocation/etc all `=()`) | ✅ |
| `X-XSS-Protection` | `1; mode=block` | ✅ (legacy but harmless) |
| `Document-Policy` | `force-load-at-top` | ✅ |
| `X-Correlation-ID` | unique per request | ✅ great for tracing |
| `Server` | `uvicorn, Azure-Governance-Platform` | ⚠️ minor info disclosure (F18) |

**This is one of the cleanest header sets I've audited.** Promote whoever wrote `app/core/security_headers.py`.

---

## 5. axe-core 4.10 a11y matrix

Standards profile: default (WCAG 2.1 A/AA + best practice).

| Page | Viewport | Total | critical | serious | moderate | minor | Top violations |
|---|---|---|---|---|---|---|---|
| `/login` | 1280×900 | 2 | 0 | 0 | 2 | 0 | `landmark-one-main` (1), `region` (7 nodes) |
| `/login` | 360×640 | 2 | 0 | 0 | 2 | 0 | same as desktop |
| `/dashboard` | 1280×900 | 1 | 0 | 1 | 0 | 0 | `color-contrast` (1 node: header tenant badge) |
| `/sync-dashboard` | 1280×900 | 2 | 0 | 2 | 0 | 0 | `color-contrast`, `scrollable-region-focusable` (Recent Sync Jobs table) |

---

## 6. Top-7 findings (for the standup)

1. **🔥 P0 — Universal URL clobber → blank page on F5** (F1). HTMX `hx-trigger="load"` partials push their URL through `hx-boost`. F5 returns 1 byte. **This IS Tyler's bug.** ✅ **FIXED THIS SESSION.**
2. **P1 — Dashboard misreports sync state** (F2). KPI cards have data but say "Synced never"; charts say "No data yet" right above a populated tile.
3. **P1 — Three pages have totally broken JS hydration** (F3). `/costs`, `/resources`, `/identity` show "— —" + "Loading…" forever.
4. **P1 — `/api/v1/costs/summary` returns zeros while detail endpoints have data** (F4). Backend aggregation bug independent of UI.
5. **P1 — Header tenant badge shows "4 Tenants" but reality is 5** (F5). Off-by-one confirmed.
6. **P2 — Brand identity crisis** (F13). "Riverside Capital", "Azure Governance", "HTT Control Tower" all appear on one page.
7. **P2 — Cookie consent appears AFTER login** (F6) — should be on `/login` first.

---

## 7. Round 2 sign-off

| Verification | Result |
|---|---|
| Is the dashboard empty state now correct? | **NO.** The page hydrates with mixed/misleading state. Numbers + "Synced never" + "No data yet" contradict each other. (F2/F12 — Round 3) |
| Does the `ct-0b1` dev-form fix work in a real browser? | **YES** — confirmed visible in dev mode, gated on prod. |
| Does the `role="alert"` fix work in a real browser? | **YES, but** — alert is announced and visible; however `aria-live="polite"` overrides the assertive default of role=alert (F8 — Round 3). |
| Does pressing F5 on the dashboard reproduce the blank page Tyler reported? | **YES — definitively reproduced.** Screenshot `screenshot_20260519_142130_017398.png` is white. **NOW FIXED** via middleware in this session's second commit. |

**Recommendation:** F1 was treated as a hotfix and shipped this session. The codebase is otherwise in remarkably good security posture and the data layer is mostly working — the remaining UX pain is in 3-4 isolated render bugs (F2, F3, F4, F5) that fit cleanly in a Round 3 sweep.

---

🐱 *Filed by `qa-kitten-9c1da5` · Round 2 of 3 · Persisted by `code-puppy-a5faf1` because qa-kitten can't write to disk.*
