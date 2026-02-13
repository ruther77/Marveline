/**
 * k6 Load Test: Mixed Workload - Scénario Réaliste
 *
 * Ratio: 90% GET (read) / 10% PATCH (write)
 * Simule un workload production typique
 *
 * Objectifs:
 * - Hit rate stable > 80% malgré invalidations
 * - Latence p99 < 50ms (mix GET/PATCH)
 * - Throughput > 800 req/s
 *
 * Usage:
 *   k6 run tests/load/mixed_workload.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Métriques custom
const getRequests = new Counter('get_requests');
const patchRequests = new Counter('patch_requests');
const cacheHitRate = new Rate('cache_hit_rate');
const getLatency = new Trend('get_latency');
const patchLatency = new Trend('patch_latency');

// Configuration
export const options = {
  stages: [
    { duration: '20s', target: 20 },   // Ramp-up
    { duration: '120s', target: 50 },  // Sustained load
    { duration: '20s', target: 100 },  // Spike
    { duration: '10s', target: 0 },    // Cool down
  ],

  thresholds: {
    'http_req_duration': ['p(95)<50', 'p(99)<100'],
    'http_req_failed': ['rate<0.05'],
    'cache_hit_rate': ['rate>0.80'],
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8001';
const PRODUCT_IDS = Array.from({length: 20}, (_, i) => i + 1);

export function setup() {
  const loginRes = http.post(`${BASE_URL}/api/v1/auth/login`, {
    username: 'admin@carocorp.com',
    password: 'admin123',
  });

  if (loginRes.status !== 200) {
    throw new Error(`Login failed: ${loginRes.status}`);
  }

  const token = loginRes.json('access_token');
  const csrfToken = loginRes.headers['X-Csrf-Token'] || '';

  return { token, csrfToken };
}

export default function(data) {
  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'X-CSRF-Token': data.csrfToken,
    'Content-Type': 'application/json',
  };

  const productId = PRODUCT_IDS[Math.floor(Math.random() * PRODUCT_IDS.length)];

  // 90% GET, 10% PATCH
  const isWrite = Math.random() < 0.1;

  if (isWrite) {
    // PATCH request (write)
    const patchPayload = JSON.stringify({
      price_per_day_cents: Math.floor(Math.random() * 1000) + 100,
    });

    const res = http.patch(
      `${BASE_URL}/api/v1/products/${productId}`,
      patchPayload,
      { headers }
    );

    check(res, { 'PATCH 200': (r) => r.status === 200 });
    patchRequests.add(1);
    patchLatency.add(res.timings.duration);

  } else {
    // GET request (read)
    const res = http.get(`${BASE_URL}/api/v1/products/${productId}`, { headers });

    check(res, { 'GET 200': (r) => r.status === 200 });
    getRequests.add(1);
    getLatency.add(res.timings.duration);

    // Heuristique cache HIT/MISS
    const isCacheHit = res.timings.duration < 5;
    cacheHitRate.add(isCacheHit);
  }

  sleep(Math.random() * 0.3); // Variable think time
}

export function handleSummary(data) {
  const hitRate = data.metrics.cache_hit_rate?.values?.rate || 0;
  const getCount = data.metrics.get_requests?.values?.count || 0;
  const patchCount = data.metrics.patch_requests?.values?.count || 0;
  const p95 = data.metrics.http_req_duration?.values['p(95)'] || 0;
  const p99 = data.metrics.http_req_duration?.values['p(99)'] || 0;

  console.log('\n📊 Mixed Workload Summary:');
  console.log(`   Total requests: ${getCount + patchCount}`);
  console.log(`   GET: ${getCount} (${((getCount/(getCount+patchCount))*100).toFixed(1)}%)`);
  console.log(`   PATCH: ${patchCount} (${((patchCount/(getCount+patchCount))*100).toFixed(1)}%)`);
  console.log(`   Cache Hit Rate: ${(hitRate * 100).toFixed(1)}%`);
  console.log(`   Latency p95: ${p95.toFixed(2)}ms`);
  console.log(`   Latency p99: ${p99.toFixed(2)}ms`);

  const objectives = {
    'Hit Rate > 80%': hitRate > 0.8,
    'p95 < 50ms': p95 < 50,
    'p99 < 100ms': p99 < 100,
  };

  console.log('\n✅ Objectifs:');
  for (const [name, passed] of Object.entries(objectives)) {
    console.log(`   ${passed ? '✅' : '❌'} ${name}`);
  }

  return {
    'summary_mixed.json': JSON.stringify(data),
  };
}
