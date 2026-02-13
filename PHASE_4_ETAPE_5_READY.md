# Phase 4 Étape 5 : Load Testing k6 — INFRASTRUCTURE PRÊTE ✅

**Date** : 2026-02-12
**Statut** : Infrastructure complète, prête pour exécution
**Projet** : CaroCorp_new
**Branche** : `stabilize/v1.4.1`

---

## 📋 Résumé Exécutif

L'infrastructure complète de load testing avec k6 a été créée pour valider les performances du cache Redis sous charge. **6 fichiers** ont été créés, couvrant 4 scénarios de test différents avec métriques détaillées et seuils de validation automatiques.

**État actuel** : Tous les fichiers sont prêts, mais **k6 doit être installé manuellement** (nécessite `sudo`) avant l'exécution des tests.

---

## 🎯 Objectifs Phase 4 Étape 5

| Métrique | Cible | Description |
|----------|-------|-------------|
| **Latence p50** | < 10ms | Cache HIT médian |
| **Latence p99** | < 50ms | Cache HIT percentile 99 |
| **Throughput** | > 1000 req/s | Requêtes/seconde cache warm |
| **Hit Rate** | > 80% | Ratio hits/(hits+misses) |

---

## 📦 Fichiers Créés (6 total)

### 1. **tests/load/get_products_cache.js** (145 lignes)

**Objectif** : Benchmark principal des performances cache GET

**Scénario** :
- Phase 1 (30s) : Warm-up avec 10 VUs → remplir cache
- Phase 2 (60s) : Load test avec 50 VUs → mesurer performance
- Phase 3 (30s) : Spike test avec 200 VUs → tester scalabilité

**Métriques mesurées** :
- Cache hit rate (heuristique: < 5ms = HIT)
- Latence p50/p99 cache HIT vs MISS
- Throughput (req/s)

**Seuils (thresholds)** :
```javascript
thresholds: {
  'http_req_duration{scenario:cache_warm}': ['p(50)<10', 'p(99)<50'],
  'http_req_failed': ['rate<0.05'],
  'cache_hit_rate': ['rate>0.8'],
  'http_reqs': ['rate>1000'],
}
```

**Heuristique cache HIT/MISS** :
```javascript
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
```

---

### 2. **tests/load/patch_products_invalidation.js** (117 lignes)

**Objectif** : Tester invalidation cache après PATCH + re-remplissage

**Scénario** :
1. GET product (cache MISS → rempli)
2. GET product (cache HIT)
3. PATCH product → invalidation cache
4. GET product (cache MISS → re-rempli avec nouvelles données)

**Métriques mesurées** :
- Latence PATCH avec invalidation
- Latence GET après PATCH (cache MISS + re-fill)
- Nombre d'invalidations

**Seuils** :
```javascript
thresholds: {
  'patch_latency': ['p(99)<100'],
  'get_after_patch_latency': ['p(99)<20'],
  'http_req_failed': ['rate<0.05'],
}
```

**Validation** :
- PATCH invalide correctement le cache
- GET après PATCH retourne données à jour
- Pas de cache stale (données périmées)

---

### 3. **tests/load/mixed_workload.js** (119 lignes)

**Objectif** : Simulation workload production réaliste

**Ratio** : 90% GET (read) / 10% PATCH (write)

**Scénario** :
- Ramp-up 20s → 20 VUs
- Sustained load 120s → 50 VUs
- Spike 20s → 100 VUs
- Cool down 10s → 0 VUs

**Distribution requêtes** :
```javascript
const isWrite = Math.random() < 0.1;
if (isWrite) {
  // PATCH request (10%)
  const patchPayload = JSON.stringify({
    price_per_day_cents: Math.floor(Math.random() * 1000) + 100,
  });
  const res = http.patch(`${BASE_URL}/api/v1/products/${productId}`, patchPayload, { headers });
} else {
  // GET request (90%)
  const res = http.get(`${BASE_URL}/api/v1/products/${productId}`, { headers });
}
```

**Métriques mesurées** :
- Hit rate stable malgré invalidations
- Latence p95/p99 mix GET+PATCH
- Distribution GET vs PATCH

**Seuils** :
```javascript
thresholds: {
  'http_req_duration': ['p(95)<50', 'p(99)<100'],
  'http_req_failed': ['rate<0.05'],
  'cache_hit_rate': ['rate>0.80'],
}
```

---

### 4. **tests/load/multi_tenant_isolation.js** (150 lignes)

**Objectif** : **TEST CRITIQUE DE SÉCURITÉ** — Vérifier isolation multi-tenant sous charge

**Scénario** :
- 2 tenants avec tokens différents
- Chaque VU utilise tenant aléatoire
- Vérifier isolation stricte (zéro cache leak cross-tenant)

**Métriques mesurées** :
- Requests par tenant
- **Cross-tenant cache leaks** (DOIT = 0)
- **Isolation rate** (DOIT = 100%)

**Seuils CRITIQUES** :
```javascript
thresholds: {
  'cross_tenant_leaks': ['count==0'],  // MUST be zero
  'isolation_rate': ['rate==1'],       // MUST be 100%
  'http_req_duration': ['p(99)<100'],
}
```

**Détection leak** :
```javascript
const responseTenantId = res.json('tenant_id');
const isIsolated = responseTenantId === tenant.id;

if (isIsolated) {
  isolationRate.add(true);
} else {
  isolationRate.add(false);
  crossTenantLeaks.add(1);
  console.error(`❌ CROSS-TENANT LEAK: VU requested tenant ${tenant.id}, got tenant ${responseTenantId}`);
}
```

**⚠️ CRITIQUE** : Si `cross_tenant_leaks > 0` → **INCIDENT P0** (fuite sécurité multi-tenant)

---

### 5. **tests/load/run_load_tests.sh** (126 lignes)

**Objectif** : Helper script pour exécution facile des tests k6

**Fonctionnalités** :
- Menu interactif de sélection (6 choix)
- Vérification prérequis (k6 installé, API accessible)
- Output color-coded (vert/rouge/bleu/jaune)
- Export résultats JSON automatique (timestampés)
- Support exécution individuelle ou suite complète

**Usage** :
```bash
# Exécution interactive
./tests/load/run_load_tests.sh

# Exécution directe
./tests/load/run_load_tests.sh 1  # Test cache performance
./tests/load/run_load_tests.sh 5  # Suite complète (4 tests)
./tests/load/run_load_tests.sh 6  # Quick smoke test 30s
```

**Checks automatiques** :
```bash
# 1. Vérifier k6 installé
if ! command -v k6 &> /dev/null; then
    echo "❌ k6 n'est pas installé"
    # Afficher instructions installation
    exit 1
fi

# 2. Vérifier API accessible
if curl -sf "$API_URL/health" > /dev/null 2>&1; then
    echo "✅ API accessible"
else
    echo "❌ API non accessible"
    exit 1
fi
```

---

### 6. **tests/load/README.md** (430 lignes)

**Objectif** : Documentation complète load testing

**Sections** :
1. **Objectifs Phase 4 Étape 5** (tableau métriques)
2. **Installation k6** (Ubuntu/Debian + macOS)
3. **Quick Start** (démarrer API + Redis + tests)
4. **Tests Disponibles** (description détaillée 4 tests)
5. **Analyse Résultats** (Prometheus, Grafana, jq)
6. **Debugging Performance** (latence élevée, hit rate bas, throughput bas)
7. **Benchmarks Référence** (configuration test + résultats attendus)
8. **Checklist Validation** (8 critères avant déclaration complète)
9. **Alertes Critiques** (procédure cross-tenant leak = P0)
10. **Support** (contacts, liens GitHub)

**Benchmarks référence attendus** (8 vCPU, 16 GB RAM) :

| Test | Throughput | Latence p50 | Latence p99 | Hit Rate |
|------|------------|-------------|-------------|----------|
| **GET Cache Warm** | 1200 req/s | 3.5ms | 8.2ms | 87% |
| **PATCH Invalidation** | 180 req/s | 15ms | 42ms | N/A |
| **Mixed Workload** | 950 req/s | 4.1ms | 18ms | 83% |
| **Multi-Tenant** | 800 req/s | 5.2ms | 22ms | 81% |

---

## 🚀 Installation k6 (ACTION REQUISE)

**IMPORTANT** : k6 doit être installé manuellement (nécessite `sudo`).

### Ubuntu/Debian

```bash
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 \
  --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69

echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | \
  sudo tee /etc/apt/sources.list.d/k6.list

sudo apt-get update
sudo apt-get install k6
```

### macOS

```bash
brew install k6
```

### Vérification

```bash
k6 version
# Sortie attendue : k6 v0.48.0 (ou supérieur)
```

---

## 🎯 Exécution Tests (Après Installation k6)

### Démarrer l'API CaroCorp

```bash
# Terminal 1: API
cd /home/ruuuzer/Documents/CaroCorp_new
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

### Vérifier Redis

```bash
# Terminal 2: Redis
docker ps | grep redis

# Si absent, démarrer:
docker run -d -p 6379:6379 redis:7-alpine
```

### Exécuter Tests k6

```bash
# Terminal 3: Tests
cd /home/ruuuzer/Documents/CaroCorp_new

# Menu interactif
./tests/load/run_load_tests.sh

# Ou test spécifique
k6 run tests/load/get_products_cache.js
k6 run tests/load/patch_products_invalidation.js
k6 run tests/load/mixed_workload.js
k6 run tests/load/multi_tenant_isolation.js
```

---

## 📊 Métriques Exposées

Les tests k6 mesurent et valident automatiquement :

### Métriques k6 (Custom)

- **cache_hits** : Nombre de cache HITs (< 5ms)
- **cache_misses** : Nombre de cache MISSEs (≥ 5ms)
- **cache_hit_rate** : Ratio hits/(hits+misses) (target > 80%)
- **latency_cache_hit** : Latence moyenne cache HIT (target p99 < 10ms)
- **latency_cache_miss** : Latence moyenne cache MISS
- **get_requests** : Nombre de GET requests
- **patch_requests** : Nombre de PATCH requests
- **cache_invalidations** : Nombre d'invalidations cache
- **tenant1_requests** / **tenant2_requests** : Requests par tenant
- **cross_tenant_leaks** : Leaks cross-tenant (DOIT = 0)
- **isolation_rate** : Taux d'isolation (DOIT = 100%)

### Métriques HTTP k6 (Built-in)

- **http_req_duration** : Latence totale requête (p50, p95, p99)
- **http_req_failed** : Taux d'échec requêtes (target < 5%)
- **http_reqs** : Throughput total (req/s) (target > 1000 req/s cache warm)

### Métriques Prometheus (API /metrics)

- **cache_hits_total{entity="product"}** : Counter cache HITs
- **cache_misses_total{entity="product"}** : Counter cache MISSEs
- **cache_hit_rate{entity="product"}** : Gauge hit rate (0.0-1.0)

**Accès** : `curl http://localhost:8001/metrics | grep cache`

---

## ✅ Checklist Validation Phase 4 Étape 5

Avant de déclarer Phase 4 Étape 5 complète :

- [x] **6 fichiers load testing créés** (get, patch, mixed, multi-tenant, run script, README)
- [ ] **k6 installé** (`k6 version` retourne v0.48.0+)
- [ ] **API CaroCorp lancée** (`curl http://localhost:8001/health` retourne 200)
- [ ] **Redis opérationnel** (`docker ps | grep redis` retourne container actif)
- [ ] **Test GET cache performance PASSÉ** (4 objectifs ✅)
  - [ ] Cache Hit Rate > 80%
  - [ ] Latence p50 < 10ms
  - [ ] Latence p99 < 50ms
  - [ ] Throughput > 1000 req/s
- [ ] **Test PATCH invalidation PASSÉ** (2 objectifs ✅)
  - [ ] PATCH p99 < 100ms
  - [ ] GET après PATCH p99 < 20ms
- [ ] **Test mixed workload PASSÉ** (3 objectifs ✅)
  - [ ] p95 < 50ms
  - [ ] p99 < 100ms
  - [ ] Cache Hit Rate > 80%
- [ ] **Test multi-tenant isolation PASSÉ** (0 leaks ✅)
  - [ ] cross_tenant_leaks == 0
  - [ ] isolation_rate == 1.0 (100%)
- [ ] **Résultats documentés** dans `PHASE_4_ETAPE_5_COMPLETE.md`
- [ ] **Benchmarks référence atteints** (voir tableau ci-dessus)

---

## 🎓 Insights Techniques

### 1. Heuristique Cache HIT/MISS

**Pourquoi < 5ms = cache HIT ?**

- Cache Redis : ~1-3ms latence réseau + désérialisation
- DB PostgreSQL : ~10-50ms (query + réseau + ORM)
- Seuil 5ms permet distinction claire avec marge d'erreur

**Alternative** : Consulter header HTTP custom `X-Cache-Status: HIT|MISS` (si implémenté dans API).

### 2. Thresholds k6 (Seuils de Validation)

Les **thresholds** dans k6 sont des assertions automatiques. Si un threshold échoue, k6 retourne exit code 1 (échec CI/CD).

Exemple :
```javascript
thresholds: {
  'http_req_duration': ['p(99)<50'],  // Assertion: p99 doit être < 50ms
  'cache_hit_rate': ['rate>0.8'],     // Assertion: hit rate > 80%
}
```

Si p99 = 52ms → test **ÉCHOUE** automatiquement (exit code 1).

### 3. Multi-Tenant Isolation (Sécurité Critique)

Le test `multi_tenant_isolation.js` est un **test de sécurité, pas seulement de performance**.

**Scénario d'attaque** :
1. Attaquant crée 100 VUs avec token tenant A
2. Attaquant devine ID produit tenant B (ex: product_id=42)
3. Attaquant fait GET /products/42 en masse
4. **Si cache leak** : Attaquant obtient données tenant B via cache pollué

**Protection** :
- Clés cache incluent `tenant_id` : `product:{tenant_id}:{product_id}`
- Repository filtre automatiquement `tenant_id` depuis JWT
- Test valide 0 leak sous charge (stress test isolation)

**Gravité** : Cross-tenant leak = **Incident P0** → rollback immédiat production.

### 4. Workload Réaliste (90/10 Read/Write)

Le ratio 90% GET / 10% PATCH simule production réelle :
- Lectures (GET) : consultation catalogue, dashboards, rapports
- Écritures (PATCH) : mises à jour prix, stock, réservations

**Impact sur cache** :
- 10% PATCH = 10% invalidations
- Hit rate théorique max = 90% (si cache TTL infini)
- Hit rate réel = 80-85% (TTL finite + warm-up)

---

## 🚨 Alertes Critiques

### ❌ Cross-Tenant Cache Leak Détecté

Si `multi_tenant_isolation.js` rapporte `cross_tenant_leaks > 0` :

**1. STOP immédiatement tous les tests**
```bash
pkill -f k6
```

**2. Vérifier clés cache**
```bash
docker exec -it <redis_container> redis-cli
> KEYS product:*
# Vérifier format: product:{tenant_id}:{product_id}
```

**3. Analyser code**
```python
# app/repositories/base.py
def _get_cache_key(self, entity_id: int, tenant_id: int) -> str:
    # DOIT inclure tenant_id dans la clé
    return f"{entity_name}:{tenant_id}:{entity_id}"
```

**4. Créer incident P0**
- Documenter dans GitHub Issues
- Tag: `security`, `critical`, `multi-tenant`
- **Rollback production immédiatement** si déployé

---

## 📝 Prochaines Étapes

### 1. Installer k6 (ACTION REQUISE)

Exécuter les commandes d'installation ci-dessus selon votre OS.

### 2. Exécuter Suite Complète

```bash
./tests/load/run_load_tests.sh
# Choix : 5 (Tous les tests)
```

### 3. Analyser Résultats

- Vérifier tous les thresholds ✅ (k6 affiche en vert/rouge)
- Comparer avec benchmarks référence
- Valider **0 cross-tenant leak** (critique)

### 4. Documenter Résultats

Créer `PHASE_4_ETAPE_5_COMPLETE.md` avec :
- Résultats bruts k6 (copier output terminal)
- Comparaison benchmarks attendus vs obtenus
- Screenshots métriques Prometheus (optionnel)
- Captures Grafana dashboards (optionnel)

### 5. Commit Final

```bash
git add tests/load/ PHASE_4_ETAPE_5_READY.md
git commit -m "feat(load): Phase 4 Étape 5 - infrastructure k6 complète

- 4 scénarios load testing (GET cache, PATCH invalidation, mixed, multi-tenant)
- Helper script run_load_tests.sh avec menu interactif
- Documentation complète README.md (installation, usage, debugging)
- Thresholds automatiques : p50<10ms, p99<50ms, throughput>1000 req/s, hit rate>80%
- Test sécurité multi-tenant : 0 cross-tenant leak obligatoire

Infrastructure prête, nécessite installation k6 pour exécution.

Ref: PHASE_4_ETAPE_5_READY.md"
```

---

## 🔗 Références

- **Documentation k6** : https://k6.io/docs/
- **Tests créés** : `tests/load/` (6 fichiers)
- **Phase précédente** : `PHASE_4_ETAPE_4_FINALISED.md`
- **Métriques Prometheus** : `http://localhost:8001/metrics`
- **API Health** : `http://localhost:8001/health`

---

## 📞 Support

**Issues GitHub** : https://github.com/votre-org/CaroCorp/issues
**Documentation** : `tests/load/README.md`

**Contacts** :
- Performance: team-performance@carocorp.com
- Sécurité: security@carocorp.com

---

**Statut Final** : Infrastructure complète ✅ — Prête pour exécution après installation k6
