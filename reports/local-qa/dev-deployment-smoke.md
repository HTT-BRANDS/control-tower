# Development deployment smoke evidence

Target: `https://app-governance-dev-001.azurewebsites.net`


- PASS GET /health: status=200 bytes=66
- PASS GET /health/detailed: status=200 bytes=366
- PASS GET /openapi.json: status=200 bytes=248532
- PASS GET /docs: status=200 bytes=948
- PASS GET / root redirect: status=307 bytes=0
- PASS GET /login: status=200 bytes=15956
- PASS GET /dashboard protected route no-500: status=302 bytes=0
- PASS GET /costs protected route no-500: status=302 bytes=0
- PASS GET /compliance protected route no-500: status=302 bytes=0
- PASS GET /resources protected route no-500: status=302 bytes=0
- PASS GET /identity protected route no-500: status=302 bytes=0
- PASS GET /sync-dashboard protected route no-500: status=302 bytes=0
- PASS GET /riverside protected route no-500: status=302 bytes=0
- PASS GET /dmarc protected route no-500: status=302 bytes=0

Health status: `healthy`; environment: `development`; version: `2.5.0`
