# ADR-0012: Manager Role — Franchise Coach Dashboard

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-05-28 |
| **Decision Maker** | Tyler Granlund |
| **Implementer** | Richard (code-puppy-5deed9) |
| **Related** | ADR-0011 (Granular RBAC), GH issue #66, bd ct-2nk |

## Context

The Miro design-system spec (issue #66, p.7-8) defines four access tiers:
**Admin / Manager / Operator / Viewer**. The codebase had only three
(`viewer / operator(tenant_admin) / admin`).

The Manager role is **not just another permission level** — it represents
the franchise-leadership persona who needs cross-brand visibility to coach
brand operators. Tyler's brand-voice framework
(`~/code_puppy/docs/htt_brand_voice_framework.html`) frames this as
"franchisee-first, operationally exact, warm but disciplined."

## Decision

Add `Role.MANAGER` between `ANALYST` and `TENANT_ADMIN` in the role
containment hierarchy. The Manager role is **read + export across all
accessible brands**, with no write/manage capability — by design.

```
VIEWER ⊂ ANALYST ⊂ MANAGER ⊂ TENANT_ADMIN ⊂ ADMIN
```

Manager-specific permissions:
- `franchise_coach:read` — view cross-brand insight dashboard
- `franchise_coach:export` — export coaching prep packets

Manager inherits all Analyst permissions (read + export of costs,
resources, identity, audit logs).

## Why read-only

The Manager is a **coach, not an operator**. Their job is to surface
data-driven conversations with brand operators — not to push the buttons
themselves. Read-only enforces a clear separation between leadership
visibility and operational responsibility, which:

1. Matches the brand voice: "Coach / Guide" — not "Override"
2. Reduces blast radius (no Manager-tier mistakes)
3. Makes audit logs cleaner (writes only happen at Operator+ tiers)
4. Lets us trust Manager UX to surface friction rather than fix it

## What the Manager dashboard headlines

Per Tyler's directive: identity gaps and known compliance gaps across
brands, so franchise leadership can have informed conversations with
franchisees.

Concretely, the franchise-coach dashboard surfaces:

1. **Identity gaps per brand** — MFA registration shortfalls,
   privileged users without recent activity, stale guest accounts
2. **Compliance gaps per brand** — failing policies, low secure scores,
   policy assignments diverging from baseline
3. **Sync freshness per brand** — which data is current, which is stale
   (the DCE pattern: caught one tenant in partial sync)
4. **Brand-voice copy throughout** — every insight phrased per the
   4-step pattern: objective → reality → action → expected outcome

## Alternatives considered

| Alternative | Why rejected |
|-------------|-------------|
| Collapse Manager into Admin permissions | Loses the read-only safety; muddles audit trail |
| Make Manager a permission set on Analyst | Roles are user-facing labels; Manager is its own job |
| Build per-brand managers (multi-tenant manager) | Cross-brand visibility is the entire point |
| Defer to a future release | Tyler explicitly asked for it now (ct-2nk P1) |

## Consequences

### Positive
- ✅ Matches Miro spec exactly — diagram and code now agree
- ✅ Operationalizes the brand voice in a real UI surface
- ✅ Read-only role is the safest place to start RBAC expansion
- ✅ Reuses existing permission resolution (no architectural change)

### Negative / risks
- 🟡 One more role to maintain in fixture data + tests
- 🟡 Franchise-coach dashboard becomes a new surface to keep aligned
  with sync-domain models — if identity/compliance schemas drift, the
  dashboard needs maintenance

### Migration
- Adds a row to `LEGACY_ROLE_MAP` so existing `"manager"` strings resolve
- Default for new `UserTenant` rows remains `"viewer"` — no implicit promotions
- Existing users unaffected unless explicitly assigned Manager

## Validation

- Unit: `tests/unit/test_permissions_manager_role.py`
- Integration: dashboard route requires `franchise_coach:read`
- E2E: Playwright tests verify Manager sees coach view, Viewer doesn't

## References

- ADR-0011 — Granular RBAC (parent decision)
- `~/code_puppy/docs/htt_brand_voice_framework.html` — voice charter
- Miro spec PDF page 7-8 (`docs/design-system/issue-66-design-system-spec-v1.pdf`)
- bd ct-2nk — original tracking issue
