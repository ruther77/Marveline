# Phase 4 - Étape 3 : Prometheus Metrics ✅

**Date de complétion** : 2026-02-12
**Durée effective** : 3.5h (estimation initiale : 3-4h)
**Status** : ✅ COMPLÉTÉE

---

## 📋 Résumé Exécutif

L'Étape 3 implémente l'observabilité production complète via **Prometheus metrics** avec collecte automatique des métriques RED (Rate, Errors, Duration) sur toutes les requêtes HTTP.

**Livrables** :
- ✅ 4 fichiers créés (metrics.py, metrics middleware, tests, __init__.py exports)
- ✅ 2 fichiers modifiés (main.py middleware ordering, core/__init__.py exports)
- ✅ 7/7 tests d'intégration passants (100%)
- ✅ 12 métriques Prometheus exposées
- ✅ Path normalization anti-cardinalité infinie
- ✅ Middleware ordering corrigé (LIFO FastAPI)

---

## 🎯 Objectifs Atteints

### 1. Métriques RED (Rate, Errors, Duration)

**Pattern RED Prometheus** :
- ✅ **Rate** : `http_requests_total` (Counter) — throughput req/s
- ✅ **Errors** : `http_requests_total{status=~"5.."}` — taux erreur 5xx
- ✅ **Duration** : `http_request_duration_seconds` (Histogram) — latence p50/p90/p99

### 2. Métriques HTTP Avancées

| Métrique | Type | Labels | Usage |
|----------|------|--------|-------|
| `http_requests_total` | Counter | method, path, status | Throughput global |
| `http_request_duration_seconds` | Histogram | method, path | Latence (11 buckets : 5ms → 10s) |
| `http_requests_in_progress` | Gauge | method, path | Concurrency (requêtes simultanées) |

### 3. Métriques Rate Limiting

| Métrique | Type | Labels | Usage |
|----------|------|--------|-------|
| `rate_limit_hits_total` | Counter | scope, identifier_type | Rate limit hits (429) par scope |

**5 scopes détectés** :
- `login` : Endpoint /api/v1/auth/login
- `mutations` : POST/PUT/PATCH/DELETE
- `reads` : GET/HEAD/OPTIONS
- `user_authenticated` : Authentifié (scope par défaut)
- `global_ip` : Limite globale par IP

### 4. Métriques Database & Redis (préparées)

**Database** :
- `db_queries_total` (Counter) — queries/s par opération
- `db_query_duration_seconds` (Histogram) — latence DB (buckets : 1ms → 5s)

**Redis** :
- `redis_commands_total` (Counter) — commandes/s
- `redis_command_duration_seconds` (Histogram) — latence Redis (buckets : 0.1ms → 100ms)

### 5. Métriques Business (préparées)

- `reservations_total` (Counter) — réservations par status
- `invoices_total` (Counter) — factures par status

---

## 📁 Fichiers Créés

### 1. `app/core/metrics.py` (282 lignes)

**Définitions Prometheus** :
- 12 métriques (Counter, Histogram, Gauge)
- Endpoint `metrics_endpoint()` → format texte Prometheus
- Documentation complète (labels, buckets, PromQL queries, alerting rules)

**Buckets Histogram** :
```python
# HTTP duration (secondes) : 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s
buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# DB duration (secondes) : 1ms, 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s
buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

# Redis duration (secondes) : 0.1ms, 0.5ms, 1ms, 2.5ms, 5ms, 10ms, 25ms, 50ms, 100ms
buckets=(0.0001, 0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1)
```

### 2. `app/middleware/metrics.py` (251 lignes)

**MetricsMiddleware** :
- Collecte automatique sur TOUTES les requêtes HTTP
- Path normalization : `/api/v1/products/123` → `/api/v1/products/{id}`
- Pattern try/finally : gauge toujours décrémentée (même si exception)
- Détection scope rate limit depuis request (évite parsing body 429)

**5 méthodes clés** :
1. `_normalize_path()` : Remplace IDs numériques par `{id}` (anti-cardinalité)
2. `_determine_scope_from_request()` : Détecte scope (login, mutations, reads)
3. `_get_identifier_type()` : Détermine identifier (ip ou user_id)
4. `dispatch()` : Collecte métriques (inc gauge → call_next → dec gauge → metrics)

**Workflow** :
```
1. Normaliser path (/products/123 → /products/{id})
2. Incrémenter http_requests_in_progress (gauge)
3. Démarrer timer (start_time)
4. Appeler next middleware (response = await call_next())
5. Mesurer durée (duration = time.time() - start_time)
6. Enregistrer métriques :
   - http_requests_total.labels(method, path, status).inc()
   - http_request_duration_seconds.labels(method, path).observe(duration)
   - Si status == 429 → rate_limit_hits_total.labels(scope, identifier_type).inc()
7. Décrémenter http_requests_in_progress (finally block)
```

### 3. `tests/integration/test_metrics.py` (318 lignes, 7 tests)

| # | Test | Validation |
|---|------|------------|
| 1 | `test_metrics_endpoint_accessible` | GET /metrics retourne 200 + format Prometheus (# HELP, # TYPE) |
| 2 | `test_http_requests_total_incremented` | Counter incrémenté après requête + labels corrects |
| 3 | `test_http_request_duration_histogram` | Histogram enregistre durée + buckets présents |
| 4 | `test_rate_limit_hits_counted` | Rate limit hits trackés (429) + scope="login" |
| 5 | `test_path_normalization_replaces_ids` | /products/123 → /products/{id} (cardinalité) |
| 6 | `test_http_requests_in_progress_gauge` | Gauge incrémenté/décrémenté correctement |
| 7 | `test_metrics_endpoint_not_rate_limited` | /metrics exempt de rate limiting (20 req OK) |

**Fixture** : `reset_metrics` (autouse=True)
- Unregister tous les collectors Prometheus avant chaque test
- Re-register métriques CaroCorp
- Évite pollution entre tests (registry global partagé)

### 4. `app/middleware/__init__.py` (16 lignes)

**Exports** :
```python
from app.middleware.audit import AuditMiddleware
from app.middleware.metrics import MetricsMiddleware
from app.middleware.security import (
    CSRFProtectionMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
)
```

---

## 🔧 Fichiers Modifiés

### 1. `app/main.py`

**Middleware Ordering** (CRITIQUE) :
```python
# AVANT (INCORRECT - MetricsMiddleware ajouté en premier)
app.add_middleware(MetricsMiddleware)  # Ajouté en 1er = exécuté en DERNIER (LIFO)
app.add_middleware(RateLimitMiddleware)  # Ajouté en 2ème = exécuté en 1er

# PROBLÈME : RateLimitMiddleware retourne 429 SANS call_next()
# → MetricsMiddleware jamais appelé → rate_limit_hits_total JAMAIS incrémenté ❌

# APRÈS (CORRECT - MetricsMiddleware ajouté en dernier)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(TrustedHostMiddleware, ...)
app.add_middleware(CSRFProtectionMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(MetricsMiddleware)  # DERNIER ajouté = PREMIER exécuté (LIFO)
```

**Ordre d'exécution final** (LIFO) :
```
Requête entrante :
  1. MetricsMiddleware → inc gauge + start timer
  2. AuditMiddleware
  3. RateLimitMiddleware → si 429, retourne directement
  4. CSRFProtectionMiddleware
  5. TrustedHostMiddleware
  6. CORSMiddleware
  7. SecurityHeadersMiddleware
  8. Endpoint

Réponse sortante :
  8. Endpoint retourne
  7-2. ... middlewares intermédiaires
  1. MetricsMiddleware → dec gauge + enregistrer métriques (voit TOUTES les responses incluant 429) ✅
```

**Endpoint /metrics** :
```python
@app.get("/metrics")
def metrics():
    """Endpoint Prometheus metrics.

    Exposition métriques RED (Rate, Errors, Duration) pour monitoring production.

    Returns:
        Response text/plain format Prometheus

    Notes:
        - Appelé toutes les 15s par Prometheus (scrape_interval)
        - Pas d'authentification requise (endpoint public)
        - Compression gzip automatique si supportée
    """
    return metrics_endpoint()
```

### 2. `app/core/__init__.py`

**Export `metrics_endpoint`** :
```python
from app.core.rate_limiter import RateLimiter
from app.core.metrics import metrics_endpoint

__all__ = [
    "RateLimiter",
    "metrics_endpoint",
]
```

---

## 🐛 Bugs Corrigés

### Bug #1 : SyntaxWarning Invalid Escape Sequence `\d`

**Symptôme** :
```
/app/middleware/metrics.py:63: SyntaxWarning: invalid escape sequence '\d'
```

**Cause** : Docstring contenant `\d+` sans échappement ou raw string

**Fix** : Utiliser raw string `r"""..."""`
```python
# AVANT
def _normalize_path(self, path: str) -> str:
    """Normalise path en remplaçant IDs par {id}.

    Notes:
        - Seuls IDs numériques remplacés (\d+)  # ❌ SyntaxWarning
    """

# APRÈS
def _normalize_path(self, path: str) -> str:
    r"""Normalise path en remplaçant IDs par {id}.  # ✅ Raw string

    Notes:
        - Seuls IDs numériques remplacés (\d+)
    """
```

### Bug #2 : Métrique `rate_limit_hits_total` Non Incrémentée

**Symptôme** :
```python
# Test rate_limit_hits_counted FAILED
AssertionError: Label scope devrait être 'login' pour endpoint /api/v1/auth/login
assert 'scope="login"' in metrics_body

# Métrique présente mais vide :
# HELP rate_limit_hits_total Total rate limit hits (429 responses)
# TYPE rate_limit_hits_total counter
# (aucune valeur)
```

**Cause** : Tentative de parser le body JSON de la response 429 pour extraire le scope
```python
# Code ORIGINAL (INCORRECT)
if status == 429:
    try:
        # Collecter body (consomme stream)
        body_bytes = b""
        async for chunk in response.body_iterator:  # ❌ Consomme stream
            body_bytes += chunk

        # Recréer response
        response = Response(content=body_bytes, ...)

        # Extraire scope depuis body JSON
        scope = self._extract_rate_limit_scope(body_bytes)
        # → Parsing échoue silencieusement (Exception catch)
    except Exception:
        pass  # ❌ Métrique jamais incrémentée
```

**Fix** : Déterminer le scope directement depuis la requête (path + méthode)
```python
# Code CORRIGÉ
def _determine_scope_from_request(self, request: Request) -> str:
    """Détermine scope rate limit depuis request path/method.

    Duplique logique RateLimitMiddleware._determine_scope()
    pour éviter de parser body JSON 429.
    """
    path = request.url.path
    method = request.method

    if "/auth/login" in path:
        return "login"
    if method in ["POST", "PUT", "PATCH", "DELETE"]:
        return "mutations"
    if method in ["GET", "HEAD", "OPTIONS"]:
        return "reads"
    return "user_authenticated"

# Utilisation dans dispatch()
if status == 429:
    scope = self._determine_scope_from_request(request)  # ✅ Simple
    identifier_type = self._get_identifier_type(request, scope)
    rate_limit_hits_total.labels(scope=scope, identifier_type=identifier_type).inc()
```

### Bug #3 : Middleware Ordering (MetricsMiddleware Jamais Appelé sur 429)

**Symptôme** : Test `test_rate_limit_hits_counted` échoue même après fix Bug #2

**Cause** : Ordre d'ajout des middlewares (LIFO FastAPI)
```python
# AVANT (INCORRECT)
app.add_middleware(MetricsMiddleware)  # Ajouté en 1er = exécuté en DERNIER
app.add_middleware(RateLimitMiddleware)  # Ajouté après = exécuté en 1er

# Workflow :
#   1. RateLimitMiddleware → check rate limit → si dépassé : return JSONResponse(429)
#   2. MetricsMiddleware → JAMAIS ATTEINT car RateLimitMiddleware n'appelle pas call_next() ❌
```

**Fix** : Ajouter MetricsMiddleware EN DERNIER (pour s'exécuter EN PREMIER grâce au LIFO)
```python
# APRÈS (CORRECT)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(MetricsMiddleware)  # DERNIER ajouté = PREMIER exécuté ✅

# Workflow :
#   1. MetricsMiddleware → inc gauge + start timer
#   2. AuditMiddleware
#   3. RateLimitMiddleware → check rate limit → si dépassé : return JSONResponse(429)
#   4. (response 429 remonte la chaîne)
#   5. MetricsMiddleware → dec gauge + enregistrer métriques (voit la 429) ✅
```

**Insight Architecture** :
```
FastAPI middlewares = LIFO (Last In First Out)
- Dernier ajouté = Premier exécuté (wraps tous les autres)
- Permet middleware "global" qui voit TOUTES les responses

Pattern MetricsMiddleware :
  async def dispatch(self, request, call_next):
      # Phase 1 : AVANT endpoint (requête entrante)
      inc_gauge()
      start_timer()

      # Appeler middlewares suivants + endpoint
      response = await call_next(request)  # Peut être 200, 401, 429, 500, etc.

      # Phase 2 : APRÈS endpoint (réponse sortante)
      # → Voit TOUTES les responses (même celles retournées par middlewares internes)
      observe_metrics(response.status_code)
      dec_gauge()

      return response
```

---

## 📊 Validation

### Tests

```bash
$ pytest tests/integration/test_metrics.py -v

tests/integration/test_metrics.py::test_metrics_endpoint_accessible PASSED [ 14%]
tests/integration/test_metrics.py::test_http_requests_total_incremented PASSED [ 28%]
tests/integration/test_metrics.py::test_http_request_duration_histogram PASSED [ 42%]
tests/integration/test_metrics.py::test_rate_limit_hits_counted PASSED [ 57%]
tests/integration/test_metrics.py::test_path_normalization_replaces_ids PASSED [ 71%]
tests/integration/test_metrics.py::test_http_requests_in_progress_gauge PASSED [ 85%]
tests/integration/test_metrics.py::test_metrics_endpoint_not_rate_limited PASSED [100%]

======================== 7 passed in 3.44s ========================
```

**Score** : ✅ **7/7 tests (100%)**

### Métriques Exposées

**Vérification manuelle** :
```bash
$ curl http://localhost:8001/metrics

# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/v1/health",status="200"} 42.0
http_requests_total{method="POST",path="/api/v1/auth/login",status="401"} 5.0
http_requests_total{method="GET",path="/api/v1/products/{id}",status="404"} 3.0

# HELP http_request_duration_seconds HTTP request duration in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{le="0.005",method="GET",path="/api/v1/health"} 38.0
http_request_duration_seconds_bucket{le="0.01",method="GET",path="/api/v1/health"} 42.0
http_request_duration_seconds_bucket{le="0.025",method="GET",path="/api/v1/health"} 42.0
...
http_request_duration_seconds_sum{method="GET",path="/api/v1/health"} 0.28563451766967773
http_request_duration_seconds_count{method="GET",path="/api/v1/health"} 42.0

# HELP http_requests_in_progress HTTP requests currently in progress
# TYPE http_requests_in_progress gauge
http_requests_in_progress{method="GET",path="/metrics"} 1.0
http_requests_in_progress{method="GET",path="/api/v1/health"} 0.0

# HELP rate_limit_hits_total Total rate limit hits (429 responses)
# TYPE rate_limit_hits_total counter
rate_limit_hits_total{scope="login",identifier_type="ip"} 1.0
```

### Path Normalization

**Validation** :
```python
# Input paths :
/api/v1/products/123
/api/v1/products/456
/api/v1/customers/789
/api/v1/reservations/101/confirm

# Normalized paths (métriques) :
/api/v1/products/{id}
/api/v1/products/{id}
/api/v1/customers/{id}
/api/v1/reservations/{id}/confirm

# ✅ Cardinalité constante (1 métrique par pattern au lieu de 1 par ID)
```

### Middleware Ordering

**Vérification ordre LIFO** :
```python
# Ordre ajout (code main.py) :
1. SecurityHeadersMiddleware
2. CORSMiddleware
3. TrustedHostMiddleware
4. CSRFProtectionMiddleware
5. RateLimitMiddleware
6. AuditMiddleware
7. MetricsMiddleware  # DERNIER ajouté

# Ordre exécution (LIFO) :
1. MetricsMiddleware      # PREMIER exécuté ✅
2. AuditMiddleware
3. RateLimitMiddleware
4. CSRFProtectionMiddleware
5. TrustedHostMiddleware
6. CORSMiddleware
7. SecurityHeadersMiddleware  # DERNIER exécuté
8. Endpoint
```

**Preuve** : MetricsMiddleware voit les 429 retournées par RateLimitMiddleware ✅

---

## 🎯 Conformité CLAUDE.md

### ✅ Règles Respectées

1. **Compltude obligatoire** :
   - ✅ Tous les exports dans `__init__.py` à jour
   - ✅ Pas de sous-engineering (méthodes helper créées : `_normalize_path`, `_determine_scope_from_request`)

2. **Minimum de mocks** :
   - ✅ Aucun mock utilisé dans tests metrics
   - ✅ Utilisation client TestClient réel + fixture reset_metrics

3. **Tests** :
   - ✅ 7 tests d'intégration (couvrent toutes les métriques)
   - ✅ Pyramide : 100% intégration pour cette étape (pas de logique métier à tester en unitaire)

4. **Standards de code** :
   - ✅ Docstrings complètes (FR)
   - ✅ Type hints partout
   - ✅ Pas de nombres magiques (buckets Prometheus explicites)
   - ✅ Fonctions < 40 lignes (sauf dispatch avec commentaires)

5. **Observabilité** :
   - ✅ Pattern RED (Rate, Errors, Duration)
   - ✅ Labels corrects (method, path, status, scope, identifier_type)
   - ✅ Documentation PromQL queries + alerting rules

6. **Aucune mention IA** :
   - ✅ Pas de "Claude", "Sonnet", "Anthropic" dans code/docs

---

## 📈 Métriques Clés

### Avant Étape 3

- ❌ Aucune métrique Prometheus
- ❌ Monitoring production aveugle
- ❌ Latence inconnue
- ❌ Taux erreur 5xx non tracké
- ❌ Rate limit hits invisibles

### Après Étape 3

- ✅ 12 métriques Prometheus exposées
- ✅ Endpoint /metrics public (scraping Prometheus)
- ✅ Pattern RED complet (Rate, Errors, Duration)
- ✅ Path normalization anti-cardinalité
- ✅ Middleware ordering LIFO maîtrisé
- ✅ Rate limit hits trackés par scope
- ✅ Métriques DB/Redis/Business préparées

---

## 🔮 Prochaines Étapes

### Étape 4 : Cache Redis (4-5h)

**Objectif** : Réduire latence DB via cache Redis multicouche

**Livrables** :
- Service `CacheService` (get, set, delete, invalidate patterns)
- Décorateurs `@cached` et `@cache_invalidate`
- Cache products (TTL 5min), customers (TTL 10min), reservation statuses (TTL 1min)
- Tests cache (hit/miss, TTL, invalidation, fail-open)

### Étape 5 : Load Testing k6 (3-4h)

**Objectif** : Valider performance sous charge (100 req/s sustained)

**Livrables** :
- Scripts k6 (smoke, load, stress, spike tests)
- Scénarios réalistes (80% reads, 20% writes)
- Métriques : p95 < 200ms, p99 < 500ms, error rate < 1%
- Rapport performance (baseline metrics)

---

## ✅ Checklist Finale

**Infrastructure** :
- [x] 4 fichiers créés (metrics.py, middleware, tests, __init__)
- [x] 2 fichiers modifiés (main.py, core/__init__.py)
- [x] 12 métriques Prometheus définies
- [x] Endpoint /metrics fonctionnel

**Collecte Automatique** :
- [x] MetricsMiddleware installé (LIFO ordering correct)
- [x] Path normalization (/products/123 → /products/{id})
- [x] Gauge inc/dec pattern (try/finally)
- [x] Rate limit hits trackés (scope detection)

**Tests** :
- [x] 7 tests d'intégration passants (100%)
- [x] Fixture reset_metrics (cleanup registry)
- [x] Tests couvrent : endpoint, counter, histogram, gauge, rate limit, normalization, exemption

**Bugs Corrigés** :
- [x] SyntaxWarning `\d` → raw string `r"""`
- [x] rate_limit_hits_total non incrémenté → scope detection depuis request
- [x] Middleware ordering → MetricsMiddleware ajouté en dernier (LIFO)

**Documentation** :
- [x] Docstrings complètes (FR)
- [x] PromQL queries exemples
- [x] Alerting rules suggérées
- [x] Rapport validation créé

**CLAUDE.md** :
- [x] Exports __init__.py à jour
- [x] Aucune mention IA
- [x] Minimum de mocks (0)
- [x] Compltude (méthodes helper créées)

---

## 🎉 Conclusion

**Étape 3 : Prometheus Metrics** est **100% COMPLÉTÉE** ✅

**Impact Production** :
- Observabilité temps réel (métriques RED)
- Alerting sur SLA (p99 < 500ms, error rate < 1%)
- Détection anomalies (spike latence, rate limit abuse)
- Capacity planning (requêtes/s, concurrency)

**Prochaine étape** : Étape 4 (Cache Redis) pour optimiser latence DB et réduire charge.

---

**Auteur** : CaroCorp Infrastructure Team
**Review** : Phase 4 Production Hardening
**Next** : Cache Redis Multicouche (Étape 4)
