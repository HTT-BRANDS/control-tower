# Production Readiness Plan — to 100% (ops team go-live)

**Owner:** Tyler + Richard (`code-puppy-1725d8`)
**Created:** 2026-06-04 (live audit + planning-agent)
**Goal:** Take HTT Control Tower from *release-blocked, stale data, ops-not-enabled*
to a validated **go-live where the HTT operations team uses it daily.**

> **Source of truth for *work* is the bd database.** This doc is the *sequenced
> narrative*; each step links to a bd issue. `STATE.md` is the live "where are
> we right now" snapshot. When this doc and an older `PHASE_*`/`FINAL_*` doc
> disagree, this doc + bd win.

---

## Audited ground truth (2026-06-04, live)

- Prod `/health` = `healthy / v2.5.0 / production`. Staging + prod App Services
  exist; dev does not (not a go-live blocker).
- **`judge.py --env production` = 25/27 — RELEASE BLOCKED.** Pillars: Security
  7/7, Design 1/1, Sync 2/2, Infra 3/3, Process 4/4, **Health 3/4** (the fail).
  (A 2nd local "fail", P5.7 role-enum, is a false negative — the audit shell
  lacked `fastapi`; it passes in CI.)
- **#1 blocker — data freshness (`ct-cne`, P1):** the 4 CORE tenants
  (HTT/BCC/FN/TLL) are `stale=true` — prod data is >24h old. `diagnose_sync`
  shows data *complete* but the scheduler hasn't completed a recent cycle.
- **Root cause (verified in code):** `app/core/scheduler.py` is an in-process
  `AsyncIOScheduler` started in the FastAPI lifespan with
  `misfire_grace_time=300`. An App Service worker unload / instance recycle /
  idle-without-Always-On stops it firing and **skips** missed runs — with no
  alarm, dashboards rot invisibly. → `ct-ar3` (permanent fix) + `ct-vuv` (alert).
- **DCE:** the 05-28 RBAC fix landed (DCE now `stale=false` for present
  domains) but still **missing `resources` + `compliance`** (2/4) → `ct-4if`.
- **Ops readiness is the real long pole:** `OPERATIONAL_RUNBOOK.md` is stale
  (v1.8.1, 2026-03-31, lists *puppy agents* as emergency contacts, no
  sync-recovery section); the `FULL_SEND_CRITERIA.md` operational/team
  checklists are almost entirely unchecked and weren't in bd until now.

---

## Definition of Done = ops team is live

Everything below true → Tyler hands the keys. Everything *not* listed here is
the acceptable **post-go-live tail**.

1. **`judge.py --env production` = 27/27**, holding for ≥1 *scheduled* (not
   manual) sync cycle. *(`ct-cne` + `ct-ar3`)*
2. **`/healthz/data` `any_stale=false` for all 4 CORE tenants**, AND the
   **freshness alert proven to fire** so a future stall is visible. *(`ct-vuv`)*
3. **Release tagged & deployed** at 27/27.
4. **Ops users provisioned & logging in at correct tiers.** *(`ct-hvv`)*
5. **Current runbook + onboarding guide exist and were team-reviewed.**
   *(`ct-6su`, `ct-bmq`)*
6. **Monitoring access granted + alerts wired to ops channel + escalation/
   on-call/incident plan named.** *(`ct-8by`, `ct-8jt`, `ct-vuv`, `ct-o1w`)*
7. **Rollback tested on staging.** *(`ct-c60`)*
8. **Signed go-live declaration.** *(`ct-71r`)*

**Outside the gate (post-go-live tail):** DCE completeness (`ct-4if`, document
a waiver if RBAC lags), prod UAMI cutover + secret decommission (`ct-f9p.3`),
external cred revocation (`ct-18z`), Q3 DR test (`uchp`), audit-log archive
(`m4xw`), Swagger a11y (`ct-8zr` — never, accepted), docs archival (`ct-ana`),
dev App Service (not needed).

---

## Phases (ordered by dependency)

### Phase 0 — Make data trustworthy & unblock release · **CRITICAL PATH**
*Exit: judge 27/27, `any_stale=false` on CORE, and a permanent guard exists.*

| Step | bd | Owner | Action / validation |
|------|----|-------|---------------------|
| 0.1 Recover the stall | `ct-cne` | pairing | Run `scripts/manual_sync.py` on prod → `diagnose_sync.py`.  when `any_stale=false`. |
| 0.2 Root-cause the stall | `ct-cne` | Richard+Tyler | App Service / App Insights logs for the window; confirm unload vs recycle vs swallowed exception.  written root-cause note on issue. |
| 0.3 Permanent fix | `ct-ar3` | pairing | Always On=true (prod+staging) and/or heartbeat watchdog + stop swallowing fatal sync errors.  idle/restart → scheduled cycle still completes. |
| 0.4 Freshness alert | `ct-vuv` | pairing | Azure Monitor/webtest on `/healthz/data` → ops channel.  trip stale → alert fires. |
| 0.5 Prove P5.7 CI-green | — | Richard | Re-run judge in CI / venv with `fastapi`.  27/27; note false-negative in STATE.md. |

### Phase 1 — Cut the release · **CRITICAL PATH** (gated by Phase 0)
*Exit: tagged/deployed release at 27/27 holding ≥1 scheduled cycle.*

| Step | bd | Owner | Action / validation |
|------|----|-------|---------------------|
| 1.1 Soak verification | `ct-cne` | Richard | Let the *scheduled* cycle run once post-fix; re-diagnose.  `any_stale=false` after scheduler-driven cycle (proves 0.3). |
| 1.2 Release PR + tag | — | Richard PR / Tyler merge | PR through branch protection, squash-merge, tag `v2.5.x`.  prod judge 27/27 on tag. |
| 1.3 Close `ct-cne` | `ct-cne` | Richard |  closed with evidence. |

### Phase 2 — Data completeness · *parallelizable after Phase 1*
*Exit: DCE 4/4 OR documented go-live waiver.*

| Step | bd | Owner | Action / validation |
|------|----|-------|---------------------|
| 2.1 DCE resources+compliance | `ct-4if` | pairing | Grant/verify DCE reader scope; sync; diagnose.  `diagnose_sync` DCE `missing=[]`. RBAC lag → documented waiver, not a blocker. |

### Phase 3 — Security & resilience hardening · *mostly post-go-live tail*
*Exit: staging UAMI live, DR passed, secrets-of-record authored.*

| Step | bd | Owner | Notes |
|------|----|-------|-------|
| 3.1 SECRETS_OF_RECORD.md | `azure-governance-platform-9lfn` | **Tyler only** | DR/legal provenance; recommended before go-live, parallelizable. |
| 3.2 UAMI cutover | `ct-f9p` / `.2` / `.3` | pairing | Staging cutover OK pre-go-live; **prod cutover + secret decommission (`ct-f9p.3`) = post-go-live tail** (don't destabilize fresh sync). |
| 3.3 Revoke external creds | `ct-18z` | Tyler | Cloudflare + Cloudways consoles. Tail. |
| 3.4 Q3 DR test | `uchp` | pairing | PITR + redeploy + KV recover. Tail (rollback sub-portion pulled forward → `ct-c60`). |
| 3.5 Audit-log archive | `m4xw` | Richard | Tail. |
| 3.6 Swagger a11y | `ct-8zr` | — | **DO NOT FIX** — accepted vendored limitation, tracking only. |

### Phase 4 — Ops team enablement · **CRITICAL PATH for go-live**
*Exit: every FULL_SEND operational/team box checked or explicitly waived.*

| Step | bd | Owner | Action / validation |
|------|----|-------|---------------------|
| 4.1 Provision ops users | `ct-hvv` | pairing | 4 tiers via `setup_admin.py`.  one user per tier logs in, least-privilege. |
| 4.2 Refresh runbook | `ct-6su` | Richard→Tyler | Real contacts + sync-recovery section.  ops dry-runs daily check. |
| 4.3 Monitoring access | `ct-8by` | Tyler | Azure RBAC.  ops opens dashboards unaided. |
| 4.4 Alert thresholds | `ct-8jt` | pairing | Availability/error/latency.  test-fire each. |
| 4.5 Escalation/on-call/incident | `ct-o1w` | Tyler+Richard | Named humans + rotation + sev matrix. |
| 4.6 Rollback tested (staging) | `ct-c60` | pairing | Slot-swap end-to-end.  swap + verify passes. |
| 4.7 Onboarding guide | `ct-bmq` | Richard→Tyler | Task-oriented.  ops completes 3 tasks unaided. |
| 4.8 Training session | `ct-dxb` | Tyler |  attendance + sign-off. |
| 4.9 Docs consolidation | `ct-ana` | Richard | Archive sprawl → `docs/archive/`.  one authoritative set. |

### Phase 5 — Go-live handoff · **CRITICAL PATH terminus**

| Step | bd | Owner | Action / validation |
|------|----|-------|---------------------|
| 5.1 Full Send declaration | `ct-71r` | **Tyler signs** | Fill `FULL_SEND_CRITERIA.md` template with real results + DCE waiver + tail.  signed, ops notified live. |

---

## Critical path vs parallelizable

- **Critical path (serial):**
  `0.1 → 0.2 → 0.3 → 0.4 → 1.1 → 1.2 → 4.1 → 4.2/4.6 → 5.1`.
- **Parallel once Phase 1 lands:** Phase 2 (DCE), Phase 3 (staging UAMI /
  SECRETS_OF_RECORD / DR), and the *documentation* halves of 4.2/4.5/4.7/4.9.
- **Throughput limiter = Tyler-human items** (RBAC grants, UAMI, secret
  decommission, DR, SECRETS_OF_RECORD, training, sign-off). Richard pre-stages
  every script/doc/PR so Tyler's actions are minutes, not hours; batch them.
- **Longest realistic pole = Phase 4 ops-enablement** (human scheduling), not code.

## Key risks

- **Manual sync (0.1) masks the real bug (0.3):** gate the `ct-cne` close on a
  *scheduled* cycle (1.1) + the freshness alert (0.4), never the manual kick.
- **Prod UAMI cutover during go-live week** risks destabilizing fresh sync →
  keep `ct-f9p.3` in the tail; only staging UAMI before go-live.
- **DCE perceived as "not ready"** → explicit documented waiver; don't let the
  newest tenant's 2-domain gap hold the other four hostage.

## Alternatives considered

1. **Externalize the scheduler** (WebJob / Logic App / Container Job hitting an
   internal sync endpoint) — durable fix if 0.2 shows structural recycle/idle;
   otherwise Always-On + watchdog suffices now, externalize as a P3 follow-up.
2. **Soft go-live (Viewer-only first)**, promote tiers after a 1-week soak —
   good hedge if freshness stability is borderline after Phase 1.
3. **Defer DCE entirely** with a waiver — recommended over blocking on it.

---

## bd issue map (filed 2026-06-04)

| bd | P | Phase | Title |
|----|---|-------|-------|
| `ct-cne` | P1 | 0/1 | core-4 freshness stall *(the release blocker)* |
| `ct-ar3` | P1 | 0.3 | scheduler permanent fix (Always On + watchdog) — *blocks `ct-cne`* |
| `ct-vuv` | P1 | 0.4 | data-freshness alert → ops channel |
| `ct-4if` | P2 | 2.1 | DCE resources+compliance completeness |
| `ct-hvv` | P1 | 4.1 | provision ops users into 4 tiers |
| `ct-6su` | P1 | 4.2 | refresh OPERATIONAL_RUNBOOK.md + sync-recovery |
| `ct-bmq` | P1 | 4.7 | ops onboarding guide |
| `ct-c60` | P1 | 4.6 | test slot-swap rollback on staging |
| `ct-8by` | P2 | 4.3 | monitoring dashboard access |
| `ct-8jt` | P2 | 4.4 | alert thresholds (availability/error/latency) |
| `ct-o1w` | P2 | 4.5 | escalation + on-call + incident-response |
| `ct-dxb` | P2 | 4.8 | ops training session |
| `ct-ana` | P3 | 4.9 | docs consolidation/archival |
| `ct-71r` | P1 | 5.1 | **Full Send / go-live declaration** — *blocked by the DoD set* |

**Pre-existing (unchanged):** `azure-governance-platform-9lfn` (SECRETS_OF_RECORD),
`uchp` (DR test), `ct-f9p`/`.2`/`.3` (UAMI), `ct-18z` (cred revoke),
`m4xw` (audit archive), `ct-8zr` (Swagger — tracking only).
