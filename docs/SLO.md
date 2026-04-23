# Service-Level Objectives (SLOs) — Azure Governance Platform

> **Status:** Accepted (initial commitment) · **Version:** 1.0 · **Date:** 2026-04-23
> **Owner:** Tyler Granlund · **Review cadence:** Quarterly

This document establishes the formal reliability commitments for the Azure
Governance Platform. Before this doc existed, uptime expectations were implicit
(defaulting to whatever Azure App Service's platform SLA happened to be) which
made it impossible to answer downstream questions like "do we need multi-region
deployment?" or "when do we upgrade to S1?" with a non-hand-wavy answer.

**Why this is a cost document as much as a reliability one:** every tier of
reliability costs money. The COST_MODEL_AND_SCALING.md Open Question #5 asks
*"What uptime guarantee do we promise customers?"* — the answer drives whether
we stay single-region (~$18/mo prod) or go multi-region (~$160/mo prod, 9×).
This doc closes that question.

---

## 1. Commitment summary

| Environment | Uptime SLO | Budget (mo) | Budget (yr) | Strategy |
|---|---|---|---|---|
| **Production** | **99.9%** (≤ 43m 12s downtime/mo, ≤ 8h 45m/yr) | ~$18 | ~$217 | Single-region on B1, accept deploy blips |
| **Staging** | "Best effort" (no SLO) | ~$13 | ~$152 | May be intentionally downed for testing |
| **Dev** | "Best effort" (no SLO) | ~$23 | ~$272 | Low-priority; can be paused between sprints |

**Headline:** We commit **99.9% uptime to production API consumers** — just
below the Azure App Service B1 platform SLA of 99.95%. The 0.05% buffer
absorbs our own operational risks (deploys, config pushes, planned restarts)
without burning the customer-facing budget.

---

## 2. Why 99.9% and not 99.95% / 99.99%?

| SLO | Allowed monthly downtime | Annualized | Who offers this | Marginal cost |
|---|---|---|---|---|
| 99.0% | 7h 18m | 3d 15h | — | — |
| **99.9%** ✅ | **43m 12s** | **8h 45m** | **Our commitment** | **~$0** (current setup) |
| 99.95% | 21m 36s | 4h 22m | Azure App Service B1 platform SLA | ~$0 IF deploys never fail |
| 99.99% | 4m 20s | 52m | AWS / Azure multi-AZ + geo-replicated DB | **+$105/mo** (S1 + SQL geo-replica) |
| 99.999% | 26s | 5m | Hyperscaler core services only | **+$400+/mo** (multi-region active-active) |

### 2.1 Rationale for 99.9%

**Commit one notch below what infrastructure gives us, for three reasons:**

1. **Deployment buffer.** Our deploys are direct image-pin on a single slot
   (not blue-green) and cause ~10 seconds of API unavailability. At 4
   deploys/month that's 40s of self-inflicted downtime — already 3% of the
   99.95% monthly budget. 99.9% gives us headroom for ~11 deploys/month before
   the SLO is at risk from deploys alone.

2. **Single-region reality.** Azure App Service B1 gives a 99.95% SLA only
   within a single region. A region-wide outage is a permitted SLA event but
   a customer-facing emergency. 99.9% implicitly accepts regional risk as
   part of our posture; 99.99%+ would require real multi-region.

3. **Current user count (~5).** At launch scale, an hour of downtime is
   annoying but not catastrophic. 99.9% gives us 45 minutes per month — that's
   roughly one "oh crap" event per month and still meets the SLO. This is
   calibrated to reality, not aspirational.

### 2.2 When to re-evaluate

Re-open this commitment when any of these fire:

- Customer contract language demands ≥ 99.95% (renegotiate or upgrade to S1+
  and multi-AZ)
- User count exceeds 50 concurrent active
- A single incident consumes > 50% of the monthly error budget two months
  running (systematic issue, not noise)
- Regulatory scope expands to SOX / HIPAA / FedRAMP (those frameworks have
  implicit uptime requirements)

---

## 3. SLIs (how we measure)

An SLO without measurement is a wish. The following SLIs are computed from
Application Insights + synthetic probes and published monthly.

### 3.1 Availability SLI

**Definition:** `(successful synthetic probes) / (total synthetic probes)`
measured over a rolling 30-day window against `/health`.

**Probe config** (from Bicep `modules/app-insights.bicep` + manual
availability tests):

| Attribute | Value |
|---|---|
| Probe endpoint | `https://app-governance-prod.azurewebsites.net/health` |
| Probe frequency | Every 5 minutes |
| Probe count per window | 8,640/mo (30 days × 288/day) |
| Success criteria | HTTP 200 within 30 seconds, response body contains `"status":"healthy"` |
| Failure criteria | Any non-200, timeout, DNS fail, or JSON body absent/wrong |
| Regions probed from | East US 2, Central US, West US 2 (3-way consensus) |
| Ticket-failure rule | 2 of 3 regions failing = real outage; 1 of 3 = possibly a probe issue |

**Budget at 99.9%:** 0.1% of 8,640 = **8.64 failed probes allowed per month**.

### 3.2 Latency SLI (informational, no SLO)

**Definition:** p95 response time at `/api/v1/health`.

Not an SLO yet because we don't have a performance baseline post-April 16
plan downsize. Once `mvxt` is root-caused and we have a stable cold-start
profile, latency-SLO follow-up.

Tracked for situational awareness:

| Target | Value |
|---|---|
| p50 | < 500ms (currently ~470ms per staging validation) |
| p95 | < 2.0s |
| p99 | < 5.0s |
| Cold-start (post-deploy) | < 90s (waived; tracked in `bd mvxt`) |

### 3.3 Data-freshness SLI (domain-specific)

The platform's core value is cross-tenant sync. Stale data is a correctness
failure even if the API is technically "up". We ship a dedicated SLI for
this, backed by `/healthz/data` which monitors 10 sync domains (see
INFRASTRUCTURE_END_TO_END §10).

**Definition:** `(domains with fresh data) / (total domains monitored)` where
"fresh" means updated within `settings.sync_stale_threshold_hours`.

**Target:** ≥ 95% domains fresh, computed hourly over a rolling 24-hour
window. This is an internal target, NOT a customer commitment — surfacing it
to customers invites gotcha disputes. Used internally to decide whether a
sync incident is material.

---

## 4. Error budget policy

**Monthly error budget** = 100% − SLO = 0.1% = **43m 12s of allowed downtime**.

Budget accounting rules:

| Event type | Counts against budget? |
|---|---|
| Synthetic probe failure (confirmed by 2/3 regions) | ✅ Yes |
| Single-region probe flake (1/3 regions) | ❌ No (probe issue) |
| Planned maintenance with ≥ 24h notice to stakeholders | ❌ No (excluded window) |
| Deploy-induced brownout up to 15s | ❌ No (within "planned" envelope, 4×/mo max) |
| Deploy-induced outage > 15s | ✅ Yes (this is where slot-based deploys earn their cost) |
| Azure regional outage | ✅ Yes (still affects customers) |
| Dependency outage (Entra ID, Azure SQL control-plane) | ✅ Yes (we own the uptime contract, not the dependency) |

### 4.1 Budget-exhaustion responses

| Budget remaining | Response |
|---|---|
| > 50% | Normal operations; any deploy cadence is fine |
| 25-50% | Yellow zone: hold non-critical deploys; investigate recent incidents |
| < 25% | Orange zone: only security-critical deploys; incident retro required |
| < 10% | Red zone: deploy freeze until start of next month OR post-mortem + exec sign-off |
| 0% (exhausted) | SLO breach: formal incident review, consider tier upgrade |

**Two-month consecutive breach** = automatic re-evaluation of tier (B1 → S1+)
and/or region strategy (single → multi-region). This is the unambiguous
signal to open COST_MODEL Open Question #5 for real money.

---

## 5. Exclusions (what doesn't count against SLO)

- **Staging and dev environments** — no SLO, intentional.
- **GitHub Pages docs site** — best-effort; Pages is its own platform SLA.
- **/docs and /openapi.json** — auth-gated in production; availability here
  matters to developers, not end users. Tracked informally.
- **Customer-side issues** — wrong tenant config, expired Entra ID tokens on
  the customer's side, etc. Captured in support tickets, not the SLO.
- **Planned maintenance windows** — announced ≥ 24h in advance via Teams +
  the banner in the app (feature not yet built; use Teams-only until banner
  lands as a separate bd).

---

## 6. What this doc unblocks

| Previously open question | Now answered |
|---|---|
| COST_MODEL §Q5 "What uptime guarantee do we promise?" | **99.9% — single-region B1 is adequate** |
| "Should we upgrade to S1 for slots + autoscale?" | Not required by SLO until deploys exceed ~11/mo or user-count > 50 |
| "Should we go multi-region?" | Not required by SLO. Re-open if contracts demand ≥ 99.95% |
| "How to decide incident severity?" | Error-budget consumption (§4.1) — objective, not vibes |
| `mvxt` cold-start priority | Does NOT breach uptime SLO (failed probes during cold-start are rare), but DOES breach data-freshness SLI. Priority stays P2. |

---

## 7. Change log

| Date | Change | Rationale |
|---|---|---|
| 2026-04-23 | Initial commitment at 99.9% uptime, 95% data-freshness | First formal SLO; derived from COST_MODEL Q5 |

---

## 8. References

- `docs/COST_MODEL_AND_SCALING.md` §5, §6 — cost/SKU implications of higher SLOs
- `INFRASTRUCTURE_END_TO_END.md` §7, §10 — observability + `/healthz/data` endpoint
- `core_stack.yaml` → `observability.health_endpoints` — the 3 health endpoints
- `bd mvxt` — cold-start investigation (affects data-freshness SLI, not uptime SLO)
