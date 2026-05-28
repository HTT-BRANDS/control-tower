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

## Live release-gate state (verified 2026-05-28)

> ⚠️ **Active production incident:** Customer-tenant Graph/ARM sync is stale for BCC/FN/DCE/TLL.
> PR #63 deployed successfully (image now `sha256:5f550ae5…`) but the `USE_OIDC_FEDERATION=false`
> switchover requires a follow-up prerequisite (`AZURE_AD_CLIENT_SECRET` configured as a Key Vault
> reference on App Service) before it can be safely flipped. See `bd show ct-y47` + `bd show ct-38g`.
> Public `/health` is still 200 because the lenient health gate doesn't detect the per-tenant
> staleness — that is itself a follow-up.

| Surface | Status |
|---|---|
| Production image | `ghcr.io/htt-brands/control-tower@sha256:5f550ae5…` (run [`26535827775`](https://github.com/HTT-BRANDS/control-tower/actions/runs/26535827775), 2026-05-27 23:43 UTC, PR #63 merge `96611ec`) |
| Production `/health` | ✅ 200 — `healthy / 2.5.0 / production` (re-verified 2026-05-28 00:30 UTC) |
| Production data freshness | ⚠️ HTT fresh; BCC/FN/DCE/TLL **stale** since 2026-05-20 (active ct-y47 incident) |
| Staging `/health` | ✅ 200 — `healthy / 2.5.0 / staging` |
| v2.5.1 internal verdict | Was `PASS-pending-9lfn` (April 30); **superseded by ct-y47 incident** as the binding v2.5.1 blocker |
| Auto-rollback | ✅ field-tested via bd `1vui` cycle; second field-test 2026-05-27 (USE_OIDC_FEDERATION=false rollback in 172s) |
| Bus-factor | 1 → 2 (Tyler + Dustin Boyd, bd `213e` closed) |
| Bicep drift reconciliation (`xzt4`) | All 12 child tasks closed; staging Bicep recovered + hardened. Production Bicep apply intentionally deferred. |
| Open P0 / P1 | `ct-y47` (P1, customer-tenant sync), `ct-38g` (P0, AZURE_AD_CLIENT_SECRET prereq), `9lfn` (P1, Tyler-only SECRETS_OF_RECORD inventory) |

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
