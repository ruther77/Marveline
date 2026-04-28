# Module 06 — Repository de base

## 1. Périmètre

| Fichier | LoC | Rôle |
|---|---|---|
| `app/repositories/base.py` | 730 | `BaseRepository` (sync) + `AsyncBaseRepository`, CRUD + cache Redis + filtre tenant |

**Total** : 730 LoC.

**Dépend de** : `app/models/base.py` (Base, TenantMixin, SoftDeleteMixin), `app/core/cache.py` (lazy import via `_get_cache_service`), `app/core/metrics.py` (lazy import), `sqlalchemy`.

**Dépendu par** : ~46 sous-repositories métier (`customer`, `product`, `reservation`, …) + `core/deps.py` (`AsyncAccountRepository`, `AsyncTenantMembershipRepository`).

**Adoption observée** :
- `BaseRepository` (sync) — utilisé par la majorité (`supplier`, `delivery_zone`, `evenements`, `category`, `bundle`, etc.).
- `AsyncBaseRepository` — utilisé par `AsyncProductRepository`, `AsyncLoyalty*` (5 classes loyalty), et probablement le repository account/membership (lazy import dans `core/deps`).

---

## 2. Lecture par fichier

### 2.1 Constantes / helpers module-level

- Logger initialisé ligne 6, **après** un import sqlalchemy ligne 4 (ordering inhabituel).
- `_get_cache_service()` (ligne 14) — lazy import `app.core.cache.cache_service` pour casser le cycle :
  > `repositories.base → core.cache → core.__init__ → core.deps → services → repositories.base`
- `_get_cache_metrics()` (ligne 18) — idem pour `cache_hits_total`, `cache_misses_total`, `cache_hit_rate`.
- `T = TypeVar("T", bound=Base)` (ligne 24).

### 2.2 `BaseRepository[T]` (lignes 27-518)

#### `__init__(db: Session, model_class: Type[T])` (ligne 49)
- `_cache_ttl_map` hardcodé pour 4 entités : Product=300s, Customer=600s, Reservation=60s, Invoice=180s. Default 300s pour le reste.

#### Helpers privés

- `_get_cache_key(entity_id, tenant_id) -> str` (ligne 65) : `f"v2:{entity_name.lower()}:{tenant_id}:{entity_id}"`.
- `_get_cache_ttl()` (ligne 82) : lookup `_cache_ttl_map[__name__]`, fallback 300s.
- `_has_tenant_mixin()` / `_has_soft_delete_mixin()` (lignes 91, 95) : `issubclass(self.model_class, ...)`.
- `_apply_tenant_filter(query, tenant_id)` (ligne 99) : `query.filter(model_class.tenant_id == tenant_id)` si TenantMixin.
- `_apply_active_filter(query)` (ligne 113) : `query.filter(model_class.is_active == True)` (literal True, pas `is_(True)`).
- `_apply_filters(query, filters)` (ligne 126) : opérateurs `__gt`, `__gte`, `__lt`, `__lte`, `__ne` ; égalité par défaut. **Opérateurs inconnus ignorés silencieusement** (ligne 158 commentaire explicite).
- `_update_cache_hit_rate(entity_name)` (ligne 164) : lit `cache_hits_total.labels(...)._value.get()` (API privée Prometheus) pour calculer `hits/(hits+misses)` et set la Gauge `cache_hit_rate`.

#### CRUD sync

##### `get_by_id(id, tenant_id, include_inactive=False)` (ligne 188)
1. **Cache lookup** (ligne 215-216) :
   ```python
   cache_service = _get_cache_service()
   cached_data = cache_service.get(cache_key)  # ← async def appelé sync
   ```
   `cache_service.get` est `async def get(self, key) -> Optional[Any]` (cache.py:85). **Appelé depuis cette méthode sync sans `await`**.
2. **Si `cached_data is not None`** (ligne 218) : True systématiquement (une coroutine n'est jamais None).
3. INC `cache_hits_total` à tort (ligne 222).
4. Lookup `identity_map` :
   - Si entity en session → vérifie `tenant_id` (ligne 233) + `is_active` (ligne 236) → retourne ou None.
   - Si pas en session → `from_dict(cached_data)` (ligne 241) avec coroutine en argument → **lève**, `merge` jamais atteint.
5. Cache MISS (ligne 245-264) : query DB avec filtre tenant, retourne ; **`cache_service.set(..., to_dict(), ttl=ttl)` (ligne 262) appelé sync sur async** → coroutine perdue, cache jamais écrit. La branche du **prochain appel** repassera donc systématiquement par DB.

##### `list(tenant_id, skip, limit=100, filters, include_inactive, order_by)` (ligne 266)
- Pas de cache (commentaire ligne 277-282 : "choix délibéré").
- Limite max `min(limit, 1000)`.
- Window function `func.count().over().label("_total")` (ligne 304) : un seul round-trip DB pour items + total.
- Tri : `order_by` si valide, sinon `model_class.id`.
- Retourne `(items, total)`.

##### `count(tenant_id, filters, include_inactive)` (ligne 324)
- Query séparée `SELECT COUNT(*) FROM ...`. **Pas de réutilisation** du `_total` de `list()` (qui le calcule déjà via window).

##### `create(obj)` (ligne 352)
- Validation `tenant_id is not None` si TenantMixin → sinon raise `ValueError`.
- `db.add(obj) ; db.flush() ; db.refresh(obj)`. Pas de commit (controle service).

##### `update(obj)` (ligne 380)
- `db.flush() ; db.refresh(obj)`.
- Si TenantMixin : `_get_cache_service().delete(cache_key)` (ligne 400) → **idem F168, async appelé sync** → coroutine perdue, **cache jamais invalidé**.
- Commentaire ligne 392 : "write-through pattern" — en réalité write-around (invalide sans re-populer).

##### `soft_delete(id, tenant_id)` (ligne 404)
- Raise `NotImplementedError` si pas SoftDeleteMixin.
- `obj = get_by_id(...)` (passe par F168 — l'exception sur from_dict est probablement attrapée par try silencieux ailleurs ou jamais déclenchée si cache_data n'est pas un dict valide).
- `obj.soft_delete() ; db.flush()`.
- Cache delete (ligne 437) — idem F168.

##### `hard_delete(id, tenant_id)` (ligne 441)
- `get_by_id(include_inactive=True)`.
- `db.delete(obj) ; db.flush()`.
- Cache delete (ligne 470) — idem F168.

##### `exists`, `restore` (lignes 474, 490)
- `restore` : raise `NotImplementedError` si pas SoftDeleteMixin. Si `obj.is_active` est déjà True → return False. **Ne supprime pas le cache** après restore (ligne 516-518).

### 2.3 `AsyncBaseRepository[T]` (lignes 521-729)

Hérite de `BaseRepository[T]` mais **redéfinit toutes les méthodes CRUD** en async.

#### `__init__(db: AsyncSession, model_class)` (ligne 531)
- `self.db = db` avec `# type: ignore[assignment]` (ligne 532) — viol de typage de la classe parent (qui attend `Session`).
- `_cache_ttl_map` **dupliqué** (ligne 534-539).

#### `get_by_id(id, tenant_id, include_inactive=False)` (ligne 541)
- **Lock anti-race** (ligne 551-555) : si `cache_lock:{cache_key}` actif, skip cache (P2-02/03). Le lock est posé par `update()` async pour 2s.
- Sinon `await _cache_svc.get(cache_key)` → vrai await, **fonctionne**.
- Identity map check via `self.db.sync_session.identity_map.get(key)` (ligne 564).
- **Post-merge tenant verification** (ligne 575-581) : check explicite `instance.tenant_id != tenant_id` après `merge()`. Log CRITICAL si mismatch (P1-02 defense en profondeur).

  ⚠️ **Cette protection n'existe PAS dans la version sync** (ligne 188-264).

- DB miss → `await self.db.execute(query)` puis `await _cache_svc.set(cache_key, obj.to_dict(), ttl=ttl)`.

#### `update(obj)` (ligne 664)
- `await flush ; await refresh`.
- **Lock anti-race** (lignes 672-674) : `await cache_svc.set(lock_key, "1", ttl=2)` AVANT `await cache_svc.delete(cache_key)`.

#### `hard_delete(id, tenant_id)` (ligne 698)
- ⚠️ Ligne 704 : `self.db.delete(obj)` **non awaité** (mais `delete` sur `AsyncSession` est sync dans SQLAlchemy 2.x — vérifier au runtime).

#### `soft_delete`, `exists`, `restore` (lignes 679, 712, 716)
- Pattern correct async.
- `restore()` ligne 716-729 : pas d'invalidation cache après restore (idem version sync).

---

## 3. Frictions identifiées

(Numérotation continue — F168 commence après le module 05.)

### 3.1 Frictions P0

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F168** | base sync | **`BaseRepository` (sync) appelle des méthodes `async def` du `cache_service` sans `await` — 4 sites** | Sites :<br>`base.py:216` (`cache_service.get`)<br>`base.py:262` (`cache_service.set`)<br>`base.py:400` (`_get_cache_service().delete`)<br>`base.py:437` (`_get_cache_service().delete`)<br>`base.py:470` (`_get_cache_service().delete`)<br>cache.py définit `async def get/set/delete` lignes 85, 132, 180. | Confirmation directe de F05 module 01.<br>Conséquences :<br>(a) **`get_by_id` cache-HIT path est cassé** : `cached_data = cache_service.get(...)` retourne une **coroutine**, jamais un dict. `if cached_data is not None:` est **toujours True** → branche cache HIT exécutée à tort. INC `cache_hits_total` à chaque appel (F178 affecté). `from_dict(coroutine)` lève, message d'erreur masqué dans le contexte général ou la coroutine garbage-collectée donne un `RuntimeWarning: coroutine was never awaited`.<br>(b) **`update`, `soft_delete`, `hard_delete` n'invalident PAS le cache** : `_get_cache_service().delete(...)` retourne une coroutine perdue. Si jamais le cache async fonctionne par ailleurs, **les données sont stale après mutation**.<br>(c) **`get_by_id` cache MISS ne CACHE PAS le résultat** : `cache_service.set(...)` retourne une coroutine perdue. Tout cache MISS reste un cache MISS la fois d'après → **DB hit à chaque appel**.<br>**Status réel** : impossible d'évaluer sans run. Soit la couche cache sync est **complètement non-fonctionnelle** (Celery + scripts hit la DB systématiquement), soit `from_dict` raise et un try/except plus haut tolère. Dans tous les cas, 0 valeur ajoutée du cache pour les flux sync.<br>**À fixer** : soit créer `cache_service_sync` qui utilise un client Redis sync (`redis.Redis` au lieu de `redis.asyncio.Redis`), soit déprécier `BaseRepository` sync au profit de `AsyncBaseRepository` partout. |
| **F169** | base | **`to_dict()` cache TOUS les champs en Redis — y compris secrets et PII** | `base.py:262` (sync), `base.py:599` (async) appellent `cache_service.set(cache_key, result.to_dict(), ttl=ttl)` ; `to_dict` itère sur **toutes les colonnes** (`models/base.py:39-46`, cf F150 module 05) | Confirmation directe de F150 module 05.<br>Pour chaque entité cachée :<br>- `Account` → `hashed_password`, `email`, `first_name`, `last_name` cachés en clair en Redis.<br>- `MFADevice` → `encrypted_secret`, `encrypted_dek` cachés.<br>- `WebAuthnCredential` → `public_key` cachée.<br>- `Customer` → `email`, `phone`, `address`, `siret` cachés.<br>- `ApiKey` → `key_hash` (hash, pas catastrophique mais inutile).<br>**Si Redis est compromis** (RCE, dump mémoire, snapshot exposé), tous les secrets et PII sont exfiltrés. Multiplie l'impact d'un breach Redis × 100. À fixer en priorité avec F150 (`__cache_excluded_fields__` ou bascule vers Pydantic).<br>**TTL aggravant** : Customer caché 600s, Reservation 60s — fenêtre suffisante pour exfiltration. |
| **F170** | base | **Protection cross-tenant post-merge MANQUE en sync** | `base.py:241-243` (sync) merge sans vérif post-merge ; vs `base.py:575-581` (async) qui vérifie explicitement `instance.tenant_id != tenant_id` après merge | Si on fix F168 (le cache sync fonctionne) et qu'une entrée cache est empoisonnée (cross-tenant via clé corrompue, race condition, exploit Redis), le **sync repo** charge l'objet d'un autre tenant **sans aucune vérification**. La protection async (P1-02 commentaire ligne 574) reconnaît explicitement ce risque mais ne l'applique pas en sync. Combiné avec F148 module 05 (pas de FK), aucune contrainte côté DB non plus. À ajouter le même check en sync. |
| **F171** | base | **`_apply_filters` ignore silencieusement les opérateurs inconnus** | `base.py:142-160` (commentaire explicite ligne 158 : « Opérateur inconnu : ignorer silencieusement ») | Si un caller fait `filters={"status__likes": "active"}` (typo `like → likes`) ou `filters={"role__exact": "admin"}` (operator inexistant) :<br>- Le `if "__" in key` matche.<br>- Aucun `if operator == "likes"` ne matche.<br>- **Aucun filtre n'est appliqué**, le commentaire ligne 158 confirme.<br>- Query retourne **TOUS les éléments du tenant**.<br>**Faille de filtrage** : un endpoint qui s'attend à filtrer sur `is_admin__likes=True` retourne tous les users, exposant des données. À fixer : raise `ValueError(f"Unknown operator '{operator}'")` au lieu de fall-through silencieux. |

### 3.2 Frictions P1

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F172** | base | `_update_cache_hit_rate` accède `_value.get()` (API privée Prometheus) | `base.py:178-179` (`cache_hits_total.labels(entity=entity_name)._value.get()`) | `_value` est un attribut interne de `prometheus_client.Counter`. Cassera silencieusement à la prochaine version mineure de la lib. Le calcul devrait être fait côté Prometheus (cf F98 module 03). À supprimer cette Gauge maintenue manuellement. |
| **F173** | base sync | **F168 + F148 (FK manquante) = combo dangereux** | F168 + F148 (module 05) | Si on fix F168 mais pas F148 :<br>- Cache reconstruit via `from_dict` peut contenir `tenant_id=99999` (valeur en cache historique d'un tenant qui n'existe plus, ou valeur exploitée).<br>- `merge()` insère sans contrainte FK.<br>- F170 (manque post-merge check) → l'entité d'un tenant inexistant arrive dans la session.<br>Combinaison à traiter ensemble : F148 + F168 + F170. |
| **F174** | base sync | **`update` invalidate cache mais pas de lock anti-race** | `base.py:380-402` ; vs `base.py:664-677` (async avec lock 2s) | Sans lock : si un autre worker fait `get_by_id` pendant que l'update est en cours, il peut re-populer le cache avec les anciennes valeurs juste après le `delete`. La version async corrige avec un lock de 2s (P2-02/03). Sync n'a pas cette protection. À porter ou supprimer le sync repo. |
| **F175** | base | **`count()` ne réutilise pas le `_total` de `list()`** | `base.py:266-322` (window function) vs `base.py:324-350` (SELECT COUNT séparé) | Pattern courant en pagination : `items, total = repo.list(...)`. `list()` renvoie déjà total via window function. Mais beaucoup d'endpoints appellent ensuite `count()` séparément → 2 queries DB au lieu d'une. À auditer dans les services qui consomment ces 2 méthodes. |
| **F176** | base | **`hard_delete` ne refuse pas un modèle SoftDeleteMixin** | `base.py:441-472` | Si un modèle a `SoftDeleteMixin`, hard delete devrait être interdit ou exiger un flag explicite (`force=True`). Sinon le pattern soft-first/hard-after est cassable. À ajouter check : `if self._has_soft_delete_mixin() and not force: raise ValueError("Use soft_delete first")`. |
| **F177** | base async | **`AsyncBaseRepository.hard_delete` appelle `self.db.delete(obj)` sans `await`** | `base.py:704` | `AsyncSession.delete` retourne `None` synchroment dans SQLAlchemy 2.x mais le pattern async usuel attend `await session.delete(obj)`. Selon la version, ça peut générer un warning ou un comportement non-déterministe. À vérifier et harmoniser. |
| **F178** | base | **Aucun __init__.py audité — la liste exhaustive des sous-repos n'est pas vérifiée** | `repositories/__init__.py:2,72` re-export `BaseRepository` ; sub-repos individuels | Sur 65 sous-repositories, certains peuvent enrichir `BaseRepository` avec des queries custom qui contournent les filtres. À auditer dans les modules métier. |
| **F179** | base | **`restore()` ne supprime pas le cache** | `base.py:490-518` (sync), `base.py:716-729` (async) | Aucune des 2 versions n'invalide le cache après restore. Si l'entité était cachée comme `is_active=False`, le cache reste stale après restore. Petit bug, à corriger pour cohérence avec `soft_delete` qui invalide. |
| **F180** | base sync | **`AsyncBaseRepository` viole le typage de la classe parent** | `base.py:531-533` (`# type: ignore[assignment]`) | `BaseRepository.__init__(self, db: Session)` mais `AsyncBaseRepository.__init__(self, db: AsyncSession)`. La hiérarchie d'héritage est une **violation Liskov** masquée par `# type: ignore`. Devrait avoir une classe abstraite `AbstractBaseRepository[T]` parente, et 2 implémentations sync et async indépendantes. |
| **F181** | base | **`AsyncBaseRepository` n'appelle pas `super().__init__()`** | `base.py:531-539` ; init duplique `_cache_ttl_map` (lignes 534-539 vs 58-63) | Si le parent ajoute des attributs init plus tard, ils ne seront pas portés. Couplage fragile. À résoudre via classe abstraite (cf F180). |
| **F182** | base | **`_cache_ttl_map` hardcodé pour 4 entités Marveline** | `base.py:58-63` et `:534-539` (Product, Customer, Reservation, Invoice) | Cf F37 module 01 et F184 module 03. Pas de TTL pour épicerie/restaurant entities (`EpicerieProduit`, `RestaurantCommande`, etc.) — fallback 300s. Pas de TTL par tenant (Splendid pourrait avoir des durées de cache différentes). À déplacer dans `app/constants/cache.py` ou `tenant_settings`. |

### 3.3 Frictions P2

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F183** | base | `_apply_active_filter` utilise `is_active == True` au lieu de `is_(True)` | `base.py:123` | SQLAlchemy émet généralement un warning. PEP8 + linter prefere `is_(True)`. |
| **F184** | base | `_apply_filters` opérateurs limités à 5 | `base.py:142-160` (gt, gte, lt, lte, ne) | Pas de `like`, `ilike`, `in`, `not_in`, `between`, `is_null`, `not_null`. Tout filtre complexe nécessite custom query dans le sous-repo → duplication. À étendre. |
| **F185** | base | Logger initialisé entre les imports | `base.py:6` après les imports `from sqlalchemy import...` lignes 4-7 | Convention : tous les imports en haut, puis constantes/logger. À réordonner. |
| **F186** | base | `BaseRepository.__init__` exige `model_class` arg redondant avec `Generic[T]` | `base.py:49-57` ; sub-repo pattern : `super().__init__(db, Product)` répétitif | Solution : `model_class: ClassVar[Type[T]]` dans la classe enfant, init parent ne prend que `db`. |
| **F187** | base | **`list()` window function avec `func.count().over()` peut être lent sur grandes tables** | `base.py:304` | Window function calcule COUNT sur tout le résultat avant LIMIT/OFFSET. Pour une table 10M rows + filtre tenant + 100k rows par tenant, c'est OK. Pour 100M rows avec tenant_id mal indexé, lent. À profiler en charge. Alternative : `count()` séparé en mode "estimé" (PG `pg_stat_user_tables.n_live_tup`) si l'exact total n'est pas critique. |
| **F188** | base | `model_class.id` accédé sans vérif PK simple | `base.py:251, 314, 590, 624` | Si un modèle a PK composite (rare en SaaS — possible pour `auth_role_scope` (role_id, scope_id)), `model_class.id` lève AttributeError. À documenter ou ajouter check. |
| **F189** | base | `merge()` peut inserter sans validation tenant si l'entité n'est pas en session ET cache empoisonné | `base.py:241-243` (sync — pas de check post-merge), `:572-573` (async avec post-check) | Voir F170. Symptôme du `from_dict` qui ne valide rien. |
| **F190** | base | Cache hit/miss compté à tort pour la version sync | `base.py:222, 248` | Tant que F168 n'est pas fixé, `cache_hits_total` est incrémenté à chaque appel (cached_data is not None car coroutine). Métrique fausse. |
| **F191** | base | `from_dict` reconstruction n'utilise pas `__init__` custom | `models/base.py:85` (`return cls(**filtered_data)`) | Si un modèle a un `__init__` qui pose des invariants (ex: hash automatique), bypass. À documenter. |

### 3.4 Frictions P3

| ID | Couche | Friction | Citation |
|---|---|---|---|
| **F192** | base | Comments en français | `base.py:62-63, 80, 95, ...` — convention FR/EN non documentée. |
| **F193** | base | `restore` ne distingue pas "non trouvé" et "déjà actif" | `base.py:513-514` (`if not obj or obj.is_active: return False`) — caller ne sait pas pourquoi False. |
| **F194** | base | Docstrings très verboses avec exemples | À aérer ou déplacer en `docs/`. |

---

## 4. Dépendances inter-modules / fuites

### 4.1 Couplages observés

- `repositories/base` → `models/base` (TenantMixin, SoftDeleteMixin) → propre.
- `repositories/base` → `core/cache.cache_service` via lazy import → cycle évité par lazy mais le graph reste tordu.
- `repositories/base` → `core/metrics` lazy → couplage sain.
- `repositories/base.AsyncBaseRepository.get_by_id` → `core/cache.cache_service` (vrai await ici).

### 4.2 Cycles évités par lazy

- `repositories.base → core.cache → core.__init__ → core.deps → services → repositories.base` (cycle commenté ligne 12-13).
- Symptôme du module 01 (deps.py 1066 LoC, core.__init__ re-export massif F38).

### 4.3 Forward-references confirmées

- **F148** module 05 (FK manquante) + F168 + F170 = combo : cache empoisonné cross-tenant non bloqué par la DB.
- **F150** module 05 (`to_dict` expose tout) confirmé ici (F169) : utilisé pour cache Redis effectivement. **Secrets en cache.**
- **F05** module 01 (cache async appelé sync) confirmé ici (F168) : 4 sites concrets dans `BaseRepository`.

### 4.4 Fuites Marveline / multi-brand

- **F182** : `_cache_ttl_map` hardcodé Marveline (Product, Customer, Reservation, Invoice). Tout autre brand/app utilise default 300s, sans tuning.
- Pas de tenant-aware TTL ni de cache namespacé par brand_code (Splendid pourrait avoir des stratégies de cache différentes).

---

## 5. Recommandations de refonte

### 5.1 Priorité 1 — Cache cassé en sync (P0)

1. **F168** : décider du sort du `BaseRepository` sync :
   - **Option A** : déprécier complètement, migrer Celery + scripts vers `AsyncBaseRepository` (préférable — un seul codepath).
   - **Option B** : créer `cache_service_sync` qui utilise `redis.Redis` (sync) au lieu de `redis.asyncio.Redis`, et faire pointer `BaseRepository` dessus :
     ```python
     # cache.py
     class CacheServiceSync:
         def __init__(self): self.redis = redis_cache_sync  # Redis sync client
         def get(self, key): return self.redis.get(key)
         # etc.
     cache_service_sync = CacheServiceSync()
     ```
     Et `repositories/base.py` :
     ```python
     def _get_cache_service_sync():
         from app.core.cache import cache_service_sync
         return cache_service_sync
     ```
   - **Option C (refonte propre)** : rendre `BaseRepository` 100% sync sans cache (Celery batch jobs n'ont pas besoin de cache HTTP-style).

   Tests à écrire : `from app.repositories.base import BaseRepository ; repo = ProductRepository(db) ; r1 = repo.get_by_id(1, tenant_id=1) ; r2 = repo.get_by_id(1, tenant_id=1)` → check que la 2ème call ne repasse pas par DB (cache HIT) ou échoue explicitement.

2. **F169 + F150** : implémenter `__cache_excluded_fields__` dans les modèles. Pour les modèles à secrets (Account, MFADevice, WebAuthnCredential, ApiKey) :
   ```python
   class Account(Base, TimestampMixin, SoftDeleteMixin):
       __cache_excluded_fields__ = {"hashed_password"}
       # ...
   ```
   Et `BaseRepository.get_by_id` doit `to_dict(exclude=getattr(model_class, "__cache_excluded_fields__", set()))`.

   **Mieux** : ne **JAMAIS** cacher les modèles auth (Account, MFADevice, etc.) — ajouter `__cacheable__: ClassVar[bool] = False` et skip dans le repo.

3. **F170** : porter la protection post-merge `BaseRepository.get_by_id` (sync) :
   ```python
   instance = self.model_class.from_dict(cached_data)
   instance = self.db.merge(instance)
   # P1-02 sync : post-merge tenant verification
   if self._has_tenant_mixin() and instance.tenant_id != tenant_id:
       logger.critical("CROSS-TENANT post-merge sync: %s#%d", ...)
       return None
   return instance
   ```

4. **F171** : raise `ValueError(f"Unknown operator: {operator}")` dans `_apply_filters` au lieu de fall-through silencieux. Tests : query avec `filters={"status__likes": "active"}` doit raise, pas retourner toutes les rows.

### 5.2 Priorité 2 — Cohérence sync/async (P1)

5. **F180, F181** : refondre l'héritage :
   ```python
   class AbstractBaseRepository(Generic[T]):
       """Méthodes communes — helpers, filtres, cache key generation."""
       # ...
   class BaseRepository(AbstractBaseRepository[T]):
       """CRUD sync."""
   class AsyncBaseRepository(AbstractBaseRepository[T]):
       """CRUD async."""
   ```
   Élimine le `# type: ignore` ligne 532 et la duplication `_cache_ttl_map`.

6. **F174** : porter le lock anti-race en sync (si on garde le sync repo).

7. **F177** : harmoniser `await self.db.delete(obj)` ou documenter pourquoi le cas async est en mode sync.

8. **F179** : invalider le cache après `restore()` dans les 2 versions.

### 5.3 Priorité 3 — Métriques propres (P1)

9. **F172, F190** : supprimer la Gauge `cache_hit_rate` et le helper `_update_cache_hit_rate`. Calcul côté Prometheus :
   ```promql
   rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
   ```

### 5.4 Priorité 4 — Configurabilité (P2)

10. **F182** : extraire `_cache_ttl_map` dans `app/constants/cache.py` :
    ```python
    CACHE_TTL_BY_ENTITY: dict[str, int] = {
        "Product": 300, "Customer": 600, "Reservation": 60, "Invoice": 180,
        # extensible par brand via tenant_settings
    }
    DEFAULT_CACHE_TTL = 300
    ```

11. **F184** : étendre `_apply_filters` aux opérateurs `like`, `ilike`, `in`, `not_in`, `between`, `is_null` :
    ```python
    elif operator == "like":
        query = query.filter(field.like(value))
    elif operator == "ilike":
        query = query.filter(field.ilike(value))
    elif operator == "in":
        query = query.filter(field.in_(value))
    # etc.
    ```

12. **F186** : `model_class: ClassVar[Type[T]]` dans la classe enfant — élimine le param `model_class` redondant à l'init.

### 5.5 Priorité 5 — Hygiène (P2-P3)

13. **F183** : `is_(True)` au lieu de `== True`.
14. **F176** : `hard_delete` exige `force=True` si `SoftDeleteMixin` disponible.
15. **F185** : réordonner les imports / logger.
16. **F188** : check explicite `hasattr(model_class, "id")` ou supporter PK composite via `inspect(model_class).primary_key`.
17. **F193** : différencier les codes de retour `restore()` (NotFound vs AlreadyActive).

### 5.6 Tests à écrire avant refonte

- **F168** : `repo = ProductRepository(db) ; repo.get_by_id(1, tenant_id=1)` 2× → la 2ème call doit hit le cache (sync) — devrait actuellement échouer.
- **F169** : `account_repo.get_by_id(1, tenant_id=1)` puis `redis.get("v2:account:1:1")` → ne doit PAS contenir `hashed_password`. Devrait actuellement contenir.
- **F170** : forger une entrée cache `v2:product:1:5` avec `tenant_id=999` → `repo.get_by_id(1, tenant_id=1)` doit retourner None et logger CRITICAL. Sync devrait actuellement retourner l'objet du tenant 999.
- **F171** : `repo.list(tenant_id=1, filters={"status__likes": "active"})` doit raise `ValueError`. Devrait actuellement retourner toutes les entités.
- **F175** : profiler la double query `list()` + `count()` sur un endpoint typique pour mesurer le gain.

### 5.7 Hors-scope

- Sub-repositories spécifiques (`customer`, `product`, `reservation`, etc.) → modules métier (14, 15, 17, …).
- `AsyncAccountRepository` / `AsyncTenantMembershipRepository` → modules 09, 10.

---

## 6. Verdict module 06

| Aspect | État |
|---|---|
| Convention 4 couches | Repository = couche 2 (entre models et services). Pattern présent mais double-implémentation sync/async. |
| Étanchéité tenant | **Trou multiple** : F148 (FK manquante module 05) + F168 (cache sync cassé) + F170 (post-merge check manque sync) + F171 (operators silencieux) = 4 maillons faibles dans la chaîne d'isolation cache cross-tenant |
| Sécurité cache | **Critique** : `to_dict` cache **hashed_password, encrypted_secret, PII** en Redis (F169). Pas de filtre. |
| Fonctionnalité cache | **Cassée en sync** : 4 sites async appelés sync sans await — cache jamais lu, jamais écrit, jamais invalidé en sync (F168) |
| Cohérence sync/async | **Faible** : `AsyncBaseRepository` redéfinit toute l'API au lieu de hériter, viol Liskov masqué par `# type: ignore` (F180), `_cache_ttl_map` dupliqué (F181), post-merge check seulement async (F170), lock anti-race seulement async (F174) |
| Filtre sécurité | **Trou** : opérateurs filtres inconnus → fall-through silencieux (F171). Filter `status__likes=active` retourne toutes les rows. |
| Multi-brand | TTL Marveline-only (F182), pas de tenant-aware caching |
| Dette | 27 nouvelles frictions : 4 P0, 11 P1, 9 P2, 3 P3 |

**Conclusion** : `repositories/base.py` est le **niveau le plus critique de la chaîne tenant**. Tous les services métier en dépendent. **Les 4 P0 doivent être traités ensemble** :
- F168 (cache sync cassé) — soit fix, soit déprécation du sync repo.
- F169 (secrets en cache) — fix urgent avec F150 module 05.
- F170 (post-merge cross-tenant) — porter en sync.
- F171 (filter silent fallthrough) — raise au lieu d'ignorer.

La version async est globalement plus saine (F168 absent, F170 présent, lock anti-race présent), ce qui plaide pour la dépréciation du sync repo (option A de §5.1.1). Migration coût élevé (Celery + scripts à porter en async ou via wrapper sync->async via `asyncio.run`).

→ Module suivant : `07-constants.md` (`app/constants/*.py` — business, errors, http, security, limits, loyalty, metrics, approvisionnement).
