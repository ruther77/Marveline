# Module 11 — RBAC (Role-Based Access Control)

> **Phase B — Identité & Sécurité.** Audit du sous-système autorisation : tables `auth_roles`, `auth_scopes`, `auth_role_scopes`, `user_roles` (legacy), enum `Permission`, enum `Scope`, `ROLE_SCOPES_FALLBACK`, `ROLE_HIERARCHY`, `ROLE_PERMISSIONS`, dependencies `require_permission` / `require_scope` / `require_scope_user`, service `services/rbac.py`, cache Redis-CACHE des scopes par rôle.
>
> **Forward-références purgées :** F09 / F10 / F50 (mod. 01 — 4 systèmes RBAC), F55 / F56 / F66 (mod. 02 — Permission v2 vs Scope v3, INVENTORY vs STOCK), F70 / F71 / F72 (mod. 02 — `get_effective_permissions` raise vs cached `set()`), F201 (mod. 07 — `UserRole.ADMIN` legacy).

---

## 1. Inventaire des fichiers lus intégralement

| Fichier | LoC | Rôle |
|---|---|---|
| `app/models/auth_role.py` | 78 | Référentiel rôles RBAC (6 rôles) |
| `app/models/auth_scope.py` | 65 | Référentiel scopes (62 valeurs) |
| `app/models/auth_role_scope.py` | 47 | Mapping rôle → scope (PK composite) |
| `app/models/user_role.py` | 127 | Assignation rôle ↔ user ↔ tenant (legacy IAM v1) |
| `app/services/rbac.py` | 248 | Lecture scopes : Redis-CACHE → DB → fallback statique |
| `app/core/permissions.py` | 412 | Enums `Permission` (v2) + `Scope` (v3) + `ROLE_HIERARCHY` + `ROLE_PERMISSIONS` |
| `app/core/deps.py` (410-870) | 460 | `require_permission` / `require_scope` / `require_scope_user` / aliases |
| `app/services/token.py` (35-145) | 110 | Émission JWT — `_build_access_claims` injecte `scopes` |
| `app/middleware/request_context.py` (100-160) | 60 | Peuple `request.state.jwt_scopes` |

**Volume total ciblé** : ~1 600 LoC d'autorisation pure, sans compter les ~400 alias dans `deps.py` (`ProductWriter`, `ReservationReader`, etc.).

---

## 2. Architecture observée — **5 systèmes RBAC qui coexistent**

```
                    ┌──────────────────────────────────────┐
                    │  IAM v2 — TenantMembership.role_name │  ← source de vérité runtime
                    │           (FK → auth_roles.name)      │
                    └────────────────┬─────────────────────┘
                                     │
                                     ▼
   ╔═══════════════════════════════════════════════════════╗
   ║  TABLES DB (référentiel statique, géré par Alembic) ║
   ║   auth_roles (6 lignes) ──┬── auth_role_scopes      ║   System #1
   ║                           │      (PK composite)      ║
   ║                           └── auth_scopes (62)       ║
   ╚═══════════════════════════════════════════════════════╝
                                     │
   ┌─────────────────────────────────┴──────────────────────┐
   │ services/rbac.py — get_role_scopes(role, db) :         │
   │   1. Redis-CACHE rbac:scopes:{role} (TTL 5 min)        │   System #2
   │   2. SELECT auth_role_scopes WHERE role=:r             │
   │   3. ROLE_SCOPES_FALLBACK[role] (175 LoC hardcodés)    │   ⚠ FAIL-OPEN
   └────────────────────────┬───────────────────────────────┘
                            │
                            ▼
   ┌────────────────────────────────────────────────────────┐
   │ token.py — _build_access_claims :                      │
   │   scopes = await get_role_scopes(role, None)  ← db=None│   System #3
   │   → JWT.claims["scopes"] (embed)                       │   (toujours fallback)
   └────────────────────────┬───────────────────────────────┘
                            │
                            ▼
   ┌────────────────────────────────────────────────────────┐
   │ middleware/request_context.py :                        │
   │   request.state.jwt_scopes = claims["scopes"]          │   System #4
   └────────────────────────┬───────────────────────────────┘
                            │
                            ▼
   ╔════════════════════════════════════════════════════════╗
   ║ deps.py — require_scope(*Scope) :                      ║
   ║   user_scopes = jwt_scopes ?? ROLE_SCOPES_FALLBACK[r]  ║   System v3 (Scope enum, 62)
   ║                                                         ║
   ║ deps.py — require_permission(*Permission) :            ║
   ║   user_perms = get_effective_permissions_cached(role)  ║   System v2 (Permission enum, ~40)
   ║   → ROLE_HIERARCHY=["staff","manager","admin"] (3)     ║   ⚠ legacy
   ╚════════════════════════════════════════════════════════╝
```

**Cinq sources qui doivent rester synchronisées** :

1. **DB tables** (`auth_roles`, `auth_scopes`, `auth_role_scopes`) — 6 rôles × 62 scopes
2. **`ROLE_SCOPES_FALLBACK`** dans `services/rbac.py` (175 LoC, 6 rôles + alias `admin`)
3. **`Permission` enum v2** dans `core/permissions.py` (~40 valeurs)
4. **`ROLE_PERMISSIONS` v2** (3 rôles `staff`/`manager`/`admin`)
5. **`Scope` enum v3** dans `core/permissions.py` (62 valeurs)

À cela s'ajoute **`UserRole` enum** dans `app/constants/business.py` (7 valeurs : `SUPER_ADMIN`, `PLATFORM_OPS`, `TENANT_ADMIN`, `MANAGER`, `STAFF`, `VIEWER`, `ADMIN` legacy), `ROLE_LEVELS` dans `services/rbac.py` (6 niveaux), et la **table `user_roles`** (legacy IAM v1, gardée mais probablement dead — cf. F341).

> ⚠ Aucune classe `RBACService` n'existe. La logique RBAC est éclatée entre `services/rbac.py` (lecture scopes), `services/user.py` (assignation rôle via `can_manage_role`), `core/permissions.py` (enums + cache mémoire), `core/deps.py` (enforcement). Pas de service unique.

---

## 3. Frictions identifiées — module 11

> Compteur global cumulé (modules 01–10) ≈ 326 frictions.
> Le module 11 ouvre à **F327**.

### 3.1 P0 — Bloquant production

#### F327 — Cinq systèmes RBAC coexistent sans loi d'unicité

**Constat.** Cf. diagramme §2. Les 5 sources doivent être synchronisées **manuellement** :

| Source | Rôles | Scopes | Maintenue par |
|---|---|---|---|
| DB `auth_roles` × `auth_role_scopes` | 6 | 62 | Migration Alembic |
| `ROLE_SCOPES_FALLBACK` (rbac.py:35-180) | 7 (avec alias `admin`) | ~62 | Édition Python |
| `Permission` enum (permissions.py:22-114) | — | ~40 | Édition Python |
| `ROLE_PERMISSIONS` (permissions.py:121-179) | 3 | — | Édition Python |
| `Scope` enum (permissions.py:229-407) | — | 62 | Édition Python |

**Symptôme déjà observé** : `Scope.LOYALTY_*` ajouté au fallback pour `tenant_admin` (l.108-109), `manager` (l.137-138), `staff` (l.160-161) mais **absent pour `super_admin`** (l.36-68) et `viewer` (l.163-176). `super_admin` a moins de scopes loyalty que `tenant_admin` au fallback. Drift confirmé.

**Pourquoi P0** : le système est conçu pour faire silence en cas de drift (FAIL-OPEN avec scopes manquants → 403 sans alerte). Une migration qui ajoute un scope DB sans MAJ Python → JWT existants ne l'auront jamais (cf. F332).

**Action** : générer `ROLE_SCOPES_FALLBACK` à partir d'un YAML unique consommé par migration + import Python. Ou supprimer le fallback (laisser DB-only avec FAIL-CLOSED contrôlé).

---

#### F328 — `Permission.INVENTORY_*` ≠ `Scope.STOCK_*` (divergence ressources)

**Constat.** Mêmes ressources, noms différents :

| Permission v2 (legacy) | Scope v3 (cible) |
|---|---|
| `inventory:read` / `inventory:write` | `stock:read` / `stock:write` / `stock:adjust` |
| `users:admin` | `users:manage` + `users:delete` (split) |
| `sessions:admin` | `sessions:read` + `sessions:revoke` (split) |
| `api_keys:write` (couvre delete) | `api_keys:write` + `api_keys:delete` (split) |

**Conséquence** : un endpoint protégé par `require_permission(Permission.INVENTORY_WRITE)` n'est **pas** équivalent à `require_scope(Scope.STOCK_WRITE)`. Migrer endpoint par endpoint **régresse** silencieusement (un User v3 avec `stock:write` se voit refusé sur l'ancien endpoint Permission, alors que c'est la même action métier).

**Cf. F66 module 02** déjà identifié ; conservé ici pour traçabilité.

**Pourquoi P0** : la migration ne peut **pas** être progressive sans dual-décoration `require_permission(...)` + `require_scope(...)`. Or aucun endpoint actuel ne fait les deux ; chaque endpoint choisit son camp → fragmentation.

---

#### F329 — `ROLE_SCOPES_FALLBACK` duplique la table DB (FAIL-OPEN aveugle)

**Constat.** `services/rbac.py:35-180` contient 175 LoC de scopes en dur, recopiés depuis migrations Alembic. Code-commentaire l. 33-34 :

```python
# Source de verite = auth_role_scopes en DB.
# Ce fallback est utilise si DB et Redis sont simultanement indisponibles.
```

Mais en pratique :
1. **Au login (`token.py:49`)** : `await get_role_scopes(role, None)` — `db=None` passé volontairement → la fonction saute l'étape DB (l. 204 `if db is not None`) → fallback statique systématique tant que Redis-CACHE est vide.
2. Une fois le cache peuplé, c'est le fallback statique qui s'y trouve, pas la valeur DB.
3. Au prochain `invalidate_role_cache(role)`, le cache est vidé → recomputed avec `db=None` → re-fallback.

**Conséquence** : la DB `auth_role_scopes` n'est **jamais lue à l'émission JWT**. Modifier `auth_role_scopes` en SQL n'a **aucun effet** sur les JWT futurs. `ROLE_SCOPES_FALLBACK` est de fait la seule source de vérité opérationnelle.

**Pourquoi P0** : promesse de "DB source of truth" non tenue. L'admin qui modifie un mapping en DB pense propager le changement → en réalité il faut redéployer l'app (changer `ROLE_SCOPES_FALLBACK` Python).

---

#### F330 — `get_role_scopes(role, db=None)` au login → DB ignorée systématiquement

**Constat.** `token.py:48-49` :

```python
from app.services.rbac import get_role_scopes
scopes = await get_role_scopes(role, None)  # ← db=None par design
```

`get_role_scopes` (rbac.py:185-225) :
```python
# 1. Cache Redis-CACHE
cached = await redis_cache.get_cached_scopes(role_name)
if cached is not None: return cached
# 2. DB (source de verite)
if db is not None:           # ← faux puisque db=None passé
    ...
# 3. Fallback statique
scopes = list(ROLE_SCOPES_FALLBACK.get(role_name, []))
```

**Pourquoi P0** : double bug.
- `TokenService` n'a pas accès à la session DB pour cette opération (volontaire, pour découplage).
- Mais alors `auth_role_scopes` ne sert qu'aux outils admin externes (lecture directe SQL), pas à l'app.

**Action** : injecter `db: AsyncSession` dans `TokenService.issue_tokens` ou exposer un getter `RBACService.refresh_role_cache(role, db)` appelé en post-migration pour pré-peupler Redis avec la valeur DB.

---

#### F331 — Pas de validation cross-app sur l'attribution de scopes

**Constat.** `super_admin` a tout : `restaurant:read/write` + `epicerie:read/write` (ROLE_SCOPES_FALLBACK l.65-67). `tenant_admin` aussi (l.105-107). `manager` aussi (l.134-136). `staff` a `restaurant:read` + `epicerie:read` (l.157-159).

**Aucune contrainte** ne lie un scope à un `app_code`. Or :
- Tenant `marveline` (app_code=`marveline`) ne devrait **pas** émettre des JWT contenant `restaurant:write` ou `epicerie:write`.
- Tenant `restaurant` (app_code=`restaurant`) ne devrait **pas** voir `epicerie:*` (sauf si feature cross-app autorisée).

**Conséquence** : un staff Marveline reçoit `restaurant:read` + `epicerie:read` dans son JWT. Si l'audit `aud` JWT est mal vérifié (cf. F47 module 02 — bypass quand claim `type` absent), le token Marveline peut interroger `/api/v1/restaurant/*` ou `/api/v1/epicerie/*` et **ça passe**.

**Pourquoi P0** : cumulé avec F47, c'est un chemin d'évasion de l'isolation app→app. La séparation app/brand devient cosmétique.

**Action** : table `auth_app_scopes (app_code, scope_name)` pour autoriser un scope par app. Filtrer à l'émission : `scopes = [s for s in scopes if (app_code, s) in app_scope_allowlist]`.

---

#### F332 — `_get_principal_scopes` retourne `set()` silencieusement pour rôle inconnu

**Constat.** `deps.py:619-640` :

```python
def _get_principal_scopes(principal, jwt_scopes):
    if isinstance(principal, ApiKeyClient):
        return set(principal.scopes)
    if jwt_scopes:
        return set(jwt_scopes)
    logger.warning("RBAC fallback: JWT scopes absents user=%s role=%s ...")
    return set(ROLE_SCOPES_FALLBACK.get(principal.role, []))
```

Si `principal.role` n'existe pas dans `ROLE_SCOPES_FALLBACK` (rôle DB orphelin, typo, rôle ajouté en migration mais oublié dans le dict Python), `dict.get(...)` retourne `[]` → `set()` → `missing = required - set() = required` → 403 propre.

Mais le warning à la ligne 636 est émis **avant** la récupération du dict, **uniquement** quand `jwt_scopes` est vide ET pas ApiKeyClient. Si `jwt_scopes` est non-vide (cas standard) mais que le role est inconnu, **aucun log** n'apparaît.

**Pourquoi P0** : un rôle DB ajouté manuellement ou via migration buggée vit silencieusement → tous les utilisateurs concernés voient leurs requêtes refusées sans diagnostic. Ne casse pas la sécu mais casse la prod sans signal.

**Action** : log ERROR (pas warning) quand `principal.role not in ROLE_SCOPES_FALLBACK` ; émettre métrique `rbac_unknown_role_total{role=...}`.

---

#### F333 — `UserRole.ADMIN = "admin"` legacy crée une dérive level/hiérarchie incohérente

**Constat.** Trois sources contradictoires sur la position de `"admin"` :

| Source | Position de `"admin"` |
|---|---|
| `ROLE_LEVELS` (rbac.py:23-30) | **absent** → `ROLE_LEVELS.get("admin", 99) = 99` |
| `ROLE_HIERARCHY` v2 (permissions.py:118) | `["staff", "manager", "admin"]` → niveau 2 (top) |
| `ROLE_SCOPES_FALLBACK["admin"]` (rbac.py:180) | alias `tenant_admin` (level 2 dans ROLE_LEVELS) |
| `UserRole.ADMIN` (business.py:184) | `"admin"` (legacy) |

**Conséquence** : un User dont `membership.role_name = "admin"` :
- Reçoit les scopes de `tenant_admin` au login (OK).
- Mais `can_manage_role("admin", "tenant_admin")` → `99 < 2 = False` → `admin` ne peut **pas** gérer `tenant_admin` (bloqué).
- `can_manage_role("admin", "admin")` → `99 < 99 = False` → `admin` ne peut pas gérer un autre `admin`.
- `can_manage_role("admin", "manager")` → `99 < 99 = False` → bloqué (manager absent aussi de ROLE_LEVELS sauf ligne 26 = level 3).

Re-vérifié : `ROLE_LEVELS = { super_admin:0, platform_ops:1, tenant_admin:2, manager:3, staff:4, viewer:5 }` (l. 24-30). `"admin"` absent → fallback 99.

**`admin` est donc administrativement paralysé** alors que ses scopes lui donnent toutes les permissions tenant_admin.

**Pourquoi P0** : crée un état où les ex-admins legacy ne peuvent plus gérer personne sans modification SQL directe.

**Action** : migration `UPDATE tenant_memberships SET role_name='tenant_admin' WHERE role_name='admin'` puis suppression de l'alias `ROLE_SCOPES_FALLBACK["admin"]` et `UserRole.ADMIN`.

---

#### F334 — `UserCompat.permissions` retourne `set()` (Protocol Principal violé)

**Constat.** `deps.py:91-92` :
```python
class UserCompat:
    """Agrégat Account + TenantMembership ...
    Satisfait le Protocol Principal (tenant_id, principal_type, principal_id, permissions)."""
```

`deps.py:195-197` :
```python
@property
def permissions(self) -> set[str]:
    return set()  # ← VIDE
```

À l'inverse, `ApiKeyClient.permissions` (l. 83-84) retourne ses scopes.

`require_permission` ne lit **jamais** `principal.permissions` pour un User (l. 449 : `user_perms = get_effective_permissions_cached(principal.role)`), donc le bug est latent. Mais :
- Tout code applicatif qui itérerait sur `principal.permissions` voit `set()` pour un humain.
- Tests qui font `assert "products:read" in user.permissions` passent silencieusement à False sans alerter.

**Pourquoi P0** : viole le contrat Protocol Principal documenté dans le docstring. Source de bugs latents lors de tout futur refactor s'appuyant sur ce protocole (notamment middlewares de log d'audit qui iraient lire les permissions du principal).

**Action** : implémenter `UserCompat.permissions` → `set(get_effective_permissions_cached(self.role)) | set(get_role_scopes_sync(self.role))` ou supprimer le `permissions` property du protocole et passer par un helper `get_principal_scopes(principal)` partout.

---

### 3.2 P1 — Forte friction architecturale

#### F335 — `super_admin` a moins de scopes loyalty que `tenant_admin` (drift fallback)

**Constat.** `ROLE_SCOPES_FALLBACK["super_admin"]` (l.36-68) liste 80+ scopes mais **pas** `loyalty:read/write/manage`. `tenant_admin` (l.108-109), `manager` (l.137-138), `staff` (l.160-161) en ont. `viewer` (l.163-176) n'a aucun scope V2 (epicerie/restaurant/loyalty).

**Conséquence** : un super_admin ne peut **pas** gérer la fidélité. Un platform_ops non plus (5 scopes infrastructure seulement). Inversion de hiérarchie.

**Action** : ajouter `loyalty:*` à `super_admin` et harmoniser via test d'invariant : `for r in ROLE_SCOPES_FALLBACK: assert ROLE_SCOPES_FALLBACK[r] ⊆ ROLE_SCOPES_FALLBACK["super_admin"]`.

---

#### F336 — `viewer` n'a aucun scope module V2 (`epicerie`, `restaurant`, `loyalty`)

**Constat.** Cf. F335. `viewer` est censé être lecture seule sur tout, mais ne peut rien lire des modules V2.

**Action** : ajouter `epicerie:read`, `restaurant:read`, `loyalty:read` à `viewer`.

---

#### F337 — `auth_role_scopes` ON DELETE CASCADE / `user_roles` ON DELETE RESTRICT (incohérence)

**Constat.**
- `auth_role_scope.role_name` : `ondelete="CASCADE"` (auth_role_scope.py:23)
- `user_roles.role_name` : `ondelete="RESTRICT"` (user_role.py:53)
- `tenant_memberships.role_name` : `ondelete="RESTRICT"` (cf. mod 09)

Supprimer un rôle DB :
- Vide `auth_role_scopes` automatiquement (CASCADE).
- Mais bloque la suppression si **un seul** `user_roles` ou `tenant_memberships` actif référence le rôle (RESTRICT).
- Donc en pratique on ne peut **jamais** supprimer un rôle utilisé. Mais si on force la suppression (`UPDATE ... revoked_at=NOW()` puis `DELETE`), on perd les mappings rôle→scope d'un coup → utilisateurs en cours de session voient leurs scopes vidés silencieusement (cache jamais invalidé pour rôle disparu).

**Action** : harmoniser sur `ondelete="RESTRICT"` partout pour les tables référentielles, ou interdire la suppression au niveau service (soft-delete `auth_roles.is_archived`).

---

#### F338 — `UserRole.assigned_by` `nullable=False` mais `ondelete="SET NULL"` (incohérence schema)

**Constat.** `user_role.py:58-63` :
```python
assigned_by: Mapped[int] = mapped_column(
    BigInteger,
    ForeignKey("accounts.id", ondelete="SET NULL"),
    nullable=False,
    ...
)
```

Quand l'admin qui a assigné le rôle est supprimé, PostgreSQL essaie de mettre `assigned_by=NULL` → violation `NOT NULL` → la suppression de l'account échoue.

**Action** : passer `nullable=True` (cohérent avec `SET NULL`) ou changer `ondelete="RESTRICT"` (mais alors impossible de supprimer un account ayant assigné des rôles).

---

#### F339 — `user_roles` table dead ? `tenant_memberships.role_name` est la source runtime

**Constat.** Module 09 a montré que `tenant_memberships.role_name` est lu au login via `UserCompat._membership.role_name` (deps.py:111). `services/user.py:151,221,226` utilise `can_manage_role` mais lit/modifie `user._membership.role_name` (mod. 09 §3.1 F273), **pas** `user_roles`.

`UserRole` model (`user_role.py`) a 127 LoC, des index partiels, des relationships, mais **aucun service applicatif ne le lit ou l'écrit** (à confirmer en grepant `repos/user_role.py` — n'existe pas).

**Action** : vérifier en module 14+ si `user_roles` est encore peuplé (probablement plus). Si oui, drop la table en migration ; sinon, déprécier et supprimer le model.

---

#### F340 — `RBAC_CACHE_TTL = 300` hardcodé (pas configurable, pas dans constants)

**Constat.** `services/rbac.py:182`. Aucune entrée dans `constants/security.py`, aucune entrée dans `Settings`. Modification = redéploiement.

**Action** : extraire vers `Settings.RBAC_CACHE_TTL_SECONDS` avec default 300.

---

#### F341 — `invalidate_role_cache` n'invalide QUE Redis, JWT actifs gardent l'ancien set jusqu'à expiration

**Constat.** `services/rbac.py:245-248` :
```python
async def invalidate_role_cache(role_name: str) -> None:
    await redis_cache.invalidate_cached_scopes(role_name)
```

Les scopes étant **embarqués dans le JWT au login** (`token.py:49`), le cache n'invalide rien pour les sessions en cours. `JWT_ACCESS_TOKEN_EXPIRE_SECONDS` ≈ 15 min → fenêtre de drift = 15 min.

Ajouter ou retirer un scope d'un rôle → toutes les sessions actives gardent leur ancien set pendant 15 min. Pour un retrait de privilège urgent (compromission, démission), c'est un bug de sécu critique.

**Pourquoi P1** : 15 min de drift acceptable pour ajouts, **pas** pour retraits. Pas P0 car la révocation de session (mod. 10 §sessions, F292/F293) est une voie alternative.

**Action** : sur retrait de scope, révoquer toutes les sessions des users avec ce rôle (`SessionService.revoke_by_role(role)`). Ou réduire `JWT_ACCESS_TOKEN_EXPIRE_SECONDS` à 5 min.

---

#### F342 — `has_scope` défini deux fois (rbac.py:229 + permissions.py:410), dead duplicate

**Constat.** Identique : `return scope in user_scopes`. Aucun import de l'un par l'autre.

**Action** : conserver `permissions.has_scope`, supprimer `rbac.has_scope`.

---

#### F343 — `AuthScope.action` : valeurs hétérogènes sans enum (read, write, delete, manage, adjust, revoke, verify, export, admin)

**Constat.** Pas de validation côté DB ni Pydantic. Un INSERT `auth_scopes(name='foo:bar', action='bar')` passe. Pas de cohérence avec `Scope` enum Python.

**Action** : enum DB `auth_scope_action_enum` ou `CHECK (action IN (...))`. Idéalement, `AuthScope.action` cesse d'exister (parsable depuis `name`).

---

#### F344 — Pas d'index sur `auth_role_scopes(scope_name)` → recherche inverse "qui a ce scope" = full scan

**Constat.** Migration `f1a2b3c4d5e6_create_rbac_and_sessions_tables.py:130-143` crée la PK composite `(role_name, scope_name)` (donc index implicite sur `role_name` first). Aucun index séparé sur `scope_name`.

**Conséquence** : `SELECT role_name FROM auth_role_scopes WHERE scope_name = 'reservations:write'` = full scan (O(N)). Volume faible (375 lignes max = 6 × 62), donc pas P0 ; mais bloque les outils admin "lister tous les rôles ayant ce scope".

**Action** : ajouter `idx_auth_role_scopes_scope` sur `(scope_name)`.

---

#### F345 — `services/rbac.py` ne ré-exporte pas via `app/services/__init__.py`

**Constat.** `app/services/__init__.py` n'inclut pas `get_role_scopes`, `has_scope`, `can_manage_role`, `invalidate_role_cache`, `ROLE_SCOPES_FALLBACK`. Tous les consommateurs importent en direct (`from app.services.rbac import ...`).

**Action** : standardiser via `app/services/__init__.py`. Ou consolider en `RBACService` classe.

---

#### F346 — Pas de `RBACService` classe (logique éclatée entre rbac.py, permissions.py, deps.py, user.py)

**Constat.** Conventions §1 du projet exigent 4 couches strictes (Models / Repositories / Services / Endpoints). RBAC viole :
- Logique read scopes : `services/rbac.py` (fonctions module-level)
- Logique enforce scope : `core/deps.py` (factory)
- Logique enums : `core/permissions.py` (statique)
- Logique assign role : `services/user.py:set_role` (couplé au domaine User)
- Pas de repo `repositories/auth_role.py` ni `repositories/auth_scope.py`

**Action** : refactor en `RBACService` (read scopes, can_manage_role, invalidate_cache) + `AuthRoleRepository` + `AuthScopeRepository`. Externaliser `set_role` de `UserService` vers `RBACService`.

---

#### F347 — `permissions.py` mélange Permission v2 et Scope v3 dans le même fichier

**Constat.** `core/permissions.py` 412 LoC contient :
- Permission enum (v2) — l. 22-114
- ROLE_HIERARCHY + ROLE_PERMISSIONS (v2) — l. 118-179
- get_effective_permissions / has_permission / cache (v2) — l. 182-221
- Scope enum (v3) — l. 229-407
- has_scope (v3) — l. 410

**Conséquence** : un développeur qui veut supprimer Permission v2 doit toucher la même file que Scope v3 → risque de casse v3. Le commentaire l. 224-227 marque la séparation visuellement mais pas structurellement.

**Action** : split en `core/permissions_v2.py` (deprecated) + `core/scopes.py` (v3 source unique).

---

#### F348 — `auth_roles` n'a pas de `tenant_id` → impossible d'avoir des rôles custom par tenant

**Constat.** `auth_role.py:23` : `__tablename__ = "auth_roles"`, pas de `TenantMixin`, pas de `tenant_id`. Les 6 rôles sont **globaux**.

**Conséquence** : un tenant SaaS ne peut pas définir un rôle `comptable_externe` ou `chef_de_secteur` sans modifier le code. Bloque toute personnalisation SaaS scalable.

**Action** : ajouter `tenant_id Nullable=True` ; NULL = rôle système (les 6 actuels), NOT NULL = rôle tenant. Adapter `auth_role_scopes.role_name` en clé composite `(tenant_id, role_name)`.

---

### 3.3 P2 — Friction modérée

#### F349 — `AuthRole`, `AuthScope`, `AuthRoleScope` sans `TimestampMixin` (`updated_at` absent)

**Constat.** `auth_role.py:57-62` a `created_at` mais pas `updated_at`. Pareil pour `AuthScope`. `AuthRoleScope` n'a même pas `created_at`.

**Action** : appliquer `TimestampMixin` partout (mod. 05 — convention).

---

#### F350 — `auth_scopes` non tenant-scoped non plus

Même que F348 mais pour les scopes. Un tenant ne peut pas créer un scope custom.

---

#### F351 — Pas de schémas Pydantic `AuthRoleSchema` / `AuthScopeSchema`

**Constat.** `app/schemas/` n'a aucun schéma RBAC. Les éventuels endpoints d'admin RBAC sont à écrire ad hoc.

**Action** : créer `schemas/auth_role.py`, `schemas/auth_scope.py` pour exposition API future.

---

#### F352 — `UserRole.tenant_id` sans FK vers `tenants` (cf. F148 module 05)

Confirmé. Pas réparé.

---

#### F353 — `ROLE_SCOPES_FALLBACK["admin"]` = snapshot, pas référence à `tenant_admin`

**Constat.** `services/rbac.py:180` :
```python
ROLE_SCOPES_FALLBACK["admin"] = list(ROLE_SCOPES_FALLBACK["tenant_admin"])
```

`list(...)` crée une copie. Toute modification ultérieure de `ROLE_SCOPES_FALLBACK["tenant_admin"]` ne propage **pas** à `"admin"`.

**Action** : utiliser un `@property` ou supprimer `"admin"` (cf. F333 — migration).

---

#### F354 — `Permission.SESSIONS_ADMIN` (v2) ≠ `Scope.SESSIONS_REVOKE` (v3) — granularité incompatible

**Constat.** v2 a 1 permission read + 1 admin (couvre revoke implicitement). v3 a 1 read + 1 revoke (pas de manage). Pour un endpoint qui "lit + révoque dans la même action" (ex. liste avec bouton revoke), il faut v3 = les deux scopes.

**Action** : ajouter `Scope.SESSIONS_MANAGE` (read + revoke fusionnés) ou documenter le mapping 1→2.

---

#### F355 — `services/rbac.py` exports sans `__all__`

**Constat.** Aucun `__all__` défini. `from app.services.rbac import *` exporte aussi `logger`, `text`, `AsyncSession`.

---

#### F356 — `UserRole.revoke_reason` String(200) non chiffré → PII potentielle

**Constat.** `user_role.py:78-82`. Si on y stocke "licenciement faute grave employé X", c'est une donnée RH sensible. Pas de `EncryptedField`.

**Action** : chiffrer ou contraindre à un set d'enum (`VOLUNTARY_LEAVE`, `ROLE_CHANGE`, `MISCONDUCT`, ...).

---

#### F357 — `AuthRole.role_scopes` `lazy="selectin"` → potentiel N+1 si batch tenant_membership

**Constat.** `auth_role.py:65-69` : `lazy="selectin"`. Chaque chargement d'un `AuthRole` joint `auth_role_scopes`. Couplé à `TenantMembership.role` (mod. 09) `lazy="selectin"`, un batch `SELECT * FROM tenant_memberships WHERE tenant_id=X` joint `auth_roles` puis `auth_role_scopes` → 2 requêtes (acceptable). Mais si le batch dépasse les 6 rôles avec `IN`, OK.

**Action** : passer à `lazy="raise"` et charger explicitement quand nécessaire — ou laisser `selectin` mais documenter.

---

#### F358 — `AuthRole.user_roles` relationship pointe vers `UserRole` (legacy) mais pas vers `TenantMembership`

**Constat.** `auth_role.py:71-75` : relation vers `UserRole`. Mais `TenantMembership.role_name` (mod. 09) est aussi FK → `auth_roles.name`. Pas de relation `auth_role.memberships` → on ne peut pas faire `role.memberships` pour lister les users actifs.

**Action** : ajouter `memberships: Mapped[list["TenantMembership"]] = relationship(...)`.

---

#### F359 — Aucun test d'invariant Scope enum ↔ DB `auth_scopes`

**Constat.** Pas de test `for s in Scope: assert s.value in db_scope_names`. Drift Python ↔ DB silencieux.

**Action** : test d'invariant en `tests/test_rbac_invariants.py`.

---

### 3.4 P3 — Cosmétique / dette légère

#### F360 — Strings hardcoded `"super_admin"`, `"tenant_admin"`, ... partout au lieu de `UserRole.X.value`

Cf. `services/rbac.py:24-30`, `:36-176`, `:180`, etc. Risque typo non détecté.

#### F361 — Commentaire `staff < manager < admin` (permissions.py:6) obsolète vs Scope v3 6 niveaux

#### F362 — Sous-comments "Infrastructure v3", "Metier M5", "Restaurant V2", "Épicerie V2", "Fidélité" dans `ROLE_SCOPES_FALLBACK` → couches d'évolution visibles, refactor jamais fait

#### F363 — `AuthRole.description` Text obligatoire (peut être 1 mot, lourd pour API)

#### F364 — Pas de versionning du schéma RBAC (ex. `auth_scopes_v3.json` snapshot)

---

## 4. Synthèse module 11

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 8 | F327 (5 systèmes), F328 (INVENTORY/STOCK), F329 (fallback duplique DB), F330 (db=None login), F331 (cross-app), F332 (rôle inconnu silencieux), F333 (admin legacy paralysé), F334 (UserCompat.permissions vide) |
| P1 | 14 | F335, F336, F337, F338, F339, F340, F341, F342, F343, F344, F345, F346, F347, F348 |
| P2 | 11 | F349 → F359 |
| P3 | 5 | F360 → F364 |
| **Total module 11** | **38** | F327 → F364 |

**Compteur cumulé après module 11** : ≈ 326 + 38 = **364 frictions** (43 P0, 146 P1, 135 P2, 40 P3).

---

## 5. Forward-références à traiter dans modules suivants

- **Module 12 (MFA / WebAuthn / Trusted Device)** : vérifier consommation de `auth_roles.mfa_required` (F336 actuellement non listé mais à investiguer) au login. Contrôler interaction `require_stepup` ↔ `Scope`.
- **Module 13 (API Key / OAuth)** : `ApiKeyClient.scopes` ne fait aucune validation contre `Scope` enum à l'attribution. Un admin peut créer une API key avec `scopes=["i:invented:this"]` → pas de 403, juste skipped silencieusement.
- **Module 14+ (Customer, Product, etc.)** : pour chaque endpoint, vérifier dual-decoration `require_permission` + `require_scope` ; identifier les drift v2/v3.
- **Module 99 (registry)** : consolider F328 cas par cas (mapping concret Permission → Scope).

---

## 6. Décision architecturale recommandée (synthèse)

> **L'audit recommande la suppression de Permission v2 / ROLE_HIERARCHY / ROLE_PERMISSIONS et la consolidation autour de Scope v3, avec :**
> 1. **Génération automatique** de `ROLE_SCOPES_FALLBACK` depuis un YAML unique (ou suppression du fallback, mode FAIL-CLOSED contrôlé).
> 2. **`RBACService` classe** (mod. F346) — fin de l'éclatement.
> 3. **Tenant-scoping** des `auth_roles` (F348) pour scalabilité SaaS.
> 4. **App-scoping** des scopes (F331) pour isolation app/brand.
> 5. **Migration définitive** `UserRole.ADMIN` → `tenant_admin` (F333) et drop de la table `user_roles` (F339).
> 6. **Tests d'invariants** Python ↔ DB (F359, F343).
>
> Sans ces 6 chantiers, le projet conserve **5 systèmes RBAC** dont un (`ROLE_SCOPES_FALLBACK`) est de fait la source de vérité runtime, contredisant les commentaires du code.
