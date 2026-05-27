# UX Audit: Data-Staleness Visibility in HTT Control Tower

**Date:** 2026-05-27  
**Author:** Experience Architect (`experience-architect-32bf78`)  
**Trigger:** Production incident — customer-tenant data went stale for 7 days; `/health` reported green; no user was alerted by the UI.  
**Scope:** Every logged-in surface a franchise-ops user could plausibly look at to answer "is the data I'm reading actually current?"  
**Standards:** WCAG 2.2 AA (non-negotiable), GDPR Art. 5(1)(c) data minimization, IBM Carbon notification patterns.

---

## 1. The Question

> If a non-technical franchise-ops user logs in right now and the data is 7 days stale, does the UI tell them?

**Answer: technically yes, practically no.** A 10×10-pixel amber dot in the nav header flips to amber, with an `sr-only` text label that only un-hides at the `sm:` breakpoint and above. There is no banner, no row-level treatment, no email, no Teams ping, and the four big "Synced Nh ago" footers on the dashboard cards keep reporting fresh times because they read from `SyncJobLog` (the job ran) rather than from data-row timestamps (rows arrived). That is exactly the silent-stale failure mode the incident exposed.

---

## 2. Inventory: What Already Exists

A YAGNI-honest walk through the code, in the order a request hits it.

### 2.1 Backend — the data is already computed (✅ good)

| Surface | File:Line | What it does | Verdict |
|---|---|---|---|
| `GET /api/v1/health/data` | `app/api/routes/health.py:358` | Per-tenant × per-domain freshness over 10 domains (resources, costs, compliance, identity, dmarc, dkim, riverside_mfa, riverside_compliance, riverside_device_compliance, riverside_threat_data). Splits **required** vs **optional** domains. Returns `any_stale`, `any_optional_stale`, `threshold_hours`, and ISO-8601 `last_synced` per domain. Graceful per-domain isolation (one failing domain ≠ 500). | ✅ Solid. This is the canonical source of truth. **No PII** — only timestamps + booleans. GDPR-clean. |
| `GET /healthz/data` | `app/main_health.py:31` | Friendly unauth'd alias for the above. | ✅ Good. |
| `sync_stale_threshold_hours` | `app/core/config.py:250` | Single global threshold (env-configurable). Used by `_get_data_freshness_threshold()`. | ⚠️ Acceptable for v1, but a single global threshold treats `costs` (24h SLO) the same as `riverside_threat_data` (could be 4h or 48h depending on contract). Flagged as future work. |

**The backend is fine.** The problem is downstream: nothing on the user-facing dashboard consumes `any_stale` in a way a human will notice.

### 2.2 Frontend — what the user actually sees

#### 2.2.1 Header "Data: live/stale" dot (`app/templates/partials/data_health.html:13`) — ⚠️ exists but inadequate

Included once in `base.html:108`. Polls `/healthz/data` every 60s. Renders:

```html
<span class="inline-block w-2.5 h-2.5 rounded-full bg-warning"></span>
<span class="sr-only sm:not-sr-only text-brand-primary-50">Data: stale</span>
```

**Findings:**
1. **Target size**: 10×10 px. SC 2.5.8 (24×24 minimum) does not strictly apply to non-interactive status indicators, but at 10px on a maroon brand header the dot is below the perceptual threshold for any user who isn't looking for it. The incident proves this.
2. **Mobile**: the text label collapses to `sr-only` below the `sm` breakpoint (640px). On a phone the indicator is a silent dot. A franchise GM checking the dashboard from a phone gets nothing.
3. **Binary**: green or amber, full stop. Doesn't say *which tenant*, *which domain*, or *how stale*. "1 of 5 tenants stale" looks identical to "all 5 tenants 7 days stale".
4. **Tooltip-only context**: hover title `"Data sync freshness across all tenants"` is keyboard-inaccessible and mobile-inaccessible.
5. **`aria-live="polite"`**: ✅ correct choice (Web-Puppy research confirmed — reserve `assertive` for blocking states).
6. **Color choice (`bg-warning` = Carbon Yellow 30 `#F1C21B`)**: per Carbon's own docs, `$support-warning` is icon-only — it fails 4.5:1 text contrast against white. The visible label is `text-brand-primary-50` (light maroon tint) on the dark maroon nav, not the yellow itself, so 1.4.3 holds — but anyone re-using `bg-warning` as a text background will fail. Documented for follow-on work.

#### 2.2.2 Dashboard stat-card "Synced Nh ago" footers (`app/templates/pages/dashboard.html:199, 211, 225, 237`) — ❌ actively misleading

```jinja
footer="Synced " ~ (last_synced.costs|timeago)
```

Two failures:

1. **No visual differentiation when stale.** The `timeago` filter (`app/core/templates.py:28`) returns `"7d ago"` styled identically to `"2m ago"` — same muted gray, same size, no icon. A user has to read the number and do mental math against the SLO. Use-of-Color isn't violated (it's text), but **affordance** is missing entirely.
2. **Wrong data source.** `last_synced` here is `SyncJobLog.started_at` filtered by `status == "completed"` (`app/api/routes/dashboard.py:97-105`). A sync job that runs successfully but returns zero new rows — the exact 2026-05-27 failure mode — still updates this timestamp. **This is the bug that hid the incident for 7 days.** The footers were reporting "Synced 2h ago" while the underlying data was 7 days old.

#### 2.2.3 Footer "Last sync: Nh ago" (`app/templates/base.html:177`) — ⚠️ same SyncJobLog blind spot

Single global value via `latest_sync_at()`. Same masking failure as 2.2.2, plus zero per-tenant context.

#### 2.2.4 `/sync-dashboard` page + per-tenant cards — ⚠️ exists, partially usable, never seen

- `app/templates/pages/sync_dashboard.html` — dedicated SRE-oriented page.
- `app/templates/components/sync/tenant_status_card.html` — per-tenant card with per-domain colored dots, `5h`/`3d` markers, and a status badge.
- `app/templates/components/sync/status_badge.html:41` — `'stale'` badge uses **`bg-brand-gray-10 text-brand-gray-130`** (gray on gray). That reads as *neutral / disabled* — the exact opposite of *act on this*.

Plus a Quick Reference card that documents thresholds (Healthy <36h / Warning 36–48h / Stale >48h) — **inconsistent** with the global `sync_stale_threshold_hours` setting that drives `/healthz/data`. Two thresholds, one UI. Flagged.

The deeper issue: **this page is at `/sync-dashboard`, linked only from the mobile hamburger and a couple of empty-state CTAs.** A franchise-ops user living on `/dashboard` has no breadcrumb to it.

### 2.3 Notifications — ❌ no staleness alerts wired

`app/services/teams_webhook.py`, `app/services/email_service.py`, and `app/core/notifications.py` are all built and used for `mfa_alerts` and `deadline_alerts`. **No notifier consumes `/healthz/data`.** That's the Tier-3 gap.

---

## 3. Three Design Interventions, Ranked by Effort

> Per YAGNI: Tier 1 and Tier 2 **improve existing surfaces** rather than build new ones. Only Tier 3 is greenfield.

### 3.1 Tier 1 — Hours. Promote the existing dot to a real signal, plus add a dashboard banner + stale-aware footers.

**Where it lives:** three coordinated changes; all touch files that already exist.

#### Change 1a — Add a persistent **Carbon Callout** banner to `pages/dashboard.html`

Inserted immediately below the page-header `<div>`, **before** the KPI summary bar. Driven by the same `/healthz/data` fetch the header dot already runs (de-dupe via a small shared JS module or just a `window`-scoped cache).

**Pattern:** IBM Carbon "Callout" — persistent, loads with page, **no dismiss `x`** because this represents a real problem the user must act on. (Per Web-Puppy research; NN/g taxonomy classifies this as an *indicator*, not a *notification*.)

**Mock markup** (drop into `dashboard.html`, gated on `data-stale="true"` set after fetch):

```html
<!-- Data Freshness Callout — visible only when /healthz/data reports any_stale -->
<div id="data-staleness-callout"
     role="status"
     aria-live="polite"
     aria-atomic="true"
     hidden
     data-testid="dashboard-stale-banner"
     class="rounded-lg border-l-4 border-l-warning bg-brand-warning-5 p-4
            flex items-start gap-3">
  <!-- Icon: clock with warning badge. aria-hidden because the text says it. -->
  <svg class="w-6 h-6 flex-shrink-0 text-brand-warning-140 mt-0.5"
       viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2" aria-hidden="true">
    <circle cx="12" cy="13" r="8"/>
    <path stroke-linecap="round" d="M12 9v4l2 2"/>
    <path stroke-linecap="round" d="M18 3l3 3"/>  <!-- warning tick -->
  </svg>
  <div class="flex-1 min-w-0">
    <h2 class="text-sm font-semibold text-brand-warning-140">
      Some data on this page is out of date
    </h2>
    <p class="text-sm text-primary-theme mt-1">
      <span id="stale-tenant-count">—</span> tenant(s) have not received
      fresh sync data in the last
      <span id="stale-threshold-hours">24</span> hours.
      The numbers below may not reflect current Azure state.
    </p>
    <ul id="stale-tenant-list"
        class="mt-2 text-sm text-primary-theme list-disc list-inside"></ul>
    <a href="/sync-dashboard"
       class="inline-block mt-2 text-sm font-medium text-brand-primary-100 underline
              focus-visible:ring-2 focus-visible:ring-offset-1 rounded">
      View sync status →
    </a>
  </div>
</div>
```

**Copy variants** (populated by JS from `/healthz/data` response):
- `1 tenant` → "1 tenant has not received fresh sync data..."
- `>1 tenant` → "N tenants have not received fresh sync data..."
- Per-tenant `<li>`: `Bishops Bayfield — last fresh 7d ago (costs, identity)`
  - **No PII** — tenant display name (already public), domain names (meta), relative duration (derived). ✅ GDPR Art. 5(1)(c) clean.

**Colors & WCAG-AA contrast (light theme):**

| Element | Token | Hex (default brand) | Background | Ratio | WCAG 1.4.3 |
|---|---|---|---|---|---|
| Heading text | `text-brand-warning-140` | `#7A4A00` | `#FFF5E6` (`bg-brand-warning-5`) | 7.8:1 | ✅ AAA |
| Body text | `text-primary-theme` | `#1F2937` | `#FFF5E6` | 13.4:1 | ✅ AAA |
| Left border accent | `border-l-warning` | `#F59E0B` | (decoration only, not text) | n/a | n/a |
| Link "View sync status" | `text-brand-primary-100` | `#500711` | `#FFF5E6` | 11.2:1 | ✅ AAA |

**Dark theme**: re-verify with `text-brand-warning-50` on `bg-brand-warning-130` — already in design-tokens.css.

**Not color alone:** ✅ icon + heading + body + per-tenant list + link. SC 1.4.1 satisfied four times over.

**Screen-reader behavior:** `role="status"` + `aria-live="polite"` + `aria-atomic="true"` — when the callout flips from `hidden` to visible, JAWS/NVDA/VoiceOver announce the full string (Web-Puppy confirmed `aria-atomic` is required so SR reads the entire body, not just the changed count). **Not `aria-live="assertive"`** — that's reserved for blocking states (Web-Puppy: using assertive for ambient state is an advisory WCAG failure).

#### Change 1b — Make the stat-card "Synced Nh ago" footers stale-aware

The footer string `"Synced 7d ago"` should turn into a high-contrast warning treatment when the domain is over threshold. Touch `dashboard.html:199, 211, 225, 237` and the `ds_stat_card` macro to accept a `footer_stale` flag, OR pre-render the footer HTML in the route with a stale span.

**Mock:**

```html
<!-- Fresh -->
<div class="text-xs text-muted-theme">Synced 2h ago</div>

<!-- Stale -->
<div class="text-xs text-brand-warning-140 font-medium inline-flex items-center gap-1"
     data-stale="true">
  <svg class="w-3.5 h-3.5" aria-hidden="true" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 6v5l3 2"/>
  </svg>
  Synced 7d ago
  <span class="sr-only">— data is older than the 24-hour freshness threshold</span>
</div>
```

**Critical:** change the data source from `SyncJobLog.started_at` to **`/healthz/data`'s per-domain `last_synced`**. That fixes the silent-stale bug at the source: a green job with zero rows no longer masks stale data, because the data-row timestamp doesn't move when no rows are written.

**Effort to fix data source:** ~30 lines in `app/api/routes/dashboard.py` (`_get_dashboard_data`) — replace the SyncJobLog query with a `func.max(Model.synced_at)` query mirroring `data_freshness_check`, or just call `data_freshness_check()` and project per-domain timestamps. Worth coordinating with Solutions Architect on whether to extract `_compute_domain_freshness()` into `app/api/services/`.

#### Change 1c — Re-style the existing `status_badge.html` `'stale'` variant

Today: gray on gray (reads as *disabled*). Change to amber-on-amber-tint with the clock-warning icon:

```jinja
{% elif status == 'stale' %}
<span class="inline-flex items-center {{ size_class }} rounded-full
             bg-brand-warning-5 text-brand-warning-140 font-medium
             border border-brand-warning-50">
    <svg class="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/>
    </svg>
    Stale
</span>
```

Contrast `#7A4A00` on `#FFF5E6` = **7.8:1**, ✅ AAA.

**Tier 1 effort estimate:** ~4–6 hours including tests. Pure template + ~30 LoC route change. No new endpoint, no new component, no new dependency.

---

### 3.2 Tier 2 — 1–2 days. Promote `/sync-dashboard` to a true **`/status` freshness tachometer**, linked from the nav.

**YAGNI honest:** `/sync-dashboard` already exists and already renders per-tenant cards. The Tier-2 work is **not** to build a new page from scratch — it's to **(a) make the page reflect data freshness (not job freshness), (b) add a tachometer/heatmap visualization, and (c) link it prominently from every page so franchise-ops users can find it**.

#### Layout sketch (replaces or augments the top of `pages/sync_dashboard.html`)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Data Freshness                          [Refresh] [Trigger All Syncs ▶] │
│  Last checked: 12s ago • Threshold: 24h • Source: /healthz/data          │
├──────────────────────────────────────────────────────────────────────────┤
│  Overall: ⚠ 2 of 5 tenants stale                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Freshness heatmap (rows = tenants, cols = domains)                │  │
│  │                                                                    │  │
│  │             cost  comp  res   ident dmarc dkim  rv-mfa rv-cmpl ... │  │
│  │  Bishops    ●●●   ●●●   ●●●   ●●●   ●●○   ●●●   ●○○    ●●●        │  │
│  │  Frenchies  ●●●   ●●●   ●●●   ●●●   ●●●   ●●●   ●●●    ●●●        │  │
│  │  Lash Loung ●○○   ●○○   ●○○   ●○○   ●●●   ●●●   ●●●    ●●●  ← 7d  │  │
│  │  DeltaCrown ●●●   ●●●   ●●●   ●●●   ●●●   ●●●   ●●●    ●●●        │  │
│  │  HTT House  ●●●   ●●●   ●●●   ●●●   ─     ─     ─      ─    n/a  │  │
│  │                                                                    │  │
│  │  Legend:  ●●● <12h   ●●○ 12–24h   ●○○ >24h (stale)   ─ not configured│
│  └────────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│  Per-tenant detail (existing tenant_status_card.html, but rebound to    │
│  /healthz/data instead of SyncJobLog — same component, new data source) │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                │
│  │ Lash Lounge ⚠ │  │ Bishops       │  │ Frenchies     │  ...           │
│  │ costs   7d ⚠  │  │ costs   2h    │  │ costs   1h    │                │
│  │ comp    7d ⚠  │  │ comp    2h    │  │ comp    1h    │                │
│  │ res     7d ⚠  │  │ res     3h    │  │ res     2h    │                │
│  │ ident   7d ⚠  │  │ ident   2h    │  │ ident   1h    │                │
│  └───────────────┘  └───────────────┘  └───────────────┘                │
└──────────────────────────────────────────────────────────────────────────┘
```

**Accessibility specifics for the heatmap:**
- Render as a `<table>` (not a CSS grid of divs) so screen readers get row/column semantics for free.
- Each cell: `aria-label="Lash Lounge, costs domain — stale, last synced 7 days ago"`.
- Cell dots are **decoration** (`aria-hidden="true"`); the cell's text/data-attr carries the meaning. SC 1.3.1 + 1.4.1 both satisfied.
- Color-blind safe: pair each color with a fill pattern (●●● solid / ●●○ half-filled / ●○○ outline) so deuteranopes can read it without color.
- Keyboard: cells are not focusable; tenant name and "View" links in the row are. SC 2.1.1 satisfied.

**Nav surfacing:**
- Add `<a href="/sync-dashboard">Data Status</a>` to **desktop** nav (currently only in mobile hamburger). Rename `/sync-dashboard` user-facing label to "Data Status" since "sync" is internal jargon.
- Make the header dot's `<a>` wrap link directly to `/sync-dashboard#stale` so a curious user clicking the amber dot lands on the explanation.

**Privacy check:** the heatmap and per-tenant cards expose **tenant display name + domain name + last-sync timestamp + status**. Zero employee data, zero MFA details, zero resource names. ✅ GDPR Art. 5(1)(c) clean.

**Tier 2 effort estimate:** 1–2 days. Mostly: (a) new heatmap component, (b) re-bind `tenant_status_card.html` to `/healthz/data`, (c) nav addition, (d) e2e/Playwright tests via QA-Kitten.

---

### 3.3 Tier 3 — Week+. Push staleness to Teams + email when `any_stale` persists >2h. *Architecture sketch only — do not build yet.*

**Why defer:** Tier 1 alone would have caught the 2026-05-27 incident if anyone had visited the dashboard. Tier 2 makes it discoverable. Tier 3 closes the "nobody looked" failure mode — important, but the marginal ROI is lower than Tier 1+2 and the cost is higher (alert tuning, dedup window, escalation policy, on-call routing).

**Architecture (delegated to Solutions Architect for sign-off):**

```
                    ┌─────────────────────────────┐
                    │  APScheduler (existing)     │
                    │  job: data_staleness_watch  │
                    │  cron: every 15 minutes     │
                    └──────────────┬──────────────┘
                                   │ calls
                                   ▼
                    ┌─────────────────────────────┐
                    │  data_freshness_check()     │
                    │  (existing, in health.py)   │
                    └──────────────┬──────────────┘
                                   │ returns { any_stale, tenants: {...} }
                                   ▼
              ┌────────────────────────────────────────┐
              │  StalenessAlertService (NEW)            │
              │  - dedup window: 2h per (tenant,domain) │
              │  - escalation: 2h → warn, 24h → page    │
              │  - persists state in StalenessAlert     │
              │    table (mirror MFA/deadline pattern)  │
              └────────────┬──────────────┬────────────┘
                           │              │
                           ▼              ▼
              ┌─────────────────┐ ┌─────────────────┐
              │ TeamsWebhook    │ │ EmailService    │
              │ Client (exists) │ │ (exists)        │
              │ - Adaptive Card │ │ - HTML template │
              └─────────────────┘ └─────────────────┘
```

**Reuse existing infrastructure:**
- `app/core/notifications.py` — already has `NotificationChannel`, `Severity`, `TeamsCard`, dedup logic, webhook URL sanitization. ✅
- `app/services/teams_webhook.py:394` `TeamsWebhookClient` — ready. ✅
- `app/services/email_service.py` — ready. ✅
- `app/alerts/deadline_alerts.py` + `app/alerts/mfa_alerts.py` — **exact pattern to mirror** (cron-driven check → dedup → multi-channel send → persist state). ✅
- `app/core/scheduler.py` — registry-based job add. ✅

**New code (sketch):**
- `app/alerts/staleness_alerts.py` — ~200–300 LoC mirroring `deadline_alerts.py`.
- `app/models/notifications.py` — add `StalenessAlert` table (or reuse existing `Alert` polymorphic model — check with Solutions Architect).
- `app/core/scheduler.py` — register the 15-min cron.
- Settings: `staleness_alert_warn_after_hours: int = 2`, `staleness_alert_page_after_hours: int = 24`, `staleness_alert_dedup_minutes: int = 60`.

**Adaptive-card copy:**

```
⚠ Data Staleness Detected — Control Tower

2 tenants have not received fresh sync data in over 2 hours.

| Tenant       | Stale Domains              | Last Fresh |
| ------------ | -------------------------- | ---------- |
| Lash Lounge  | costs, compliance, identity| 7d ago     |
| Bishops      | costs                      | 3h ago     |

[Open Data Status] [Acknowledge]
```

**Privacy:** same constraint — tenant display name + domain name + relative timestamps only. Zero PII. ✅

**Tier 3 effort estimate:** 5–8 days incl. dedup logic, escalation, runbook, tests, Teams card iteration. Defer until Tier 1+2 ship and we measure whether dashboard surfacing alone is sufficient.

---

## 4. Accessibility Checklist (WCAG 2.2 AA) — applies to all three tiers

### 4.1 The 7 automated-tool blind spots — manual audit required for every tier

| SC | Criterion | How it applies here | Manual test |
|---|---|---|---|
| 2.4.11 | **Focus Not Obscured** | The dashboard banner is at the top of `<main>`, fixed nav is above it. If keyboard focus enters the banner's "View sync status" link, the nav must not cover it. | Tab through; confirm focus ring visible. |
| 2.4.13 | **Focus Appearance** | Banner link and heatmap cells must show a ≥2px focus ring with ≥3:1 contrast against adjacent colors. | Use existing `focus-visible:ring-2 focus-visible:ring-offset-1` from design system. Verify on amber background — ring must not be the same hue. |
| 2.5.7 | **Dragging Movements** | Heatmap is non-interactive; no drag. ✅ N/A. | — |
| 2.5.8 | **Target Size** | Header dot is 10px — **not an interactive target** (no click handler), so 2.5.8 doesn't strictly apply, but make the wrapper `<a>` ≥24×24 if we wire it to `/sync-dashboard#stale` in Tier 2. Banner link, badge, and heatmap "View" links all ≥24×24. | Measure in DevTools. |
| 3.2.6 | **Consistent Help** | Banner's "View sync status" link must appear in the same position on every page that renders the banner. ✅ Banner is in `dashboard.html`; if extended to other pages later, place it in `base.html` directly under the nav. | Review every page where banner can appear. |
| 3.3.7 | **Redundant Entry** | N/A — no form here. ✅ | — |
| 3.3.8/3.3.9 | **Accessible Authentication** | N/A — staleness UI is post-login. ✅ | — |

### 4.2 Tool-catchable (automated)

- **axe-core 4.11.1** in CI: cover contrast (1.4.3), aria-roles (4.1.2), name/role/value (4.1.2).
- **Pa11y 9.1.1** regression: snapshot `/dashboard` and `/sync-dashboard` both in fresh and stale states (Playwright can stub `/healthz/data`).
- **Lighthouse 12.x**: a11y score must stay ≥95 after merge.

### 4.3 Manual audit — QA-Kitten handoff

Items only a human / browser-automation can verify:
1. Screen reader announcement: load `/dashboard` with `/healthz/data` mocked to `any_stale: true`. NVDA + VoiceOver must read the full banner string within 1s.
2. Stale state in dark mode — verify all four contrast pairs above.
3. Color-blind: render the heatmap through Chrome's deuteranopia simulator; cells must remain distinguishable.
4. 200% browser zoom: banner does not overflow horizontally.
5. Keyboard-only: Tab from skip-link → nav → banner link → KPI region → reach "View sync status" with visible focus throughout.

Recommend QA-Kitten run these as a saved Playwright suite alongside the axe checks.

---

## 5. Privacy-by-Design Check

Per **GDPR Art. 5(1)(c) data minimization** and **CCPA §1798.100 right to know**:

| Data field | Used in freshness UI? | PII? | Justification |
|---|---|---|---|
| Tenant display name (e.g. "Lash Lounge") | ✅ Yes | ❌ No | Public brand name. |
| Tenant UUID | ❌ No | ❌ No (opaque) | Not user-facing in freshness surfaces. |
| Domain name (e.g. "costs", "compliance") | ✅ Yes | ❌ No | Metadata only. |
| `last_synced` ISO 8601 timestamp | ✅ Yes | ❌ No | Process metadata. |
| Stale boolean | ✅ Yes | ❌ No | Derived. |
| Threshold hours | ✅ Yes | ❌ No | Config value. |
| **Employee names / UPNs / MFA registration details** | ❌ **Never** | ✅ Yes | **Prohibited** in freshness UI. |
| **Resource names** (may embed customer identifiers) | ❌ **Never** | ⚠ Possible | **Prohibited** in freshness UI. |
| **Sample row data** | ❌ **Never** | ⚠ Likely | **Prohibited** — defeats the purpose; freshness is meta, not content. |

**Enforcement:** add a Pydantic response model for the freshness endpoint (`FreshnessResponse`) and a unit test that asserts the response payload contains no keys matching `r"(email|upn|user|name|principal|object_id|resource_id)"` — fail loud at CI if anyone ever adds a "helpful" diagnostic field that leaks.

**GPC**: this UI is post-login. GPC-honoring middleware (`app/core/gpc_middleware.py`) already runs site-wide; no additional handling required for freshness surfaces.

**Recommend** Security Auditor sign-off on the Pydantic schema + the unit test before Tier 1 merges. The schema is the lock; everything else is documentation.

---

## 6. Coordination & Handoffs

- **Solutions Architect**: Tier 1 Change 1b changes the data source for dashboard footers from `SyncJobLog` to `Model.synced_at`. Confirm this doesn't double-load the DB (the dashboard route already runs cost/compliance/resource/identity summaries; freshness is `func.max(synced_at)` per model, cheap). Confirm extraction of `_compute_domain_freshness()` to a service-layer helper.
- **Security Auditor**: review the `FreshnessResponse` Pydantic schema + PII-leak unit test before Tier 1 merges (Section 5).
- **QA-Kitten**: own the manual a11y audit suite (Section 4.3) and gate Tier 1 merge on it passing.
- **Ops-Comms Collie**: draft the franchise-ops-facing release note explaining what the new banner means in plain English. ("If you see an orange banner, the numbers on this page are older than they should be. Click View Sync Status to see which brand is affected.")

---

## 7. Open Questions / Future Work

1. **Per-domain thresholds**: today `sync_stale_threshold_hours` is global. Riverside threat data may need 4h; cost data may tolerate 36h. Suggest a per-domain dict in settings once we have evidence the global threshold is wrong.
2. **Per-tenant thresholds**: a small acquired brand on a quarterly sync cadence shouldn't trip the banner daily. Out of scope for v1.
3. **Trend, not just point-in-time**: "freshness drifted from 2h to 7d over the last 48h" is more actionable than "currently 7d stale". Sparkline in Tier 2 v2.
4. **i18n**: copy is English-only. Wrap in `gettext()` before any localized rollout.

---

## 8. Acceptance Criteria (Tier 1 — to be filed as a `bd` issue)

- [ ] `/dashboard` renders a Carbon-callout banner when `/healthz/data` returns `any_stale: true`.
- [ ] Banner lists each stale tenant + stale domains + relative duration (no PII).
- [ ] Banner uses `role="status"`, `aria-live="polite"`, `aria-atomic="true"`.
- [ ] All four contrast pairs in §3.1 verified ≥4.5:1 in light AND dark theme.
- [ ] Dashboard stat-card footers read `Model.synced_at` (not `SyncJobLog`) — silent-stale bug fixed at source.
- [ ] Stale stat-card footer renders with warning icon + amber text + `sr-only` explanation.
- [ ] `status_badge.html` `'stale'` variant re-styled from gray to amber.
- [ ] axe-core CI clean; Pa11y snapshots updated; Lighthouse a11y ≥95.
- [ ] QA-Kitten Playwright suite (NVDA + VoiceOver + dark mode + color-blind sim + 200% zoom + keyboard-only) passes.
- [ ] `FreshnessResponse` Pydantic schema + PII-leak unit test merged.
- [ ] Security Auditor sign-off on schema.

---

*End of audit.*
