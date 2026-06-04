# Runbook: provision ops users into access tiers (ct-hvv)

**Goal:** give each operations person a login at the right least-privilege tier
so they can use Control Tower. Owner: **Tyler** (identity) + this script.

## Tier -> role mapping

The design spec names four tiers; the code's canonical roles live in
`app/core/permissions.py` (`Role` enum + `LEGACY_ROLE_MAP`). They map cleanly:

| Spec tier | `--role` value | What they can do |
|-----------|----------------|------------------|
| **Viewer** | `viewer` | Read every dashboard. No exports, no writes. |
| (Analyst) | `analyst` | Viewer + CSV exports. |
| **Manager** | `manager` | Analyst + cross-brand franchise-coach insight. Read-only by design. |
| **Operator** | `operator` | Alias of `tenant_admin`: write/manage/trigger within a tenant. |
| **Admin** | `admin` | Everything, incl. user management (`/admin`). |

> The provisioning script (`scripts/setup_admin.py`) now derives its allowed
> `--role` values directly from that enum + aliases, so it can't drift (ct-hvv
> fixed the old hardcoded list that was missing `manager`).

## Provision a user

Always **dry-run first** (no DB write), then run for real:

```bash
# Dry-run (shows what it would do)
uv run python scripts/setup_admin.py \
  --email jane.ops@httbrands.com --name "Jane Ops" --role viewer --dry-run

# Real
uv run python scripts/setup_admin.py \
  --email jane.ops@httbrands.com --name "Jane Ops" --role viewer
```

Repeat per person at the appropriate tier. Grant the **minimum** that does the
job (most ops staff = `viewer`; only platform ops = `operator`; only owners =
`admin`).

Valid roles: `admin, analyst, manager, operator, reader, tenant_admin, user,
viewer` (`uv run python scripts/setup_admin.py --help`).

## Validation (the ct-hvv close criterion)

For **each tier you actually use**, provision one real user and confirm:

1. They can **log in** at `https://app-governance-prod.azurewebsites.net`.
2. They see **tier-appropriate UI** — e.g. a `viewer` can read `/costs` and
   `/compliance` but has **no** export buttons and cannot reach `/admin`; an
   `admin` can reach `/admin` (user management).
3. **Least privilege holds:** a lower tier cannot do a higher tier's action
   (spot-check one, e.g. a viewer hitting an export/admin route is refused).

Record who got which tier (keeps the audit log meaningful).

## Notes

- Identity/SSO grants (Entra app-role assignment) are **Tyler's** part; this
  script seeds the app `users` table + role. If you use Entra App Roles as the
  source of truth, align the role names with the table above.
- Unknown role strings fail **closed** (empty permissions) by design — so a
  typo locks a user out rather than over-granting. Good, but double-check the
  spelling against the valid list above.
