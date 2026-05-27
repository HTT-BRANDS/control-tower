# Incident Comms — Customer-Brand Dashboard Data Stale (2026-05-20 → 2026-05-27)

**Status**: DRAFT — pending ops-comms-collie review
**Audience**: Internal franchise-ops leadership (COOs, franchise success leads, franchise IT)
**Drafted by**: Richard (code-puppy-5deed9), 2026-05-27
**Reviewer requested**: ops-comms-collie (pre-send), Tyler (final approve)

---

## VERSION A — Microsoft Teams post (≤180 words)

> **Heads up — customer-brand dashboards showing data from last week**
>
> A platform change we shipped on May 20 quietly stopped the daily data refresh for **Bishops Cuts/Color, Frenchies, Delta Crown, and the Lash Lounge**. Our own HTT-Brands dashboard kept refreshing normally.
>
> No data was lost. No credentials were exposed. The dashboards stayed up — the numbers just stopped updating.
>
> We caught this today during a manual review — not via an automated alarm, which is the gap we're closing next. Cause is identified and a fix is queued for deployment. Expected restoration: **within 2 hours of deploy approval**.
>
> 👉 **One ask**: if you made a decision in the past week based on a BCC / FN / DCE / TLL dashboard view, please reply or DM me — we want to revisit it once fresh data is in.
>
> HTT-Brands dashboard data has been refreshing normally throughout. We're also adding a data-freshness alarm so this doesn't slip past us again.

---

## VERSION B — Email to COOs + franchise success leads (≤450 words)

**Subject**: Customer-brand dashboards showing stale data (May 20 → today) — fix in progress

Team,

**Bottom line:** four customer-brand dashboards (Bishops, Frenchies, Delta Crown, Lash Lounge) have been showing May 20 data for the past 7 days. We identified the cause today, a fix is ready, and we expect those dashboards to be current within 2 hours of deploy approval. No data was lost, no credentials were exposed, and the HTT-Brands dashboard has been refreshing normally throughout.

Detail below.

### What happened
On Wednesday, May 20, we shipped an authentication change to the Control Tower platform that was intended to reduce the amount of manual credential-rotation work the platform requires over time. The change inadvertently triggered a limitation on Microsoft's side that only affects how we connect to *customer-brand* tenants — specifically Bishops, Frenchies, Delta Crown, and the Lash Lounge. Our own HTT-Brands data path was unaffected.

The result: for the past seven days, the dashboard views for those four brands have been showing the same numbers they showed on May 20. The dashboard itself stayed up the whole time. The "is the site up?" health check we monitor stayed green, because the site *was* up — it just wasn't pulling fresh data behind the scenes.

### How we found it
This was caught today during a routine review pass, not by an automated alarm. That gap — the platform staying green while data went stale — is the single most important thing we're fixing in our process. More below.

### What we're doing right now
1. A code fix has been written, peer-reviewed, and is ready to deploy.
2. Within 2 hours of deploy approval, we expect all four customer brands' dashboards to be refreshing on the normal hourly cycle.
3. We're treating the verification step seriously: each brand's data will be checked against the source systems before we close this out.

### What changed in our process
We are adding a **data-freshness alarm** alongside the existing site-up alarm, so that the next time data stops flowing — for any reason — we hear about it within hours, not days. We're also scoping a longer-term platform change that eliminates this whole class of problem — a multi-week project, tracked separately.

### What we need from you
- **Please acknowledge receipt** so we know the message landed.
- **If you made or supported a decision between May 20 and today that relied on a BCC, FN, DCE, or TLL dashboard view**, please reply with a brief note. We'd rather revisit one decision than miss one that mattered.
- **Continue to rely on the HTT-Brands dashboard view with confidence** — that data path has been refreshing normally throughout.

Happy to walk through this on a call if useful.

— [SENDER NAME]
[TITLE], HTT Brands

---

## Draft notes for the reviewer

**Items I deliberately left out and want collie's call on**:
1. **PR number (#63)** — left it in the Teams post (technical audience tolerates it, signals "we have a real fix") but omitted from the email. Adjust if your house style differs.
2. **"Richard the puppy"** — not mentioned anywhere. AI-agent attribution feels off-tone for incident comms; keeping authorship human-facing.
3. **AADSTS error codes, OIDC/SAMI/UAMI jargon** — all stripped. Replaced with "authentication change", "limitation on Microsoft's side", and "User-Assigned Managed Identity migration" (the last one only in the long version, with enough context that the reader can google it if curious without it interrupting their read).
4. **Specific deploy date for the fix** — left as "within 2 hours of deploy approval" rather than committing to a clock time. Tyler approves the deploy.
5. **"7 days" is named explicitly** — in both versions. Wanted to avoid the trap of saying "since last week" which reads as smaller than it is.
6. **CTA ranked**: ack → flag past-week decisions → continue using HTT view. The "flag past-week decisions" ask is the most important one and is named explicitly in both versions.

**Items I want collie to pressure-test**:
- Is "we caught this today during a scheduled review" too soft on the 7-day delay? Honest framing is that nobody was actively watching the right signal — should that be named more directly?
- Is the "what changed in our process" section thin? It contains a real change (freshness alarm) and a real future state (UAMI migration), but the size of the gap (7 days undetected) might warrant more.
- Does the Teams post need a sign-off line / who-to-DM line beyond "DM me"?
