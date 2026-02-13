/**
 * k6 Load Test: Multi-Tenant Isolation
 *
 * Objectifs:
 * - Vérifier isolation cache entre tenants sous charge
 * - Pas de cache leak cross-tenant
 * - Performance stable par tenant
 *
 * Usage:
 *   k6 run tests/load/multi_tenant_isolation.js
 *
 * Scénario:
 * - 2 tenants avec tokens différents
 * - Chaque VU utilise un tenant aléatoire
 * - Vérifier que tenant A ne voit jamais données tenant B
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate } from 'k6/metrics';

// Métriques custom
const tenant1Requests = new Counter('tenant1_requests');
const tenant2Requests = new Counter('tenant2_requests');
const crossTenantLeaks = new Counter('cross_tenant_leaks');
const isolationRate = new Rate('isolation_rate');

// Configuration
export const options = {
  stages: [
    { duration: '30s', target: 30 },  // 15 VUs par tenant
    { duration: '60s', target: 60 },  // 30 VUs par tenant
    { duration: '10s', target: 0 },
  ],

  thresholds: {
    // Zéro cross-tenant leak toléré
    'cross_tenant_leaks': ['count==0'],

    // Isolation parfaite (100%)
    'isolation_rate': ['rate==1'],

    // Performance stable
    'http_req_duration': ['p(99)<100'],
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8001';

export function setup() {
  console.log('🔧 Setup: Authentification multi-tenant...');

  // Tenant 1
  const loginRes1 = http.post(`${BASE_URL}/api/v1/auth/login`, {
    username: 'admin@carocorp.com',
    password: 'admin123',
  });

  // Tenant 2 (si existe)
  const loginRes2 = http.post(`${BASE_URL}/api/v1/auth/login`, {
    username: 'tenant2@carocorp.com',
    password: 'tenant2pass',
  });

  const tenant1Token = loginRes1.status === 200 ? loginRes1.json('access_token') : null;
  const tenant2Token = loginRes2.status === 200 ? loginRes2.json('access_token') : null;

  console.log(`✅ Tenant 1 token: ${tenant1Token ? 'OK' : 'FAIL'}`);
  console.log(`✅ Tenant 2 token: ${tenant2Token ? 'OK (using fallback)' : 'FAIL (using tenant1)'}`);

  return {
    tenants: [
      {
        id: 1,
        token: tenant1Token,
        productIds: [1, 2, 3, 4, 5],
      },
      {
        id: 2,
        token: tenant2Token || tenant1Token, // Fallback si tenant2 n'existe pas
        productIds: [6, 7, 8, 9, 10],
      },
    ],
  };
}

export default function(data) {
  // Sélectionner tenant aléatoire
  const tenant = data.tenants[Math.floor(Math.random() * data.tenants.length)];

  const headers = {
    'Authorization': `Bearer ${tenant.token}`,
    'Content-Type': 'application/json',
  };

  // GET produit du tenant
  const productId = tenant.productIds[Math.floor(Math.random() * tenant.productIds.length)];
  const res = http.get(`${BASE_URL}/api/v1/products/${productId}`, { headers });

  // Vérifications
  const success = check(res, {
    'status 200': (r) => r.status === 200,
    'has tenant_id': (r) => r.json('tenant_id') !== undefined,
  });

  if (success && res.status === 200) {
    const responseTenantId = res.json('tenant_id');

    // Vérifier isolation (tenant_id de la réponse doit matcher le tenant actuel)
    const isIsolated = responseTenantId === tenant.id;

    if (isIsolated) {
      isolationRate.add(true);
    } else {
      isolationRate.add(false);
      crossTenantLeaks.add(1);
      console.error(`❌ CROSS-TENANT LEAK: VU requested tenant ${tenant.id}, got tenant ${responseTenantId}`);
    }

    // Compter requests par tenant
    if (tenant.id === 1) {
      tenant1Requests.add(1);
    } else {
      tenant2Requests.add(1);
    }
  }

  sleep(0.2);
}

export function handleSummary(data) {
  const tenant1Count = data.metrics.tenant1_requests?.values?.count || 0;
  const tenant2Count = data.metrics.tenant2_requests?.values?.count || 0;
  const leaks = data.metrics.cross_tenant_leaks?.values?.count || 0;
  const isolationRate = data.metrics.isolation_rate?.values?.rate || 0;

  console.log('\n📊 Multi-Tenant Isolation Summary:');
  console.log(`   Tenant 1 requests: ${tenant1Count}`);
  console.log(`   Tenant 2 requests: ${tenant2Count}`);
  console.log(`   Cross-tenant leaks: ${leaks}`);
  console.log(`   Isolation rate: ${(isolationRate * 100).toFixed(2)}%`);

  const passed = leaks === 0 && isolationRate === 1.0;

  console.log(`\n${passed ? '✅' : '❌'} Multi-tenant isolation: ${passed ? 'PASSED' : 'FAILED'}`);

  if (leaks > 0) {
    console.error(`\n⚠️  CRITICAL: ${leaks} cross-tenant cache leaks detected!`);
  }

  return {
    'summary_isolation.json': JSON.stringify(data),
  };
}
