# GitHub Enterprise Seat Audit Procedure

> **Status:** Accepted procedure · **Version:** 1.0 · **Date:** 2026-04-23
> **Owner:** Tyler Granlund · **Review cadence:** Quarterly

Procedure for right-sizing the HTT Brands GitHub Enterprise subscription.
GitHub Enterprise is currently **73% of the all-in monthly bill** — larger
than the entire Azure spend — so quarterly seat audits have the highest
dollar-per-minute ROI of any ops activity we do.

This is the answer to `COST_MODEL_AND_SCALING.md` Open Question #1.

---

## 1. Why this matters

Current monthly cost breakdown (per COST_MODEL §1.2):

| Line item | Monthly | % of bill | Per-year |
|---|---|---|---|
| Azure (all envs) | $53.40 | 27% | $640.80 |
| **GitHub Enterprise (7 seats × $21)** | **$147.00** | **73%** | **$1,764.00** |
| **Total** | $200.40 | 100% | $2,404.80 |

Reducing GitHub spend has more impact on TCO than any Azure SKU change
short of multi-region. Conservative seat right-sizing (7 → 5 seats) saves
**$504/yr**. Tier right-sizing (Enterprise → Team, if acceptable) saves
**$1,428/yr**. A single 20-minute audit per quarter captures most of this.

---

## 2. Audit cadence

| Cadence | Trigger | Scope |
|---|---|---|
| **Quarterly** (fixed) | First business day of each quarter | Full audit per §3 |
| **Ad-hoc** | Any hire / departure | Add/remove seat within 48h |
| **Annual** (tier-level) | Renewal date | Re-justify Enterprise vs Team tier per §5 |

---

## 3. Quarterly audit procedure

**Expected time: 20 minutes. Expected savings: $0-$504/yr depending on seat activity.**

### 3.1 Pull the activity report (5 min)

```bash
# Requires: GitHub admin token with read:enterprise scope
# Replace HTT-BRANDS with the actual enterprise slug

gh api /enterprises/HTT-BRANDS/consumed-licenses \
    --jq '.users[] | {login, last_activity_on, license_type}' \
    > /tmp/gh-seats-$(date +%Y-%m-%d).json

# Sort by last activity, oldest first
cat /tmp/gh-seats-$(date +%Y-%m-%d).json | \
    jq -s 'sort_by(.last_activity_on)' | \
    jq -r '.[] | "\(.last_activity_on // "NEVER")\t\(.login)\t\(.license_type)"' | \
    column -t
```

**Alternative (web UI):** GitHub Enterprise admin → Billing → Licensing →
Consumed licenses. Export to CSV, open in Numbers/Excel, sort by "Last
activity" ascending.

### 3.2 Classify each seat (10 min)

For each of the 7 current seats, assign one classification:

| Classification | Signal | Action |
|---|---|---|
| 🟢 **Active** | Commit or PR in last 30 days | Keep seat |
| 🟡 **Sporadic** | Activity in last 90 days but not 30 | Keep + note for next quarter |
| 🔴 **Inactive** | No activity in 90 days | Candidate for removal |
| ⚫ **Former** | Departed HTT Brands | Remove immediately (not at audit cadence) |

**Gotcha — agent seats don't count as "inactive":** automated accounts
(e.g., `dependabot[bot]`, `github-actions[bot]`, and `code-puppy-*` agent
IDs if they exist as distinct users) may have zero direct commits but are
still functional. Verify a seat is tied to a human before classifying
inactive.

### 3.3 Take action (5 min)

For each 🔴 Inactive seat:

1. Confirm with the seat-holder that they don't need access (email, Teams
   message, or the enterprise admin's standard offboarding protocol).
2. If confirmed inactive: `gh api -X DELETE /enterprises/HTT-BRANDS/consumed-licenses/<login>`
   or via the admin web UI.
3. Close immediately — GitHub bills for seats **held** during the month,
   so removing mid-month saves pro-rata.

Log the action to the quarterly audit table (§6).

### 3.4 Document outcome

Append a row to the "Quarterly audit log" table in §6 of this doc. If zero
changes this quarter, still record "0 changes" — the audit happening is the
artifact, not just the removals.

---

## 4. Add-seat procedure (new hires)

New contributors go through the same 48-hour-or-better turnaround:

1. Hiring manager opens a ticket (internal tracker or email to Tyler).
2. Tyler adds the seat via `gh api -X PUT
   /enterprises/HTT-BRANDS/consumed-licenses/<login>` or the admin web UI.
3. Seat is assigned to the `htt-brands/contributors` team at minimum; other
   team memberships per the onboarding checklist.
4. Row added to §6 audit log: date, reason=hire, seat count after.

**Cost awareness:** Each added seat is +$21/mo / +$252/yr. For a 4-month
project contractor, that's $84 of pure seat cost. Worth it for real work;
skip for shoulder-surfing access.

---

## 5. Tier justification (annual)

Current tier: **Enterprise Cloud at $21/seat/mo**.
Next-cheapest tier: **Team at $4/seat/mo** — saves $17/seat/mo = $119/mo at
7 seats = $1,428/yr.

### 5.1 What Enterprise Cloud provides that Team does not

| Feature | Enterprise | Team | Do we use it? |
|---|---|---|---|
| SAML SSO (Azure AD federation) | ✅ | ❌ | **YES — core authZ model** |
| Audit log API access | ✅ | ❌ | **YES — used by bd tracking + release-gate arbiter** |
| IP allowlisting | ✅ | ❌ | No |
| Advanced Security (secret scanning paid tier, dependency review, CodeQL unlimited) | ✅ | ❌ | **YES — detect-secrets is pre-commit only; CodeQL runs in CI** |
| Unlimited private repos with Actions | ✅ | ✅ | Both tiers offer this |
| GitHub Packages (GHCR) | ✅ | ✅ | Both tiers offer this |
| Support SLA | 24/7 | Next business day | No active need |
| Organization insights / seat analytics | ✅ | Limited | Used for this audit itself |

### 5.2 Decision criteria

**Stay on Enterprise if ALL of these are true:**

- [x] SAML SSO is an authZ requirement (not a nice-to-have)
- [x] Audit log API integrations exist (bd / release-gate arbiter)
- [x] CodeQL runs against any private repo
- [x] The $1,428/yr delta is acceptable given the security posture gains

**Move to Team if ANY of these become true:**

- [ ] SAML SSO is no longer a requirement (e.g., all users accept GitHub's
  native MFA as sufficient)
- [ ] The audit-log-API integrations are retired in favor of different tooling
- [ ] CodeQL is replaced by a third-party SAST tool
- [ ] Leadership directs cost optimization at the tier level

**Current recommendation: stay on Enterprise Cloud.** Revisit at next
renewal.

---

## 6. Quarterly audit log

Append one row per quarter. Never edit previous rows.

| Quarter | Audit date | Seats before | Seats after | Inactive found | Removed | Added (hires) | Notes |
|---|---|---|---|---|---|---|---|
| 2026-Q2 | _2026-04-23 (policy creation)_ | 7 | 7 | _(not yet run)_ | 0 | 0 | Policy created; first real audit due 2026-07-01 |
| 2026-Q3 | _2026-07-01 (scheduled)_ | — | — | — | — | — | — |
| 2026-Q4 | _2026-10-01 (scheduled)_ | — | — | — | — | — | — |
| 2027-Q1 | _2027-01-02 (scheduled)_ | — | — | — | — | — | — |

---

## 7. Annual tier review log

| Year | Tier before | Tier after | Renewal date | Decision rationale |
|---|---|---|---|---|
| 2026 | Enterprise Cloud | _unchanged — renewal not yet reached_ | _TBD_ | §5.2 checklist — all Enterprise criteria still hold |

---

## 8. What this doc unblocks

| Previously open question | Now answered |
|---|---|
| COST_MODEL §Q1 "How many GitHub seats needed?" | **Subject to quarterly audit per §3; current baseline is 7 pending first audit** |
| "Should we downgrade Enterprise → Team?" | **No — justified by §5.1 checklist; revisit at annual renewal** |
| "Who owns the GitHub seat budget?" | **Tyler Granlund (enterprise admin)** |

---

## 9. Change log

| Date | Change | Rationale |
|---|---|---|
| 2026-04-23 | Initial procedure + tier justification | Closes COST_MODEL Q1 |

---

## 10. References

- `docs/COST_MODEL_AND_SCALING.md` §1.1 GitHub subtotal, §Appendix B #1
- GitHub Enterprise admin console: `https://github.com/enterprises/HTT-BRANDS`
- `gh` CLI docs: `gh help api`
