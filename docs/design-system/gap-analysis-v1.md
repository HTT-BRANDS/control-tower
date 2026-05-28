# Design System Gap Analysis — v1

**Source spec:** `issue-66-design-system-spec-v1.pdf` (8 pages, Miro export)
**Analyzed against:** `app/static/css/design-tokens.css`, `app/models/tenant.py`, `app/templates/`, current architecture
**Date:** 2026-05-28
**Analyst:** Richard (code-puppy-5deed9)

---

## 🚨 Critical gaps (file as P0/P1)

### G1 — Color palette mismatch (P0)

The spec and the code disagree on the **primary brand color**.

| Token | Spec (PDF p.1) | Code (`design-tokens.css`) | Match? |
|-------|----------------|----------------------------|--------|
| Primary | **HTT Blue `#0046FF`** | `#500711` (deep red) | ❌ |
| Primary Dark | `#0836B8` | `#3A0509` | ❌ |
| Primary Light | `#E6EFFF` | `#6B1A24` | ❌ |
| Secondary | Teal `#00B3A4` | `#BB86FC` (purple) | ❌ |
| Amber Accent | `#FFB000` | `#FFC957` | 🟡 close, not exact |
| Success | `#1A7F37` | `#0369A1` (blue, not green) | ❌ |
| Warning | `#B54708` | `#D97706` | 🟡 close |
| Error | `#B42318` | `#C2410C` | 🟡 close |
| Info | `#0B6BBD` | `#3B82F6` | 🟡 close |

**Question for Tyler:** is the PDF the new direction (re-brand to blue) or does the PDF need to be re-exported to match the current dark-red `#500711` brand?

**Suggested resolution path:** decide which is canonical, then either (a) update tokens.css + tailwind + brand themes, or (b) regenerate the Miro spec.

### G2 — Missing "Manager" role (P1)

PDF page 7 access-tier diagram defines **4 user tiers**: Admin, Manager, Operator, Viewer.

Code (`app/models/tenant.py:89`) only has **3**: `viewer`, `operator`, `admin`.

- Manager workflow in PDF page 8: Team dashboard → metrics → manage team members → approve requests → reports
- No `manager` role exists in `UserTenant.role` enum
- No `/dashboard/team` route exists for manager-scoped view

**Suggested resolution:** add `manager` to the role enum + scaffold the team-dashboard route, OR collapse Manager into a permission set under Admin and update the spec.

---

## 🟡 Aspirational architecture (P2 — clarify intent)

PDF page 7 shows components that **don't exist in the current monolith**:

| Component in diagram | Current reality |
|----------------------|-----------------|
| API Gateway | None — FastAPI handles everything |
| Auth service (separate) | Inlined into FastAPI middleware |
| Cache layer | No Redis/Memcached configured |
| Message queue | No queue — sync jobs run in-process via APScheduler |
| File storage (separate) | App Service ephemeral disk only |
| Audit logging (separate) | Application Insights logs only |

**Suggested resolution:** label the diagram as "Target Architecture (Q3 2026+)" and create a "Current Architecture" companion diagram. Otherwise new contributors will hunt for components that don't exist.

This aligns with existing bd issue **ct-f9p** (long-term UAMI migration).

---

## 🟢 Aligned (no action)

| Spec | Code | Notes |
|------|------|-------|
| Inter font family | `design-tokens.css` uses `'Inter', ui-sans-serif, system-ui` ✅ | Match |
| 8px spacing base | tailwind default ✅ | Match |
| Multi-brand theming via `[data-brand=...]` | `app/core/css_generator.py` does exactly this ✅ | Match |
| ADR-0005 (design-system-overhaul) | exists | References this spec |
| WCAG 2.1 AA baseline | `tests/unit/test_accessibility.py` enforces | Match |
| Rate limiting / focus ring / security headers | Production judge confirms all green | Match |

---

## 🟠 Missing tooling / process gaps (P2)

PDF section 7 (Implementation Standards) requires:

- [ ] **TypeScript** — repo is Python (FastAPI + Jinja). TS only used in `static/js`. *Decide:* is this a new SPA direction or does "TypeScript" mean only `static/js` modules?
- [ ] **Unit tests AND a11y tests required** — we have unit tests, but no formal a11y harness like `pa11y` or `axe-core` running in CI
- [ ] **Story-based docs** — no Storybook / Histoire. Templates live in `app/templates/components/` with no rendered catalog.
- [ ] **Component changelog** — `CHANGELOG.md` exists but doesn't separately track component changes
- [ ] **SemVer for components** — not currently versioned independently of app

PDF section 8 (Governance):

- [ ] **Design owner / Code owner / a11y lead / Docs maintainer** — no `CODEOWNERS` entries for the design system specifically
- [ ] **RFC workflow** — no `docs/rfcs/` directory or template
- [ ] **Biweekly review cadence** — not on any calendar / not in docs
- [ ] **Monthly maintenance audits** — not scheduled

---

## Recommended bd issues to file

| ID (proposed) | Title | Priority |
|---------------|-------|----------|
| design-system-G1 | Resolve color-palette canon: spec says HTT Blue, code has deep red | **P0** |
| design-system-G2 | Add Manager role + team dashboard OR remove from spec | P1 |
| design-system-G3 | Label target architecture diagram + add "current" companion | P2 |
| design-system-G4 | Add automated a11y CI gate (axe-core or pa11y) | P2 |
| design-system-G5 | Decide on Storybook / story-based component catalog | P2 |
| design-system-G6 | Establish design-system CODEOWNERS + RFC workflow | P3 |

---

## What I deliberately did NOT do

Following YAGNI / Tyler-decides-priority discipline:

- ❌ Did **not** change `design-tokens.css` colors — Tyler hasn't told me which is canonical
- ❌ Did **not** add a Manager role — needs product decision
- ❌ Did **not** scaffold Storybook — large scope, separate decision
- ❌ Did **not** "fix" the architecture diagram — it's a Miro export, edit happens upstream

This file is a **finding report**, not an implementation. Decisions get made in bd issues / on the Miro board.
