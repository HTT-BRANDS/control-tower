# Turbot / Guardrails — Raw UX Findings (March 2026)

**Sources:** turbot.com
**Date Accessed:** March 27, 2026
**Tier:** 2 (vendor product marketing)

---

## Product Identity — Major Pivot
- **Previous:** Turbot Guardrails — cloud governance & compliance platform
- **Current:** Turbot — "Prevention-first Cloud Security"
- **New product category:** PSPM (Preventive Security Posture Management)
- **Banner:** "Introducing PSPM: Preventive Security Posture Management →"
- **Launch activity:** "Launch Week 12 announcements & demos →" (active as of March 2026)

## Homepage Architecture Diagram

### Visual Flow
```
Left Side:          Center:           Right Side:
Threats 🗡         ┌──────────┐      ┌──────────┐
                   │          │      │   CNAPP   │
Agents 🤖    →→→  │  Cloud   │  ←←  │   Wiz    │
                   │          │      │  Cortex  │
Teams 👥    →→→   └──────────┘      │  Pipes   │
                       ↑             └──────────┘
                  Guardrails
              ┌──────────────┐
              │  PSPM  Turbot │
              └──────────────┘
                   Alerts ↕
           Educate ↕    Priorities ↕
```

### Integration Partners Shown
- **CNAPP layer:** Wiz, Cortex (Palo Alto Networks)
- **Own product:** Pipes (data pipeline product)
- **Positioning:** Turbot PSPM works **alongside** existing CNAPP tools, not replacing them

## "The Power of Prevention" — 6-Card Feature Layout

### Row 1 (3 cards)
1. **Visualize Current State**
   - "Understand and communicate your current preventive posture"
   - Isometric 3D illustration (green/gold color palette)

2. **Understand Gaps**
   - "Discover the best ways to reduce risk and prevent alerts"
   - Purple geometric illustration

3. **Prevention for Policy Posture**
   - "Use organization-level policies (AWS SCPs, Azure Policies, GCP Org Policies) to block risky actions at the API level"
   - Checklist: ✓ Enforce security, ✓ Prevent vulnerabilities, ✓ Override root user
   - Blue cloud/shield illustration

### Row 2 (3 cards)
4. **Prevention for Runtime**
   - "Continuously monitor for drift and **instantly fix misconfigurations** with automated remediation"
   - Checklist: ✓ Close exposure windows, ✓ Reduce alerts by 60%, ✓ Continuous compliance
   - World map with orange connection dots

5. **Simulate & Test**
   - "**Safely simulate** new preventive controls before deployment"
   - Red/purple abstract illustration

6. **Rollout & Expand**
   - "Deploy and communicate preventive controls across stakeholders"
   - Gold/brown modular illustration

## Design Language
- **Theme:** Dark mode by default (unusual for governance tools)
- **Background:** Dark navy/charcoal (#1a1a2e or similar)
- **Accent colors:** Gold/yellow for headings and highlights, blue for links
- **Illustrations:** Isometric 3D, geometric, abstract — high-quality custom art
- **Typography:** Modern sans-serif, clean hierarchy
- **Brand identity:** Sleek, developer-focused, premium feel
- **404 page:** Cute bee mascot ("Uh oh! I lost you.") — adds personality

## Navigation
```
[TURBOT logo]  [Why Prevent? 🛡]  [Features]  [Resources ▼]  [News]  |  [Pricing]  [Book a demo]
```
- "Why Prevent?" is a dedicated nav item (not standard "Product" or "Solutions")
- Resources has dropdown
- "Book a demo" is the primary CTA (filled button)

## Footer Details
- **Certifications:** AICPA SOC, CIS
- **Community:** 3,100+ practitioners on Slack
- **CloudGovernance.org →** — separate site for governance frameworks
- **Links:** About us, We're hiring!, Contact us, System Status, Terms of Use, Security, Privacy

## Key Strategic Insight
Turbot has **fundamentally repositioned** away from dashboard-heavy governance monitoring toward **prevention at the API level**. Their thesis:
- Detection/alerting creates alert fatigue
- Prevention blocks issues before they happen
- Prevention + Detection = complementary approach
- "Reduce alerts by 60%" is their key claim

This makes Turbot **less directly comparable** to our governance dashboard platform, but their **Simulate & Test** pattern and **prevention-first thinking** offer interesting UX concepts.
