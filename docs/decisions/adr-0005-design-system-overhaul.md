# ADR-0005 — Design System Overhaul: Adopt the HTT `ds-template` Standard

**Status:** 🟡 Proposed · Draft (2026-04-17)
**Authors:** Richard (agent `code-puppy-bf0510`) · Tyler Granlund
**Supersedes:** current bespoke `theme.css` + DaisyUI approach

---

## TL;DR

The governance-platform UI looks and feels inconsistent with every other HTT
app. Root cause: **we went off-standard** — Tailwind v4 + DaisyUI + five
overlapping CSS files (~237KB of CSS), while every sibling app uses
Tailwind v3 + the `ds-template` component library documented in
`~/dev/master-hub-infra/`.

**Action:** adopt the `Domain-Intelligence` pattern — which is the proven,
FastAPI-compatible expression of the master-hub-infra design system — as
the new baseline for governance-platform.

---

## 1. Evidence — The HTT Design System IS Real and Documented

All sourced from `~/dev/master-hub-infra/`:

| Artifact | Lines | Purpose |
|---|---:|---|
| `03-DESIGN-SYSTEM.md` | 405 | Canonical written spec |
| `Design-System-Temp/DESIGN_SYSTEM.md` | 775 | Expanded living spec (v2.0, 2026-02-09) |
| `src/components/ds-template/tokens.ts` | 157 | Copy-paste source of truth (CSS vars + Tailwind colors + recipes) |
| `src/components/ds-template/*.tsx` | — | 10 reference components: Alert, Button, Card, DataTable, FormField, Modal, PageShell, Primitives, StatCard, Tabs, Toolbar |
| `src/index.css` | 94 | Runtime CSS layer (tokens + utilities + WCAG focus rules) |
| `tailwind.config.ts` | — | Brand/tenant color extend config |

### Brand tokens (authoritative):

```css
--htt-primary:       #500711;  /* Burgundy */
--htt-primary-light: #6B1A24;
--htt-primary-dark:  #3A0509;
--htt-secondary:     #BB86FC;  /* Soft purple */
--htt-accent:        #FFC957;  /* Gold */

/* Tenant scales */
--tenant-htt:        #500711;
--tenant-bishops:    #c2410c;  /* Orange */
--tenant-lashlounge: #7c3aed;  /* Purple */
--tenant-frenchies:  #2563eb;  /* Blue */
```

Typography: **Inter**, weights 400/500/600, body `text-sm` (14px).
Radii: cards `rounded-xl` (12px), buttons `rounded-lg` (8px).
Dark mode via `.dark` class toggle.

---

## 2. What Sibling Apps Actually Do

| App | Stack | Uses ds-template? |
|---|---|---|
| `master-hub-infra` | React 18 + TS + Tailwind v3 + Vite | ✅ (defines it) |
| `microsoft-group-management` | React 18 + Tailwind v3 + Vite | ✅ |
| `control-tower` | React + Tailwind v3 | ✅ |
| **`Domain-Intelligence`** | **FastAPI + Jinja2 + HTMX + Tailwind v3 + `design-tokens.css`** | ✅ **(server-rendered port — our closest match)** |
| **`azure-governance-platform`** (this repo) | **FastAPI + Jinja2 + HTMX + Alpine + Tailwind v4 + DaisyUI** | **❌ (off-standard)** |

**Domain-Intelligence is the blueprint.** It proves the `ds-template`
design system survives the jump from React SPA to server-rendered
Jinja/HTMX without losing fidelity.

---

## 3. What We Have Today (the "icky")

```
app/static/css/theme.css         185,232 bytes   6,358 lines   ← Tailwind v4 + DaisyUI
app/static/css/theme.src.css      21,272 bytes     684 lines
app/static/css/riverside.css      22,092 bytes   1,046 lines
app/static/css/ui-polish.css       3,729 bytes     102 lines
app/static/css/accessibility.css   4,475 bytes     144 lines
                                 ────────────   ──────────
                                 236,800 bytes   8,334 lines
```

**Diagnosis:**
1. **Tailwind v4 + DaisyUI is a singular choice** — no other HTT app uses this. DaisyUI injects its own design opinions that fight the HTT brand at every turn.
2. **Five CSS files with overlapping rules** = unclear cascade = inconsistent look across pages.
3. The brand hex `#500711` is defined correctly, but buried under DaisyUI components.
4. Jinja components are **feature-specific** (`cost_summary_card.html`, `sync_status.html`) rather than **design-system primitives** (`Button`, `Card`, `StatCard`, `Alert`). Every feature reinvents layout.
5. No `PageShell` / `Toolbar` primitives → each page chrome is bespoke.

---

## 4. The Target — Domain-Intelligence Pattern, Ported

### New CSS architecture (3 files, ~35KB total target):

```
app/static/css/
├── design-tokens.css       ~750 lines   ← copy from Domain-Intelligence, adjust for our needs
├── tailwind-output.css     ~20KB        ← built via Tailwind Standalone CLI
└── (delete all others)
```

### New `base.html` head:

```html
<link rel="stylesheet" href="/static/css/design-tokens.css">
<link rel="stylesheet" href="/static/css/tailwind-output.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
```

### New Jinja macros (`app/templates/macros/ds.html`):

Port the 10 ds-template primitives to Jinja macros:
- `{{ ds.button(label, variant='primary') }}`
- `{{ ds.card(title, body) }}`
- `{{ ds.stat_card(label, value, trend) }}`
- `{{ ds.data_table(columns, rows) }}`
- `{{ ds.alert(message, severity='info') }}`
- `{{ ds.page_shell(title, subtitle, breadcrumb) }}`
- `{{ ds.toolbar(actions) }}`
- `{{ ds.form_field(label, input) }}`
- `{{ ds.modal(id, title, body) }}`
- `{{ ds.tabs(tabs) }}`

Feature-specific components become **compositions** of primitives instead of reinventing them.

---

## 5. Scope + Phasing

This is **2–3 weeks of focused work** — NOT a single sitting. Phase it:

### Phase 1 — Foundation (1–2 days)
- [ ] Copy `design-tokens.css` from Domain-Intelligence, adjust tenant list
- [ ] Set up Tailwind Standalone CLI (no Node runtime in prod)
- [ ] Rewrite `base.html` to load new CSS layer
- [ ] Delete `theme.css`, `theme.src.css`, `ui-polish.css`, `accessibility.css`
- [ ] Verify: existing pages still render (may look broken — that's fine at this stage)

### Phase 2 — Primitives (2–3 days)
- [ ] Build `app/templates/macros/ds.html` with all 10 ds-template macros
- [ ] Each macro visually matches its React counterpart from master-hub-infra
- [ ] Write a `/design-system` route that renders all primitives for visual QA

### Phase 3 — Page Migration (1 week)
- [ ] Migrate pages in order of visibility: dashboard → costs → compliance → resources → identity → topology → sync_dashboard → admin_dashboard → riverside/_dashboard → dmarc_dashboard → preflight → privacy
- [ ] Each migration is one PR; each replaces bespoke markup with ds macros
- [ ] Delete `riverside.css` (riverside-specific styling absorbed into tenant token system)

### Phase 4 — Polish + Docs (2–3 days)
- [ ] Dark mode parity (Domain-Intelligence has a solid `SWA Dark Glassmorphism` surface system we can adopt)
- [ ] WCAG 2.2 AA audit (the tokens already include `--min-target-size: 2.75rem` for AAA)
- [ ] Update `03-DESIGN-SYSTEM.md` equivalent for this repo
- [ ] Screenshot diff vs. sister apps to prove consistency

---

## 6. Risks + Open Questions

1. **Tailwind v4 → v3 downgrade**: any templates using v4-only syntax need rework. Scan needed.
2. **DaisyUI removal**: any `btn-primary`, `card`, `modal-box`, etc. DaisyUI classes will break. Need a migration map.
3. **Alpine.js** — sibling apps don't use Alpine. Do we keep it or move to HTMX-only? (Domain-Intelligence uses HTMX + Idiomorph for polling, no Alpine.) **Probably remove Alpine**.
4. **Chart.js** styling: charts currently use CSS vars — Domain-Intelligence does the same with the dual `--brand-primary / --brand-primary-rgb` pattern. Need to adopt that.
5. **Multi-tenant branding**: we dynamically swap brand colors per tenant. The ds-template supports this via `--tenant-*` tokens already.

---

## 7. Decision

**Recommended:** APPROVE this overhaul. Execute in phases above.

**Alternative considered:** incremental cleanup of the existing CSS without
switching stacks. **Rejected** because: (a) DaisyUI opinions can't be
"cleaned up" out — they're baked into every `.btn`, `.card`, `.modal`
class used on every page; (b) we'd still drift from the sibling apps over
time without a shared primitives layer.

---

## 8. Reference Files (for the person executing this)

**Copy-paste-ready sources in `~/dev/`:**

1. `master-hub-infra/03-DESIGN-SYSTEM.md` — start here for the full spec
2. `master-hub-infra/Design-System-Temp/DESIGN_SYSTEM.md` — expanded v2.0
3. `master-hub-infra/src/components/ds-template/tokens.ts` — token export
4. `master-hub-infra/src/components/ds-template/*.tsx` — React component references (for Jinja porting)
5. `Domain-Intelligence/app/static/css/design-tokens.css` — **direct copy target for Phase 1**
6. `Domain-Intelligence/app/templates/base.html` — **direct template target for Phase 1**
7. `Domain-Intelligence/app/templates/macros/` — look here for existing Jinja macro patterns
