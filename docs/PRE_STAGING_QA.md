# Pre-Staging QA Checklist

## Must Pass Before Staging Deployment

### 1. Dev Environment Health ✅/❌
- [ ] Health endpoint returns 200 with JSON
- [ ] Detailed health shows all green
- [ ] Response time < 2 seconds
- [ ] No 5xx errors in last hour

### 2. API Endpoints ✅/❌
- [ ] All 100+ endpoints respond correctly
- [ ] Authentication working (OAuth2/JWT)
- [ ] Rate limiting active
- [ ] CORS configured

### 3. Database & Sync ✅/❌
- [ ] Database connections stable
- [ ] All sync jobs running (cost, compliance, identity, resources)
- [ ] No sync failures in last 24h
- [ ] Data integrity verified

### 4. Riverside Tenants ✅/❌
- [ ] All 4 tenants configured (HTT, BCC, FN, TLL)
- [ ] Graph API connectivity verified
- [ ] DMARC/DKIM data collection working
- [ ] MFA compliance tracking accurate

### 5. Security ✅/❌
- [ ] No secrets exposed in logs/responses
- [ ] HTTPS enforced
- [ ] Security headers present
- [ ] Vulnerability scan clean

### 6. Performance ✅/❌
- [ ] p95 response time < 2s
- [ ] Database query time < 500ms
- [ ] Memory usage < 1GB
- [ ] CPU usage < 70%

### 7. Documentation ✅/❌
- [ ] Runbook complete
- [ ] Rollback procedures tested
- [ ] Monitoring configured
- [ ] Alerting active

## Sign-Off Required
- [ ] QA Lead: ________________ Date: _______
- [ ] Security Lead: __________ Date: _______
- [ ] DevOps Lead: ___________ Date: _______
- [ ] Product Owner: _________ Date: _______
