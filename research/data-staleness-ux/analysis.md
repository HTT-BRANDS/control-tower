# Multi-Dimensional Analysis

## 1. Accessibility (WCAG 2.2 AA)

### Required (normative)
- **SC 1.4.1 Use of Color** — Color alone cannot signal staleness. Pair amber surface with an icon **and** explicit text ("Data is 14h old · last sync 2026-01-15 03:00 UTC").
- **SC 1.1.1 Non-text Content** — Icon needs an accessible name (`aria-label` or visually-hidden text). If text label is already present beside the icon, mark the icon `aria-hidden="true"` to avoid duplicate announcement.
- **SC 4.1.3 Status Messages** — When the banner appears *without focus change* (e.g., poll detects staleness), wrap it in `role="status"` (implicit `aria-live="polite"`, `aria-atomic="true"`).
- **SC 3.3.1 Error Identification** — If staleness blocks a workflow action (e.g., "Cannot generate report — data 48h old"), the error must be identified in **text**, near the disabled control.

### `polite` vs `assertive` decision table
| Stale state | Live region | Rationale |
|---|---|---|
| Soft stale (>SLA but readable) | `role="status"` / `aria-live="polite"` | Wait for SR idle; non-urgent. |
| Hard stale + blocks action | `role="alert"` / `aria-live="assertive"` | Interrupts; user *must* act. |
| Stale resolved (data refreshed) | `role="status"` polite | Confirmation; never assertive (per WCAG advisory). |

### Common failures to avoid (per WCAG F103 + advisory)
- Banner inserted into DOM with **no** ARIA role → screen reader users never hear it. F103 failure.
- Using `role="alert"` for *every* status update — causes "chatty" SR experience, users disable AT.
- Updating only the changing number (e.g., "14" → "15") without `aria-atomic="true"` → SR announces just the digit, losing context.

## 2. Color & Contrast

WCAG 2.2 AA requires **4.5:1** for normal text, **3:1** for large text and non-text UI components (SC 1.4.11).

### Carbon (IBM) — verified from Carbon design tokens
- `$support-warning` = **#F1C21B** (Yellow 30). Contrast vs white ≈ **1.74:1** → **PASSES only as a 3:1 non-text UI indicator at large size**, FAILS as text. Carbon uses this for the warning icon fill and pairs it with `$text-primary` (near-black) for the label.
- Carbon `$notification-background-warning` = a desaturated yellow tint designed to pass 4.5:1 against `$text-primary`. Use the **token**, not the brand swatch.

### Material 3
- M3 has no first-class "warning" role; canonical roles are `primary` / `secondary` / `tertiary` / `error`. For stale-data UI, teams typically:
  - Use the **tertiary** container + on-tertiary text pair, or
  - Define a custom `warning` / `on-warning` pair and run the M3 Color Builder to guarantee tonal palette steps that hit 4.5:1.
- **Do not** reuse `error` for stale; that semantic is reserved for blocking failures.

### SLDS 2 (Salesforce Lightning 2)
- Ships explicit semantic warning tokens (e.g., `--slds-g-color-warning-base-50` ≈ `#FE9339`, with `--slds-g-color-on-warning-base-50` paired to hit AA). Use tokens, not raw hex.

### Operational rule
> Pick the design-system **token** (`warning-surface` + `on-warning-text`) rather than a hex. The token contract guarantees AA contrast across light/dark themes. If implementing without a design system, sample both light **and** dark backgrounds with a contrast checker before merge.

## 3. Pattern Choice: Banner vs Toast vs Inline

| Pattern | Persistent? | Dismissable? | Use for staleness? |
|---|---|---|---|
| **Toast** | No (auto-dismiss ~5s in Carbon) | Yes | ❌ Wrong — user can miss it. |
| **Inline notification** | Yes | Optional `x` | ⚠️ OK for transient errors but Carbon notes "do not include `x` if it is critical the user reads it". |
| **Carbon Callout** | Yes, loads with page | **No dismiss** | ✅ **Exact fit.** "Persistent, always present on the screen to provide necessary information." |
| **Modal** | Yes, blocks | Yes (close) | ❌ Too disruptive for ambient state. |
| **Per-row badge (indicator)** | Yes | No | ✅ Pair with banner for row-level granularity. NN/g taxonomy: "indicator". |

### NN/g taxonomy mapping
- **Indicator** = persistent visual cue on a dynamic UI element → per-row freshness badge.
- **Notification** = transient, system-initiated message → not appropriate here.
- **Validation** = inline feedback during user input → not applicable.

## 4. Privacy (GDPR Art. 5(1)(c) Data Minimisation)

### Safe to display per tenant
- Tenant display name (viewer is already authorized).
- Last successful sync timestamp (ISO 8601 + relative "14h ago").
- Row count delta (e.g., "0 new rows in 14h").
- Sync job ID / correlation ID (opaque).
- Job status enum (`success_no_rows`, `partial`, `failed`).

### Never in the indicator
- Sample/preview rows from tenant data.
- Employee names, UPNs, email addresses, Entra ID object IDs.
- Resource names that may embed PII (e.g., `vm-jdoe-laptop`).
- Tenant-internal IP / subscription names if your viewer is cross-tenant support.

### GDPR rationale
Article 5(1)(c) requires personal data to be "adequate, relevant and limited to what is necessary". Sync metadata (timestamp, count, job ID) is not personal data and fully answers "is this tenant's data fresh?". Including sample rows would be a minimisation violation with no operational justification.

### Multi-tenant defense-in-depth
- Render staleness via a server-side endpoint that filters by the requester's authorization scope.
- Log audit trail when an operator opens *deep* sync details (separate page with full RBAC check) — not for the dashboard glance view.
- For cross-tenant support views, **pseudonymize** tenant identifiers in URLs and screenshots to prevent shoulder-surfing leakage.

## 5. Icon Glyph Selection

| Glyph | A11y at 16px | Distinguishable from loading? | Verdict |
|---|---|---|---|
| **Clock with exclamation** (or warning overlay) | ✅ Strong silhouette, recognizable | ✅ Loading spinners are circular motion; clock is static | ✅ **Recommended.** Carbon ships `time--warning` / similar; Material Symbols `schedule` + badge. |
| Hourglass | ⚠️ Ambiguous — Windows used hourglass for "busy/loading" for decades | ❌ Conflicts with loading semantic | Avoid. |
| Cloud-off | ⚠️ Implies *network/connectivity* failure, not data staleness | ✅ Distinct from loading | Wrong semantic. Reserve for actual offline state. |
| Refresh with slash | ⚠️ "Cannot refresh" — different meaning | OK | Misleading; sync *did* succeed in our scenario. |
| Database with warning badge | ✅ Clear for technical audience | ✅ | Good secondary choice; less universal than clock+warning. |

### Implementation
- Use **16px** glyph + adjacent text label (e.g., "Stale · 14h").
- Mark icon `aria-hidden="true"` when text label is adjacent.
- Provide a `title` attribute / tooltip with absolute timestamp.
- Ensure 3:1 contrast for the glyph against its background (SC 1.4.11).

## 6. Stability / Maintenance

- WCAG 2.2 is the current Recommendation (since Oct 2023) and remains stable for AA conformance through 2026. WCAG 3.0 is still in draft.
- Carbon Notification component is at React `^1.105.0` (verified May 2026). Callout is GA. A feature flag exists for *actionable* notifications heading to v12 — does not affect Callout.
- Material 3 color system stable; M3 Expressive update (2025) did not change role semantics.
