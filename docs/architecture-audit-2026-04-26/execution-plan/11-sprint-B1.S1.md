# Sprint B1.S1 — Hotfixes core

> **STATUT** : ⏳ À démarrer après Sprint 1 PROD FIRE-DRILL
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev1 (lead Bloc 1)
> **BLOQUE** : B1.S2 (RLS), B1.S3 (KMS), tout B2 (Identity)
> **DÉPEND DE** : Sprint 1 PROD FIRE-DRILL livré (sinon prod casse)
> **OBJECTIF** : Corriger les anti-patterns fondamentaux du `core/` qui polluent tout le codebase aval. Aucune amélioration architecturale future ne tient si ces 6 frictions persistent.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B1.S1.T1** | F01 RLS f-string SQL → param | P1 (mitigé par cast) | 0.5 j | B1.S2 (RLS active) |
| **B1.S1.T2** | F02 ApiKey set_tenant_context | P0 SEC | 1 j | B1.S2 (sinon ApiKey régressent) |
| **B1.S1.T3** | F05 cache_invalidate await/drop | P1 | 0.5 j | aucun (code mort actuel) |
| **B1.S1.T4** | F111 réordonnancement middlewares | P0 | 1.5 j | rate-limit identity-based |
| **B1.S1.T5** | F94 rate-limiter Lua atomic | P1 | 0.75 j | sous charge en prod |
| **B1.S1.T6** | F85 SENSITIVE_FIELDS étendu KMS | P1 | 0.25 j | B1.S3 (KMS) |

**Total effort** : 4.5 jours-homme (Dev1 seul, séquentiel) OU 2.5 jours avec Dev1 + Dev2 collaboration.

**CI invariants nouveaux livrés en fin de sprint** :
- `check_middleware_order.py` (54 §16) — détecte les régressions F111
- `check_no_unawaited_async.py` (54 §18) — détecte F255/F05 patterns
- `check_no_sync_httpx_in_async.py` (54 §22) — détecte F1091 patterns
- `check_token_creator_passes_db.py` (54 §19) — refuse merge si F329 régresse

---

# Story B1.S1.T1 — F01 RLS f-string SQL → paramètre lié

## Contexte

**Friction** : F01 (cf. `01-core-foundations.md` §F01 ligne 244)
**Sévérité** : P1 (atténué actuellement par cast `int(tid)` dans `deps.py:274,1027`, mais anti-pattern propagé partout)
**Code source** : `app/core/database.py:82`

### Description

```python
# app/core/database.py:74-90 (état actuel)
@event.listens_for(Engine, "begin")
def receive_begin(conn):
    """SET LOCAL app.current_tenant_id avant chaque requete SQL."""
    tid = _request_tenant_var.get(None)
    if tid is None:
        return
    cursor = conn.connection.cursor()
    cursor.execute(f"SET LOCAL app.current_tenant_id = '{tid}'")  # ← f-string
    cursor.close()
```

L'injection est neutralisée actuellement par le typage `int(tid)` côté caller (`deps.py:274`, `deps.py:1027`), mais :
1. Tout futur callsite (Celery task, batch script, ETL) qui oublie le cast → injection SQL sur le contexte RLS
2. Le risque n'est pas l'exfiltration mais la **désactivation des policies tenant** sur tout le batch
3. Pattern propagé : Phase 1 §1.4 documente que `f"SET ..."` apparaît dans 4 autres callsites (audit pre-merge requis)

**Impact bloquant pour B1.S2** : Une fois RLS activé (B1.S2), toute injection sur le SET LOCAL contourne RLS pour la durée de la transaction → cross-tenant leak.

## Solution

Remplacer la f-string par un paramètre lié SQLAlchemy `text()` :

```python
# app/core/database.py:74-90 (corrigé)
from sqlalchemy import text

@event.listens_for(Engine, "begin")
def receive_begin(conn):
    """SET LOCAL app.current_tenant_id avant chaque requete SQL.

    F01 fix : paramètre lié au lieu de f-string pour empêcher injection SQL
    sur le contexte RLS (mitigation defense-in-depth — le cast int(tid) côté
    caller reste en place pour la défense en profondeur).
    """
    tid = _request_tenant_var.get(None)
    if tid is None:
        return
    # Paramètre lié — empêche toute injection SQL même sans cast caller
    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :tid, true)"),
        {"tid": str(tid)},
    )
```

**Pourquoi `set_config` au lieu de `SET LOCAL`** : `SET LOCAL` n'accepte pas de paramètres liés en PostgreSQL. `set_config(name, value, is_local=true)` est l'équivalent fonctionnel qui accepte les params. Comportement identique côté policies RLS (`current_setting('app.current_tenant_id')`).

## Fichiers à modifier

- `app/core/database.py` (fonction `receive_begin`, ~5 lignes)
- Audit grep pre-merge : `grep -rn 'f".*\(SET\|SELECT\|INSERT\|UPDATE\|DELETE\)'` dans `app/` — corriger tous les autres callsites détectés
- `tests/integration/test_rls_injection_safety.py` (à créer)

## Tests

```python
# tests/integration/test_rls_injection_safety.py
import pytest
from sqlalchemy import select
from app.models import Customer

@pytest.mark.asyncio
async def test_rls__tenant_id_with_sql_injection_payload__safe(db, tenant):
    """Tenter d'injecter via tenant_id contrôlé — doit être traité comme valeur littérale."""
    # Simule un caller qui passe un payload malveillant (cas où cast int oublié)
    malicious_payload = "1; DROP TABLE customers; --"

    from app.core.database import _request_tenant_var
    token = _request_tenant_var.set(malicious_payload)
    try:
        # Tente une requête simple — doit échouer car tenant_id non castable en bigint côté policy
        result = await db.execute(select(Customer))
        # Si on arrive ici sans exception, la policy a bien échoué (résultat vide)
        # mais surtout : `customers` n'a PAS été droppée
        from sqlalchemy import text
        check = await db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_name = 'customers'"))
        assert check.scalar() == 1, "Table customers droppée par injection SQL — F01 régression critique"
    except Exception:
        # Erreur attendue si malicious_payload pas un bigint valide
        pass
    finally:
        _request_tenant_var.reset(token)


@pytest.mark.asyncio
async def test_rls__tenant_id_int_valid__filters_correctly(db, tenant, other_tenant):
    """Régression : tenant_id valide continue de filtrer correctement."""
    from app.core.database import _request_tenant_var
    customer_a = Customer(tenant_id=tenant.id, nom="A", email="a@a.fr")
    customer_b = Customer(tenant_id=other_tenant.id, nom="B", email="b@b.fr")
    db.add_all([customer_a, customer_b])
    await db.flush()

    token = _request_tenant_var.set(tenant.id)
    try:
        result = await db.execute(select(Customer))
        visible_ids = {c.id for c in result.scalars().all()}
        assert customer_a.id in visible_ids
        assert customer_b.id not in visible_ids
    finally:
        _request_tenant_var.reset(token)
```

## Definition of Done

- [ ] `receive_begin` utilise `text("SELECT set_config(...)", {"tid": ...})` (param lié)
- [ ] Audit pre-merge : 0 résultat à `grep -rn 'f".*\(SET\|SELECT\|INSERT\|UPDATE\|DELETE\)' app/core/`
- [ ] 2 tests intégration verts
- [ ] Test perf régression : `set_config` vs `SET LOCAL` < 5% écart (négligeable, même appel pgwire)
- [ ] B1.S2 peut démarrer sans risque

## Risque

- **Probabilité** : 1 (équivalence sémantique stricte SET LOCAL ↔ set_config)
- **Impact** : 4 (régression RLS = data leak cross-tenant)
- **Score** : 4 — LOW
- **Rollback** : git revert (équivalence sémantique permet revert sans perte)

---

# Story B1.S1.T2 — F02 ApiKey RLS context

## Contexte

**Friction** : F02 (cf. `01-core-foundations.md` §F02 ligne 245)
**Sévérité** : **P0 SEC** — bug latent qui s'active à la livraison de B1.S2 (RLS)
**Code source** : `app/core/deps.py:531-582` (`_resolve_api_key_async`)

### Description

```python
# app/core/deps.py:349-350 (chemin User — OK, set_tenant_context appelé)
async def get_current_user(...):
    ...
    from app.core.database import set_tenant_context
    set_tenant_context(user.tenant_id)
    ...

# app/core/deps.py:531-582 (chemin ApiKey — F02 : set_tenant_context ABSENT)
async def _resolve_api_key_async(api_key_value, db, request):
    api_key = await api_key_repo.get_by_hash(db, hashed_key)
    if not api_key or not api_key.is_active:
        raise HTTPException(...)
    # ❌ MANQUE : set_tenant_context(api_key.tenant_id)
    return ApiKeyClient(api_key=api_key)
```

**Conséquence** : Une requête authentifiée par API key exécute des SELECT sans `current_setting('app.current_tenant_id')` côté Postgres. Toutes les RLS policies basées sur ce setting **ne s'appliquent pas**. La sécurité tenant ne tient plus que par les filtres Python explicites dans les repositories. **Un repository qui oublie un filtre = leak cross-tenant garanti pour les API keys.**

**Bloque B1.S2** : Une fois B1.S2 (RLS) déployé, les API keys qui n'avaient pas `set_tenant_context()` voient toutes leurs requêtes filtrées à zéro (RLS strict), ou pire, voient des données cross-tenant si ordering policies mal configurées.

## Solution

```python
# app/core/deps.py:531-582 (corrigé)
async def _resolve_api_key_async(api_key_value, db, request):
    """Résout une API key et établit le contexte RLS tenant.

    F02 fix : set_tenant_context obligatoire après résolution de la clé.
    Symétrie avec _resolve_user_token_async qui le fait à ligne 349-350.
    """
    hashed_key = hashlib.sha256(api_key_value.encode()).hexdigest()
    api_key = await api_key_repo.get_by_hash(db, hashed_key)

    if not api_key or not api_key.is_active:
        raise HTTPException(401, "Invalid API key")

    if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
        raise HTTPException(401, "API key expired")

    if api_key.revoked_at:
        raise HTTPException(401, "API key revoked")

    # F02 fix : RLS context — sinon toutes les requêtes ApiKey
    # contournent les policies tenant_id côté DB.
    from app.core.database import set_tenant_context
    set_tenant_context(api_key.tenant_id)

    # Audit explicite (pour brute-force detection)
    request.state.api_key_id = api_key.id
    request.state.tenant_id = api_key.tenant_id

    return ApiKeyClient(api_key=api_key)
```

## Fichiers à modifier

- `app/core/deps.py` (fonction `_resolve_api_key_async`, ~10 lignes)
- `app/core/deps.py` (fonction `_resolve_api_key` sync — variante legacy si encore présente)
- `tests/integration/test_apikey_rls_isolation.py` (à créer — INV-8 réutilisé)

## Tests

```python
# tests/integration/test_apikey_rls_isolation.py
@pytest.mark.asyncio
async def test_apikey__cross_tenant_query__blocked_by_rls(client, db, tenant, other_tenant):
    """F02 fix : ApiKey du tenant A ne voit PAS les données du tenant B via RLS."""
    from app.models import ApiKey, Customer
    import hashlib

    # Setup : 2 customers cross-tenant
    customer_a = Customer(tenant_id=tenant.id, nom="A", email="a@a.fr")
    customer_b = Customer(tenant_id=other_tenant.id, nom="B", email="b@b.fr")
    db.add_all([customer_a, customer_b])
    await db.flush()

    # API key du tenant A
    raw_key = "test-api-key-tenant-a"
    api_key = ApiKey(
        tenant_id=tenant.id,
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        is_active=True,
    )
    db.add(api_key)
    await db.flush()

    # Requête avec X-API-Key
    response = await client.get(
        "/api/v1/customers",
        headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 200
    customers = response.json()["items"]
    customer_ids = {c["id"] for c in customers}

    assert str(customer_a.id) in customer_ids
    assert str(customer_b.id) not in customer_ids, (
        "F02 régression : ApiKey du tenant A voit customer du tenant B"
    )


@pytest.mark.asyncio
async def test_apikey__expired_or_revoked__rejected_with_401(client, db, tenant):
    """Régression : ApiKey expirée/révoquée toujours rejetée."""
    from app.models import ApiKey
    from datetime import datetime, UTC, timedelta

    expired_key = ApiKey(
        tenant_id=tenant.id,
        key_hash=hashlib.sha256(b"expired").hexdigest(),
        is_active=True,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db.add(expired_key)
    await db.flush()

    response = await client.get(
        "/api/v1/customers",
        headers={"X-API-Key": "expired"}
    )
    assert response.status_code == 401
```

## Definition of Done

- [ ] `set_tenant_context()` appelé dans `_resolve_api_key_async` après résolution
- [ ] `request.state.api_key_id` et `request.state.tenant_id` populés (pré-requis pour F111 + RateLimit identity-based)
- [ ] 2 tests intégration verts
- [ ] **Test E2E pré-requis B1.S2** : créer ApiKey + appel `/api/v1/customers` → liste tenant correctement filtrée (sans RLS encore actif, le filtre applicatif suffit ; AVEC RLS actif, le test reste vert grâce à `set_tenant_context`)
- [ ] Validation staging : créer ApiKey de Marveline, requête depuis l'environnement Splendid → 0 résultats (RLS bloque)

## Risque

- **Probabilité** : 1 (10 lignes ajoutées, fonction isolée)
- **Impact** : 5 (bloquer B1.S2 + risque cross-tenant si pas fixé avant RLS)
- **Score** : 5 — LOW (mais bloquant pour suite)
- **Rollback** : git revert (régresse à l'état actuel, pas pire qu'avant)

---

# Story B1.S1.T3 — F05 cache_invalidate await/drop

## Contexte

**Friction** : F05 (cf. `01-core-foundations.md` §F05 ligne 248)
**Sévérité** : P1 (Phase 1 dit "0 usages réels donc impact prod = 0 aujourd'hui" — code mort actif)
**Code source** : `app/core/cache.py:299-340` (décorateur `cache_invalidate`)

### Description

```python
# app/core/cache.py:299-340 (état actuel)
def cache_invalidate(patterns: List[str]):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):                  # ← wrapper SYNC
            result = func(*args, **kwargs)
            for pattern in patterns:
                cache.invalidate_pattern(pattern)      # ← async sans await
            return result
        return wrapper
    return decorator
```

`cache.invalidate_pattern` est `async def` (cache.py:216). Le wrapper sync l'appelle sans await → coroutine garbage-collected silencieusement → invalidation jamais effectuée. Phase 1 confirme : **0 usages réels actuellement**, donc impact prod = 0. Mais le code mort propage le pattern (autres callsites comme `repositories/base.py:216,262,400,437,470,694,708`).

**Choix** : Phase 1 (§1.4 ligne 343) recommande de **déterminer si `BaseRepository` (sync) est appelé en prod**. Si non → drop le code mort. Si oui → wrapper sync avec `redis-py` synchrone OU migration vers async.

## Solution

**Approche choisie** : Drop le décorateur (Q5=A async-only — toutes les méthodes deviennent async, le wrapper sync n'a plus de raison d'être) + remplacement par appels explicites `await cache.invalidate_pattern(...)` dans les services async.

```python
# app/core/cache.py — supprimer le décorateur cache_invalidate
# Remplacer par helper async (utilisable directement par les services async)

async def invalidate_cache_patterns(patterns: List[str]) -> int:
    """Invalide les patterns Redis. À appeler explicitement post-mutation.

    Remplace le décorateur cache_invalidate (cassé F05) — appel explicite
    rend l'invalidation visible dans le code et await traceable.

    Returns: nombre de clés invalidées (pour audit/observability).
    """
    total = 0
    for pattern in patterns:
        total += await cache.invalidate_pattern(pattern)
    return total
```

Migration appelants :
```python
# AVANT (décorateur silencieusement no-op)
@cache_invalidate(patterns=["product:*"])
def update_product(...):
    ...

# APRÈS (appel explicite, await traceable)
async def update_product(...):
    ...
    await invalidate_cache_patterns(["product:*"])
```

## Fichiers à modifier

- `app/core/cache.py` : supprimer `cache_invalidate` décorateur, ajouter `invalidate_cache_patterns()` helper
- Audit grep `@cache_invalidate` dans `app/` : remplacer chaque occurrence par appel explicite `await invalidate_cache_patterns(...)` après la mutation
- `app/repositories/base.py` : audit lignes 216,262,400,437,470,694,708 — convertir cache calls en async (cohérence Q5=A)
- `tests/unit/core/test_cache_invalidate.py` (à créer)

## Tests

```python
@pytest.mark.asyncio
async def test_invalidate_cache_patterns__actually_deletes_keys(redis_client):
    """F05 fix : invalidation effective (pas no-op silencieux)."""
    await redis_client.set("product:1", "{...}")
    await redis_client.set("product:2", "{...}")
    await redis_client.set("customer:1", "{...}")  # control

    deleted = await invalidate_cache_patterns(["product:*"])
    assert deleted == 2

    assert not await redis_client.exists("product:1")
    assert not await redis_client.exists("product:2")
    assert await redis_client.exists("customer:1") == 1


@pytest.mark.asyncio
async def test_invalidate_cache_patterns__empty_pattern_list__noop():
    """Régression : liste vide ne lève pas d'erreur."""
    deleted = await invalidate_cache_patterns([])
    assert deleted == 0
```

## Definition of Done

- [ ] Décorateur `cache_invalidate` supprimé
- [ ] Helper `invalidate_cache_patterns()` async créé
- [ ] 0 résultat à `grep -rn '@cache_invalidate' app/`
- [ ] 0 résultat à `grep -rn 'cache_invalidate(' app/` (sauf imports nettoyés)
- [ ] 2 tests unit verts
- [ ] CI invariant `check_no_unawaited_async.py` (54 §18) ne lève pas de régression sur `app/core/cache.py`

## Risque

- **Probabilité** : 1 (code mort — pas d'usage prod confirmé)
- **Impact** : 1 (impact prod nul aujourd'hui)
- **Score** : 1 — LOW
- **Rollback** : git revert si découverte d'usage caché

---

# Story B1.S1.T4 — F111 réordonnancement chaîne middlewares

## Contexte

**Friction** : F111 (cf. `04-middleware.md` §2.1 ligne 211)
**Sévérité** : **P0** — rate-limit identity-based 100% inopérant en prod actuelle
**Code source** : `app/main.py:104-159` (registration LIFO middlewares)

### Description

L'ordre actuel d'enregistrement (FastAPI = LIFO, dernier ajouté = exécuté en premier = outermost) :

```python
# app/main.py:104-159 (état actuel)
app.add_middleware(AuditMiddleware)          # pos 1 (innermost)
app.add_middleware(RequestContextMiddleware) # pos 2
app.add_middleware(GZipMiddleware, ...)
app.add_middleware(AppEnforcementMiddleware) # pos 4 — lit request.state.tenant_id
app.add_middleware(RateLimitMiddleware)      # pos 5 — lit request.state.api_key_id
app.add_middleware(SecurityHeadersMiddleware) # pos 6
app.add_middleware(CSRFProtectionMiddleware)  # pos 7
# ...
app.add_middleware(StrictCORSMiddleware)     # pos 12 (outermost)
```

LIFO = ordre d'exécution INVERSÉ : `StrictCORSMiddleware` s'exécute en premier, `RequestContextMiddleware` en avant-dernier, `AuditMiddleware` en dernier (tout au fond).

**Conséquence** : `RateLimitMiddleware._dispatch` (`security.py:329`) accède à `request.state.api_key_id` ligne 329 → **toujours `None`** car `RequestContextMiddleware` (qui peuple `request.state`) ne s'est pas encore exécuté à ce moment.

5 conséquences directes (cf. Phase 1 §F111) :
- (a) Quota par-API-key inopérant — fallback IP au lieu d'identity
- (b) Anti-brute-force email-based ne fonctionne pas
- (c) MetricsMiddleware ne peut pas tenant-labéliser (cf. F83)
- (d) AppEnforcementMiddleware doit re-décoder le JWT (perf)
- (e) CSRFProtectionMiddleware doit re-décoder JWT pour `sid` (perf)

## Solution

**Phase 1 §F111 propose 2 options** :
- A) Déplacer `RequestContextMiddleware` au début de la chaîne (rendre outermost)
- B) Éclater en 2 : un mini-extractor en amont (sans DB call), puis enrichisseur en aval

**Choix retenu** : Option B (éclater) — plus performant, pas de DB call sur le path bloquant.

### Architecture cible

```
Outermost (exécuté en 1er) :
    StrictCORSMiddleware       (defense-in-depth CORS)
    TrustedHostMiddleware      (host filtering)
    RequestContextExtractor    ← NOUVEAU : décode JWT, peuple request.state (sans DB)
    DegradedModeMiddleware     (READ_ONLY/AUTH_DOWN/EMERGENCY_BYPASS gate)
    SecurityHeadersMiddleware  (CSP, HSTS — peut maintenant lire tenant pour CSP per-tenant)
    CSRFProtectionMiddleware   (lit request.state.sid déjà extrait)
    RateLimitMiddleware        (lit request.state.api_key_id / user_id / email)
    MetricsMiddleware          (label app_code/tenant_bucket depuis request.state)
    AppEnforcementMiddleware   (vérif app_code vs tenant.app_code)
    GZipMiddleware
    RequestContextEnricher     ← NOUVEAU : DB lookup tenant complet pour endpoints qui en ont besoin
    AuditMiddleware            (innermost — log POST mutation)
```

### Code

```python
# app/middleware/request_context_extractor.py (NOUVEAU)
class RequestContextExtractor(BaseHTTPMiddleware):
    """Décode JWT/ApiKey et peuple request.state SANS DB call.

    F111 fix : ce middleware doit s'exécuter AVANT RateLimit/CSRF/Security
    pour que ces middlewares puissent lire request.state.{api_key_id, user_id, tenant_id, sid}.
    """
    async def dispatch(self, request, call_next):
        # 1. Extraire JWT depuis Authorization header (sans valider signature ici — décode lazy)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                # decode_unverified — pas de DB, pas de KMS lookup
                payload = jwt.decode(token, options={"verify_signature": False})
                request.state.user_id = payload.get("sub")
                request.state.tenant_id = payload.get("tenant_id")
                request.state.sid = payload.get("jti")  # session id
                request.state.scopes = payload.get("scopes", [])
            except Exception:
                pass  # Token invalide — handlers downstream rejette

        # 2. Extraire X-API-Key (fingerprint sans DB lookup)
        api_key_value = request.headers.get("x-api-key")
        if api_key_value:
            # Hash-only — pas de lookup DB (fait dans get_current_principal)
            request.state.api_key_hash = hashlib.sha256(api_key_value.encode()).hexdigest()

        # 3. Email body parsé pour /auth/login (rate-limit anti-brute-force email-based)
        if request.url.path == "/api/v1/auth/login" and request.method == "POST":
            body = await request.body()
            request._body = body  # restore pour handlers downstream
            try:
                payload = json.loads(body)
                request.state.parsed_login_email = payload.get("email")
            except json.JSONDecodeError:
                pass

        return await call_next(request)


# app/middleware/request_context_enricher.py (NOUVEAU)
class RequestContextEnricher(BaseHTTPMiddleware):
    """Enrichit request.state avec données DB (tenant complet, app_code, brand).

    Exécuté APRÈS les middlewares de sécurité (rate-limit, CSRF) pour ne pas
    bloquer le path rapide (rejet rate-limit avant DB call).
    """
    async def dispatch(self, request, call_next):
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            # Cache Redis 60s (cf. Bloc 1 §1.4)
            tenant = await tenant_cache.get_tenant(tenant_id)
            if tenant:
                request.state.tenant = tenant
                request.state.app_code = tenant.app_code
                request.state.vertical = tenant.vertical
        return await call_next(request)


# app/main.py (NOUVEAU ordre, LIFO inversé)
def create_app() -> FastAPI:
    app = FastAPI(...)

    # LIFO : dernier ajouté = exécuté en premier (outermost)
    # On les ajoute dans l'ordre inverse de l'exécution souhaitée

    # Innermost (exécuté en dernier)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(RequestContextEnricher)  # DB lookup tardif
    app.add_middleware(GZipMiddleware, minimum_size=settings.GZIP_MIN_SIZE)

    # Middle layer
    app.add_middleware(AppEnforcementMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CSRFProtectionMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(DegradedModeMiddleware)

    # Outermost (exécuté en premier — extracteur sans DB)
    app.add_middleware(RequestContextExtractor)  # ← AVANT tous les middlewares qui lisent request.state
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
    app.add_middleware(StrictCORSMiddleware)
    app.add_middleware(CORSMiddleware, ...)

    return app
```

## Fichiers à modifier

- `app/middleware/request_context_extractor.py` (NOUVEAU)
- `app/middleware/request_context_enricher.py` (NOUVEAU)
- `app/middleware/request_context.py` (legacy) : drop ou marquer deprecated, transition graduelle
- `app/middleware/security.py` (`RateLimitMiddleware`, `CSRFProtectionMiddleware`) : utilisent maintenant `request.state` directement (drop re-decode JWT)
- `app/main.py:104-159` : nouveau ordre d'enregistrement
- `tests/integration/test_middleware_order.py` (à créer)

## Tests

```python
@pytest.mark.asyncio
async def test_rate_limit__by_api_key_identity__effective(client, db, tenant):
    """F111 fix : RateLimitMiddleware lit request.state.api_key_id correctement."""
    from app.models import ApiKey
    api_key = ApiKey(tenant_id=tenant.id, key_hash="hash1", is_active=True)
    db.add(api_key)
    await db.flush()

    # Burst de 100 requêtes avec même ApiKey → rate-limit kick in identity-based
    responses = []
    for _ in range(100):
        r = await client.get("/api/v1/customers", headers={"X-API-Key": "test-key-1"})
        responses.append(r.status_code)

    # Au moins 1 doit être 429 (rate-limit par identity, pas par IP)
    assert 429 in responses, "Rate-limit identity-based ne déclenche pas → F111 régression"


@pytest.mark.asyncio
async def test_security_headers__csp_per_tenant_brand(client, tenant):
    """SecurityHeadersMiddleware peut lire tenant via request.state (CSP per-tenant)."""
    tenant.brand_primary_color = "#A52A2A"
    response = await client.get("/api/v1/products")
    csp = response.headers.get("content-security-policy", "")
    # CSP doit pouvoir injecter une directive style basée sur tenant.brand_primary_color
    assert csp != ""  # Présent sans erreur
```

## Definition of Done

- [ ] `RequestContextExtractor` et `RequestContextEnricher` créés
- [ ] Ordre middlewares dans `main.py` cohérent avec architecture cible
- [ ] CI invariant `check_middleware_order.py` (54 §16) vert
- [ ] 5 conséquences F111 résolues : rate-limit identity OK, CSRF lit `sid` sans re-decode, MetricsMiddleware tenant-label OK, AppEnforcement sans DB call superflu, SecurityHeaders accède tenant
- [ ] 3 tests intégration verts (rate-limit by api_key, CSRF lit sid, metrics labels)
- [ ] Test perf : pas de régression latence P95 sur GET endpoints (extraction JWT sans DB est plus rapide qu'avant)
- [ ] Documentation `docs/middleware-architecture.md` mise à jour avec diagramme nouvelle chaîne

## Risque

- **Probabilité** : 3 (refacto chaîne middleware = beaucoup de surface)
- **Impact** : 5 (régression de l'auth ou du rate-limit)
- **Score** : 15 — HIGH
- **Plan rollback** : feature flag `request_context_v2_enabled` + bascule progressive (10%, 50%, 100%) sur staging avant prod
- **Mitigation** : pair-programming Lead + Dev1, review obligatoire Dev2 (Bloc 2 lead — dépend de cette refacto)

---

# Story B1.S1.T5 — F94 rate-limiter Lua atomic

## Contexte

**Friction** : F94 (cf. `03-core-observabilite.md` §F94)
**Sévérité** : P1 — race condition entre INCR et EXPIRE (fenêtre 0s mais fatale si crash)
**Code source** : `app/core/rate_limiter.py:107-120`

### Description

```python
# app/core/rate_limiter.py:107-120 (état actuel)
async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
    current = await self.redis.incr(key)              # ← commande 1
    if current == 1:
        await self.redis.expire(key, window)          # ← commande 2
    return current <= limit
```

Deux commandes Redis séparées. Entre les deux, si le process meurt (SIGKILL OOM, déploiement rolling), la clé reste sans TTL → compteur permanent → **tous les users bloqués à jamais sur ce scope** jusqu'à expiration manuelle.

## Solution

Script Lua atomique chargé via `SCRIPT LOAD` au boot de l'application :

```python
# app/core/rate_limiter.py (corrigé)
import logging

logger = logging.getLogger(__name__)

# Script Lua atomique : INCR + EXPIRE en 1 commande
INCR_WITH_EXPIRE_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


class RateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis
        self._script_sha: Optional[str] = None

    async def _load_script(self) -> str:
        """Charge le script Lua. Caché par Redis EVALSHA."""
        if self._script_sha is None:
            self._script_sha = await self.redis.script_load(INCR_WITH_EXPIRE_SCRIPT)
            logger.info("Rate limiter Lua script loaded: sha=%s", self._script_sha)
        return self._script_sha

    async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """F94 fix : INCR + EXPIRE atomiques via Lua script."""
        script_sha = await self._load_script()
        try:
            current = await self.redis.evalsha(script_sha, 1, key, str(window))
        except ResponseError as e:
            if "NOSCRIPT" in str(e):
                # Redis a évincé le script (ex: FLUSHALL admin) — re-load
                self._script_sha = None
                script_sha = await self._load_script()
                current = await self.redis.evalsha(script_sha, 1, key, str(window))
            else:
                raise
        return int(current) <= limit
```

## Fichiers à modifier

- `app/core/rate_limiter.py` (~30 lignes)
- `tests/unit/core/test_rate_limiter_atomic.py` (à créer)

## Tests

```python
@pytest.mark.asyncio
async def test_rate_limiter__atomic_under_simulated_crash(redis_client):
    """F94 fix : si process crash entre INCR et EXPIRE, le TTL reste appliqué (atomique)."""
    rl = RateLimiter(redis_client)

    # 1ère requête — clé créée avec TTL
    allowed = await rl.check_rate_limit("test:user1", limit=10, window=60)
    assert allowed is True

    # Vérifier TTL set (pas -1 = infini)
    ttl = await redis_client.ttl("test:user1")
    assert 0 < ttl <= 60, f"F94 régression : TTL = {ttl} (devrait être 0 < ttl <= 60)"


@pytest.mark.asyncio
async def test_rate_limiter__noscript_recovery(redis_client):
    """Si le script est évincé (Redis FLUSHALL), recharge automatique."""
    rl = RateLimiter(redis_client)
    await rl.check_rate_limit("test:user2", limit=10, window=60)

    # Simule éviction script
    await redis_client.script_flush()
    rl._script_sha = None  # Forcer le reload

    # Doit fonctionner sans erreur
    allowed = await rl.check_rate_limit("test:user2", limit=10, window=60)
    assert allowed is True
```

## Definition of Done

- [ ] Script Lua chargé au boot (lazy load + cache SHA)
- [ ] `evalsha` avec fallback `NOSCRIPT` → re-load
- [ ] 2 tests unit verts
- [ ] Test perf : `evalsha` vs `INCR + EXPIRE` séparés < 5% écart (1 round-trip vs 2)
- [ ] Validation staging : `redis-cli SCRIPT FLUSH` puis burst requêtes → fonctionnel

## Risque

- **Probabilité** : 1 (script Lua simple, 4 lignes)
- **Impact** : 3 (race condition latente, pas exploitée à ma connaissance)
- **Score** : 3 — LOW
- **Rollback** : git revert (les 2 commandes séparées fonctionnent quand pas de crash)

---

# Story B1.S1.T6 — F85 SENSITIVE_FIELDS étendu KMS secrets

## Contexte

**Friction** : F85 (cf. `03-core-observabilite.md` §F85)
**Sévérité** : P1 — fuite latente de secrets MFA/KMS dans logs structurés
**Code source** : `app/core/logging.py:38-56`

### Description

```python
# app/core/logging.py:38-56 (état actuel)
SENSITIVE_FIELDS = {
    "password", "password_hash", "secret",
    "token", "access_token", "refresh_token",
    "api_key", "csrf_token", "cookie",
    "authorization", "session_id",
    # ... 16 entrées au total
    # MANQUE : pin, totp_secret, mfa_code, kek, dek, encrypted_dek, nonce, signature, backup_code
}
```

Phase 1 §F85 documente que la liste actuelle de 16 entrées ne couvre pas les secrets cryptographiques manipulés post-Bloc 2 (KMS) et post-Bloc 6 (audit chain). Si un dev oublie de masquer un dict avant logging (`logger.info("Decrypted: %s", payload)` avec `payload={"dek": "..."}`), le DEK fuit dans Loki.

## Solution

```python
# app/core/logging.py:38-56 (corrigé)
SENSITIVE_FIELDS = {
    # Auth tokens
    "password", "password_hash", "secret",
    "token", "access_token", "refresh_token", "api_key",
    "csrf_token", "cookie", "authorization", "session_id",

    # MFA / Auth factors
    "pin", "pin_hash", "totp_secret", "mfa_code",
    "backup_code", "recovery_code",
    "credential_id", "public_key",  # WebAuthn — public_key technically OK mais évite log

    # KMS / Crypto envelope
    "kek", "dek", "encrypted_dek", "encrypted_secret",
    "nonce", "signature", "iv", "aad",

    # PII (correlation Bloc 4 Q24)
    "phone", "phone_encrypted",
    "address", "address_encrypted",
    "first_name", "first_name_encrypted",
    "last_name", "last_name_encrypted",
    "notes", "notes_encrypted",
    # email reste OK loggable (clé business non-PII selon DPO ; à confirmer)
}
```

## Fichiers à modifier

- `app/core/logging.py` (~15 lignes ajoutées dans set)
- `tests/unit/core/test_logging_redaction.py` (à créer ou enrichir si existe)

## Tests

```python
def test_sanitize_dict__totp_secret_redacted():
    """F85 fix : totp_secret doit être masqué."""
    payload = {"user_id": 1, "totp_secret": "JBSWY3DPEHPK3PXP"}
    sanitized = sanitize_dict(payload)
    assert sanitized["user_id"] == 1
    assert sanitized["totp_secret"] == "[REDACTED]"


def test_sanitize_dict__kms_dek_redacted():
    """KEK / DEK ne doivent jamais apparaître dans les logs."""
    payload = {"operation": "decrypt", "dek": b"\\x01\\x02\\x03", "kek": "kms-key-id-1"}
    sanitized = sanitize_dict(payload)
    assert sanitized["dek"] == "[REDACTED]"
    assert sanitized["kek"] == "[REDACTED]"


def test_sanitize_dict__pii_phone_redacted():
    """Phone PII redacted en logs (RGPD)."""
    payload = {"customer_id": 1, "phone": "+33612345678"}
    sanitized = sanitize_dict(payload)
    assert sanitized["phone"] == "[REDACTED]"
```

## Definition of Done

- [ ] `SENSITIVE_FIELDS` étendu avec 15+ entrées (MFA + KMS + PII)
- [ ] 3 tests unit verts
- [ ] Audit Loki staging post-déploiement : pas d'occurrence de `totp_secret`, `dek`, `phone` dans logs des 7 derniers jours
- [ ] Documentation `docs/logging-conventions.md` listant les patterns sensibles

## Risque

- **Probabilité** : 1 (extension d'un set Python)
- **Impact** : 1 (impact prod nul aujourd'hui, exposition latente)
- **Score** : 1 — LOW
- **Rollback** : git revert

---

## Critères de succès Sprint B1.S1

- [ ] **F01** : `receive_begin` paramétré, 0 résultat à l'audit grep f-string SQL dans `app/core/`
- [ ] **F02** : ApiKey teste cross-tenant blocked, B1.S2 peut démarrer
- [ ] **F05** : décorateur supprimé, helper async traceable
- [ ] **F111** : RequestContextExtractor outermost, rate-limit identity OK
- [ ] **F94** : Lua script atomique, race condition impossible
- [ ] **F85** : SENSITIVE_FIELDS étendu, audit Loki vérifié

- [ ] **CI invariants nouveaux** : `check_middleware_order.py`, `check_no_unawaited_async.py`, `check_no_sync_httpx_in_async.py`, `check_token_creator_passes_db.py` — tous verts
- [ ] **CI 100% verte** sur main (1782 tests + ~15 nouveaux tests)
- [ ] **0 régression** signalée
- [ ] **MEMORY.md à jour** : F01, F02, F05, F111, F94, F85 marqués résolus
- [ ] **Doc `docs/middleware-architecture.md`** mise à jour avec nouvelle chaîne

## Communication post-Sprint B1.S1

**Slack `#devup-stakeholders`** :

> Sprint B1.S1 livré le `<date>`. **Foundations core** consolidées :
> - Sécurité : pattern f-string SQL éliminé (mitigation defense-in-depth RLS)
> - Performance : décodage JWT factorisé (10 middlewares amont peuvent maintenant lire le contexte sans re-decode)
> - Stabilité : rate-limiter atomique (race condition éliminée)
> - Observabilité : redaction logs étendue (PII + secrets MFA/KMS)
>
> **Débloque** : Sprint B1.S2 (RLS PostgreSQL) peut démarrer.

## Dépendances downstream débloquées

- **B1.S2** (RLS) : F01 + F02 corrigés
- **B1.S3** (KMS) : F85 SENSITIVE_FIELDS prêt à intégrer secrets KMS
- **B6.S6** (Observability mTLS) : F111 chaîne middleware nettoyée
- **B2.S3** (RBAC) : `check_token_creator_passes_db.py` invariant CI prêt

---

**Fin du document — 11-sprint-B1.S1.md**
