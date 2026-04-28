# Module 32 — Feature Flag

> **Phase E — module 2/5.** Audit du système feature flags : kill-switch global, whitelist tenants, rollout % hash déterministe, cache Redis 60s.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/feature_flag.py` | 86 |
| `app/services/feature_flag.py` | 285 |
| `app/repositories/feature_flag.py` | 170 (parcours) |
| `app/api/v1/endpoints/features.py` | 119 |
| `app/schemas/feature_flag.py` | 175 |

**Volume total** : 835 LoC.

---

## 2. Architecture observée

```
FeatureFlag (global, pas de TenantMixin)
  name UNIQUE String(100) snake_case (CHECK regex)
  is_enabled bool master kill-switch
  target_tenants ARRAY[int] (NULL=tous, []=aucun)
  rollout_pct Integer 0-100 (CHECK)
  metadata JSONB

is_feature_enabled(flag_name, tenant_id) → (enabled, reason)
  1. cache Redis SET 60s TTL
  2. kill_switch (is_enabled=False)
  3. whitelist (target_tenants présent)
  4. rollout md5(name+tenant_id) % 100 < pct

Endpoints CRUD admin only (Scope.FEATURES_*)
  POST/GET/PATCH/DELETE /features
  GET /features/check/{flag_name}?tenant_id=X
```

---

## 3. Frictions identifiées — module 32

> Compteur cumulé (mod. 01-31) ≈ 1 030. Module 32 ouvre à **F1031**.

### 3.1 P0

#### F1031 — `is_feature_enabled` **fail-safe = False** sur cache Redis down

`services/feature_flag.py:259-267` `_get_from_cache` `except Exception: return None`. Cache miss → DB lookup. Si DB elle aussi inaccessible → `repo.get_by_name` raise → propagation à l'appelant. Mais surtout, si un flag `mfa_enabled` est censé bloquer login sans MFA et que le service répond `(False, "not_found")` pour cause d'incident DB, **les utilisateurs perdent MFA temporairement**. Selon le flag, fail-safe peut être un `True` ou `False` mais **aucune politique** documentée.

→ Ex: `disable_dangerous_feature` flag activé → si cache+DB down, le flag retourne `(False, "not_found")` → la dangerous feature redevient active. **Inversion de sécurité**.

**Action** : politique explicite `default_value` (config.py FALLBACK_FLAGS dict) + test couvrant les deux directions.

---

#### F1032 — `hashlib.md5` utilisé pour bucketing rollout (services/feature_flag.py:244)

MD5 cryptographiquement faible. Pour bucketing déterministe c'est OK fonctionnellement mais flag par flake8/bandit (security review). Aucun salting, donc deux flags avec mêmes noms partagent les buckets → corrélation tenants (non secret mais drift d'expérience A/B).

**Action** : `hashlib.sha256` (ou `xxhash` si perf) ; ou explicite "non-cryptographic, intentional" tag bandit.

---

#### F1033 — Pas d'**audit log** sur création/modification/suppression de feature flag

`endpoints/features.py:25-119`. Aucun appel `audit_service.log_*`. Un admin malveillant peut activer/désactiver un kill-switch sécurité (ex: `mfa_enabled=False`) sans laisser de trace. Le middleware audit (mod. 31) le capture en CREATE/UPDATE générique mais sans le diff `before/after` du flag (cf. F1010 mod. 31).

→ Forensics impossible sur changement flag sécurité critique.

**Action** : `audit_service.log_update(entity_type="FeatureFlag", before, after)` explicite dans `update_flag` ; idem create/delete.

---

#### F1034 — `target_tenants ARRAY[int]` **pas de FK** vers `tenants.id`

Model l. 52-56. Si un tenant est supprimé, `target_tenants=[1,2,3]` peut référencer un id mort silencieusement. Le flag s'applique à un tenant qui n'existe plus → no-op silent ou pire, un nouveau tenant prenant cet id récupère le flag d'un autre.

**Action** : trigger DB validant existence des IDs ; ou table `feature_flag_tenants` (M:N) avec FK propre.

---

### 3.2 P1

#### F1035 — Cache TTL 60s **hardcoded** (FEATURE_FLAG_CACHE_TTL)

`services/feature_flag.py:19`. Pas configurable par environnement. Pour un kill-switch d'urgence, 60s de propagation peut être trop long (ex: bug paiement → désactiver flag → encore 60s avant que tous les workers se mettent à jour).

**Action** : config `FEATURE_FLAG_CACHE_TTL` env var ; `_invalidate_cache` PUB/SUB Redis pour propagation immédiate cross-workers.

---

#### F1036 — `_invalidate_cache` fait DELETE sur **un seul nœud Redis** — workers multi-process voient cache stale jusqu'à TTL

Implémentation `redis_client.client.delete(key)` est atomique mais ne notifie pas les autres processus. En architecture worker pool 4 workers gunicorn, un commit d'update flag invalide le cache (donc tous lecteurs doivent re-lire DB), MAIS si le cache est par-process Memory + Redis, drift.

À vérifier : `redis_client.client` est partagé OK, mais si l'app a aussi `lru_cache` ou Memory cache local sur les flags, drift garanti.

---

#### F1037 — `name` `~ '^[a-z][a-z0-9_]*$'` CHECK regex strict (model l. 78-81) — empêche flags namespacés `iam.mfa_enabled`

Pas de `.` ni `:`. Pour 100+ flags futurs, manque de structure.

---

#### F1038 — `metadata_json` JSONB **pas de schema validation**

Drift libre. Si un service lit `flag.metadata_json["plan"]` en croyant à du str et c'est int, AttributeError runtime.

---

#### F1039 — Pas de **historique** des changements de flag (`flag_history` table absente)

Combiné F1033 (no audit), aucun moyen de répondre à "à quelle date avons-nous activé le flag X ?". `created_at`/`updated_at` du TimestampMixin ne capture que la dernière modif.

---

#### F1040 — `is_feature_enabled` accepte `tenant_id: int` mais **pas de validation** que tenant existe

Si un endpoint passe `tenant_id=0` (anonyme) ou un id forgé, le rollout_pct calcule un bucket pour cet id fictif → `True` ou `False` arbitraire propagé.

→ Endpoint `/features/check/{flag_name}?tenant_id=X` (l. 60-80) trust l'admin pour passer des id valides.

---

#### F1041 — Pas de **cap rate limit** sur `is_feature_enabled` — appelée potentiellement à chaque requête

Si chaque endpoint app appelle `is_feature_enabled("xxx_enabled", tenant_id)`, ça fait 1 Redis GET par requête. À 1000 req/s × 5 flags = 5000 Redis GET/s. Pour la même donnée. Pas de cache mémoire local LRU.

**Action** : `lru_cache(maxsize=100, ttl=10)` per-process avant Redis ; ou batch get (`is_features_enabled([f1, f2, f3], tenant_id)`).

---

#### F1042 — Pas de **clé "rollout_seed"** — modifier rollout_pct re-shuffle les tenants

Le bucket `md5(flag_name + tenant_id) % 100` est déterministe mais figé. Si on passe rollout_pct 20→50, on ajoute 30% nouveaux tenants ; mais les premiers 20% restent OK. C'est OK. **Mais** si on change le `name` du flag (rare, pas autorisé par contrainte UNIQUE), tout re-shuffle. Pas de drift sauf renaming.

→ Aucune friction réelle ici, mais documentation manquante. Re-classifié P3.

---

#### F1043 — Pas de feature flag "tier" / "plan" intégré — `metadata_json["plan"]` libre

Manque pattern type `flag.required_plan = "premium"` enforced par DB. Tous les flags cohabitent dans un seul namespace.

---

#### F1044 — `rollout_pct=0` route à `(False, "rollout")` (l. 240-241) — distinction **floue avec kill_switch**

Reason "rollout" alors que c'est un override total. Devrait retourner `(False, "rollout_zero")` ou similaire pour observabilité.

---

#### F1045 — `delete_flag` hard delete sans grace period

Si un service log `flag.is_enabled` à chaque appel et qu'un admin DELETE le flag, soudainement le service reçoit `(False, "not_found")`. F1031 cascade.

**Action** : SoftDeleteMixin avec `is_active=False` au lieu de hard delete, ou status `archived` avec garde 30 jours.

---

### 3.3 P2

#### F1046 — Pas de propagation **multi-region** (si déploiement géo-distribué) — Redis local

#### F1047 — Pas de mécanique **dependent flags** (ex: `feature_b` requires `feature_a`)

#### F1048 — `description` Text libre — pas de structure d'owner/contact

#### F1049 — Pas de **TTL natif** sur le flag DB (auto-purge anciens flags >X jours inactifs)

#### F1050 — `target_tenants` array peut grossir indéfiniment — pas de cap (ex: `len > 1000` warning)

---

### 3.4 P3

#### F1051 — Magic number `MD5_HASH_BASE_16` hardcoded — pas dans constants

#### F1052 — `metadata_json` colonne nommée `metadata` SQL — collision avec SQLAlchemy `metadata` reserved

`models/feature_flag.py:65-71` mappe le Python attribute `metadata_json` au SQL column `metadata`. SQLAlchemy `Base.metadata` = registry global. Risque collision (test à confirmer).

---

## 4. Synthèse module 32

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 4 | F1031 (fail-safe ambigu), F1032 (md5), F1033 (no audit log), F1034 (no FK target_tenants) |
| P1 | 11 | F1035 → F1045 |
| P2 | 5 | F1046 → F1050 |
| P3 | 2 | F1051, F1052 |
| **Total** | **22** | F1031 → F1052 |

**Compteur cumulé après module 32** : ≈ 1 030 + 22 = **1 052 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) politique fail-safe explicite per flag (F1031) ; (2) sha256 (F1032) ; (3) audit log explicite create/update/delete (F1033) ; (4) FK ou trigger validation target_tenants (F1034).
>
> **Refactor** : LRU mémoire + PUB/SUB invalidation (F1041+F1036) ; SoftDelete `archived` (F1045) ; flag history table (F1039).

---

# Module 33 (suivant) — Orchestration / Celery / Background tasks
