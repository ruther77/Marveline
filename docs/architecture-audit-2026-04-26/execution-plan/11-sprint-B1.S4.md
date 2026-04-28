# Sprint B1.S4 — Stores Redis éclatés + auth/ découpé

> **STATUT** : ⏳ À démarrer après B1.S3
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1
> **BLOQUE** : B2.S4 (sessions cascade — dépend redis_sec splitté), B6.S4 (Celery broker)
> **DÉPEND DE** : B1.S1 (F94 rate-limiter Lua atomique)
> **OBJECTIF** : Séparer Redis en 3 instances logiques (`redis_sec`, `redis_cache`, `redis_general`) avec stratégies FAIL-OPEN/CLOSED documentées par middleware (R23). Découper `app/auth/` (legacy `UserCompat`) en services modulaires aligned RBAC v3.

## Vue d'ensemble

| Story | Description | Estimation | Bloque |
|---|---|---|---|
| **B1.S4.T1** | 3 Redis stores : sec / cache / general | 1.5 j | T2 |
| **B1.S4.T2** | DegradedModeMiddleware + stratégies FAIL-OPEN/CLOSED par middleware (R23) | 1.5 j | aucun |
| **B1.S4.T3** | Drop `UserCompat` legacy + découpage `app/auth/` | 2 j | B2.\* |
| **B1.S4.T4** | Rate-limit namespace tenant (F113) | 0.5 j | B7.S1 (cohérent vertical) |

**Total effort** : 5.5 jours-homme.

---

# Story B1.S4.T1 — 3 Redis stores

## Contexte

**Décision** : Phase 1 §1.4 + §S-08.4 (mode dégradé)
**Sévérité** : P0 — sans séparation, un incident sur le cache (volume) impacte aussi sessions/CSRF (sécurité)

### Description

3 instances Redis logiques (peuvent partager une instance physique en dev mais 3 connexions distinctes) :

| Store | Usage | TTL typique | Eviction policy | Priorité disponibilité |
|-------|-------|-------------|-----------------|----------------------|
| **redis_sec** | Sessions, CSRF, MFA pending, rate-limit, stepup | 5min-1h | `noeviction` (jamais évincer) | P0 — incident = auth down |
| **redis_cache** | Cache repository, scope cache, RFM bucket | 60s-1h | `allkeys-lru` (LRU OK) | P2 — incident = perf dégradée |
| **redis_general** | Outbox dedup keys, idempotence Celery | 24h | `allkeys-lru` | P1 |

## Solution

```python
# app/core/redis.py (refacto)
class RedisStore:
    """Wrapper Redis avec namespace prefix + métriques."""
    def __init__(self, name: str, url: str, fail_safe: bool = False):
        self.name = name
        self.client = aioredis.from_url(url, decode_responses=False)
        self.fail_safe = fail_safe

    async def get(self, key: str):
        try:
            return await self.client.get(key)
        except Exception as e:
            if self.fail_safe:
                logger.warning("redis_%s.get(%s) fail-safe : %s", self.name, key, e)
                return None
            raise


# Singletons
redis_sec = RedisStore("sec", settings.REDIS_SEC_URL, fail_safe=False)  # Fail strict
redis_cache = RedisStore("cache", settings.REDIS_CACHE_URL, fail_safe=True)  # Fail-open
redis_general = RedisStore("general", settings.REDIS_GENERAL_URL, fail_safe=True)
```

## Definition of Done

- [ ] 3 instances configurées dev/staging/prod
- [ ] Settings `REDIS_SEC_URL`, `REDIS_CACHE_URL`, `REDIS_GENERAL_URL`
- [ ] Migration callsites legacy `redis_client` → store dédié
- [ ] Test : redis_cache down → app continue (rate-limit fail-open)
- [ ] Test : redis_sec down → app refuse auth (fail-closed contrôlé via DegradedMode)

---

# Story B1.S4.T2 — DegradedModeMiddleware + stratégies (R23)

## Contexte

**R23** (cf. `05-risk-register.md`) : Cascade FAIL-CLOSED Redis-SEC down → app totalement inutilisable même pour read-only.

### Description

Stratégie par middleware en mode dégradé :

| Middleware | NOMINAL | READ_ONLY | AUTH_DOWN | EMERGENCY_BYPASS |
|------------|---------|-----------|-----------|------------------|
| SecurityHeaders | strict | strict | strict | strict |
| CSRFProtection | enforce | enforce GET=skip | skip POST allowed | skip all |
| RateLimit | redis_sec | in-memory fallback | in-memory fallback | skip |
| AppEnforcement | enforce | enforce | enforce | skip |
| Auth (require_user) | enforce | enforce | service degraded msg | bypass (admin only ops) |

**EMERGENCY_BYPASS** = mode de guerre activé manuellement par ops via Redis CLI (jamais via API — F1123 fix).

## Solution

> **TR-93 / Vague 2** : `DegradedModeMiddleware` lit Redis à chaque requête → 1 GET Redis × 10 000 req/s = surcharge réseau + latency +0.5ms. Cache local LRU TTL 5s mitige la pression Redis tout en gardant détection rapide changement de niveau.

```python
# app/middleware/degraded.py
from cachetools import TTLCache

class DegradedModeMiddleware(BaseHTTPMiddleware):
    """Lit le mode dégradé courant et l'expose à la chaîne via request.state.
    
    TR-93 fix : cache local LRU TTL 5s (évite 1 GET Redis par requête HTTP).
    """
    
    # Cache local par-pod : 1 entrée unique 'level' avec TTL 5s
    _cache: TTLCache = TTLCache(maxsize=1, ttl=5)
    _CACHE_KEY = "degraded_level"
    
    async def dispatch(self, request, call_next):
        # 1. Cache local hit (TR-93 fix) — évite hit Redis chaque requête
        cached = self._cache.get(self._CACHE_KEY)
        if cached is not None:
            level = cached
        else:
            # 2. Cache miss → lecture Redis + populate cache
            try:
                level = await redis_sec.get_degradation_level()
            except Exception:
                level = "AUTH_DOWN"  # Si redis_sec down, on entre en mode dégradé
            self._cache[self._CACHE_KEY] = level
        
        request.state.degraded_level = level

        # Hard-block sur mutations en READ_ONLY
        if level == "READ_ONLY" and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.url.path not in self._READ_ONLY_WHITELIST:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Service temporarily read-only", "level": level}
                )

        return await call_next(request)

    _READ_ONLY_WHITELIST = {
        "/api/v1/admin/provision/degraded/disable",  # Pour sortir du mode
    }
    
    @classmethod
    def invalidate_cache(cls):
        """Appelé par admin endpoint quand level change explicitement (force refresh < 5s)."""
        cls._cache.clear()
```

### Invalidation explicite admin

```python
# app/api/v1/endpoints/admin/degraded.py
@router.post("/admin/degraded/set-level", dependencies=[Depends(require_scope(Scope.SUPERADMIN))])
async def set_degradation_level(level: Literal["NOMINAL", "READ_ONLY", "AUTH_DOWN", "EMERGENCY_BYPASS"]):
    await redis_sec.set_degradation_level(level)
    DegradedModeMiddleware.invalidate_cache()  # propagation immédiate sans attendre TTL
    return {"level": level, "applied_at": datetime.now(UTC)}
```

### Tests perf + cohérence

```python
async def test_degraded_cache_reduces_redis_calls(redis_mock, client):
    """TR-93 — 100 requêtes HTTP successives → 1 seul GET Redis (cache TTL 5s)."""
    redis_mock.get.return_value = "NOMINAL"
    for _ in range(100):
        await client.get("/api/v1/health/live")
    assert redis_mock.get.call_count <= 2  # 1 cache miss initial + 1 éventuel post-TTL

async def test_degraded_cache_invalidate_on_admin_change(client, redis_mock):
    """Admin change level → cache invalidé → propagation immédiate."""
    redis_mock.get.return_value = "NOMINAL"
    await client.get("/api/v1/health/live")  # populate cache NOMINAL
    
    # Admin set READ_ONLY
    await client.post("/api/v1/admin/degraded/set-level", json={"level": "READ_ONLY"})
    redis_mock.get.return_value = "READ_ONLY"
    
    # Mutation suivante doit voir READ_ONLY (cache invalidé)
    response = await client.post("/api/v1/customers", json={...})
    assert response.status_code == 503
```

Migration des middlewares pour lire `request.state.degraded_level` :

```python
# app/middleware/security.py:RateLimitMiddleware
async def dispatch(self, request, call_next):
    level = getattr(request.state, "degraded_level", "NOMINAL")
    if level == "EMERGENCY_BYPASS":
        return await call_next(request)  # Skip rate-limit

    if level in ("AUTH_DOWN", "READ_ONLY"):
        # Fallback in-memory (par-pod, dégradé mais fonctionnel)
        await self._check_inmemory(request)
    else:
        await self._check_redis(request)
    return await call_next(request)
```

## Definition of Done

- [ ] DegradedModeMiddleware enregistré au bon niveau (cf. B1.S1.T4)
- [ ] 3 middlewares (RateLimit, CSRF, Auth) gèrent les 4 niveaux
- [ ] Tests E2E : redis_sec down → app sert GET / refuse POST
- [ ] Runbook ops `docs/ops/runbook-redis-sec-incident.md`
- [ ] R23 marqué résolu

## Risque

- Probabilité 2, impact 4 → score 8 MEDIUM

---

# Story B1.S4.T3 — Drop `UserCompat` legacy

## Contexte

**Friction** : F334 (vague 4) — `UserCompat.permissions` retourne `set()` systématiquement → tous les endpoints v1 RBAC v2 sans permissions effectives.

### Description

Migration des ~40 endpoints legacy de `UserCompat.permissions` vers `Account` + scopes v3. Effort élevé mais nécessaire pour merge B2.S3.

## Solution

```python
# app/core/deps.py (refacto)
# AVANT (legacy)
class UserCompat:
    @property
    def permissions(self) -> set[Permission]: return set()

async def get_current_user_legacy(...) -> UserCompat: ...

# APRÈS
async def get_current_principal(...) -> Principal:
    """Principal protocol post-Bloc 2 : Account + scopes v3."""
    ...

# Pont temporaire (dépréciation graduelle)
async def get_current_user(...) -> UserCompat:
    """DEPRECATED — utiliser get_current_principal. Sera supprimé en B2.S3."""
    principal = await get_current_principal(...)
    # Adaptateur scopes v3 → permissions v2 pour compat
    return UserCompat.from_principal(principal)
```

## Definition of Done

- [ ] `Principal` protocol défini
- [ ] `get_current_principal` opérationnel
- [ ] Pont `get_current_user` → `get_current_principal` fonctionnel
- [ ] ~40 endpoints migrés (audit list `grep require_permission` → 0)
- [ ] Suppression `UserCompat` planifiée B2.S3

## Risque

- Probabilité 4, impact 4 → score 16 CRITICAL
- Mitigation : pair-programming Lead + Dev1, déploiement progressif (10 endpoints/PR)

---

# Story B1.S4.T4 — Rate-limit namespace tenant (F113)

## Contexte

**Friction** : F113 (vague 3) — `RateLimitMiddleware` namespace global → cross-tenant collision

### Description

Clés Redis rate-limit doivent inclure `tenant_id` ou `vertical` pour éviter qu'un tenant épuise le quota d'un autre.

## Solution

```python
# app/core/rate_limiter.py
def build_key(scope: str, identifier: str, tenant_id: Optional[int] = None) -> str:
    """F113 fix : namespace tenant_id pour éviter collision cross-tenant."""
    if tenant_id is not None:
        return f"ratelimit:t{tenant_id}:{scope}:{identifier}"
    return f"ratelimit:global:{scope}:{identifier}"
```

Migration des callsites pour passer `tenant_id`.

## Definition of Done

- [ ] `build_key` accepte `tenant_id`
- [ ] Tous les callsites passent `request.state.tenant_id`
- [ ] Test : 2 tenants distincts ne se bloquent pas mutuellement

---

## Critères de succès Sprint B1.S4

- [ ] 3 stores Redis distincts opérationnels
- [ ] DegradedMode 4 niveaux fonctionnels (R23 résolu)
- [ ] UserCompat dépréciation engagée (~40 endpoints migrés)
- [ ] Rate-limit tenant-scoped (F113 résolu)

---

**Fin du document — 11-sprint-B1.S4.md**
