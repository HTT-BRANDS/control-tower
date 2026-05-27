# UAT Sweep — HTT Control Tower Prod + Staging
**Session**: 2026-05-27 · richard-session
**Agent**: qa-kitten (Playwright headless, Chromium/Firefox/WebKit), orchestrated by code-puppy-5deed9
**Ticket**: ct-4uu gate work
**Verdict**: 🟢 **GREEN** (with one staging-only YELLOW)

## Targets

| Env | URL |
|---|---|
| Production | https://app-governance-prod.azurewebsites.net |
| Staging | https://app-governance-staging-xnczpwyv.azurewebsites.net |
| Public docs | https://htt-brands.github.io/control-tower/ |

## Scope

Unauthenticated surfaces + visual QA. No login attempts. Three browsers (Chromium, Firefox, WebKit), all headless.

---

## Results matrix

Legend: ✅ pass · ⚠️ warn · ❌ fail · 🔒 auth-gated (working as intended)

### Production

| Check | Chromium | Firefox | WebKit | Evidence |
|---|---|---|---|---|
| `/` redirects to `/auth/login` | ✅ | ✅ | ✅ | 307 → 200, title "Sign in — HTT Control Tower" |
| `/auth/login` renders + MS SSO present | ✅ | ✅ | ✅ | `chromium-prod-login.png`, `firefox-prod-login.png`, `webkit-prod-login.png` |
| `/health` 200 JSON, no PII | ✅ | ✅ | ✅ | `{"status":"healthy","version":"2.5.0","environment":"production"}` · 101 ms |
| `/health/detailed` 200, no PII | ✅ | ✅ | ✅ | components/cache_metrics/database_pool · 757 ms |
| `/healthz/data` 200, structure correct | ✅ | ✅ | ✅ | `required_domains` correct, `tenants{}` present, 405 ms |
| `/openapi.json` 200, valid spec | ✅ | ✅ | ✅ | 245 KB, 3.2 s |
| `/docs` Swagger UI | 🔒 | 🔒 | 🔒 | 401 `{"detail":"Authentication required..."}` — `chromium-prod-docs-401.png` |
| `/version` 404 graceful | ✅ | ✅ | ✅ | `{"detail":"Not Found"}`, no stack trace |
| `/nonexistent` 404 graceful | ✅ | ✅ | ✅ | same |
| Mixed content | ✅ none | ✅ none | ✅ none | |
| CSP / HSTS / XFO / XCTO | ✅ | ✅ | ✅ | nonce-CSP, HSTS 1y+includeSubDomains, DENY, nosniff |
| `/static/` asset 404s | ✅ none | ✅ none | ✅ none | All 3 CSS files load 200 |
| Tailwind / FOUC | ✅ | ✅ | ✅ | tailwind-output.css 200 (26 KB) |
| Page `<title>`, `<h1>`, `lang` | ✅ | ✅ | ✅ | title set, 1 h1, lang="en" |

### Staging

| Check | Chromium | Firefox | WebKit | Evidence |
|---|---|---|---|---|
| `/` redirects to `/auth/login` | ✅ | ✅ | ✅ | |
| `/auth/login` renders + MS SSO present | ✅ | ✅ | ✅ | `chromium-staging-login.png` — pixel-identical to prod |
| `/health` 200 JSON | ✅ | ✅ | ✅ | `environment: "staging"`, 143 ms |
| `/health/detailed` 200 | ✅ | ✅ | ✅ | components present, SQLite backend, 113 ms |
| `/healthz/data` 200, structure correct | ✅ | ✅ | ✅ | required/optional domains correct, 282 ms |
| `/openapi.json` 200 | ✅ | ✅ | ✅ | 245 KB, 3.0 s |
| **`/docs` Swagger UI renders** | ❌ | ❌ | ❌ | **BLANK PAGE** — see `*-staging-docs-BLANK.png` |
| `/version` 404 graceful | ✅ | ✅ | ✅ | |
| `/nonexistent` 404 graceful | ✅ | ✅ | ✅ | |
| Mixed content | ✅ none | ✅ none | ✅ none | |
| Security headers | ⚠️ | ⚠️ | ⚠️ | HSTS only 24 h (acceptable for staging tier) |
| Asset 404s / Tailwind / FOUC | ✅ / ✅ / ✅ | ✅ / ✅ / ✅ | ✅ / ✅ / ✅ | |
| Page `<title>`, `<h1>`, `lang` | ✅ | ✅ | ✅ | |

### Public docs (htt-brands.github.io/control-tower/)

| Check | Chromium | Firefox | WebKit | Evidence |
|---|---|---|---|---|
| Loads + correct title | ✅ | ✅ | ✅ | "HTT Control Tower" |
| Headings present, lang="en" | ✅ | ✅ | ✅ | 1 h1 + 7 h2 |
| Mixed content | ✅ none | ✅ none | ✅ none | |
| Asset 404s | ✅ none | ✅ none | ✅ none | |
| TTFB / load | 96 ms / 486 ms | (not retested — cached) | 0 ms / 84 ms (warm) | well under budget |

---

## 🚨 Bugs found

### BUG-1 — Staging `/docs` blank (browser-agnostic) — **HIGH (staging only)** → filed as `ct-z0b` (P1)

**Symptom**: Navigating to `https://app-governance-staging-xnczpwyv.azurewebsites.net/docs` shows a completely blank white page in Chromium, Firefox, and WebKit. Title set correctly, but `<div id="swagger-ui">` never populates.

**Root cause** (verified via CSP header inspection): FastAPI's default Swagger HTML uses an **inline `<script>` to initialize SwaggerUIBundle** with no `nonce` attribute. Staging's CSP requires either a nonce or `'unsafe-inline'` → the initializer is blocked. Also `style-src` does NOT include `cdn.jsdelivr.net`, so `swagger-ui.css` is blocked.

**Fix**: override FastAPI's `get_swagger_ui_html(...)` to inject the per-request CSP nonce + add `cdn.jsdelivr.net` to `style-src`. OR self-host swagger-ui assets under `/static/swagger/`.

**Screenshots**: `screenshots/chromium-staging-docs-BLANK.png`, `firefox-staging-docs-BLANK.png`, `webkit-staging-docs-BLANK.png`

### BUG-2 — Prod `/openapi.json` publicly accessible while `/docs` is gated — **LOW (info disclosure)** → filed as `ct-g7q` (P3 policy decision)

Prod returns `401` on `/docs` (auth required) but `200` + full 245 KB OpenAPI 3.1.0 spec on `/openapi.json` — including endpoint paths, schemas, auth flow, rate-limit policy. Either gate both or document why public.

### NIT-1 — Public docs `<h1>` reads as `"HTT ControlTower"` to a screen reader — **LOW (a11y)** → filed as `ct-684` (P4)

H1 splits "HTT Control" and "Tower" across two spans without separating space; `textContent` returns `"HTT ControlTower"`. May affect screen-reader pronunciation.

### KNOWN — Prod `/healthz/data` `any_stale: true` (BCC/FN/DCE/TLL) — **NOT FAILING (flagged per ct-4uu scope)**

Confirmed: prod and staging both show `any_stale: true` with multiple tenants timestamped 2026-05-19. Tracked under in-flight PR #63.

---

## Cross-cutting observations

- `Server: uvicorn, Azure-Governance-Platform` header on every response — minor framework/platform disclosure. Strip in reverse proxy. → filed as `ct-9n8` (P3)
- Staging HSTS = `max-age=86400; includeSubDomains` (24 h). Acceptable for staging, document the tier difference vs prod's 1 yr.
- All `/health*`, `/healthz/*` payloads inspected — **no PII** present. Internal metrics only (cache stats, pool counts, component status, tenant names + sync timestamps).

## Performance numbers (Chromium headless, US-to-US)

| Endpoint | TTFB | Notes |
|---|---|---|
| prod `/health` | 101 ms | ✅ < 300 ms target |
| staging `/health` | 143 ms | ✅ |
| prod `/auth/login` cold load | ~1.5 s | ✅ < 3 s target |
| staging `/auth/login` cold load | 1.83 s | ✅ |
| prod `/openapi.json` | 3.2 s | acceptable (245 KB) |
| public docs `/` cold | 486 ms | ✅ |

## Tools / methodology

- Playwright (`headless=True`) via qa-kitten agent, 1 browser context per browser type
- Visual: full-page + viewport screenshots, analyzed inline by the QA agent
- Behavioral: `fetch()` from same-origin to capture status, headers, body previews
- Perf: `performance.getEntriesByType('navigation' | 'resource')`
- Security: CSP / HSTS / XFO / XCTO header inspection
