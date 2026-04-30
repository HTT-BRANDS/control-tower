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

- **Project board** — <https://github.com/orgs/htt-brands/projects> (pinned board: Control Tower / Azure Governance during cutover)
- **Repository** — <https://github.com/htt-brands/azure-governance-platform> _(current; target slug `control-tower` is tracked by bd `0dsr`)_
- **Staging app** — <https://app-governance-staging-xnczpwyv.azurewebsites.net>
- **Continuity status** — [operations/continuity-status.html](operations/continuity-status.html)

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
