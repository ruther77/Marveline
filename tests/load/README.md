# Load Testing CaroCorp - k6

Tests de charge pour valider les performances du cache Redis et de l'API CaroCorp.

## 📋 Objectifs Phase 4 Étape 5

| Métrique | Cible | Description |
|----------|-------|-------------|
| **Latence p50** | < 10ms | Cache HIT médian |
| **Latence p99** | < 50ms | Cache HIT percentile 99 |
| **Throughput** | > 1000 req/s | Requêtes/seconde cache warm |
| **Hit Rate** | > 80% | Ratio hits/(hits+misses) |

---

## 🔧 Installation k6

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
# k6 v0.48.0 (ou supérieur)
```

---

## 🚀 Quick Start

### 1. Démarrer l'API CaroCorp

```bash
# Terminal 1: API
cd /path/to/CaroCorp_new
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

### 2. Vérifier que Redis tourne

```bash
# Terminal 2: Redis
docker ps | grep redis
# Ou démarrer si absent:
docker run -d -p 6379:6379 redis:7-alpine
```

### 3. Exécuter tests de charge

```bash
# Script interactif
./tests/load/run_load_tests.sh

# Ou test spécifique
k6 run tests/load/get_products_cache.js
```

---

## 📊 Tests Disponibles

### 1. GET Products Cache Performance

**Fichier**: `get_products_cache.js`

**Scénario**:
- Phase 1 (30s): Warm-up avec 10 VUs → remplir cache
- Phase 2 (60s): Load test avec 50 VUs → mesurer performance
- Phase 3 (30s): Spike test avec 200 VUs → tester scalabilité

**Métriques mesurées**:
- Cache hit rate (heuristique: < 5ms = HIT)
- Latence p50/p99 cache HIT vs MISS
- Throughput (req/s)

**Seuils (thresholds)**:
```javascript
'http_req_duration{scenario:cache_warm}': ['p(50)<10', 'p(99)<50'],
'cache_hit_rate': ['rate>0.8'],
'http_reqs': ['rate>1000'],
```

**Exécution**:
```bash
k6 run tests/load/get_products_cache.js
```

**Output attendu**:
```
📊 Résumé Performance Cache:
   Cache Hit Rate: 85.3%
   Latence p50: 3.2ms
   Latence p99: 8.7ms
   Throughput: 1247 req/s

✅ Objectifs:
   ✅ Cache Hit Rate > 80%
   ✅ Latence p50 < 10ms
   ✅ Latence p99 < 50ms
   ✅ Throughput > 1000 req/s
```

---

### 2. PATCH Products Cache Invalidation

**Fichier**: `patch_products_invalidation.js`

**Scénario**:
1. GET product (cache MISS → rempli)
2. PATCH product → invalidation cache
3. GET product (cache MISS → re-rempli avec nouvelles données)

**Métriques mesurées**:
- Latence PATCH avec invalidation
- Latence GET après PATCH (cache MISS)
- Nombre d'invalidations

**Seuils**:
```javascript
'patch_latency': ['p(99)<100'],
'get_after_patch_latency': ['p(99)<20'],
```

**Exécution**:
```bash
k6 run tests/load/patch_products_invalidation.js
```

**Validation**:
- PATCH invalide correctement le cache
- GET après PATCH retourne données à jour
- Pas de cache stale

---

### 3. Mixed Workload (Réaliste)

**Fichier**: `mixed_workload.js`

**Ratio**: 90% GET (read) / 10% PATCH (write)

**Scénario**:
- 120s de charge soutenue avec mix read/write
- Simule workload production typique

**Métriques mesurées**:
- Hit rate stable malgré invalidations
- Latence p95/p99 mix GET+PATCH
- Distribution GET vs PATCH

**Seuils**:
```javascript
'http_req_duration': ['p(95)<50', 'p(99)<100'],
'cache_hit_rate': ['rate>0.80'],
```

**Exécution**:
```bash
k6 run tests/load/mixed_workload.js
```

**Output attendu**:
```
📊 Mixed Workload Summary:
   Total requests: 5432
   GET: 4889 (90.0%)
   PATCH: 543 (10.0%)
   Cache Hit Rate: 82.4%
   Latency p95: 12.3ms
   Latency p99: 45.7ms
```

---

### 4. Multi-Tenant Isolation

**Fichier**: `multi_tenant_isolation.js`

**Scénario**:
- 2 tenants avec tokens différents
- Chaque VU utilise tenant aléatoire
- Vérifier isolation stricte (zéro cache leak)

**Métriques mesurées**:
- Requests par tenant
- Cross-tenant cache leaks (DOIT = 0)
- Isolation rate (DOIT = 100%)

**Seuils**:
```javascript
'cross_tenant_leaks': ['count==0'],  // CRITIQUE
'isolation_rate': ['rate==1'],       // 100%
```

**Exécution**:
```bash
k6 run tests/load/multi_tenant_isolation.js
```

**Validation**:
```
📊 Multi-Tenant Isolation Summary:
   Tenant 1 requests: 2847
   Tenant 2 requests: 2913
   Cross-tenant leaks: 0
   Isolation rate: 100.00%

✅ Multi-tenant isolation: PASSED
```

**⚠️ CRITIQUE**: Si `cross_tenant_leaks > 0` → **INCIDENT P0** (fuite sécurité)

---

## 📈 Analyse Résultats

### Visualiser Métriques Temps Réel

**Terminal 1**: API + Métriques
```bash
# Métriques Prometheus exposées
curl http://localhost:8001/metrics | grep cache_hit_rate
```

**Terminal 2**: k6 avec output JSON
```bash
k6 run --out json=results.json tests/load/get_products_cache.js
```

**Terminal 3**: Analyse live (jq)
```bash
tail -f results.json | jq -c 'select(.type=="Point" and .metric=="http_req_duration") | {time:.data.time, duration:.data.value}'
```

### Grafana Dashboard (Optionnel)

Si Prometheus + Grafana configurés :

1. **Scrape metrics CaroCorp** (`/metrics` endpoint)
2. **Import dashboard k6** (ID 2587)
3. **Panels custom**:
   - Cache hit rate: `cache_hit_rate{entity="product"}`
   - Latence p99: `histogram_quantile(0.99, http_request_duration_seconds)`
   - Throughput: `rate(http_requests_total[1m])`

---

## 🔍 Debugging Performance

### Latence élevée (p99 > 50ms)

**1. Vérifier hit rate**:
```bash
curl http://localhost:8001/metrics | grep cache_hit_rate
# Si < 80% → problème cache
```

**2. Analyser queries DB lentes**:
```python
# app/repositories/base.py
import logging
logger = logging.getLogger(__name__)

def get_by_id(...):
    start = time.time()
    result = self.db.execute(query).scalar_one_or_none()
    duration = (time.time() - start) * 1000
    if duration > 10:
        logger.warning(f"Slow query: {duration:.2f}ms for {self.model_class.__name__}")
```

**3. Profiler avec py-spy**:
```bash
pip install py-spy
py-spy record --pid $(pgrep -f "uvicorn app.main:app") --duration 30
```

### Hit Rate bas (< 80%)

**Causes possibles**:
1. **TTL trop court** → Augmenter dans `app/repositories/base.py`
   ```python
   self._cache_ttl_map = {
       "Product": 600,  # 10 min au lieu de 5 min
   }
   ```

2. **Invalidations excessives** → Vérifier ratio GET/PATCH
   ```bash
   k6 run tests/load/mixed_workload.js
   # Ratio GET doit être > 80%
   ```

3. **Redis saturé** → Vérifier mémoire
   ```bash
   docker stats | grep redis
   # Si > 90% → augmenter max memory
   ```

### Throughput bas (< 1000 req/s)

**1. Vérifier workers Uvicorn**:
```bash
# Augmenter workers
uvicorn app.main:app --workers 4
```

**2. Vérifier connexions DB pool**:
```python
# app/core/database.py
engine = create_engine(
    DATABASE_URL,
    pool_size=20,  # Augmenter si saturé
    max_overflow=10
)
```

**3. Profiler avec Locust (alternative k6)**:
```bash
pip install locust
locust -f tests/load/locustfile.py
```

---

## 🎯 Benchmarks Référence

### Configuration Test

- **Machine**: 8 vCPU, 16 GB RAM
- **Database**: PostgreSQL 16, pool_size=20
- **Cache**: Redis 7, 512 MB
- **Workers**: Uvicorn 4 workers

### Résultats Attendus

| Test | Throughput | Latence p50 | Latence p99 | Hit Rate |
|------|------------|-------------|-------------|----------|
| **GET Cache Warm** | 1200 req/s | 3.5ms | 8.2ms | 87% |
| **PATCH Invalidation** | 180 req/s | 15ms | 42ms | N/A |
| **Mixed Workload** | 950 req/s | 4.1ms | 18ms | 83% |
| **Multi-Tenant** | 800 req/s | 5.2ms | 22ms | 81% |

**Objectifs atteints** ✅ si:
- Latence p50 < 10ms
- Latence p99 < 50ms
- Throughput > 1000 req/s (GET cache warm)
- Hit rate > 80%

---

## 📝 Checklist Validation

Avant de déclarer Phase 4 Étape 5 complète :

- [ ] k6 installé (`k6 version`)
- [ ] API CaroCorp lancée (`curl http://localhost:8001/health`)
- [ ] Redis opérationnel (`docker ps | grep redis`)
- [ ] Test GET cache performance PASSÉ (4 objectifs ✅)
- [ ] Test PATCH invalidation PASSÉ (2 objectifs ✅)
- [ ] Test mixed workload PASSÉ (3 objectifs ✅)
- [ ] Test multi-tenant isolation PASSÉ (0 leaks ✅)
- [ ] Résultats documentés dans `PHASE_4_ETAPE_5_COMPLETE.md`
- [ ] Benchmarks référence atteints

---

## 🚨 Alertes Critiques

### ❌ Cross-Tenant Cache Leak Détecté

Si `multi_tenant_isolation.js` rapporte `cross_tenant_leaks > 0`:

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
- Rollback production si déployé

---

## 📞 Support

**Issues GitHub**: https://github.com/votre-org/CaroCorp/issues
**Documentation**: `docs/performance/load-testing.md`

**Contacts**:
- Performance: team-performance@carocorp.com
- Sécurité: security@carocorp.com
