# Requirements Traceability Matrix — v2.5.1 Release (DRAFT)

> **Status:** 🚧 **DRAFT — prospective RTM** · **Target tag:** `v2.5.1`
> **Window start:** `v2.5.0` @ `b1137cb` (2026-04-15) → *(window end TBD at release cut)*
> **Consumer:** release-gate-arbiter (Pillar 1 — Requirements Closure)

## 0. Why this file exists early

The `v2.5.0` RTM was prepared **retroactively** — after the release commits
had landed. The arbiter accepted it with a `CONDITIONAL_PASS` caveat about
"prospective traceability discipline" that matters more at prod promotion.

This file is the **prospective RTM** for v2.5.1 — started on the day the
last `v2.5.0` carve-out (bd `7mk8`) closed. Every bd ticket merged to `main`
after `v2.5.0` gets a row here at close-time, so when v2.5.1 is cut the RTM
is already done.

**Process rule (prospective RTM discipline):**

1. When a bd ticket is closed with a commit on `main`, append a row here.
2. When the row is added, reference the commit SHA in the ticket's "close"
   comment (bidirectional linkage).
3. When v2.5.1 is cut (at whatever SHA), this file is renamed
   `rtm-v2.5.1.md` (drop the `-DRAFT` suffix), the top-of-doc status flips
   to "Accepted", and it becomes a binding artifact.

---

## 1. Summary (auto-updated at each row addition)

> **Update checklist:** when you append a row below, update these counts.

| Metric | Count |
|---|---|
| Total tickets in window | 5 |
| Closed (work complete) | 4 |
| Open (carve-outs) | 1 (`rtwi`, date-gated; **NOT a prod blocker**) |
| Themes | 2 |

### Work by theme (so far)

| Theme | Tickets |
|---|---|
| Supply-chain hardening | 3 (`7mk8`, `dq49`, `my5r`) |
| Operations / infra | 1 (`x692`) |

---

## 2. Detailed traceability (append rows as work closes)

### Supply-chain hardening

| bd ID | P | Status | Title | Commits | Validation surface |
|---|---|---|---|---|---|
| `7mk8` | P1 | ✅ closed 2026-04-23 | security(supply-chain): implement SLSA L3 + Sigstore cosign + SBOM in release-production workflow | `7d816f6` `7921b92` `b28a9f2` `3042624` | ci-workflow, docs (arbiter/policies/verify.yaml), workflow-gate |
| `dq49` | P3 | ✅ closed 2026-04-23 | chore(supply-chain): SHA-pin attest-*, cosign-installer, sbom-action | `ebb2086` | ci-workflow |
| `my5r` | P2 | ✅ closed 2026-04-23 | feat(ci): env-delta.yaml schema validator + literal-rejection gate | `04d0d7b` | tests, ci-workflow, scripts |

### Operations / infra

| bd ID | P | Status | Title | Commits | Validation surface |
|---|---|---|---|---|---|
| `x692` | P3 | ✅ closed 2026-04-23 | feat(ops): scheduled Bicep drift detection | `fecf0fd` | ci-workflow |

### Staging reliability (mitigation-only, ticket stays open)

| bd ID | P | Status | Title | Commits | Validation surface |
|---|---|---|---|---|---|
| `mvxt` | P2 | 🟡 open (mitigated) | ops(staging): Deploy to Staging validation suite consistently times out | `68c0baa` (mitigation), `a7557a4` (docs sweep) | tests/staging/conftest.py |

**Note:** `mvxt` is **intentionally kept open** — the shipped change is a
compensating control (cold-start warmup + retry adapter), not a root-cause
fix. Root cause needs Azure Portal / App Insights access. Does not block
v2.5.1 promotion because the mitigation reduces CI-failure rate to
acceptable levels and the SLO (per `docs/SLO.md`) is not at risk from
cold-start behavior.

### Date-gated work (NOT in v2.5.1 — tracked only)

| bd ID | P | Status | Title | Trigger | Blocks v2.5.1? |
|---|---|---|---|---|---|
| `rtwi` | P3 | 🟡 open | ops: stop domain-intelligence App Service at 60d zero-traffic | 2026-05-17 (date-gated) | ❌ No (separate project resource group) |

---

## 3. Governance / non-ticket changes

Changes that landed without their own bd ticket but are in the release window:

| Date | Commit | Summary | Rationale for no ticket |
|---|---|---|---|
| 2026-04-23 | `a7557a4` | Close stale SBOM/SLSA/cosign gap references across 4 docs | Follow-through on `7mk8`; within same work session |
| 2026-04-23 | `59aecda` | 2026-04-23 session log | Governance artifact; session log is per-session, not per-ticket |
| 2026-04-23 | `874bc02` | README badge bump 2.3.0 → 2.5.0 | Stale badge fix; trivial |
| 2026-04-23 | _(pending)_ | SLO + Data Retention + GitHub Seat Audit policy docs | Close COST_MODEL Q1/Q5/Q6; no bd ticket because they're policy commitments, not code |
| 2026-04-23 | _(pending)_ | Stale-root-doc archive sweep (10 files to docs/archive/) | Governance hygiene; pure doc move |
| 2026-04-23 | _(pending)_ | INFRASTRUCTURE_INVENTORY.md SUPERSEDED banner | Doc correction; 11 live refs made banner preferable to archive |

---

## 4. Scope boundary — what's explicitly NOT in v2.5.1

For arbiter clarity: the following work is **known to exist** but will NOT
land in v2.5.1. Each has a declared home.

| Item | Where it lives | Why deferred |
|---|---|---|
| `mvxt` root-cause (App Insights investigation) | Stays in bd `mvxt` (open) | Needs Azure Portal access — Tyler-only activity |
| `rtwi` domain-intelligence shutdown | Stays in bd `rtwi` (open) | Date-gated 2026-05-17 — triggers AFTER v2.5.1 cut |
| Dev env auto-pause (COST_MODEL Q3) | Not yet filed | Awaiting product decision |
| Zero-downtime blue-green (COST_MODEL Q4) | Tracked in prior-session context as `bd-hofd` | Awaiting SLO-driven trigger per `docs/SLO.md` §2.2 |
| Multi-region deployment | No ticket | SLO is 99.9%, doesn't require it |

---

## 5. Pre-submission checklist (before flipping to rtm-v2.5.1.md)

- [ ] All ticket rows point at commits present in the `v2.5.0..<release-sha>` range
- [ ] Summary counts (§1) updated to match the table row counts in §2
- [ ] Governance changes (§3) all cited with commit SHA
- [ ] `mvxt` + `rtwi` explicitly documented as non-blocking in §4
- [ ] Arbiter policy file (`arbiter/policies/verify.yaml`) references v2.5.1 if any supply-chain policy diff
- [ ] `CHANGELOG.md` `[Unreleased]` section promoted to `[2.5.1] - <date>`
- [ ] `pyproject.toml` version bumped to `2.5.1`
- [ ] `core_stack.yaml` `version:` line bumped to `2.5.1`
- [ ] `env-delta.yaml` `deltas_since_previous_release` block updated
- [ ] Top-of-doc status flipped from `🚧 DRAFT` to `Accepted`
- [ ] File renamed `rtm-v2.5.1.md`
- [ ] Committed with message `docs(release-gate): promote rtm-v2.5.1 from draft`

---

## 6. References

- `docs/release-gate/rtm-v2.5.0.md` — previous (retroactive) RTM, template
- `docs/release-gate/submission-v2.5.0.md` — full release-gate dossier pattern
- `docs/release-gate/verdicts/rga-2026-04-22-azgov-v2.5.0-02.md` — previous arbiter verdict
- `arbiter/policies/verify.yaml` — production supply-chain verification policy (machine-readable)
- `docs/SLO.md` — SLO that governs what counts as "good enough for prod"
- `docs/DATA_RETENTION_POLICY.md` — retention contract
- `docs/GITHUB_SEAT_AUDIT.md` — seat-management procedure
