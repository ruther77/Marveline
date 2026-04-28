# Module 09 — Tenant / Multi-app / Multi-brand (CRITIQUE)

## 1. Périmètre

| Fichier | LoC | Rôle |
|---|---|---|
| `app/models/tenant.py` | 88 | Modèle `Tenant` — identité tenant + state machine |
| `app/models/tenant_brand.py` | 48 | Modèle `TenantBrand` — identité visuelle 1:1 |
| `app/models/tenant_settings.py` | 92 | Modèle `TenantSettings` — paramètres business 1:1 |
| `app/models/tenant_membership.py` | 142 | Modèle `TenantMembership` — N:N Account/Tenant + rôle |
| `app/services/tenant.py` | 179 | `TenantService` — provision/activate/suspend/offboard |
| `app/services/membership.py` | 159 | `MembershipService` — provision/suspend/reactivate/revoke |
| `app/repositories/tenant_membership.py` | 152 | `AsyncTenantMembershipRepository` — get_active, list, etc. |
| `app/repositories/tenant_settings.py` | 58 | `TenantSettingsRepository` (sync + async) |
| `app/api/v1/endpoints/tenant_brand.py` | 61 | `GET /tenant/brand?brand_code=` (public) |
| `app/api/v1/endpoints/provisioning.py` | 182 | `POST /admin/provision/*` + dégradé control |
| `app/schemas/tenant_brand.py` | 22 | `TenantBrandPublic` schema |

**Total** : 1 183 LoC.

**Dépend de** : `models/base` (Base, TimestampMixin), `core/database`, `core/deps` (require_stepup, UserManagerScope), `services/audit`, `constants/ErrorMessages`.

**Dépendu par** : tous les modules métier (qui consomment `tenant_id`), `core/deps.get_current_user` (lookup membership), `middleware/app_enforcement` (lookup `app_code`).

---

## 2. Modèle conceptuel observé

### 2.1 Architecture multi-tenant + multi-app + multi-brand

```
                  ┌─────────────┐
                  │   Account   │  identité globale (pas de tenant_id)
                  └──────┬──────┘
                         │ N:N via TenantMembership
                         ▼
                  ┌─────────────┐
                  │   Tenant    │  app_code: 'marveline' | 'epicerie' | 'restaurant'
                  │             │  brand_code: 'marveline' | 'lesplendid' | ...
                  │             │  status: provisioning → active → suspended → offboarding → archived
                  └──────┬──────┘
                         │ 1:1
            ┌────────────┼────────────┐
            ▼            ▼            ▼
      TenantBrand  TenantSettings  TenantMembership (N)
      (visuel)     (business)      (rôles)
```

### 2.2 Mapping observé Marveline / Splendid

| Tenant | id | app_code | brand_code | name |
|---|---|---|---|---|
| Marveline | 1 | `marveline` | `marveline` | Marveline |
| Épicerie | 2 | `epicerie` | (default `marveline` ?) | (commerce épicerie) |
| Restaurant | 3 | `restaurant` | (default `marveline` ?) | (commerce restaurant) |
| Le Splendid Events | 5 | `marveline` | `lesplendid` | Le Splendid Events |

**Décision implicite** : Splendid = même app que Marveline (workflow location événementiel) avec un branding distinct.
**Conséquence** : tout endpoint sous `/api/v1/devis`, `/api/v1/reservations`, etc. (non préfixé `/epicerie/` ou `/restaurant/`) sert les 2 brands sans distinction côté code métier.

### 2.3 Constraints DB observés

- `Tenant.app_code` : CHECK `IN ('marveline', 'epicerie', 'restaurant')` (`tenant.py:23-26`) — **3 valeurs hardcodées**.
- `Tenant.domain` : UNIQUE (`tenant.py:20`).
- `Tenant.external_id` : UNIQUE.
- `Tenant.brand_code` : INDEX simple, **pas UNIQUE**.
- `TenantBrand.tenant_id` : PK + FK `ondelete=CASCADE` (`tenant_brand.py:20-24`).
- `TenantSettings.tenant_id` : UNIQUE + INDEX, **pas FK** (`tenant_settings.py:11`).
- `TenantMembership` : 4 indexes dont UNIQUE partiel `(account_id, tenant_id) WHERE revoked_at IS NULL` (`tenant_membership.py:33-38`).

---

## 3. Lecture par fichier

### 3.1 `tenant.py` (88 LoC) — déjà couvert module 01

(Re-confirmation pour ce module.)
- `id BigInteger`, `external_id` UUID, `name`, `domain` UNIQUE, `contact_email`.
- `app_code String(20)` avec CHECK constraint 3 valeurs.
- `brand_code String(30) default "marveline"` — index simple.
- `status` String(20), `plan` String(50), `is_active` Boolean.
- `data_retention_days` Integer default 90.
- `max_users` default 50, `max_sessions_per_user` default 5.
- `TRANSITIONS` dict : `provisioning → active`, `active → suspended/offboarding`, `suspended → active/offboarding`, `offboarding → archived`, `archived → []`.
- `can_transition_to(new_status)` (ligne 86-88).

### 3.2 `tenant_brand.py` (48 LoC)

- `__tablename__ = "tenant_brands"`.
- `tenant_id BigInteger` PK + FK `ondelete=CASCADE`.
- Colonnes : `display_name, legal_name, tagline, primary_color, primary_rgb, palette_json (JSONB), logo_url, logo_square_url, favicon_url, contact_email, contact_phone, address`.
- **Defaults** : `primary_color="#b96cc4"`, `primary_rgb="185 108 196"` — **palette Marveline** hardcodée.
- Style **SQLAlchemy 1.x untyped** (`Column(...)` direct).
- Pas de TimestampMixin — `created_at` et `updated_at` redéclarés manuellement (lignes 42-48).

### 3.3 `tenant_settings.py` (92 LoC)

- `__tablename__ = "tenant_settings"`.
- `id Integer` PK (cf F156 module 05 — devrait être BigInteger).
- `tenant_id Integer NOT NULL UNIQUE INDEX` — **pas FK** (cf F148 module 05), **type Integer** au lieu de BigInteger (cf F149).
- 21 colonnes mélangées :
  - **Identité société** : `company_name`, `company_email`, `company_phone`, `company_address`.
  - **Fiscal** : `vat_rate Float default 0.20` (cf F196 module 07).
  - **Tarifs** : `hourly_rate_weekday=30.0`, `hourly_rate_weekend=60.0` (cf F195 module 07).
  - **Réservation CGV Marveline** : `advance_rate=0.40`, `deposit_multiplier=3.0`, `cancellation_threshold_days=15`, `cancellation_early_penalty_rate=0.40`, `cancellation_late_penalty_rate=1.0` (cf F195).
  - **Guards livraison** : `block_delivery_without_advance=True`, `require_signature_before_delivery=True`.
  - **Logistique** : `origin_postal_code`.
  - **Impression** : `printer_host`, `printer_port=9100`.
  - **Ticket** : `nom_commerce`, `adresse`, `siret`, `telephone`.
  - **Identité multi-brand** : `frontend_url` (commentaire ligne 80 « NULL = fallback `settings.FRONTEND_URL` »), `mfa_issuer_name` (ligne 81 « NULL = fallback `settings.MFA_ISSUER_NAME` »).
  - **Reporting** : `reservation_uplift_pct Integer default 0`.

⚠️ **Le pattern multi-brand par tenant_settings est PRÉVU** (`frontend_url`, `mfa_issuer_name`) **mais on ignore si le code le consomme effectivement** — `MFAConfig.ISSUER_NAME = "Marveline"` reste hardcodé (cf F206 module 07). À auditer dans modules 12 (mfa) et 27 (notification).

### 3.4 `tenant_membership.py` (142 LoC)

Très bien conçu :
- 4 indexes optimisés (UNIQUE partiel actif, tenant+role, account actif, tenant_all).
- CHECK constraint `status IN ('active', 'suspended', 'offboarding')`.
- Soft delete via `revoked_at IS NULL` (au lieu de `is_active`).
- Pas de DELETE — historique via `revoked_at` + `revoke_reason`.
- Relations : `account` (lazy=raise — explicite), `role` (lazy=selectin — précharge auto).
- Style SQLAlchemy 2.0 typed (`Mapped[...]`).

### 3.5 `services/tenant.py` (179 LoC)

`TenantService` :
- `provision(name, domain, contact_email, app_code, plan, provisioned_by, notes)` (lignes 28-90) :
  - Check unicité domain.
  - Check `app_code in Tenant.APP_CODES` (3 valeurs).
  - Crée Tenant en `status='provisioning', is_active=False`.
  - Audit `TENANT_PROVISIONED`.
  - **Ne crée PAS** : TenantBrand, TenantSettings, membership initial, RBAC default scopes.
- `activate`, `suspend`, `start_offboarding` (lignes 92-154) — transitions state machine.
- **Pas de méthode `archive`** malgré state machine.
- `get_by_id`, `get_by_external_id`.
- `_get_or_404`, `_assert_transition` — privés.

### 3.6 `services/membership.py` (159 LoC)

`MembershipService` :
- `get_active(account_id, tenant_id)` → `TenantMembership` ou None.
- `require_active` → 403 si absent.
- `get_by_id`, `list_by_account`, `list_by_tenant`.
- `provision(account_id, tenant_id, role_name, invited_by)` (76-101) :
  - 409 si membership actif/suspendu existe déjà.
  - Crée avec `status='active'`.
  - **Ne vérifie PAS** que `tenant.is_active == True`.
  - **Ne vérifie PAS** que `tenant.max_users` n'est pas atteint.
  - Pas d'audit.
- `suspend(membership_id, tenant_id)` (103-116) — change status, pas de revoke session.
- `reactivate(membership_id, tenant_id)` (118-128).
- `revoke(membership_id, tenant_id, reason)` (130-145) — soft, pas de revoke session.
- `_require_membership_in_tenant` — privé.

### 3.7 `repositories/tenant_membership.py` (152 LoC)

`AsyncTenantMembershipRepository` :
- `get_by_id` (lignes 21-28) — **pas de filtre tenant** (commentaire « usage admin »).
- `get_active(account_id, tenant_id)` (30-55) — filtré sur `revoked_at IS NULL AND status='active'`.
- `get_active_or_suspended` (57-74) — filtré sur `revoked_at IS NULL`.
- `list_by_account`, `list_by_tenant` (avec pagination + window count).
- `create`, `revoke`, `suspend`, `reactivate`.

⚠️ Hérite **pas** de `AsyncBaseRepository` — commentaire ligne 15 « TenantMembership n'a pas TenantMixin ». Mais TenantMembership **a** `tenant_id` (ligne 61 du modèle). Le commentaire est trompeur — c'est juste que TenantMembership n'utilise pas le mixin (cf F157 module 05).

### 3.8 `repositories/tenant_settings.py` (58 LoC)

- `TenantSettingsRepository` (sync) + `AsyncTenantSettingsRepository` (async).
- `get(tenant_id)` (lignes 12-19) :
  ```python
  obj = self.db.query(TenantSettings).filter_by(tenant_id=tenant_id).first()
  if obj is None:
      obj = TenantSettings(tenant_id=tenant_id)
      self.db.add(obj)
      self.db.flush()
  return obj
  ```
  **Race condition** : 2 requêtes concurrentes appellent `get` simultanément, both trouvent `None`, both `add`+`flush` → IntegrityError (UNIQUE constraint sur `tenant_id`) sur la 2ème. Pas de try/except, l'exception remonte en 500.
- `update(tenant_id, data)` (21-27) — upsert via `model_dump(exclude_none=True)` + `setattr`.
- `AsyncTenantSettingsRepository` même pattern (33-58).

### 3.9 `endpoints/tenant_brand.py` (61 LoC) — déjà couvert module 01

`GET /tenant/brand?brand_code={code}` :
- Public, no auth.
- Query : `JOIN tenants WHERE tenants.brand_code == brand_code AND tenants.is_active == True LIMIT 1` (ligne 36-41).
- Retourne `TenantBrandPublic`.
- 404 si pas de match.

### 3.10 `endpoints/provisioning.py` (182 LoC)

`POST /admin/provision` :
- Auth `UserManagerScope` + `require_stepup`.
- Body `TenantProvisionRequest(name, domain, contact_email, app_code, plan, notes)`.
- `app_code` regex `^(marveline|epicerie|restaurant)$` ligne 25 — **duplique le CHECK constraint** DB.
- **Pas de `brand_code` dans le body** — le brand_code reste à default `"marveline"`.
- `TenantService.provision`.
- Pas d'auto-création TenantBrand / TenantSettings / membership initial.

`POST /admin/provision/{id}/activate`, `/suspend`, `/offboard` — transitions.

`GET /admin/provision/degraded/status` (ligne 137-140) :
```python
return {"degradation_level": redis_sec.get_degradation_level()}
```
**`get_degradation_level` est `async def` (cf module 01)** — appelé sans `await` ! Réponse contient une coroutine non sérialisable → erreur 500 ou comportement non-déterministe.

`POST /admin/provision/degraded/enable` (lignes 143-161) — `redis_sec.set_degraded_flag(...)` (async) sans `await` → coroutine perdue, **flag jamais set**.

`POST /admin/provision/degraded/disable` (lignes 164-182) — idem, `redis_sec.clear_degraded_flag(...)` + `redis_sec.get_degradation_level()` sans `await`.

### 3.11 `schemas/tenant_brand.py` (22 LoC)

`TenantBrandPublic(BaseModel)` — **bypass `BaseSchema`** (cf F234 module 08). Champs : display_name, legal_name, tagline, primary_color, primary_rgb, palette, logo_url, logo_square_url, favicon_url, contact_email, contact_phone.

---

## 4. Frictions identifiées

(Numérotation continue — F255 commence après le module 08.)

### 4.1 Frictions P0

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F255** | endpoints/provisioning | **3 endpoints `degraded` appellent `redis_sec.*` async sans `await`** | `provisioning.py:140` (`get_degradation_level()`), `:159` (`set_degraded_flag(...)`), `:179` (`clear_degraded_flag(...)`) ; `redis.py:636-669` ces 3 méthodes sont `async def` | **Bug réel** : coroutines créées et perdues. Conséquences :<br>- `GET /admin/provision/degraded/status` retourne `{"degradation_level": <coroutine>}` → JSON serialization error 500.<br>- `POST /admin/provision/degraded/enable` n'active **jamais** le flag dégradé en Redis-SEC. Le mode dégradé `READ_ONLY`, `AUTH_DOWN`, `EMERGENCY_BYPASS` n'est pas activable via cet endpoint.<br>- `POST /admin/provision/degraded/disable` ne désactive jamais le flag.<br>**Le système de dégradation 4 niveaux promis par le module degraded.py (cf F121 module 04) est inopérant côté admin**. Si un ops veut basculer le tenant en READ_ONLY, l'API est cassée. Pattern identique à F168 module 06 (cache async appelé sync). |
| **F256** | services/tenant + tenant_settings | **Provisioning incomplet — TenantBrand et TenantSettings non créés** | `services/tenant.py:65-90` (provision crée seulement la ligne `Tenant`) ; `repositories/tenant_settings.py:14-19` (création à la volée au premier `get`) ; aucun `TenantBrandRepository.create_default` | Quand `POST /admin/provision` réussit, le tenant en DB a :<br>- ✅ Une ligne `tenants`.<br>- ❌ Pas de ligne `tenant_brands` → `GET /tenant/brand?brand_code=lesplendid` retourne **404** jusqu'à ce qu'un endpoint admin (qui n'existe pas) crée la ligne.<br>- ❌ Pas de ligne `tenant_settings` → première lecture déclenche création **avec defaults Marveline** (TVA 20%, acompte 40%, caution × 3, etc.) — Splendid hérite, **incohérent avec un tenant qui aurait des CGV différentes**.<br>- ❌ Pas de `TenantMembership` initial → le super_admin qui a provisionné **n'a aucun accès au nouveau tenant**.<br>**Conséquence** : pour rendre un tenant utilisable, il faut N appels manuels en plus :<br>1. Créer `tenant_brand` (logo, couleurs, contacts) → endpoint manquant.<br>2. Créer `tenant_settings` (CGV par tenant) → endpoint manquant ou via update existant.<br>3. Créer membership initial → endpoint manquant.<br>4. Activer le tenant.<br>**Atomicité brisée**, opérabilité multi-tenant cassée. |
| **F257** | tenant + provisioning | **`Tenant.app_code` CHECK constraint hardcodée à 3 valeurs — `provisioning` régex idem** | `tenant.py:23-26` (CHECK `IN ('marveline', 'epicerie', 'restaurant')`) ; `provisioning.py:25` (`pattern="^(marveline\|epicerie\|restaurant)$"`) | Toute évolution multi-app (ajout d'un 4ème app, ex: `vehicules` pour location auto, ou refonte fine `marveline_location` vs `marveline_event_planning`) requiert :<br>(a) Édition du modèle Python.<br>(b) Migration Alembic pour modifier le CHECK.<br>(c) Édition du Pydantic regex.<br>(d) Édition de `JWT_AUDIENCES` dict (`config.py:69-73`, cf F07 module 01).<br>(e) Édition de `_APP_PREFIX_MAP` dans degraded middleware (cf F121 module 04).<br>(f) Édition de `RateLimitScope` enum (cf F209 module 07).<br>**6 endroits à éditer** pour ajouter un app_code. À refactorer en table `apps` avec FK `Tenant.app_id` ou enum DB-side généré. |
| **F258** | tenant | **Aucune contrainte de cohérence `(app_code, brand_code)`** | `tenant.py` entier ; pas de CHECK constraint sur le tuple | Un tenant peut avoir `app_code='restaurant' + brand_code='lesplendid'` — combinaison non-sensique (Le Splendid n'est pas un restaurant). Le frontend chargera la palette Splendid sur un workflow Restaurant. À ajouter un table `app_brand_compat(app_code, brand_code)` ou un CHECK constraint avec mapping autorisé. |
| **F259** | services/membership | **Pas de revoke session lors de `suspend()` ou `revoke()`** | `services/membership.py:103-116, 130-145` ; cf `redis_sec.revoke_all_user_sessions` existant (`redis.py:304-311`) | Quand un admin suspend ou révoque un membership, l'utilisateur garde ses tokens valides jusqu'à expiration access (15 min). **Fenêtre de 15 min où un user révoqué peut continuer à appeler l'API**. Pour un membership révoqué pour cause de breach (compromission compte ou abus), c'est **inacceptable**. À ajouter dans `MembershipService.suspend/revoke` :<br>```python<br>from app.core.redis import redis_sec<br>await redis_sec.revoke_all_user_sessions(membership.account_id)<br>```<br>(En filtré tenant ? Difficile car les sessions sont par account, pas par membership.) |

### 4.2 Frictions P1

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F260** | tenant_brand | Style SQLAlchemy 1.x untyped | `tenant_brand.py:20-48` (`Column(...)` direct) ; vs `tenant_membership.py` (Mapped 2.0) | Cf F155 module 05. Inconsistance dans le codebase. À migrer en `Mapped[...]`. |
| **F261** | tenant_brand | **Defaults Marveline hardcodés** | `tenant_brand.py:30-31` (`primary_color="#b96cc4"`, `primary_rgb="185 108 196"`) | Si un nouveau tenant_brand est créé sans spécifier ces valeurs, hérite Marveline. Pas critique (les ops vont les set) mais piège. À supprimer les defaults : valeurs **required** (NOT NULL sans default). |
| **F262** | tenant_settings | **`tenant_id` Integer + non FK + `id` Integer** | `tenant_settings.py:10-11` | Cf F148, F149, F156, F157 module 05. Doit être migré en BigInteger + FK + TenantMixin. |
| **F263** | tenant_settings | **21 colonnes mélangées : business + infrastructure + identité + reporting** | `tenant_settings.py:7-92` | Single Responsibility violée. Sous-domaines :<br>- **Business CGV** : vat_rate, hourly_rates, advance/deposit/cancellation rates, guards livraison, linen_min_days.<br>- **Infrastructure imprimante** : printer_host, printer_port.<br>- **Identité ticket** : nom_commerce, adresse, siret, telephone.<br>- **Identité multi-brand** : frontend_url, mfa_issuer_name.<br>- **Logistique** : origin_postal_code.<br>- **Reporting** : reservation_uplift_pct.<br>À éclater en `tenant_business_settings`, `tenant_infrastructure_settings`, `tenant_brand_settings` (ou rapatrier dans `tenant_brands`). |
| **F264** | tenant_settings | **Defaults CGV Marveline pour TOUT nouveau tenant** | `tenant_settings.py:20-44` (TVA 20%, advance 40%, deposit ×3, etc.) | Cf F195, F196 module 07. Mais ici **pris dans la table** — donc même si on a override `app/constants/business.py`, les nouveaux tenants héritent quand même via les defaults colonnes. À découpler : defaults par `app_code` ou `brand_code` lus à la création du `tenant_settings` row. Ex :<br>```python<br>def create_default_settings(tenant: Tenant) -> TenantSettings:<br>    if tenant.app_code == 'marveline':<br>        return TenantSettings(tenant_id=tenant.id, vat_rate=0.20, advance_rate=0.40, ...)<br>    elif tenant.app_code == 'epicerie':<br>        return TenantSettings(tenant_id=tenant.id, vat_rate=0.055, advance_rate=0.0, ...)<br>    # ...<br>```|
| **F265** | tenant_settings repo | **Race condition sur `get()` à la première lecture** | `repositories/tenant_settings.py:14-19, 44-49` | 2 requêtes concurrentes :<br>1. R1 : `get(tenant_id=5)` → `None` → `db.add(TenantSettings(tenant_id=5))` → `flush`.<br>2. R2 (entre find et add) : `get(tenant_id=5)` → `None` → `db.add(...)` → `flush` lève `IntegrityError`.<br>Pas de try/except, exception remonte. À fixer : `INSERT ... ON CONFLICT DO NOTHING RETURNING ...` (PG upsert). |
| **F266** | tenant + provisioning | **`brand_code` absent du body de provisioning** | `provisioning.py:21-27` (`TenantProvisionRequest` ne contient pas `brand_code`) | Le tenant créé hérite du default `"marveline"` (`tenant.py:44-45`). Pour créer un tenant Splendid, il faut un endpoint séparé pour set le `brand_code` après. À ajouter `brand_code: str = Field(default="marveline", pattern="^[a-z0-9_-]+$")` dans le body. |
| **F267** | endpoints | **Aucun endpoint admin pour créer/modifier `TenantBrand` ni `TenantSettings`** | `tenant_brand.py:23-61` expose seulement `GET /tenant/brand` (public lecture) ; pas de `POST/PATCH /admin/tenants/{id}/brand` | Conséquence : pour set le brand `lesplendid` après provisioning, il faut soit :<br>- Modifier directement en DB (`UPDATE tenants SET brand_code = ...`), pas d'audit.<br>- Créer une migration Alembic.<br>**Pas d'API d'admin** — multi-brand ops impossible via API. |
| **F268** | services/tenant | **Pas de méthode `archive()` malgré state machine** | `services/tenant.py:21-179` ; `tenant.py:78-84` (`TRANSITIONS["offboarding"] = ["archived"]`) | L'état `archived` est terminal dans la state machine mais aucune méthode `TenantService.archive` ni endpoint pour y transitionner. Tenants restent à vie en `offboarding` après `data_retention_days`. À implémenter (peut-être via Celery beat qui scanne `offboarding` → `archived` après expiration). |
| **F269** | services/membership | **Pas de check `tenant.is_active` avant provision membership** | `services/membership.py:76-101` | On peut créer un membership sur un tenant `provisioning`, `suspended` ou `offboarding`. Devrait raise 400 si `tenant.status != 'active'`. |
| **F270** | services/membership | **`max_users` jamais checké** | `services/membership.py:provision` ; `tenant.py:74` (`max_users default 50`) | Le quota par-tenant n'est pas appliqué. `MembershipService.provision` n'effectue pas de count + comparison. Tenant peut avoir 1000 users malgré `max_users=50`. À ajouter check + 409 si dépassé. |
| **F271** | services/tenant | **`max_sessions_per_user` triplon** | `tenant.py:75` vs `Limits.MAX_SESSIONS_PER_USER` (`limits.py:62`) vs `SessionConfig.MAX_SESSIONS_PER_USER` (`security.py:333`) | Cf F210 module 07. Trois sources de vérité, une par-tenant. Ambiguë : laquelle est appliquée ? Le service de session devrait préférer la valeur tenant si non-NULL, fallback constants. |
| **F272** | services/tenant | **`provision()` n'audite pas via Outbox — pas atomique** | `services/tenant.py:81-88` (`audit.log_action` puis `db.flush`) ; commit global plus haut | Cf F117 module 04. Si `audit.log_action` lève, le tenant est créé mais pas audité (ou inverse selon ordre commit). À utiliser Outbox Pattern. |
| **F273** | endpoints/provisioning | **Pas de membership initial pour le `provisioned_by`** | `provisioning.py:44-76` | Le super_admin qui provisionne un tenant **n'a aucun accès au tenant créé** (sauf membership cross-tenant pre-existing). Devrait créer un `TenantMembership(account_id=current_user.id, tenant_id=tenant.id, role_name='tenant_admin')` automatiquement. |
| **F274** | tenant_brand endpoint | **Pas d'unique constraint sur `Tenant.brand_code` — endpoint expose le premier match arbitrairement** | `tenant_brand.py:36-41` (`LIMIT 1`) | Si 2 tenants partagent le même `brand_code` (ex: 2 instances Splendid prod + dev), le frontend reçoit une seule des 2 brands aléatoirement. Pas critique mais surprenant. À documenter ou ajouter unique constraint. |
| **F275** | tenant_brand endpoint | `is_active == True` filtre — un tenant `provisioning` n'a pas de brand | `tenant_brand.py:39` | Pendant la phase provisioning, le frontend tombe en fallback Marveline. Documenter ou inverser (servir le brand même en provisioning). |
| **F276** | services/membership | **Pas d'audit sur provision/suspend/reactivate/revoke** | `services/membership.py` aucun appel à `AuditService` | RGPD : changements de rôle / accès doivent être audités. Pas de trail. À ajouter. |
| **F277** | tenant_membership repo | **`get_by_id(membership_id)` sans filtre tenant — usage admin déclaré, mais utilisé partout** | `repositories/tenant_membership.py:21-28` (commentaire « usage admin ») | Dans `MembershipService._require_membership_in_tenant`, on appelle `get_by_id` puis check `membership.tenant_id != tenant_id`. La friction : si un autre callsite oublie le check (par exemple dans `core/deps.py:301`), un user peut accéder à un membership d'un autre tenant. À refactorer : exposer seulement `get_by_id_in_tenant(membership_id, tenant_id)` qui filtre directement. |
| **F278** | schemas/tenant_brand | `TenantBrandPublic` hérite de `BaseModel` direct | `schemas/tenant_brand.py:7` | Cf F234 module 08. Bypass `BaseSchema`. |

### 4.3 Frictions P2

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F279** | tenant_brand | Pas de versioning du brand | `tenant_brand.py` | Pas de table `tenant_brand_history`. Si on change la palette, l'ancienne est perdue — pas de "à quoi ressemblait le brand le 1er janvier ?". À considérer pour audit B2B. |
| **F280** | tenant_brand | Pas de TimestampMixin (redéclaration manuelle) | `tenant_brand.py:42-48` | Au lieu d'hériter `TimestampMixin`, ré-écrit les colonnes. À utiliser le mixin. |
| **F281** | services/tenant | `notes` accumulés ad-hoc dans une string | `services/tenant.py:121, 143` (`tenant.notes = f"[date] reason\n{old_notes}"`) | Pattern fragile : un fichier note de quelques KB devient illisible après 100 transitions. À structurer en table `tenant_audit_events` séparée ou JSON. |
| **F282** | services/tenant + provisioning | **`provisioning.py` body `app_code` regex hardcodé** | `provisioning.py:25` | Cf F257. Duplication. À dériver de `Tenant.APP_CODES`. |
| **F283** | services/membership | `provision` n'a pas de paramètre `audit_reason` | `services/membership.py:76-101` | Pour traçabilité, un admin qui invite un user devrait fournir une raison/justification. À ajouter. |
| **F284** | tenant.py + middleware/app_enforcement | `Tenant.APP_CODES` tuple + CHECK constraint dupliqué dans Pydantic regex | cf F257 | À unifier en single source : `Tenant.APP_CODES` est généré depuis une table `apps`. |
| **F285** | tenant_brand | `palette_json` peut être NULL | `tenant_brand.py:32` | Si NULL, le frontend doit fallback sur defaults — code de fallback partout dans le frontend. À rendre required avec defaults Marveline initiaux ou JSON `{}` vide. |
| **F286** | tenant_settings | `frontend_url`, `mfa_issuer_name` doivent fallback `settings.*` mais commentaires manquent docstring sur l'ordre de résolution | `tenant_settings.py:80-81` | Documenter explicitement l'ordre :<br>1. `tenant_settings.X` si non NULL<br>2. fallback `settings.X` (config global). |
| **F287** | tenant.py | `data_retention_days = 90` default global | `tenant.py:70-71` | Pour différents plans (standard/premium/enterprise) ou différents brands, retention RGPD peut varier. À déplacer en `tenant_settings` ou par-plan. |
| **F288** | tenant.py | Pas d'enum `Tenant.STATUSES` | (modèle) | `status: String(20)` accepte n'importe quoi. Le CHECK existe ? À vérifier. Idem pour `plan`. |

### 4.4 Frictions P3

| ID | Couche | Friction | Citation |
|---|---|---|---|
| **F289** | tenant.py | Comments en français | `tenant.py:8-13, 22, ...` — convention non documentée. |
| **F290** | tenant_brand | `address String(500)` mais pas validé format | `tenant_brand.py:40` — devrait être structured (rue, ville, CP, pays). |
| **F291** | provisioning | `TenantActionRequest.reason: Optional[str]` sans length max | `provisioning.py:40-41` — peut recevoir 1MB de texte. À add `max_length=500`. |

---

## 5. Dépendances inter-modules / fuites

### 5.1 Couplages observés

- `models/tenant_brand` → `models/base` (Base seul, pas de mixin).
- `models/tenant_settings` → `models/base` (Base, TimestampMixin).
- `models/tenant_membership` → `models/base` (Base seul, mais relations vers `Account` et `AuthRole`).
- `services/tenant` → `services/audit`, `models/tenant`.
- `services/membership` → `repositories/tenant_membership`, `models/tenant_membership`, `constants/ErrorMessages`.
- `endpoints/provisioning` → `services/tenant`, `core/redis.redis_sec` (mais async appelé sync — F255).
- `endpoints/tenant_brand` → `models/tenant`, `models/tenant_brand`, `schemas/tenant_brand`.

### 5.2 Forward-impact CRITIQUE

Les frictions de ce module impactent **directement** :
- **Module 02** (`02-core-security.md`) : F206 (`MFAConfig.ISSUER_NAME = "Marveline"`) — devrait lire `tenant_settings.mfa_issuer_name` (F286).
- **Module 04** (middlewares) : F121 (`_MARVELINE_DEGRADED_KEY` partagé) confirmé ici — doit utiliser `tenant_id` dans la clé (F258).
- **Modules métier (14-25)** : tous consomment les CGV via `tenant_settings.advance_rate`, etc. Si le tenant n'a pas de settings (F265 race condition), defaults Marveline appliqués.

### 5.3 Confirmations forward

- **F06 module 01** (brand strings hardcodés) : confirmé ici. Le système `tenant_settings.frontend_url + mfa_issuer_name` est **prévu** (commentaires lignes 80-81) mais **pas câblé** (à valider modules 12, 27).
- **F148 module 05** (FK manquante) : confirmé sur `tenant_settings.tenant_id` (F262).
- **F157 module 05** (TenantMixin pas utilisé) : confirmé sur `tenant_settings`, `tenant_brand`, `tenant_membership`.
- **F195 module 07** (CGV Marveline hardcodé) : **partiellement résolu** — les valeurs sont en colonnes `tenant_settings` mais avec defaults Marveline (F264).

---

## 6. Recommandations de refonte

### 6.1 Priorité 1 — Fixes bug critiques (P0)

1. **F255** : ajouter `await` sur tous les appels `redis_sec.*` dans `provisioning.py:140, 159, 179` :
   ```python
   @router.get("/degraded/status")
   async def get_degradation_status(...):
       from app.core.redis import redis_sec
       level = await redis_sec.get_degradation_level()
       return {"degradation_level": level}
   ```
   Tests : E2E `POST /admin/provision/degraded/enable level=READ_ONLY` puis vérifier que `redis_sec.is_degraded(DEGRADED_READ_ONLY)` retourne True. Devrait actuellement échouer.

2. **F256** : refactor `TenantService.provision` pour créer atomiquement les artifacts :
   ```python
   async def provision(self, ..., brand_code: str = "marveline", initial_admin_account_id: int):
       tenant = Tenant(..., brand_code=brand_code, ...)
       self.db.add(tenant)
       await self.db.flush()
       
       # Auto-create defaults (pas de race condition F265)
       brand = TenantBrand(tenant_id=tenant.id, display_name=name, legal_name=name, ...)  # palette init
       settings = self._build_default_settings(tenant)  # F264 dispatch par app_code
       initial_membership = TenantMembership(account_id=initial_admin_account_id, tenant_id=tenant.id, role_name='tenant_admin')
       self.db.add_all([brand, settings, initial_membership])
       await self.db.flush()
       # ...
   ```

3. **F259** : revoke sessions on suspend/revoke :
   ```python
   async def suspend(self, membership_id: int, tenant_id: int):
       membership = await self._require_membership_in_tenant(membership_id, tenant_id)
       # ...
       result = await self._repo.suspend(membership)
       # Cascade : revoke toutes les sessions du compte sur ce tenant
       await redis_sec.revoke_sessions_for_account_tenant(membership.account_id, tenant_id)
       return result
   ```
   Note : `revoke_sessions_for_account_tenant` n'existe pas (F-todo) — à implémenter dans Redis-SEC store.

### 6.2 Priorité 2 — Architecture multi-app/multi-brand (P0-P1)

4. **F257, F284** : remplacer le CHECK constraint hardcodé par une table `apps` :
   ```python
   class App(Base):
       __tablename__ = "apps"
       code = Column(String(20), primary_key=True)  # 'marveline', 'epicerie', 'restaurant', ...
       jwt_audience = Column(String(50), nullable=False)  # 'marveline-api'
       degraded_redis_key = Column(String(50), nullable=False)
       enabled = Column(Boolean, default=True)
   ```
   Et `Tenant.app_code` devient FK. `provisioning.py` regex devient dynamique : lire `apps.code` au boot.

5. **F258** : table `app_brand_compat(app_code, brand_code)` ou enum DB-side. Refuser les combinaisons incohérentes au niveau service `TenantService.provision`.

6. **F266, F267** : ajouter `brand_code` au body provisioning + endpoints admin pour TenantBrand / TenantSettings :
   ```python
   class TenantProvisionRequest(BaseModel):
       # ... existing
       brand_code: str = Field(default="marveline", pattern="^[a-z0-9_-]+$")
       brand_display_name: str
       brand_primary_color: str
       # ... ou un objet brand: TenantBrandCreate imbriqué
   ```
   Et :
   ```python
   @router.patch("/admin/tenants/{id}/brand")
   async def update_tenant_brand(id: int, body: TenantBrandUpdate, ...): ...
   @router.patch("/admin/tenants/{id}/settings")
   async def update_tenant_settings(id: int, body: TenantSettingsUpdate, ...): ...
   ```

### 6.3 Priorité 3 — Cohérence tenant_settings (P1)

7. **F262** : `tenant_settings` migration vers `BigInteger` PK + FK + TenantMixin.

8. **F263** : éclater en 3 tables :
   - `tenant_settings_business` (CGV, fiscal, tarifs).
   - `tenant_settings_infrastructure` (printer, frontend_url).
   - `tenant_settings_brand` (mfa_issuer_name, ticket info) — ou rapatrier dans `tenant_brands`.

9. **F264** : `_build_default_settings(tenant)` dispatch par `tenant.app_code` :
   - `marveline` : TVA 20%, advance 40%, deposit 3.0, etc.
   - `epicerie` : TVA 5.5%, pas d'advance (ventes immédiates), pas de deposit.
   - `restaurant` : TVA 10%, etc.

10. **F265** : utiliser PG upsert ou advisory lock pour éviter race :
    ```python
    async def get(self, tenant_id: int):
        # ON CONFLICT DO NOTHING
        stmt = pg_insert(TenantSettings).values(tenant_id=tenant_id).on_conflict_do_nothing(index_elements=['tenant_id'])
        await self.db.execute(stmt)
        result = await self.db.execute(select(TenantSettings).filter_by(tenant_id=tenant_id))
        return result.scalar_one()
    ```

### 6.4 Priorité 4 — Sûreté membership (P1)

11. **F269, F270** : check `tenant.is_active` + `max_users` dans `MembershipService.provision`.

12. **F273** : créer membership initial automatiquement dans `TenantService.provision`.

13. **F276** : ajouter audit dans tous les MembershipService methods.

14. **F277** : `AsyncTenantMembershipRepository.get_by_id` deprecated / privé. Exposer `get_by_id_in_tenant(membership_id, tenant_id)`.

### 6.5 Priorité 5 — Hygiène (P2)

15. **F260, F280** : tenant_brand en SQLAlchemy 2.0 typed + TimestampMixin.

16. **F261** : tenant_brand sans defaults (required NOT NULL).

17. **F268** : implémenter `archive()` + Celery beat scheduler.

18. **F271** : single source of truth pour `MAX_SESSIONS_PER_USER`.

19. **F272** : Outbox Pattern pour audit (cf module 04 F117).

20. **F281** : structurer `tenant.notes` en table séparée ou JSON.

21. **F285** : `palette_json` NOT NULL avec default `{}`.

22. **F287** : `data_retention_days` per-plan ou per-brand.

### 6.6 Tests à écrire avant refonte

- **F255** : `client.get("/admin/provision/degraded/status")` doit retourner JSON `{"degradation_level": "NOMINAL"}`. Devrait actuellement échouer (coroutine sérialisée).
- **F256** : `POST /admin/provision` puis `GET /tenant/brand?brand_code=lesplendid` doit retourner 200. Devrait actuellement retourner 404 (pas de tenant_brand row créé).
- **F258** : `Tenant(app_code='restaurant', brand_code='lesplendid')` doit raise (incohérent). Devrait actuellement passer.
- **F259** : suspend membership → l'access token de l'user doit être révoqué dans Redis-SEC. Devrait actuellement rester valide 15 min.
- **F265** : 100 requêtes concurrentes `tenant_settings.get(tenant_id=999)` doivent toutes réussir et **retourner la même row** (test avec `asyncio.gather`). Devrait actuellement avoir des IntegrityError sur certaines.
- **F269** : `MembershipService.provision(account_id=1, tenant_id=tenant_in_offboarding)` doit raise 400. Devrait actuellement passer.
- **F273** : après `POST /admin/provision`, le `current_user.id` doit avoir un membership actif sur le tenant créé. Devrait actuellement n'avoir aucun.

### 6.7 Hors-scope

- `auth_role`, `auth_role_scope`, `auth_scope` → module 11.
- `account`, `account_session`, `account_oauth_identity` → module 10.
- `mfa`, `webauthn`, `trusted_device` → module 12.

---

## 7. Verdict module 09 — Le module CRITIQUE

| Aspect | État |
|---|---|
| Convention 4 couches | Modèle + Repo + Service + Endpoint présents, mais `TenantSettings` ne suit pas (Integer PK, pas FK, pas TenantMixin) |
| Architecture multi-tenant | **Conceptuellement correcte** : Account global, Tenant + Membership, séparation app_code / brand_code |
| Architecture multi-app | **Hardcodée à 3 valeurs** : `Tenant.app_code` CHECK + Pydantic regex + JWT_AUDIENCES + degraded keys + RateLimit scopes — 6 endroits à éditer pour ajouter un app (F257) |
| Architecture multi-brand | **Partielle** : `brand_code` libre côté Tenant, table `tenant_brands` 1:1, endpoint public `/tenant/brand` — **mais** : pas de cohérence `(app_code, brand_code)` (F258), pas d'endpoint admin pour modifier (F267), pas de provisioning brand atomique (F256), defaults Marveline partout (F261, F264) |
| Provisioning | **Incomplet** : `TenantService.provision` ne crée que la ligne Tenant. Pas de TenantBrand, pas de TenantSettings, pas de Membership initial. Tenant créé est inutilisable sans 3+ appels manuels supplémentaires (F256). |
| Mode dégradé | **Cassé en bug réel** : 3 endpoints async appelés sans await (F255). Le système 4-niveaux (READ_ONLY/AUTH_DOWN/EMERGENCY_BYPASS) **n'est pas activable via l'API admin**. |
| Sécurité membership | **Trou** : suspend/revoke ne révoquent pas les sessions actives — fenêtre 15 min (F259) |
| RGPD offboarding | Méthode `archive` non implémentée (F268). Retention 90j hardcodé (F287). Pas de purge automatique. |
| Multi-brand support code-base | Splendid déjà déployé en prod (memory `client-splendid-events.md`) avec brand_code='lesplendid' — **fonctionne par chance** (les defaults Marveline sont compatibles avec un workflow événementiel). Mais pour des CGV différentes, blocage architectural. |
| Dette | 37 nouvelles frictions : 5 P0, 19 P1, 10 P2, 3 P3 |

**Conclusion** : Ce module est le **cœur du sujet Marveline/Splendid**. L'architecture multi-tenant + multi-app + multi-brand **existe en surface** (3 dimensions séparées : Account, app_code, brand_code) mais **mal cablée en profondeur** :

- Le **provisioning est incomplet** (F256) → impossible de créer un tenant Splendid utilisable via API.
- Les **CGV par défaut sont Marveline** (F264) → Splendid hérite des CGV Marveline silencieusement.
- Le **mode dégradé est cassé** (F255) → ops ne peut pas basculer en READ_ONLY.
- Pas de **cohérence (app_code, brand_code)** (F258) → combinaisons absurdes autorisées.
- Pas d'**endpoints admin** pour TenantBrand / TenantSettings (F267) → multi-brand ops impossibles.

**Avant tout déploiement multi-tenant sérieux**, les 5 P0 doivent être traités :
1. F255 (bug await) — fix immédiat (1h).
2. F256 (provisioning atomique) — refactor service tenant + tests (1-2j).
3. F257 (app_code unifié) — table `apps` + migration (1-2j).
4. F258 (cohérence app/brand) — table compat + check service (½j).
5. F259 (revoke sessions) — Redis-SEC store + cascade (1j).

Coût total estimé : **5-7 jours-développeur** pour un fondement multi-brand sain.

→ Module suivant : `10-account-session-membership.md` (Account, AccountSession, AccountOAuthIdentity, déjà partiellement TenantMembership couvert ici).
