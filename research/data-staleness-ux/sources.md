# Sources & Credibility Assessment

| # | Source | URL | Tier | Currency | Notes |
|---|--------|-----|------|----------|-------|
| 1 | W3C — WCAG 2.2 SC 4.1.3 Status Messages | https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html | **T1** Primary standard | WCAG 2.2 Recommendation (Oct 2023, still current 2026) | Normative; defines `role="status"` vs `role="alert"`, F103 failure for non-programmatic status. |
| 2 | W3C — WCAG 2.2 SC 1.4.1 Use of Color | https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html | **T1** | Same | Color must not be the only visual means of conveying information. |
| 3 | W3C — WCAG 2.2 SC 3.3.1 Error Identification | https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html | **T1** | Same | Errors identified in text; applies when sync state is actionable. |
| 4 | IBM Carbon — Notification component (Usage) | https://carbondesignsystem.com/components/notification/usage/ | **T1** Vendor design system | Last updated 27 May 2026 (verified in-page) | Defines *Callout* = persistent, non-dismissable, loads with page. Exact match for our banner requirement. |
| 5 | Nielsen Norman Group — Indicators, Validations, and Notifications | https://www.nngroup.com/articles/indicators-validations-notifications/ | **T2** Recognized UX research firm | Article taxonomy framework, evergreen | Distinguishes *indicators* (persistent, attention-pull) from *notifications* (transient, system-initiated). |
| 6 | Material Design 3 — Color Roles | https://m3.material.io/styles/color/roles | **T1** Vendor design system | 2024–2026 active | M3 ships `error` role only; no semantic "warning". Teams typically extend with `tertiary` or custom warning role with manually-verified contrast. |
| 7 | Salesforce SLDS 2 — Notifications & color tokens | https://www.lightningdesignsystem.com/2e1ef9b39/p/82c52e-notifications | **T1** Vendor design system | SLDS 2 GA 2025 | Provides `--slds-g-color-warning-*` semantic tokens; orange family ~#FE9339 base. |
| 8 | EUR-Lex / GDPR — Article 5(1)(c) Data Minimisation | https://gdpr-info.eu/art-5-gdpr/ | **T1** Regulation | In force | "Adequate, relevant and limited to what is necessary." Operational dashboards must not expose data subject details when metadata suffices. |
| 9 | W3C WAI-ARIA 1.2 — `aria-live` | https://www.w3.org/TR/wai-aria-1.2/#aria-live | **T1** | Current | `polite` vs `assertive` semantics — assertive interrupts; reserve for "user must act now". |

## Cross-reference notes
- WCAG 4.1.3 explicitly flags using `role="alert"` / `aria-live="assertive"` on non-time-sensitive content as a **failure** (advisory technique). This rules out making every stale banner assertive.
- Carbon's Callout (T1) and NN/g's "indicator" taxonomy (T2) **agree**: persistent non-dismissable affordance is the right primitive for "data the user must act on but is not a transient event".
- No T3/T4 sources used.
