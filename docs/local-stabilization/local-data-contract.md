# Local Data Contract

> Owner: Tyler + Richard (`code-puppy-1c7422`)  
> Bead: `ct-dag`  
> Purpose: define the minimum local seeded data required before trusting UI/API data-fetching behavior.

## Command contract

The local data flow intentionally uses a dedicated SQLite database so reset/seed cannot accidentally drop a cloud or production database.

```bash
make local-db-reset
make local-seed
make local-data-smoke
```

Combined:

```bash
make local-reset-seed-smoke
```

Local DB path:

```text
data/local-dev.db
```

Environment used by Make targets:

```bash
ENVIRONMENT=development
DATABASE_URL=sqlite:///./data/local-dev.db
```

## Safety rules

1. Local reset removes only `data/local-dev.db` and SQLite sidecar files.
2. Seed uses the existing comprehensive `scripts/seed_data.py --force` against that dedicated local SQLite DB.
3. `scripts/local_data_smoke.py` refuses to run against non-SQLite databases unless `--allow-non-sqlite` is explicitly passed.
4. This flow must not require Azure credentials.

## Seed source

Current seed source:

```bash
scripts/seed_data.py
```

It creates representative demo data for:

- HTT Brands Corporate
- Bishops Cuts & Color
- Frenchies Modern Nail Care
- The Lash Lounge
- Delta Crown Enterprises

## Minimum smoke thresholds

`make local-data-smoke` validates these minimums:

| Surface | Model/table area | Minimum |
|---|---:|---:|
| Tenants | `Tenant` | 5 |
| Tenants | `Subscription` | 10 |
| Tenants | `BrandConfig` | 5 |
| Costs | `CostSnapshot` | 300 |
| Costs | `CostAnomaly` | 1 |
| Compliance | `ComplianceSnapshot` | 150 |
| Compliance | `PolicyState` | 40 |
| Resources | `Resource` | 100 |
| Resources | `ResourceTag` | 200 |
| Resources | `IdleResource` | 10 |
| Identity | `IdentitySnapshot` | 150 |
| Identity | `PrivilegedUser` | 20 |
| Sync | `SyncJob` | 100 |
| Sync | `SyncJobLog` | 100 |
| Sync | `SyncJobMetrics` | 4 |
| Sync | `Alert` | 1 |
| Recommendations | `Recommendation` | 15 |
| DMARC | `DMARCRecord` | 8 |
| DMARC | `DKIMRecord` | 8 |
| DMARC | `DMARCReport` | 200 |
| DMARC | `DMARCAlert` | 1 |
| Riverside | `RiversideCompliance` | 5 |
| Riverside | `RiversideMFA` | 5 |
| Riverside | `RiversideDeviceCompliance` | 5 |
| Riverside | `RiversideThreatData` | 5 |
| Riverside | `RiversideRequirement` | 150 |
| Authz | `UserTenant` | 20 |

## Product-surface mapping

| Product surface | Seeded data source | Current local status |
|---|---|---|
| Dashboard | Costs, compliance, resources, identity, sync summaries | Seed-backed |
| Costs | `CostSnapshot`, `CostAnomaly` | Seed-backed |
| Compliance | `ComplianceSnapshot`, `PolicyState` | Seed-backed |
| Resources | `Resource`, `ResourceTag`, `IdleResource`, `Recommendation` | Seed-backed |
| Identity | `IdentitySnapshot`, `PrivilegedUser` | Seed-backed |
| Sync dashboard | `SyncJob`, `SyncJobLog`, `SyncJobMetrics`, `Alert` | Seed-backed |
| DMARC | `DMARCRecord`, `DKIMRecord`, `DMARCReport`, `DMARCAlert` | Seed-backed |
| Riverside | `RiversideCompliance`, `RiversideMFA`, `RiversideDeviceCompliance`, `RiversideThreatData`, `RiversideRequirement` | Seed-backed |
| Auth/dev harness | `UserTenant` mappings for Tyler + demo users | Seed-backed |

## Known limitations

1. The seed is deterministic in shape and thresholds, but many row IDs use generated UUIDs.
2. This smoke validates data availability, not that every UI component renders every seeded value.
3. Full page-level data assertions belong in `ct-1aq` Playwright local data-fetching flows.
4. Surface-by-surface route/template/API mapping belongs in `ct-80e`.

## Close evidence

Validated on 2026-05-17:

```text
make local-reset-seed-smoke
  ✅ Expected HTT/BCC/FN/TLL/DCE tenants are present.
  ✅ 27 smoke checks passed
  ❌ 0 smoke checks failed

make local-gate
  ✅ doctor passed: 9 pass, 0 warn, 0 fail
  ✅ ruff check app tests scripts
  ✅ ruff format --check app tests scripts
  ✅ unit suite: 3656 passed
  ✅ integration suite: 403 passed
  ✅ browser/accessibility E2E: 19 passed
  ✅ axe accessibility file: 17 skipped, tracked separately
  ✅ local reset/seed/smoke: 27 passed, 0 failed
```
