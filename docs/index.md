---
title: HTT Control Tower
---

# HTT Control Tower

HTT Control Tower is HTT's internal multi-brand governance hub for cost,
identity, compliance, resources, lifecycle, and evidence workflows. Riverside is
one evidence consumer, not the platform identity. This page is the self-updating
project hub: every push to `main` refreshes GitHub Pages, status docs, and
topology assets.

_Naming note: Control Tower is HTT's internal name for this platform. It is
unrelated to AWS Control Tower._

## Live links

- **Production app** — <https://app-governance-prod.azurewebsites.net> · `/health` ✅
- **Staging app** — <https://app-governance-staging-xnczpwyv.azurewebsites.net> · `/health` ✅ (allow 30–90s cold-start on first hit)
- **Repository** — <https://github.com/htt-brands/control-tower>
- **Project board** — <https://github.com/orgs/htt-brands/projects>
- **Continuity status** — [operations/continuity-status.html](operations/continuity-status.html)
- **Live single-glance status** — [STATUS.md on GitHub](https://github.com/HTT-BRANDS/control-tower/blob/main/STATUS.md) · [TEST_PLAYBOOK.md](https://github.com/HTT-BRANDS/control-tower/blob/main/TEST_PLAYBOOK.md)

## Live release-gate state (verified 2026-05-28, end of session)

> 🟡 → 🟢 **Production at 92%, expected to hit 100% next sync cycle.** Today's session shipped
> the live DCE RBAC fix (root-cause: stale `app_id` in `config/tenants.yaml`). 4/5 tenants
> already healthy on all four domains; DCE resources + compliance will populate within the
> next sync window.

| Surface | Status |
|---|---|
| Production image | `ghcr.io/htt-brands/control-tower` (PR #63 deployed 2026-05-27, OIDC federation live) |
| Production `/health` | ✅ 200 — `healthy / 2.5.0 / production` |
| Production judge score | **11/12 (92%)** — only P1.3 DCE freshness gating full pass; fix shipped, awaiting sync verify |
| Production data freshness | ✅ HTT / BCC / FN / TLL fresh on all 4 domains. ⏳ DCE: costs+identity ✅, resources+compliance pending next sync |
| Staging `/health` | ✅ 200 — `healthy / 2.5.0 / staging` |
| Auto-rollback | ✅ field-tested 2026-05-27 (USE_OIDC_FEDERATION=false rollback in 172s) |
| Bus-factor | 2 (Tyler + Dustin Boyd) |
| Bicep drift reconciliation (`xzt4`) | ✅ **CLOSED 2026-05-28** — all 12 child tasks done. Staging hardened; production apply intentionally deferred. |
| DCE RBAC fix (`ct-1m0`) | ✅ **shipped 2026-05-28** — Reader + Security Reader granted at root scope; awaiting sync verification |
| Manager role (`ct-2nk`) | ✅ **CLOSED 2026-05-28** — end-to-end (RBAC + service layer + dashboard + template) per ADR-0012 |
| Palette canon (`ct-yb1`) | ✅ **CLOSED 2026-05-28** — burgundy/deep red is canonical |
| Open P0 / P1 | `ct-1m0` (P0, verify after sync), `9lfn` (P1, SECRETS_OF_RECORD inventory), several P1 sync follow-ups pending sync-cycle verification |

## What's on this page

- [Control Tower status](status.md) — current CI/backup/rebrand/continuity notes plus audit output when available.
- [Continuity status](operations/continuity-status.html) — DR, backup, bus-factor, and blocked validation state.
- [Riverside timeline](riverside-timeline.md) — countdown to **July 8, 2026** and per-domain maturity.
- Architecture diagram — embedded below (regenerated from Azure Resource Graph on every push).

## Architecture

![Architecture overview diagram](diagrams/architecture.svg)

_Source: [`docs/diagrams/architecture.mmd`](diagrams/architecture.mmd)_

## Azure topology (live)

The live topology diagram is generated from Azure Resource Graph via OIDC and
updated on every push. See [`docs/diagrams/topology.mmd`](diagrams/topology.mmd).

## How this page updates

| Trigger | Updates |
|---|---|
| PR opened / closed / labeled | Project v2 item fields (Status, Persona, Tenant, Priority, Riverside ID) |
| Push to `main` | `topology.mmd` regenerated via Resource Graph |
| Weekly (Mondays 07:00 UTC) | `topology.svg` + `topology.drawio` refresh |
| Push to `main` touching `docs/**` or `scripts/audit_output.json` | This page rebuilds; `status.md` re-rendered from the latest audit |
