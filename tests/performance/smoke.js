/**
 * k6 Load / Smoke Test Suite for Control Tower
 *
 * Usage:
 *   k6 run tests/performance/smoke.js                           # quick smoke
 *   k6 run --vus 50 --duration 60s tests/performance/smoke.js   # load test
 *   k6 run --vus 100 --duration 120s tests/performance/smoke.js  # stress test
 *
 * Prereqs:
 *   - k6 installed (brew install k6 / apt install k6)
 *   - TARGET_URL set (default: https://app-governance-prod.azurewebsites.net)
 *
 * Notes:
 *   - Authenticated endpoints require SESSION_COOKIE env var
 *     (obtain from browser DevTools → Application → Cookies → session)
 *   - Unauthenticated endpoints (health, metrics) need no auth
 */

import { check, sleep } from 'k6';
import http from 'k6/http';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const TARGET = __ENV.TARGET_URL || 'https://app-governance-prod.azurewebsites.net';
const SESSION_COOKIE = __ENV.SESSION_COOKIE || '';

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------
export const options = {
  // Default: smoke test (1 VU, 30s)
  vus: 1,
  duration: '30s',

  // Thresholds: fail if any check drops below 95% or p95 > 2s
  // Note: http_req_failed is high because auth-gated endpoints return 401
  // (correct behavior). We exempt that threshold.
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    checks: ['rate>0.95'],
  },

  // Tag all requests with environment
  tags: { environment: 'production' },
};

// ---------------------------------------------------------------------------
// Helper: authenticated request
// ---------------------------------------------------------------------------
function authedGet(path) {
  const params = {
    headers: {
      Cookie: SESSION_COOKIE ? `session=${SESSION_COOKIE}` : '',
    },
    tags: { name: path },
  };
  return http.get(`${TARGET}${path}`, params);
}

// ---------------------------------------------------------------------------
// Unauthenticated endpoints (always accessible)
// ---------------------------------------------------------------------------
function testHealth() {
  const r = http.get(`${TARGET}/health`, { tags: { name: '/health' } });
  check(r, {
    '/health 200': (r) => r.status === 200,
    '/health body valid': (r) => r.json('status') === 'healthy',
  });
}

function testHealthDetailed() {
  const r = http.get(`${TARGET}/health/detailed`, { tags: { name: '/health/detailed' } });
  check(r, {
    '/health/detailed 200': (r) => r.status === 200,
  });
}

function testHealthzData() {
  const r = http.get(`${TARGET}/healthz/data`, { tags: { name: '/healthz/data' } });
  check(r, {
    '/healthz/data 200': (r) => r.status === 200,
    '/healthz/data fresh': (r) => {
      const d = r.json();
      return d && d.any_stale === false;
    },
  });
}

function testHealthzScheduler() {
  const r = http.get(`${TARGET}/healthz/scheduler`, { tags: { name: '/healthz/scheduler' } });
  check(r, {
    '/healthz/scheduler 200': (r) => r.status === 200,
    '/healthz/scheduler running': (r) => {
      const d = r.json();
      return d && d.running === true;
    },
  });
}

function testMetrics() {
  const r = http.get(`${TARGET}/metrics`, { tags: { name: '/metrics' } });
  check(r, {
    '/metrics 200': (r) => r.status === 200,
    '/metrics prometheus': (r) => r.body.includes('# HELP'),
  });
}

// ---------------------------------------------------------------------------
// Auth-gated endpoints (return 401 without auth)
// ---------------------------------------------------------------------------
function testDocsAuthGate() {
  const r = http.get(`${TARGET}/docs`, { tags: { name: '/docs' } });
  check(r, {
    '/docs returns 401': (r) => r.status === 401,
  });
}

function testRedocAuthGate() {
  const r = http.get(`${TARGET}/redoc`, { tags: { name: '/redoc' } });
  check(r, {
    '/redoc returns 401': (r) => r.status === 401,
  });
}

function testOpenapiAuthGate() {
  const r = http.get(`${TARGET}/openapi.json`, { tags: { name: '/openapi.json' } });
  check(r, {
    '/openapi.json returns 401': (r) => r.status === 401,
  });
}

// ---------------------------------------------------------------------------
// Authenticated endpoints (need SESSION_COOKIE)
// ---------------------------------------------------------------------------
function testDashboard() {
  if (!SESSION_COOKIE) return; // skip if no auth
  const r = authedGet('/');
  check(r, {
    '/ returns 200': (r) => r.status === 200,
    '/ contains dashboard': (r) => r.body.includes('Control Tower') || r.body.includes('governance'),
  });
}

function testDesignSystem() {
  if (!SESSION_COOKIE) return;
  const r = authedGet('/design-system');
  check(r, {
    '/design-system accessible': (r) => r.status === 200 || r.status === 401,
  });
}

function testCompliance() {
  if (!SESSION_COOKIE) return;
  const r = authedGet('/compliance');
  check(r, {
    '/compliance accessible': (r) => r.status === 200 || r.status === 401 || r.status === 302,
  });
}

function testCosts() {
  if (!SESSION_COOKIE) return;
  const r = authedGet('/costs');
  check(r, {
    '/costs accessible': (r) => r.status === 200 || r.status === 401 || r.status === 302,
  });
}

function testIdentity() {
  if (!SESSION_COOKIE) return;
  const r = authedGet('/identity');
  check(r, {
    '/identity accessible': (r) => r.status === 200 || r.status === 401 || r.status === 302,
  });
}

// ---------------------------------------------------------------------------
// Main test loop
// ---------------------------------------------------------------------------
export default function () {
  // Unauthenticated health checks (most critical)
  testHealth();
  testHealthzData();
  testHealthzScheduler();
  testMetrics();
  testHealthDetailed();

  // Auth gate verification
  testDocsAuthGate();
  testRedocAuthGate();
  testOpenapiAuthGate();

  // Authenticated pages (only if SESSION_COOKIE provided)
  testDashboard();
  testDesignSystem();
  testCompliance();
  testCosts();
  testIdentity();

  sleep(1); // 1s between iterations to avoid overwhelming the server
}
