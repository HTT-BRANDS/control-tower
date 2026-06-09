# HTT Control Tower — Ops Team Training Session (Facilitator Guide)

**Issue:** ct-dxb · Phase 4.8 · **Tyler delivers, Richard supplied these materials.**
**Validation:** attendance + sign-off recorded (see §6).
**Pairs with:** [`OPS_ONBOARDING.md`](OPS_ONBOARDING.md) — the written reference attendees keep afterward.

> This is the *facilitator's* script for a single live ~45-minute session. It does
> NOT repeat the onboarding content — it sequences a walkthrough of it, adds a
> live demo + hands-on exercises, and ends with a sign-off sheet. Send
> `OPS_ONBOARDING.md` as pre-read; run this to deliver.

---

## 0. Before the session (facilitator checklist — 10 min)

- [ ] Confirm each attendee has SSO access and lands on `/dashboard` (do this the day before — auth issues kill momentum live).
- [ ] Have the app open and logged in on the shared screen.
- [ ] Trigger a fresh sync (or confirm recent sync) so the dashboard shows live, non-stale data.
- [ ] Print or open the sign-off sheet (§6).
- [ ] Pre-read sent: `OPS_ONBOARDING.md` §1–§4.

---

## 1. Why we're here (3 min)

- One sentence: *"Control Tower is the single pane of glass for cost, compliance, resources, and identity across all our Azure tenants."*
- Frame the goal: by the end, everyone can do the **three core daily tasks unaided** (`OPS_ONBOARDING.md` §6).
- Set the tone: this is a tool to make their day easier, not another dashboard to babysit.

## 2. Guided tour (12 min) — walk `OPS_ONBOARDING.md` §3 live

Drive each page on the shared screen and state the **one question each page answers**:

| Page | "This page answers…" |
|------|----------------------|
| Dashboard | "Is anything on fire right now?" |
| Costs | "Where is the money going and is anything spiking?" |
| Compliance | "Which tenants/resources are out of policy?" |
| Resources | "What do we actually have deployed?" |
| Identity | "Who has access and is MFA on?" |
| Sync dashboard | "Is the data fresh, and did the last sync work?" |

## 3. The one concept that matters: "stale" (5 min) — `OPS_ONBOARDING.md` §4

- Show the **"Last sync"** indicator in the footer and the new **live status dot** next to it.
- Explain: a green/blue pulsing dot = real-time connection is live; numbers you see are current.
- Teach the reflex: **before acting on a number, glance at freshness.**

## 4. Live demo — the new productivity features (8 min)

These shipped in ct-6vn / ct-7d6. Demo them; they make daily use faster.

1. **Global search** — press <kbd>/</kbd> (or <kbd>⌘</kbd>/<kbd>Ctrl</kbd>+<kbd>K</kbd>). Search a tenant or user by name; jump straight to it. *"Stop hunting through menus."*
2. **Keyboard shortcuts** — press <kbd>?</kbd> to open the shortcuts overlay. Demo `g` then `d` (Dashboard), `g` then `c` (Costs). *"Power users never touch the mouse."*
3. **Real-time sync** — open the Sync dashboard; point out status updates and toast notifications appear **without refreshing** (Server-Sent Events). When a sync finishes, a toast pops.
4. **Dark mode** — click the theme toggle (or press <kbd>t</kbd>). Note it persists across sessions. *"For the late-night on-call crowd."*

## 5. Hands-on exercises (10 min) — everyone drives their own screen

Have each attendee complete and check off:

- [ ] Log in and reach `/dashboard`.
- [ ] Use search (`/`) to find a specific tenant by name.
- [ ] Identify the single most-stale data source from the Sync dashboard.
- [ ] **Core task 1** — find this week's highest-cost tenant (`OPS_ONBOARDING.md` §6).
- [ ] **Core task 2** — find one non-compliant resource and read why (`OPS_ONBOARDING.md` §6).
- [ ] **Core task 3** — confirm MFA status for a given user (`OPS_ONBOARDING.md` §6).
- [ ] Toggle dark mode and open the keyboard-shortcuts help (`?`).

## 6. Wrap-up + sign-off (2 min)

- Recap: three core tasks, the "stale" reflex, where to get help (`OPS_ONBOARDING.md` §7).
- Confirm everyone knows escalation path.
- **Record the sign-off below** (this is the issue's validation criterion).

### Attendance & competency sign-off

| Attendee | Role/Tier | Completed all 3 core tasks unaided? | Date | Initials |
|----------|-----------|-------------------------------------|------|-------------|
|          |           |                                    |      |             |
|          |           |                                    |      |             |
|          |           |                                    |      |             |
|          |           |                                    |      |             |

**Facilitator:** _______________  **Session date:** ___________  **Duration:** ______

> After the session: record completion on **ct-dxb** (attach/transcribe this sheet) and close the issue.

---

## Appendix — common live-session pitfalls

- **Auth fails for one person** → don't debug live; park them on the shared screen, fix after (it's almost always a missing tenant mapping — see `OPS_ONBOARDING.md` §5).
- **Dashboard looks empty/stale** → trigger a sync before the session, not during.
- **"Why is success blue, not green?"** → intentional: the palette is colourblind-safe (blue = good). Mention it so nobody files it as a bug.
