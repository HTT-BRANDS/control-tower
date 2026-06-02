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

## Live release-gate state

> **Single source of truth: [`STATE.md`](https://github.com/HTT-BRANDS/control-tower/blob/main/STATE.md)** — its
> "Recent" block is refreshed after every major session. This page no longer
> duplicates a point-in-time snapshot (that's what kept drifting out of date).

**As of 2026-06-02 (live-verified):** Production `/health` -> `healthy / 2.5.0 / production`;
`/healthz/data` `any_stale=true`. Core-domain coverage: HTT / BCC / FN / TLL all 4/4,
**DCE 2/4** (resources + compliance still absent — the standing freshness gap).
No open P0/P1 incidents (ct-y47, ct-38g, ct-1m0 all closed). See STATE.md +
[`STATUS.md`](https://github.com/HTT-BRANDS/control-tower/blob/main/STATUS.md) for detail.

## What's on this page

- [Control Tower status](status.md) — current CI/backup/rebrand/continuity notes plus audit output when available.
- [Continuity status](operations/continuity-status.html) — DR, backup, bus-factor, and blocked validation state.
- [Riverside timeline](riverside-timeline.html) — countdown to **July 8, 2026** and per-domain maturity.
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
