/**
 * k6 Load Test: PATCH /products/{id} - Cache Invalidation
 *
 * Objectifs:
 * - Vérifier invalidation cache après PATCH
 * - Mesurer impact invalidation sur latence
 * - Tester throughput mutations (PATCH)
 *
 * Usage:
 *   k6 run tests/load/patch_products_invalidation.js
 *
 * Scénario:
 * 1. GET product (cache MISS → rempli)
 * 2. GET product (cache HIT)
 * 3. PATCH product → invalidation
 * 4. GET product (cache MISS → re-rempli)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// Métriques custom
const cacheInvalidations = new Counter('cache_invalidations');
const patchLatency = new Trend('patch_latency');
const getAfterPatchLatency = new Trend('get_after_patch_latency');

// Configuration
export const options = {
  stages: [
    { duration: '30s', target: 10 },  // Warm-up
    { duration: '60s', target: 20 },  // Load test
    { duration: '10s', target: 0 },   // Cool down
  ],

  thresholds: {
    // PATCH latency < 100ms (avec invalidation cache)
    'patch_latency': ['p(99)<100'],

    // GET après PATCH < 20ms (cache MISS + re-fill)
    'get_after_patch_latency': ['p(99)<20'],

    // Taux de succès > 95%
    'http_req_failed': ['rate<0.05'],
  },
};

// Config API
const BASE_URL = __ENV.API_URL || 'http://localhost:8001';

export function setup() {
  console.log('🔧 Setup: Authentification...');

  const loginRes = http.post(`${BASE_URL}/api/v1/auth/login`, {
    username: 'admin@carocorp.com',
    password: 'admin123',
  });

  if (loginRes.status !== 200) {
    throw new Error(`Login failed: ${loginRes.status}`);
  }

  const token = loginRes.json('access_token');
  const csrfToken = loginRes.headers['X-Csrf-Token'] || '';

  console.log('✅ Token obtained');

  return { token, csrfToken };
}

export default function(data) {
  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'X-CSRF-Token': data.csrfToken,
    'Content-Type': 'application/json',
  };

  const productId = 1; // Produit fixe pour ce test

  // Étape 1: GET product (peut être cache HIT ou MISS)
  const getRes1 = http.get(`${BASE_URL}/api/v1/products/${productId}`, { headers });
  check(getRes1, {
    'GET #1 status 200': (r) => r.status === 200,
  });

  sleep(0.1);

  // Étape 2: PATCH product (invalidation cache)
  const patchPayload = JSON.stringify({
    name: `Product Updated ${Date.now()}`,
  });

  const patchRes = http.patch(
    `${BASE_URL}/api/v1/products/${productId}`,
    patchPayload,
    { headers }
  );

  check(patchRes, {
    'PATCH status 200': (r) => r.status === 200,
    'PATCH has name': (r) => r.json('name') !== undefined,
  });

  patchLatency.add(patchRes.timings.duration);

  if (patchRes.status === 200) {
    cacheInvalidations.add(1);
  }

  sleep(0.1);

  // Étape 3: GET product après PATCH (cache MISS → re-fill)
  const getRes2 = http.get(`${BASE_URL}/api/v1/products/${productId}`, { headers });
  check(getRes2, {
    'GET #2 status 200': (r) => r.status === 200,
    'GET #2 name updated': (r) => r.json('name').includes('Updated'),
  });

  getAfterPatchLatency.add(getRes2.timings.duration);

  sleep(0.5);
}

export function handleSummary(data) {
  const patchP99 = data.metrics.patch_latency?.values['p(99)'] || 0;
  const getP99 = data.metrics.get_after_patch_latency?.values['p(99)'] || 0;
  const invalidations = data.metrics.cache_invalidations?.values?.count || 0;

  console.log('\n📊 Résumé Cache Invalidation:');
  console.log(`   Total invalidations: ${invalidations}`);
  console.log(`   PATCH latency p99: ${patchP99.toFixed(2)}ms`);
  console.log(`   GET après PATCH p99: ${getP99.toFixed(2)}ms`);

  const objectives = {
    'PATCH p99 < 100ms': patchP99 < 100,
    'GET après PATCH p99 < 20ms': getP99 < 20,
  };

  console.log('\n✅ Objectifs:');
  for (const [name, passed] of Object.entries(objectives)) {
    console.log(`   ${passed ? '✅' : '❌'} ${name}`);
  }

  return {
    'stdout': JSON.stringify(data, null, 2),
    'summary_invalidation.json': JSON.stringify(data),
  };
}
