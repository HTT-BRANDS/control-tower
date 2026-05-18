# Local deployment smoke evidence

Environment: `ENVIRONMENT=development DATABASE_URL=sqlite:///./data/local-dev.db`

Unauthenticated public endpoints plus authenticated cookie/session protected page/API smoke.

- PASS GET /health: status=200 bytes=66
- PASS GET /health/detailed: status=200 bytes=366
- PASS GET /openapi.json: status=200 bytes=252649
- PASS GET /docs: status=200 bytes=948
- PASS GET / root redirect: status=307 bytes=0
- PASS GET /login: status=200 bytes=15956
- PASS POST /api/v1/auth/login cookie contract: status=200 bytes=73
- PASS GET /dashboard authenticated page: status=200 bytes=44815
- PASS GET /costs authenticated page: status=200 bytes=38396
- PASS GET /compliance authenticated page: status=200 bytes=36246
- PASS GET /resources authenticated page: status=200 bytes=38180
- PASS GET /identity authenticated page: status=200 bytes=37544
- PASS GET /sync-dashboard authenticated page: status=200 bytes=36649
- PASS GET /riverside authenticated page: status=200 bytes=53423
- PASS GET /dmarc authenticated page: status=200 bytes=61137
- PASS GET /api/v1/costs/summary authenticated API: status=200 bytes=1173
- PASS GET /api/v1/costs/by-tenant authenticated API: status=200 bytes=770
- PASS GET /api/v1/compliance/summary authenticated API: status=200 bytes=2991
- PASS GET /api/v1/compliance/scores authenticated API: status=200 bytes=1734
- PASS GET /api/v1/resources authenticated API: status=200 bytes=190927
- PASS GET /api/v1/resources/idle authenticated API: status=200 bytes=16915
- PASS GET /api/v1/identity/summary authenticated API: status=200 bytes=1348
- PASS GET /api/v1/identity/privileged authenticated API: status=200 bytes=17072
- PASS GET /api/v1/riverside/summary authenticated API: status=200 bytes=14257
- PASS GET /api/v1/riverside/maturity-scores authenticated API: status=200 bytes=149
- PASS GET /api/v1/dmarc/summary authenticated API: status=200 bytes=4081
- PASS GET /api/v1/dmarc/trends?days=30 authenticated API: status=200 bytes=3898
