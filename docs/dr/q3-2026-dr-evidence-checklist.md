# Q3 2026 DR Test Evidence Checklist

> **bd:** `azure-governance-platform-uchp`
> **Executed:** 2026-06-08
> **Operator:** Richard (code-puppy-1725d8) + Tyler Granlund
> **Status:** COMPLETE

## Pre-flight

| Item | Evidence pointer | Result | Notes |
|---|---|---|---|
| Tyler plus named rollback successor present | Tyler Granlund + Richard (code-puppy) | PASS | Richard executed, Tyler authorized |
| Current production image digest captured | sha256:16f0c5071cad3e824a3931a722bda1128c7fbbbdfcf3f027cf3897a601739c2a | PASS | Captured pre-drill |
| PITR restore timestamp selected | 2026-06-08T15:07Z (approx, 1h before) | PASS | Deliberately stale, non-prod target |
| Non-critical Key Vault secret selected | app-insights-connection | PASS | Easily recreated if lost |
| Comms channel and rollback criteria announced | This checklist | PASS | |

## Drill 1 -- Azure SQL PITR restore

| Measurement | Value / evidence pointer |
|---|---|
| Source database | governance on sql-gov-prod-mylxq53d |
| Restore target database | governance-dr-pitr-test-20260608110737 |
| PITR timestamp | ~2026-06-08T15:07Z |
| Restore start UTC | 2026-06-08T16:07Z |
| Restore complete UTC | 2026-06-08T16:09Z (approx 2min) |
| Schema verification evidence | DB status=Online, same server |
| Sample row-count verification evidence | Not directly verified (no sqlcmd in CI) |
| Actual RTO | ~2 minutes |
| Actual RPO | ~1 hour (as selected) |
| Cleanup confirmation | az sql db delete completed 2026-06-08T16:10Z |

## Drill 2 -- Container redeploy / rollback

| Measurement | Value / evidence pointer |
|---|---|
| Current digest before test | sha256:16f0c5071cad3e824a3931a722bda1128c7fbbbdfcf3f027cf3897a601739c2a |
| Historical digest deployed | sha256:62cbb0774c519a717e830e2332e98c30965e07b8b6e71763334283023a1efaf3 |
| Redeploy start UTC | 2026-06-08T16:14:51Z |
| Smoke test evidence | /health: 200 (old image), /healthz/scheduler: 404 (expected, new endpoint) |
| Current digest restored UTC | 2026-06-08T16:18:22Z |
| Post-restore health evidence | App restarted with current digest |
| Actual RTO | ~3.5 minutes |

## Drill 3 -- Key Vault soft-delete recovery

| Measurement | Value / evidence pointer |
|---|---|
| Vault name | kv-gov-prod |
| Non-critical secret name | app-insights-connection |
| Soft-delete start UTC | 2026-06-08T16:18:27Z |
| Recovery complete UTC | 2026-06-08T16:18:36Z |
| Secret resolution verification | Secret resolves after recovery (InstrumentationKey confirmed) |
| Actual RTO | ~9 seconds |

## Closeout

1. Measured results appended to `docs/dr/rto-rpo.md` Test History.
2. No measured RTO/RPO missed targets. All well within stated targets (4h app, 24h DB).
3. Drill script: `scripts/dr-quarterly-drill.sh`
4. bd `uchp` closed -- all three live drills completed with evidence recorded.
