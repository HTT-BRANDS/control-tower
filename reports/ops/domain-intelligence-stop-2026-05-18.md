# Domain Intelligence zero-traffic stop evidence

Captured: 2026-05-18T16:10Z

Bead: `azure-governance-platform-rtwi`

## Decision

Stop `domain-intelligence-prod` App Service and pause `domainiq-db-prod`
PostgreSQL flexible server after zero traffic remained confirmed at the 60-day
follow-up mark.

## Dry-run validation

Command:

```bash
./scripts/check-domain-intelligence-traffic.sh
```

Result:

```text
Total requests in last 30 days: 0
Zero traffic confirmed in the last 30 days.
DRY-RUN MODE — no action taken.
```

## Stop command

Command:

```bash
./scripts/check-domain-intelligence-traffic.sh --force-stop
```

Result:

```text
Total requests in last 30 days: 0
Zero traffic confirmed in the last 30 days.
App Service stopped.
PostgreSQL paused.
```

The script exited with code `2`, which is its documented success code for
"zero traffic confirmed + resources stopped".

## Post-stop verification

```json
{
  "appService": {
    "name": "domain-intelligence-prod",
    "state": "Stopped",
    "defaultHostName": "domain-intelligence-prod.azurewebsites.net"
  },
  "postgresFlexibleServer": {
    "name": "domainiq-db-prod",
    "state": "Stopped",
    "sku": "Standard_B1ms",
    "version": "16"
  }
}
```

## Resume commands

```bash
az webapp start \
  --resource-group rg-htt-domain-intelligence \
  --name domain-intelligence-prod

az postgres flexible-server start \
  --resource-group rg-htt-domain-intelligence \
  --name domainiq-db-prod
```

## Follow-up note

Azure PostgreSQL Flexible Server may auto-start after 7 days. If the service
should remain paused, re-run the traffic check and stop flow after confirming
continued zero traffic. Cloud platforms simply cannot resist being helpful in
the most annoying possible way.
