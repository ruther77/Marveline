/**
 * k6 Load Test: GET /products/{id} - Cache Performance
 *
 * Objectifs:
 * - Latence p50 < 10ms (cache HIT)
 * - Latence p99 < 50ms (cache HIT)
 * - Throughput > 1000 req/s (cache warm)
 * - Hit rate > 80% après warm-up
 *
 * Usage:
 *   k6 run tests/load/get_products_cache.js
 *
 * Phases:
 * 1. Warm-up (30s) : 10 VUs → remplir cache
 * 2. Load Test (60s) : 50 VUs → mesurer performance cache
 * 3. Spike Test (30s) : 200 VUs → tester scalabilité
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Métriques custom
const cacheHits = new Counter('cache_hits');
const cacheMisses = new Counter('cache_misses');
const cacheHitRate = new Rate('cache_hit_rate');
const latencyCacheHit = new Trend('latency_cache_hit');
const latencyCacheMiss = new Trend('latency_cache_miss');

// Configuration
export const options = {
  stages: [
    // Phase 1: Warm-up (remplir cache)
    { duration: '30s', target: 10 },

    // Phase 2: Load test (mesurer performance)
    { duration: '60s', target: 50 },

    // Phase 3: Spike test (scalabilité)
    { duration: '30s', target: 200 },

    // Phase 4: Cool down
    { duration: '10s', target: 0 },
  ],

  thresholds: {
    // Latence p50 < 10ms (cache warm)
    'http_req_duration{scenario:cache_warm}': ['p(50)<10', 'p(99)<50'],

    // Taux de succès > 95%
    'http_req_failed': ['rate<0.05'],

    // Cache hit rate > 80%
    'cache_hit_rate': ['rate>0.8'],

    // Throughput > 1000 req/s
    'http_reqs': ['rate>1000'],
  },
};

// Config API
const BASE_URL = __ENV.API_URL || 'http://localhost:8001';
const API_TOKEN = __ENV.API_TOKEN || '';

// Pool de product IDs (10 produits pour simuler cache réutilisable)
const PRODUCT_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

export function setup() {
  console.log('🔧 Setup: Authentification...');

  // Login pour obtenir token
  const loginRes = http.post(`${BASE_URL}/api/v1/auth/login`, {
    username: 'admin@carocorp.com',
    password: 'admin123',
  });

  if (loginRes.status !== 200) {
    throw new Error(`Login failed: ${loginRes.status}`);
  }

  const token = loginRes.json('access_token');
  console.log('✅ Token obtained');

  return { token };
}

export default function(data) {
  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'Content-Type': 'application/json',
  };

  // Sélectionner un product ID aléatoire (favorise cache HITs)
  const productId = PRODUCT_IDS[Math.floor(Math.random() * PRODUCT_IDS.length)];

  // GET /products/{id}
  const res = http.get(`${BASE_URL}/api/v1/products/${productId}`, { headers });

  // Vérifications
  const success = check(res, {
    'status 200': (r) => r.status === 200,
    'has name': (r) => r.json('name') !== undefined,
    'response time < 50ms': (r) => r.timings.duration < 50,
  });

  // Déterminer si cache HIT ou MISS
  // (Heuristique: < 5ms = HIT, > 5ms = MISS)
  const isCacheHit = res.timings.duration < 5;

  if (isCacheHit) {
    cacheHits.add(1);
    cacheHitRate.add(true);
    latencyCacheHit.add(res.timings.duration);
  } else {
    cacheMisses.add(1);
    cacheHitRate.add(false);
    latencyCacheMiss.add(res.timings.duration);
  }

  // Think time (simuler utilisateur réel)
  sleep(0.1);
}

export function teardown(data) {
  console.log('🧹 Teardown: Nettoyage...');
}

export function handleSummary(data) {
  const cacheHitRateValue = data.metrics.cache_hit_rate?.values?.rate || 0;
  const p50 = data.metrics.http_req_duration?.values['p(50)'] || 0;
  const p99 = data.metrics.http_req_duration?.values['p(99)'] || 0;
  const throughput = data.metrics.http_reqs?.values?.rate || 0;

  console.log('\n📊 Résumé Performance Cache:');
  console.log(`   Cache Hit Rate: ${(cacheHitRateValue * 100).toFixed(1)}%`);
  console.log(`   Latence p50: ${p50.toFixed(2)}ms`);
  console.log(`   Latence p99: ${p99.toFixed(2)}ms`);
  console.log(`   Throughput: ${throughput.toFixed(0)} req/s`);

  // Validation objectifs
  const objectives = {
    'Cache Hit Rate > 80%': cacheHitRateValue > 0.8,
    'Latence p50 < 10ms': p50 < 10,
    'Latence p99 < 50ms': p99 < 50,
    'Throughput > 1000 req/s': throughput > 1000,
  };

  console.log('\n✅ Objectifs:');
  for (const [name, passed] of Object.entries(objectives)) {
    console.log(`   ${passed ? '✅' : '❌'} ${name}`);
  }

  return {
    'stdout': JSON.stringify(data, null, 2),
    'summary.json': JSON.stringify(data),
  };
}
