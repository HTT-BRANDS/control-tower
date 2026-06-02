# domain-intelligence — re-creation stash + decommission checklist (ct-mql)

This directory exists so that **Option A (delete the idle resources)** for
`bd ct-mql` is reversible in intent. `domain-intelligence` has had **zero
traffic for 60+ days**, and Azure keeps auto-restarting the paused PostgreSQL
flexible server every 7 days — so leaving it stopped is not a stable end state.
The decision was to delete it and keep this Bicep stash for revival.

| | |
|---|---|
| Subscription | `HTT-CORE` |
| Resource group | `rg-htt-domain-intelligence` |
| App Service | `domain-intelligence-prod` (`*.azurewebsites.net`) |
| PostgreSQL flex | `domainiq-db-prod` — `Standard_B1ms`, v16 |
| Cosmos DB | present per cost model (~$35/mo) — **config unconfirmed**, see below |
| Approx cost | ~$28–30/mo (App Service + PG); ~$65/mo for the whole RG incl. Cosmos |

>  **The Bicep here is RECONSTRUCTED from operational evidence, not exported
> from the live resources.** Fields marked `// [VERIFY]` in `main.bicep` are
> best-effort. It is good enough to stand a comparable stack back up; it is
> **not** guaranteed byte-identical to what gets deleted. If you need an exact
> rebuild, run the export step below *before* deleting.

---

## Before you delete (Tyler — do these first)

These steps are **not** automated here because they are destructive and require
your Azure credentials. Run them in order.

### 1. Snapshot the real ARM templates (better than this hand-written Bicep)

```bash
az group export \
  --name rg-htt-domain-intelligence \
  --subscription HTT-CORE \
  > infra/domain-intelligence/exported-arm-$(date +%Y%m%d).json
```

Commit that file alongside this README — it captures the *actual* config
(App Service plan SKU, Cosmos schema, networking, firewall rules) that the
reconstructed `main.bicep` can only guess at.

### 2. Confirm the FULL resource inventory (don't get surprised by Cosmos)

```bash
az resource list \
  --resource-group rg-htt-domain-intelligence \
  --subscription HTT-CORE \
  --output table
```

The cost model notes a **Cosmos DB** in this RG. Deleting the resource group
(step 4) removes **everything** listed here — confirm there is nothing you want
to keep (private endpoints, managed identities, Key Vault, diagnostic storage,
etc.).

### 3. Take a final PostgreSQL backup (if any data matters)

```bash
# The server is stopped; start it just long enough to dump, then proceed.
az postgres flexible-server start \
  -g rg-htt-domain-intelligence -n domainiq-db-prod --subscription HTT-CORE

# ...pg_dump via a jump host / az postgres flexible-server connect...

az postgres flexible-server stop \
  -g rg-htt-domain-intelligence -n domainiq-db-prod --subscription HTT-CORE
```

If the data is genuinely abandoned, skip this — but decide deliberately.

---

## Delete (Tyler — the destructive part)

Simplest and most complete is to delete the whole resource group. This removes
the App Service, the App Service Plan, PostgreSQL, **and the Cosmos DB**:

```bash
az group delete \
  --name rg-htt-domain-intelligence \
  --subscription HTT-CORE \
  --yes
```

If you'd rather delete piecemeal (e.g. keep the RG for something else):

```bash
az webapp delete \
  -g rg-htt-domain-intelligence -n domain-intelligence-prod --subscription HTT-CORE

az appservice plan delete \
  -g rg-htt-domain-intelligence -n plan-domain-intelligence-prod --subscription HTT-CORE --yes

az postgres flexible-server delete \
  -g rg-htt-domain-intelligence -n domainiq-db-prod --subscription HTT-CORE --yes

# Cosmos — confirm the real account name from step 2 first:
az cosmosdb delete \
  -g rg-htt-domain-intelligence -n <cosmos-account-name> --subscription HTT-CORE --yes
```

---

## Revive later (if the project comes back)

```bash
az group create -n rg-htt-domain-intelligence -l <region> --subscription HTT-CORE

# Prefer the real exported ARM from step 1 if you captured it:
az deployment group create \
  -g rg-htt-domain-intelligence \
  -f infra/domain-intelligence/exported-arm-YYYYMMDD.json

# ...or this reconstructed stash (verify the [VERIFY] fields first):
az deployment group create \
  -g rg-htt-domain-intelligence \
  -f infra/domain-intelligence/main.bicep \
  -p infra/domain-intelligence/main.parameters.json \
  -p postgresAdminPassword='<set-at-deploy-time>'
```

Then redeploy the app code and restore the PostgreSQL dump from step 3.

---

## ct-mql closing checklist

- [ ] Step 1 — `az group export` committed (or consciously skipped)
- [ ] Step 2 — full `az resource list` inventory reviewed; Cosmos accounted for
- [ ] Step 3 — final PG backup taken (or consciously skipped — data abandoned)
- [ ] Delete — `az group delete` (or piecemeal) completed
- [ ] Verify — `az group show -n rg-htt-domain-intelligence` returns *not found*
- [ ] Cost — confirm next invoice drops by ~$65/mo for this RG
- [ ] Remove or `--defer` the recurring `scripts/check-domain-intelligence-traffic.sh`
      reminder — it's moot once the resources are gone
- [ ] `bd close ct-mql` with a link to this directory + the delete confirmation

> Once deleted, `scripts/check-domain-intelligence-traffic.sh` will error (no
> such resource). That's expected — it can be removed in the same PR that closes
> ct-mql, or left as a tombstone with a comment pointing here.
