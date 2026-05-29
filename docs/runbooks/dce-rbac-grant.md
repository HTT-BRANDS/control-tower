# Runbook: Grant DCE Sync RBAC (ct-1m0 P0 fix)

**Estimated time:** 5 minutes
**Owner:** Tyler Granlund (needs Global Admin in DCE tenant)
**Why:** Delta Crown Extensions tenant shows partial sync (costs ✅, identity ✅,
resources ❌, compliance ❌) because the multi-tenant governance app's service
principal in DCE has no RBAC at subscription scope. See [bd ct-1m0](../../) for
diagnostic evidence.

---

## TL;DR — three commands

Copy-paste these in your terminal, one at a time:

```bash
# 1. Log in to DCE tenant (device code; opens browser)
az login --tenant ce62e17d-2feb-4e67-a115-8ea4af68da30 --use-device-code --allow-no-subscriptions

# 2. Grant RBAC (self-elevates Global Admin → root UAA, grants, cleans up elevation)
./scripts/grant-dce-sync-permissions.sh --elevate-access --apply --cleanup-elevation

# 3. Verify (wait ~5 min for next scheduler tick first)
python scripts/judge.py --env production
```

When step 3 reports **`/healthz/data freshness`** as ✅ (all 5 tenants fresh),
DCE is fixed and the only remaining red P0 disappears.

---

## What the script does (transparency)

1. Confirms your `az` context is the DCE tenant
2. Optionally elevates your Global Admin → temporary `User Access Administrator`
   at scope `/` (needed because you have no sub-scope RBAC in DCE yet)
3. Finds the SP for the multi-tenant governance app (client id
   `1e3e8417-49f1-4d08-b7be-47045d8a12e9`) in the DCE tenant
4. Enumerates DCE subscriptions
5. For each subscription, assigns:
   - `Reader` (lets the sync read ARM resources)
   - `Security Reader` (lets the sync read policy compliance state)
6. Optionally removes the root-scope elevation when done

Run without `--apply` first to see a dry-run of every assignment that would be made.

---

## After the fix

1. Wait for the next scheduler tick (top of next hour for resources, top of next
   hour at xx:20 for compliance).
2. Re-run `python scripts/judge.py --env production` — should show 26/26 (100%).
3. Close ct-1m0 in bd:
   ```bash
   bd close ct-1m0 --reason "DCE RBAC granted at sub scope; healthz green"
   ```
4. Optional victory lap: tag the release.

---

## Troubleshooting

### "Could not find service principal for app … in DCE tenant"

The app hasn't been admin-consented in DCE yet. The script will print the
consent URL — open it in a browser, sign in as a DCE Global Admin, click
"Accept". Then re-run step 2.

### "Zero DCE subscriptions visible"

Even with `--elevate-access` you still need at least Reader visibility on the
subscriptions. Either:

- Use a DCE-internal account that already has Reader on the subs
- Or have a DCE admin add you as Reader at the management group root first

### Login still hangs / device code expires

Device codes have a ~15-minute TTL. If you took longer, re-run step 1 to
get a fresh code.

### Want to verify before applying?

The script defaults to dry-run if you omit `--apply`:

```bash
./scripts/grant-dce-sync-permissions.sh --elevate-access
# Reviews what it WOULD do without changing anything.
```

---

## Related

- [bd ct-1m0](../../) — the P0 bug
- [bd ct-38g](../../) — predecessor (OIDC flip that exposed this)
- [`scripts/grant-dce-sync-permissions.sh`](../../scripts/grant-dce-sync-permissions.sh) — implementation
- [`docs/architecture/current.md`](../architecture/current.md) — overall auth model
