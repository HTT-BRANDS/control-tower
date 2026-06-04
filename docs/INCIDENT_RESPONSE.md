# HTT Control Tower - Incident Response & Escalation

**The single source of truth for "something's wrong - who do I call and how fast?"**
The runbook (`OPERATIONAL_RUNBOOK.md`) tells you *how to fix* things; this doc
tells you *who owns it, how urgent it is, and how to communicate*.

**Status:** structure drafted by Richard (bd `ct-o1w`). The `_TODO_` slots are
**Tyler's to fill** before go-live - real names, real channels, real rotation.

---

## 1. Contacts & roles (FILL BEFORE GO-LIVE)

<!-- TODO(ct-o1w): replace every _TODO_ with a real person + how to reach them. -->

| Role | Person | Reach via | Backup |
|------|--------|-----------|--------|
| **Incident Commander** (runs the incident) | _TODO_ | _TODO_ | _TODO_ |
| **Platform / on-call engineer** (does the fixing) | _TODO_ | _TODO_ | _TODO_ |
| **Operations owner** (ops-facing, comms) | _TODO_ | _TODO_ | _TODO_ |
| **Security** | _TODO_ | _TODO_ | _TODO_ |
| **Business owner** (Tyler) | _TODO_ | _TODO_ | - |

**Alert channel:** `_TODO_` (the Teams channel behind the `governance-alerts`
action group - see `scripts/add-teams-webhook-to-action-group.sh`).
**Incident bridge / war-room:** `_TODO_`.

### On-call rotation
<!-- TODO(ct-o1w): define the rotation (weekly? who's in it? how is it published?). -->
- Rotation cadence: `_TODO_ (e.g., weekly, Mon 09:00)`
- Roster: `_TODO_`
- Where it's published: `_TODO_ (e.g., Teams tab / calendar)`
- Until this is real, **all severities escalate to the Business owner.**

---

## 2. Severity matrix

| Sev | Definition | Examples | Ack | Resolve target | Who |
|-----|-----------|----------|-----|----------------|-----|
| **Sev 1 - Critical** | Platform down OR data untrustworthy for decisions | `/health` failing; **all/most tenants stale** (`any_stale:true`); auth broken | **15 min** | 4 h | On-call + IC, page immediately |
| **Sev 2 - Major** | Degraded but usable; a real risk if ignored | One tenant stale; scheduler `any_overdue:true` but data still fresh; p95 > 1s sustained | 1 h (business hrs) | 1 business day | On-call |
| **Sev 3 - Minor** | Cosmetic / low-impact / known-gap | Single optional domain missing (e.g., DCE resources, `ct-4if`); flaky non-blocking alert | Next business day | Backlog | Whoever picks it up |

> **"Untrustworthy data" is a Sev 1.** The whole point of Control Tower is
> trustworthy numbers; stale dashboards that *look* fine are worse than an
> obvious outage. This is the lesson of `ct-cne`.

---

## 3. The incident loop (every severity)

1. **Detect** - an alert fires (`governance-alerts`) or someone reports it.
2. **Declare** - state the severity in the alert channel. For Sev 1/2, name an
   **Incident Commander** (the IC coordinates; they don't have to be the fixer).
3. **Diagnose & mitigate** - follow the relevant `OPERATIONAL_RUNBOOK.md`
   playbook. Mitigate first (restore service), root-cause second.
4. **Communicate** - post status updates on the cadence below.
5. **Resolve** - confirm the validation signal is green (see each playbook).
6. **Review** - Sev 1 gets a written post-mortem within 24h (blameless).

### Communication cadence
- **Sev 1:** update every **30 min** until resolved, even if "no change."
- **Sev 2:** update at declare, at mitigation, at resolve.
- **Sev 3:** note in the tracker; no live comms needed.

---

## 4. Worked example - the one you'll hit most: STALE DATA (Sev 1)

This is `ct-cne` - the in-process scheduler stalled and the core tenants went
>24h stale. Full procedure: `OPERATIONAL_RUNBOOK.md` -> "Issue: Data is STALE".

1. **Detect:** `data-freshness` availability alert fires, or `/healthz/data`
   shows `any_stale:true`.
2. **Declare Sev 1**, name an IC.
3. **Triage which failure it is:**
   ```bash
   curl -s $BASE/healthz/scheduler | jq '{running, any_overdue}'
   ```
   - `running:false` / `any_overdue:true` -> scheduler stalled -> restart the
     App Service (re-arms syncs immediately) + confirm "Always On" is on (`ct-ar3`).
   - scheduler healthy but data old -> a *sync* is failing -> pull logs, check
     credentials/throttling; recover with `python -m scripts.manual_sync --wait 90`.
4. **Verify:** `/healthz/data` -> `any_stale:false` after a **scheduled** cycle.
5. **Review:** if it was the scheduler again, escalate `ct-ar3` (Always On /
   externalize the scheduler) so it can't recur.

---

## 5. Comms templates

**Declare (Sev 1/2):**
> **[SEV1] Control Tower - <short title>** | Declared <time> | IC: <name>
> Impact: <who/what is affected, e.g., "all brand dashboards showing >24h-old data">
> Status: investigating. Next update <time>.

**Resolve:**
> **[RESOLVED] Control Tower - <short title>** | <time>
> Cause: <one line>. Fix: <one line>. Follow-up: <bd id(s)>.

---

## 6. Post-mortem template (Sev 1, within 24h, blameless)

- **What happened** (timeline, UTC) ·
- **Impact** (who, how long, what decisions were affected) ·
- **Root cause** ·
- **What went well / poorly** ·
- **Action items** (each as a bd issue with an owner)

---

**Owner:** Operations (contacts TBD - bd `ct-o1w`).
**Related:** `OPERATIONAL_RUNBOOK.md` (how-to-fix), `OPS_ONBOARDING.md`
(day-one), `PRODUCTION_READINESS_PLAN.md` (go-live gate).
