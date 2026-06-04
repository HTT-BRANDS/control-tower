# HTT Control Tower - Operations Onboarding

**Your day-one guide to using Control Tower.** This is the "how do I actually
use this thing" walkthrough. For incident response and recovery procedures,
see `docs/OPERATIONAL_RUNBOOK.md` instead.

**Audience:** HTT operations team members.
**Last updated:** 2026-06-04.

---

## 1. What Control Tower is (30 seconds)

Control Tower is HTT's single pane of glass for governing our five franchise
brands' Azure tenants:

- **Head-To-Toe (HTT)**, **Bishops (BCC)**, **Frenchies (FN)**,
  **Lash Lounge (TLL)**, **Delta Crown Extensions (DCE)**.

It pulls four kinds of data from each brand's Azure tenant - **costs**,
**identity**, **resources**, and **compliance** - plus Riverside security
signals, and shows them in one place so you don't have to log into five
separate Azure portals.

You read it. You (mostly) don't change anything in it - it's a reporting and
governance hub, not a place where you reconfigure Azure.

---

## 2. Logging in

1. Go to **https://app-governance-prod.azurewebsites.net**
2. You'll be redirected to the **login** page (`/auth/login`).
3. Sign in with the credentials Tyler provisioned for you (see your access
   tier in section 5).
4. After login you land on the **Dashboard** (`/dashboard`).

If you can't log in, that's a provisioning issue - contact the Operations
owner (see runbook "Emergency Contacts"). Don't share logins; each person gets
their own so the audit log means something.

---

## 3. The tour - what each page answers

Everything hangs off the top navigation. Here's what each page is *for*:

| Page | URL | The question it answers |
|------|-----|-------------------------|
| **Dashboard** | `/dashboard` | "Is everything healthy right now, across all brands?" |
| **Costs** | `/costs` | "What is each brand spending, and is anything trending up?" |
| **Compliance** | `/compliance` | "Are the brands meeting policy? What's failing?" |
| **Resources** | `/resources` | "What Azure resources exist per brand?" |
| **Identity** | `/identity` | "Users, sign-ins, identity posture per brand." |
| **Sync status** | `/sync-dashboard` | "Is the data fresh? When did each brand last sync?" |
| **Riverside** | `/riverside` | "Riverside security/compliance posture (MFA, device, threat)." |
| **DMARC** | `/dmarc` | "Email-auth (DMARC/DKIM) status." |
| **Topology** | `/topology` | "How the tenants/environments connect." |
| **Admin** | `/admin` | User management (Admin tier only). |

The **Dashboard** stitches the highlights together as cards: a cost summary, a
compliance gauge, resource and identity stats, **sync status**, **active
alerts**, and a **per-tenant sync status** grid.

---

## 4. The single most important concept: "stale"

Control Tower is only as good as the freshness of its data. Each brand's data
is re-synced from Azure on a schedule. If a sync stops running, the dashboards
keep showing **old numbers** - which look fine but lie.

**How to tell if the data is trustworthy today:**

- On the **Dashboard** / **Sync status** page, look at the **per-tenant sync
  status** - each brand shows when it last synced. Anything older than ~24h is
  **stale**.
- The fast machine check (bookmark it):
  ```
  https://app-governance-prod.azurewebsites.net/healthz/data
  ```
  Look for `"any_stale": false`. If it's `true`, some brand's data is old.

**What to do if data is stale:**

1. Don't make decisions off the stale numbers.
2. Flag it: this is an operational incident, not a you-did-something-wrong.
3. Hand it to the platform/on-call engineer - the recovery procedure lives in
   `docs/OPERATIONAL_RUNBOOK.md` -> "Issue: Data is STALE". (There's also an
   automatic alert being wired up, bd `ct-vuv`, so this should page someone
   on its own soon.)

> Why this matters: in June 2026 the four core brands silently went >24h stale
> because a background scheduler stopped without alarming. The dashboards still
> rendered. That's the trap this section exists to prevent.

---

## 5. Your access tier - what you can and can't do

Control Tower uses least-privilege roles. From lowest to highest:

| Tier | Can do | Typical user |
|------|--------|--------------|
| **Viewer** | Read every dashboard. No exports, no changes. | Most ops staff |
| **Analyst** | Viewer + **export** data (CSV) from modules. | Reporting / analysis |
| **Manager** (Franchise Coach) | Analyst + **cross-brand** coaching insights. Still read-only by design. | Franchise leadership |
| **Tenant Admin** | Analyst + trigger syncs / manage within a tenant. | Platform ops |
| **Admin** | Everything, including user management (`/admin`). | Tyler / platform owners |

If a page or button is missing for you, that's intentional - your tier doesn't
include it. Need more access? Ask an Admin; we grant the minimum that does the
job.

> Note: the design spec labels the tiers Admin / Manager / Operator / Viewer;
> the code's canonical role names are in `app/core/permissions.py`. If those
> names differ on your account, that reconciliation is tracked in bd `ct-hvv`.

---

## 6. Your three core daily tasks (do these unaided)

If you can do these three things, you're onboarded.

**Task A - "Is the platform healthy and the data trustworthy today?"**
1. Open `/dashboard`.
2. Check `https://app-governance-prod.azurewebsites.net/healthz/data` -> expect
   `"any_stale": false`.
3. Glance at **active alerts** on the dashboard. None firing = good morning.

**Task B - "What is a brand spending?"**
1. Open `/costs`.
2. Find the brand (e.g. Bishops / BCC).
3. Read its cost summary; note anything trending sharply up.

**Task C - "What's a brand's compliance posture, and is anything failing?"**
1. Open `/compliance`.
2. Select the brand.
3. Read the compliance gauge; drill into any failing item.

When in doubt about a number, **check freshness first** (section 4) before you
escalate - a "weird number" is very often just stale data.

---

## 7. Who to call

All escalation contacts, severities, and the on-call rotation live in
`docs/OPERATIONAL_RUNBOOK.md` -> "Emergency Contacts" and "Escalation
Procedures". (Those are being filled with real names in bd `ct-o1w`.)

Rule of thumb:
- **Platform/data looks down or stale** -> platform / on-call engineer.
- **Security concern** -> security contact, immediately.
- **"How do I...?"** -> Operations owner.

---

## 8. FAQ

**The dashboard shows old numbers.** Check `/healthz/data`. If `any_stale:true`,
it's a sync issue - escalate per section 4, don't act on the numbers.

**A button/page is missing.** Your access tier doesn't include it (section 5).

**Can I change Azure settings from here?** No - Control Tower is read/govern,
not configure. Changes happen in Azure itself.

**A brand shows fewer data types than others.** Some brands are still being
fully onboarded (e.g. DCE's resources/compliance are in progress, bd `ct-4if`).
That's a known gap, not a bug.

**Where's the deeper runbook?** `docs/OPERATIONAL_RUNBOOK.md`.

---

**Maintainer:** Operations Team. Keep this guide honest - if a page moves or a
tier changes, update this file in the same PR.
