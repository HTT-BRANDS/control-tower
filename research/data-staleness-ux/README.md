# Data Staleness UX — Executive Summary (2026)

**Project context:** Control Tower, a multi-tenant Azure governance dashboard. Sync jobs can report `success` yet produce zero new rows, leaving data silently stale. We need (a) a top-of-page banner and (b) per-row freshness indicators that meet WCAG 2.2 AA and don't leak tenant PII.

**Researcher:** `web-puppy-ddc969` · **Date:** 2026 · **Source tier breakdown:** see `sources.md`.

---

## TL;DR — Operational Guidance

| # | Question | Recommendation |
|---|----------|----------------|
| 1 | WCAG 2.2 AA for stale indicators | Pair an icon **+** text label **+** `role="status"` (polite) for normal stale states; reserve `role="alert"` / `aria-live="assertive"` only for hard-broken sync. Never communicate staleness by color alone (SC 1.4.1). |
| 2 | Amber/warning contrast tokens | Use the **token, not the raw hex**: Carbon `$support-warning` (Yellow 30 `#F1C21B`) is icon-only — its 1.7:1 ratio against white **fails text contrast**. For warning *text* use `$text-primary` on a `$notification-background-warning` surface. Material 3 has no semantic "warning" role; teams extend with `tertiary` + on-tertiary text. SLDS 2 ships `--slds-g-color-warning-*` tokens (~`#FE9339`) that pair with dark text only. **Always check contrast against your actual background, not the brand swatch.** |
| 3 | Banner vs toast vs inline | For a problem the user **must act on and cannot dismiss**, use the **Carbon "Callout"** pattern (persistent, loads with page, no dismiss `x`, contextual to the data). Toasts are *wrong* here — they auto-dismiss. NN/g classifies this as a *system status indicator* (persistent), not a *notification* (transient). |
| 4 | Per-tenant freshness without leaking PII | Show **only**: tenant display name (already authorized to viewer), last-successful-sync timestamp (ISO 8601 + relative), row-delta count, and sync job ID. **Never** include sample rows, employee names, UPNs, or object IDs in the indicator. GDPR Art. 5(1)(c) data-minimization is satisfied because counts + timestamps are *metadata about the sync*, not personal data. |
| 5 | Icon glyph | **Clock-with-exclamation** (or "history with warning overlay") has the strongest a11y track record at 16px. Avoid `hourglass` (collides with *loading* semantics) and `cloud-off` (implies network failure, not stale data). Always pair with a visible text label — icon-only fails SC 1.1.1. |

---

## Files in this research

- `README.md` — this summary
- `sources.md` — source list with credibility tier
- `analysis.md` — multi-dimensional analysis (a11y / cost / complexity / stability / privacy)
- `recommendations.md` — Control Tower-specific action items with code sketches
- `raw-findings/` — extracted source content for traceability

---

## Citation links (primary)

- WCAG 2.2 SC 4.1.3 Status Messages — https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
- WCAG 2.2 SC 1.4.1 Use of Color — https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html
- WCAG 2.2 SC 3.3.1 Error Identification — https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html
- IBM Carbon — Notification usage (Callout variant) — https://carbondesignsystem.com/components/notification/usage/
- NN/g — Indicators, Validations, and Notifications — https://www.nngroup.com/articles/indicators-validations-notifications/
- Material 3 — Color roles — https://m3.material.io/styles/color/roles
- Salesforce Lightning Design System 2 — Notification & color tokens — https://www.lightningdesignsystem.com/2e1ef9b39/p/82c52e-notifications
- GDPR Article 5(1)(c) Data Minimisation — https://gdpr-info.eu/art-5-gdpr/
