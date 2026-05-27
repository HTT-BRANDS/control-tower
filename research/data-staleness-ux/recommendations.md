# Recommendations — Control Tower Implementation

Tailored to the Control Tower multi-tenant Azure governance dashboard. Prioritized P0 → P2.

---

## P0 — Must do before shipping the staleness UI

### R1. Use a persistent Callout-style banner, not a toast
- Component: build (or adopt from Carbon React) a non-dismissable banner that loads with the page when *any* tenant in the viewer's scope is stale.
- Place it **above** the tenant grid, full width of the content area.
- Markup pattern:
  ```html
  <div role="status" aria-live="polite" aria-atomic="true"
       class="ct-callout ct-callout--warning">
    <svg aria-hidden="true">…clock-warning glyph…</svg>
    <p>
      <strong>3 tenants have stale data.</strong>
      Sync jobs succeeded but returned 0 new rows in the last 12h.
      <a href="/sync-health">Review sync health →</a>
    </p>
  </div>
  ```
- **Do not** add a close `x`. Carbon Callout spec: persistent, non-dismissable.

### R2. Per-row indicator: icon + text + tooltip
- Column: "Last sync".
- Cell content: `<icon clock-warning> Stale · 14h` (text is the source of truth; icon is decorative).
- `title` attribute + accessible tooltip with absolute ISO 8601 UTC timestamp.
- Apply the warning surface token **only to the badge background**, not the whole row (avoids overwhelming the grid and avoids SC 1.4.1 over-reliance on row color).

### R3. WCAG-compliant live region strategy
- Banner mount: `role="status"` (polite). Do not use `assertive` unless the stale state newly *blocks* an action the user just attempted.
- Updates: re-render the entire banner message string with `aria-atomic="true"` so SR users get full context, not just the changed number.
- Run an automated check (axe-core) for the dashboard route in CI gating — `pyproject.toml` / Playwright tests already exist in this repo.

### R4. Privacy contract for the staleness API
Define and enforce a TypeScript / Pydantic schema for the freshness endpoint that **excludes** any tenant data fields:
```python
class TenantFreshness(BaseModel):
    tenant_id: UUID            # opaque
    tenant_display_name: str   # authorized for viewer
    last_sync_at: datetime     # UTC
    last_success_at: datetime  # UTC
    rows_delta_24h: int
    sync_job_id: str           # correlation ID
    status: Literal["fresh", "stale_soft", "stale_hard", "failed"]
    # NO: sample_rows, employee_*, upn, object_id, resource_names
```
Add a unit test that fails if any field name matches a PII allowlist regex (`upn`, `email`, `name` other than `tenant_display_name`, `oid`, `object_id`).

---

## P1 — Strongly recommended

### R5. Two-tier staleness thresholds
- `stale_soft`: > SLA but < 2× SLA → amber Callout (`role="status"` polite), data still usable.
- `stale_hard`: ≥ 2× SLA or sync_job in `success_no_rows` for N consecutive runs → red Callout + `role="alert"` (assertive justified because user *must* act).
- Threshold values configurable per tenant tier in `config/` (this repo already has `core_stack.yaml`).

### R6. Detect "silent stale" specifically (your actual bug)
The dangerous case is `sync_status=success AND rows_inserted=0 AND elapsed_since_last_nonzero > SLA`. Surface this with distinct copy:
> "Sync completed successfully but **0 new rows** in the last 14h. This usually indicates an upstream connector issue, not a sync failure."

Treat this state as `stale_hard` even though the job reports green — that's the whole point of the indicator.

### R7. Design-system tokens, not raw hex
- If Control Tower uses Tailwind (`tailwind.config.cjs` is present): define semantic tokens `warning-surface`, `warning-text`, `warning-icon` in the config and reference them via `bg-warning-surface text-warning-text`. Verify each pair hits 4.5:1 in **both** light and dark themes.
- Add a Storybook / visual regression check for the Callout in both themes.

---

## P2 — Nice-to-have

### R8. Notification center
- Carbon recommends a notification center for users to "revisit and act on past notifications". Useful for SREs investigating *when* tenants went stale. Out of scope for v1.

### R9. Per-tenant opt-in alerts (email/Teams)
- Out of scope for the UI, but staleness model from R4 is the right primitive to power Azure Monitor alert rules later.

### R10. Internationalization
- Relative timestamps ("14h ago") need locale handling. Use `Intl.RelativeTimeFormat` (browser-native) or the existing i18n stack. Always also expose the absolute ISO 8601 UTC timestamp for SRE clarity.

---

## Acceptance checklist (paste into PR template)

- [ ] Banner uses `role="status"` (soft) or `role="alert"` (hard) — never assertive for ambient state.
- [ ] Banner is **not** dismissable.
- [ ] Per-row badge has visible text, not icon-only.
- [ ] Warning surface/text token pair verified ≥ 4.5:1 in light **and** dark themes.
- [ ] Freshness API response contains zero tenant PII fields (schema-tested).
- [ ] axe-core CI check passes for the dashboard route.
- [ ] Manual screen reader test (NVDA + VoiceOver) confirms announcement once, not on every render.
- [ ] Tooltip exposes absolute UTC timestamp (ISO 8601).
- [ ] `success_no_rows` state is treated as stale, not fresh.
