# Module 10 — Account / AccountSession / AccountOAuthIdentity

## 1. Périmètre

| Fichier | LoC | Rôle |
|---|---|---|
| `app/models/account.py` | 87 | Identité globale (email unique, password, names, address) — sans tenant_id |
| `app/models/account_session.py` | 126 | Session JWT (sid, account_id, membership_id, tenant_id dénormalisé, device, IP, MFA flag) |
| `app/models/account_oauth_identity.py` | 66 | N:1 OAuth (provider, provider_subject) → Account |
| `app/services/account.py` | 264 | `AccountService` — credentials, create, change/forgot/reset password, HIBP flag |
| `app/services/account_session.py` | 200 | `AccountSessionService` — open, validate, revoke (single, all, except), MFA mark, touch |
| `app/repositories/account.py` | 95 | Lookup global (par id, email, external_id), create, flush |
| `app/repositories/account_session.py` | 214 | CRUD + bulk revoke par membership/account |
| `app/repositories/account_oauth_identity.py` | 59 | Lookup par (provider, subject), create |

**Total** : 1 111 LoC.

**Dépend de** : `models/base`, `models/tenant_membership` (FK), `services/{audit, hibp, notification}`, `core/{redis, security, config}`, `repositories/password_reset_token`, `constants/{ErrorMessages, Limits, RedisKeys}`.

**Dépendu par** : `core/deps.get_current_user/get_current_account/get_current_membership` (lookup auth), endpoints `auth_v2`, `oauth_v2`, services métier qui ont besoin de l'account.

**Convention IAM v2** : `Account` est une **identité globale** (sans tenant_id) — l'isolation tenant est portée par `TenantMembership` (cf module 09).

---

## 2. Lecture par fichier

### 2.1 `models/account.py` (87 LoC)

- `id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)` (ligne 29) — **pas de `BigInteger`** (default Integer 32 bits).
- `external_id: String(64)` UUID v4 (ligne 31-38).
- `email: String(255)` UNIQUE (`uq_accounts_email`, ligne 26).
- `hashed_password: Optional[String(255)]` — nullable pour OAuth-only.
- `first_name`, `last_name: String(100)` NOT NULL.
- `address: Optional[String(500)]`, `postal_code: Optional[String(20)]` — données personnelles **stockées au niveau global** (lignes 56-57).
- `password_change_required: bool default False` — flag HIBP.
- `pin_hash: Optional[String(255)]` — Argon2id hash PIN 4-6 chiffres.
- Hérite `TimestampMixin`, `SoftDeleteMixin`.
- **Event listener `_normalize_email`** (lignes 82-87) : `value.lower().strip()` au `set`. Ne s'applique pas aux INSERT raw SQL.

### 2.2 `models/account_session.py` (126 LoC)

- 4 indexes :
  - `idx_account_sessions_tenant_account` `(tenant_id, account_id)`.
  - `idx_account_sessions_membership_active` `(membership_id) WHERE revoked_at IS NULL`.
  - `idx_account_sessions_device` `(device_id)`.
  - `idx_account_sessions_account_active` `(account_id) WHERE revoked_at IS NULL`.
- `id: BigInteger` PK.
- `session_id: String(64)` UNIQUE INDEX — claim `sid` JWT.
- `account_id: BigInteger FK accounts(id) CASCADE` (ligne 49-54).
- `membership_id: BigInteger FK tenant_memberships(id) CASCADE` (56-61).
- `tenant_id: BigInteger NOT NULL` — **dénormalisé pas FK** (ligne 63-67 commentaire « pour perf »).
- `device_id: String(128)` NOT NULL — fingerprint.
- `ip_address: String(45)` NOT NULL.
- `user_agent: Optional[Text]`.
- `created_at, last_active_at, expires_at: DateTime(tz=True)` — pas de TimestampMixin.
- `revoked_at: Optional[DateTime]`, `revoke_reason: Optional[String(200)]`.
- `mfa_verified: bool default False` — pas de `mfa_verified_at` timestamp.
- `is_active` property : `revoked_at is None and now < expires_at`.

### 2.3 `models/account_oauth_identity.py` (66 LoC)

- UNIQUE `(provider, provider_subject)` (ligne 25).
- INDEX `idx_oauth_account_id`.
- `id: int` PK (Integer default — F156).
- `account_id: BigInteger FK accounts(id) CASCADE`.
- `provider: String(50)` (`google | github | facebook`).
- `provider_subject: String(255)` — claim `sub` provider.
- `email_at_provider: Optional[String(255)]` — informatif.
- `linked_at: DateTime(tz=True)` server_default now.
- **Pas de TimestampMixin** — pas de `updated_at`.
- Relation `account` lazy=`noload`.

### 2.4 `services/account.py` (264 LoC)

#### `verify_credentials(email, password) -> Optional[Account]` (55-77)
- Lookup `get_by_email(email.lower().strip())`.
- Si absent → `verify_password(password, DUMMY_HASH)` puis return None (timing-safe).
- Sinon `verify_password(password, account.hashed_password)`.
- **Si `account.hashed_password is None`** (compte OAuth-only sans password set) → `verify_password(password, None)` lève `TypeError` (cf `security.py:329-366` qui n'attend pas None).
- `needs_rehash` → re-hash transparent.
- **Pas de check `account.is_active`** — un compte suspendu peut tenter login.

#### `create_account(email, password, first_name, last_name) -> Account` (79-114)
- Vérifie unicité email globalement.
- Vérifie strength password (`validate_password_strength`).
- Crée Account `is_active=True`.
- **N'attache pas l'account à un tenant** — sans `TenantMembership`, login échoue (no membership).

#### `change_password(account_id, current_password, new_password)` (116-173)
- Brute force check via `redis_sec.get_brute_force_count(brute:pwd_change:{aid})`.
- Verify old password (incrémente brute force counter sur échec).
- Refus same-as-current.
- Strength check.
- HIBP check (`is_password_compromised`).
- Update `account.hashed_password = get_password_hash(new_password)`.
- `account.password_change_required = False`.
- Reset brute force counter.
- **AUCUNE révocation de session** après changement de mot de passe.

#### `forgot_password(email, ip_address)` (175-203)
- Rate limit via `redis_client.increment_password_reset_rate(email)` (max 3/15min).
- Anti info-leakage : retourne `True` même si compte absent.
- Génère `raw_token = hex(token_bytes(32))`, `token_hash = sha256(raw_bytes)`.
- Stocke `token_hash` via `AsyncPasswordResetTokenRepository.create`.
- Construit `reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"` (ligne 201) — **`settings.FRONTEND_URL` global hardcodé**.
- `notification_service.send_password_reset_email(email, reset_url)` — **synchrone**, bloque la requête sur SMTP.

#### `reset_password(token, new_password)` (205-257)
- Décode hex, lookup token via `consume(token_hash)`.
- Validate strength + HIBP.
- Update `account.hashed_password`.
- `account.password_change_required = False`.
- **AUCUNE révocation de session après reset**.

#### `flag_password_compromised(account_id)` (259-264)
- Set `password_change_required=True`.

### 2.5 `services/account_session.py` (200 LoC)

- `_SESSION_TTL_SECONDS = 60 * 60 * 24 * 7` (ligne 28) — **doublon** avec `Limits.REFRESH_TOKEN_EXPIRE_SECONDS`.

#### Méthodes
- `open(account_id, membership_id, tenant_id, device_id, ip_address, user_agent)` (42-77) :
  - `session_id = secrets.token_hex(32)` (64 chars).
  - `expires_at = now + 7j`.
  - `mfa_verified = False`.
  - Pas de check `max_sessions_per_user`.
- `validate(session_id) -> AccountSession` (79-90) — 401 SESSION_REVOKED si absent.
- `get_by_session_id(session_id)` (92-94).
- `revoke(session_id, requesting_membership_id, reason)` (96-120) :
  - 404 si session.membership_id ≠ requesting (isolation).
  - Idempotent si déjà revoked.
- `revoke_all_except(membership_id, current_session_id)` (122-144) — bulk via repo.
- `revoke_all(membership_id, reason)` (146-162) — bulk via repo.
- `list_by_membership`, `list_by_tenant` (164-184).
- `mark_mfa_verified(session_id)` (186-196) — set `mfa_verified=True`.
- `touch(session_id)` (198-200) — UPDATE `last_active_at = now`.

### 2.6 `repositories/account.py` (95 LoC)

- `get_by_id`, `get_active_by_id` (lignes 23-38).
- `get_by_email`, `get_active_by_email` (40-64) — normalisation `.lower().strip()` au repo aussi (redondance vs event listener du modèle).
- `get_by_external_id` (66-71) — claim `sub` JWT.
- `email_exists` (73-79) — bool.
- `create`, `flush` (81-95).

### 2.7 `repositories/account_session.py` (214 LoC)

- `get_by_session_id` (23-32) — quel que soit l'état.
- `get_active_by_session_id` (34-46) — `revoked_at IS NULL AND expires_at > now`.
- `list_active_by_membership`, `list_active_by_tenant` (48-104) — pagination + window count.
- `create`, `revoke` (106-122).
- `revoke_all_by_membership(membership_id, reason, except_session_id)` (124-155) — bulk UPDATE.
- `revoke_all_by_account(account_id, reason, except_device_id)` (157-191) — bulk UPDATE cross-membership.
- `touch(session_id)` (193-199) — UPDATE last_active_at, **pas de check rowcount**.
- `list_recent(account_id, days=30)` (201-214) — **limite hardcodée 50**.

### 2.8 `repositories/account_oauth_identity.py` (59 LoC)

- `get_by_provider_subject(provider, provider_subject)` (20-36).
- `create(account_id, provider, provider_subject, email_at_provider)` (38-58) — **lève IntegrityError** si already linked.
- **Pas de méthode `list_by_account`** (pour afficher les identités OAuth d'un compte).

---

## 3. Frictions identifiées

(Numérotation continue — F292 commence après le module 09.)

### 3.1 Frictions P0

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F292** | services/account | **`change_password` ne révoque PAS les sessions actives** | `account.py:116-173` ; `AccountSessionRepository.revoke_all_by_account` existe (`account_session.py:157-191`) mais jamais appelé ici | OWASP best practice : changer un mot de passe doit révoquer toutes les sessions sauf la courante. Si un attaquant a un access token (compromis) et que l'utilisateur légitime change son mot de passe, **l'attaquant garde son access pendant 15 min** (TTL access token). Avec refresh token (7j), il peut continuer à se renouveler **jusqu'à 7 jours**. À ajouter dans `change_password` :<br>```python<br># À la fin de change_password, après update du hash<br>from app.repositories.account_session import AsyncAccountSessionRepository<br>session_repo = AsyncAccountSessionRepository(self.db)<br>await session_repo.revoke_all_by_account(account_id, reason="password_changed")<br># + cascade Redis-SEC<br>await redis_sec.revoke_all_user_sessions(account_id)<br>``` |
| **F293** | services/account | **`reset_password` ne révoque PAS les sessions actives** | `account.py:205-257` | Plus grave que F292 : un user qui demande un reset le fait souvent **parce que le compte est compromis**. Ne pas révoquer = laisser l'attaquant continuer. À ajouter pareil que F292, **sans except** (toutes les sessions, l'utilisateur va se reconnecter). |
| **F294** | services/account | **`forgot_password` envoie l'email synchroniquement (SMTP bloquant)** | `account.py:201-202` (`notification_service.send_password_reset_email(...)` direct, pas de Celery) | Endpoint `/forgot-password` bloque sur SMTP. Si SMTP timeout (10s), l'utilisateur attend 10s puis reçoit 200 OK silencieux. Pour une attaque DoS via flooding `/forgot-password`, chaque request consomme un worker uvicorn jusqu'au timeout SMTP. À déléguer à Celery :<br>```python<br>from app.tasks.email import send_password_reset_email_task<br>send_password_reset_email_task.delay(email, reset_url)<br>``` |
| **F295** | services/account | **`forgot_password` utilise `settings.FRONTEND_URL` global** | `account.py:201` (`f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"`) | Splendid (brand_code='lesplendid') reçoit un URL pointant vers le frontend Marveline. **Le user clique sur le lien et atterrit sur Marveline.fr alors qu'il s'est inscrit sur splendid.events**. Le tenant_settings.frontend_url **est déjà prévu** (cf F286 module 09 — commentaire « NULL = fallback `settings.FRONTEND_URL` ») mais **non consommé ici**. À fixer :<br>```python<br>from app.repositories.tenant_settings import AsyncTenantSettingsRepository<br>memberships = await self._membership_repo.list_by_account(account.id)<br>if memberships:<br>    primary_membership = memberships[0]  # ou meilleur : le tenant cible du reset<br>    settings_row = await AsyncTenantSettingsRepository(self.db).get(primary_membership.tenant_id)<br>    frontend_url = settings_row.frontend_url or settings.FRONTEND_URL<br>else:<br>    frontend_url = settings.FRONTEND_URL<br>```<br>**Mais** : si le user a plusieurs memberships sur des tenants différents (Marveline + Splendid), il faut soit utiliser le `Origin` de la requête, soit choisir un tenant spécifique (champ `tenant_id` dans le request body). Confirmation directe de la promesse multi-brand non tenue. |
| **F296** | services/account | **`verify_credentials` lève `TypeError` si `hashed_password is None`** | `account.py:70` (`verify_password(password, account.hashed_password)` sans check) ; `core/security.py:verify_password` ne gère pas `None` | Cas pratique : compte OAuth-only (créé via Google sans password). Si l'utilisateur tente login email/password classique, `account.hashed_password is None` → `verify_password(password, None)` → `if _is_argon2_hash(None)` lève `AttributeError: 'NoneType' has no attribute 'startswith'`. **Login form retourne 500 au lieu de 401**. À fixer :<br>```python<br>if not account or not account.hashed_password:<br>    verify_password(password, DUMMY_HASH)  # timing-safe<br>    return None<br>``` |

### 3.2 Frictions P1

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F297** | services/account | `create_account` ne crée pas de membership | `account.py:79-114` | L'account créé n'a aucun tenant assigné. Login impossible. À documenter : `create_account` doit toujours être suivi de `MembershipService.provision`. Ou exposer un endpoint atomique `register_with_membership(email, password, ..., tenant_id)`. |
| **F298** | models/account | `Account.id` Integer (pas BigInteger) | `account.py:29` | Cf F156 module 05. Pour un SaaS visant 100M+ accounts, 2³¹ = 2.1G, marginalement OK mais inconsistant avec `tenant.id BigInteger`. À harmoniser. |
| **F299** | models/account | Données personnelles (`address`, `postal_code`) au niveau global | `account.py:56-57` | RGPD : `address` est une donnée personnelle. Stockée globalement → liée à un tenant uniquement via membership. Si l'account a 2 memberships (Marveline + Splendid), Marveline et Splendid voient la **même adresse**. Si Marveline doit purger les données du user (RGPD), faut-il purger aussi pour Splendid ? Ambigu. À déplacer côté `Customer` (tenant-scoped) ou à scinder en `account_profile` global vs `tenant_account_profile` par-tenant. |
| **F300** | models/account | Pas de `last_login_at`, `last_login_ip`, `failed_login_attempts` | `account.py` | Pour dashboard "comptes inactifs depuis 90j" ou "comptes avec login récent suspect", il faut LEFT JOIN sur `account_sessions` (slow). À dénormaliser. |
| **F301** | models/account_session | `_SESSION_TTL_SECONDS = 60*60*24*7` hardcodé | `services/account_session.py:28` | Cf F210 module 07. Doublon avec `Limits.REFRESH_TOKEN_EXPIRE_SECONDS`. À unifier. |
| **F302** | services/account_session | **`open` ne check pas `max_sessions_per_user`** | `account_session.py:42-77` ; `Tenant.max_sessions_per_user` existe (cf module 09) | Quota par-user non appliqué. Un user peut ouvrir 1000 sessions simultanées. À ajouter check :<br>```python<br>active_count = await self._repo.count_active_by_account(account_id)<br>if active_count >= max_sessions:<br>    # Soit revoke la plus ancienne, soit refuser<br>    await self._repo.revoke_oldest(account_id)<br>``` |
| **F303** | services/account_session | **`touch()` UPDATE DB à chaque requête** | `account_session.py:198-200` ; appelé probablement à chaque requête authentifiée | Pour 1000 req/s authentifiées, 1000 UPDATE/s sur `account_sessions`. Pression DB. À batcher : maintenir `last_active_at` en Redis avec TTL 1min, flush DB par lot Celery (ou à la fin de session). |
| **F304** | repos/account_session | `revoke_all_by_account/membership` **ne synchronise pas Redis-SEC** | `account_session.py:124-191` ; `redis_sec.revoke_all_user_sessions` existe (`redis.py:304-311`) mais pas appelé | Le SQL marque `revoked_at` mais Redis-SEC garde la whitelist refresh token active. Le refresh peut continuer à fonctionner jusqu'à expiration. À cascader. Cf F259 module 09. |
| **F305** | repos/account | **Normalisation email dupliquée** entre event listener + repo | `account.py:65,75` (event listener `_normalize_email`) ; `account.py:43,51,...` (modèle event) ; `repositories/account.py:49,57,75` (`.lower().strip()` redondant) | Si l'event listener fonctionne, le `.lower().strip()` au repo est redondant. Si on retire le repo, et que quelqu'un fait un INSERT raw SQL bypassing l'event, l'email reste mixed-case en DB (cf F305). À renforcer côté DB :<br>```sql<br>ALTER TABLE accounts ADD CONSTRAINT check_email_lowercase CHECK (email = lower(email));<br>```<br>Ou utiliser type `citext` (PG case-insensitive). |
| **F306** | models/account_oauth_identity | Pas de TimestampMixin | `account_oauth_identity.py:1-66` ; seulement `linked_at` | Si on update `email_at_provider` (snapshot), pas de `updated_at`. À ajouter TimestampMixin. |
| **F307** | repos/account_oauth_identity | **Pas de `list_by_account`** | `account_oauth_identity.py:1-58` | Pour endpoint `/users/me/oauth-identities` (afficher les liens Google/GitHub/Facebook), il faut une query. Pas exposée. À ajouter. |
| **F308** | repos/account_oauth_identity | `create` lève IntegrityError sans gestion | `account_oauth_identity.py:38-58` | Si déjà linked à un autre account → exception non typée. Devrait raise `OAuthAlreadyLinked` typée. |
| **F309** | services/account | `verify_credentials` ne vérifie pas `account.is_active` | `account.py:55-77` | Un account suspendu peut tenter login et obtenir l'objet retour (avant que `get_current_user` re-check). Pas critique car `get_current_user` filter, mais fail tôt > fail tard. |
| **F310** | models/account_session | `tenant_id` dénormalisé sans FK | `account_session.py:63-67` | Pas de FK vers `tenants(id)` ni de check de cohérence avec `membership.tenant_id`. Drift possible si `membership.tenant_id` est modifié (théoriquement immuable, mais sans contrainte). À ajouter FK ou trigger. |

### 3.3 Frictions P2

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F311** | models/account | Event listener email pas appliqué côté DB | `account.py:82-87` (Python-side seulement) | Cf F305. Insert raw SQL bypass. À renforcer côté DB. |
| **F312** | models/account | `email: String(255)` | `account.py:40-45` | RFC 5321 limite à 254 chars (longueur max d'une adresse mail valide). 255 est convention SQL — OK mais pas optimal. |
| **F313** | models/account_session | Pas de TimestampMixin | `account_session.py:83-93` (created_at, last_active_at redéclarés) | Cf F157 module 05. Pas de `updated_at`. À utiliser TimestampMixin. |
| **F314** | models/account_session | Pas de `mfa_verified_at` timestamp | `account_session.py:109-115` | Boolean seul. Pour audit ou expiration step-up, manque. À ajouter. |
| **F315** | repos/account_session | `touch()` ne check pas rowcount | `account_session.py:193-199` | Si la session a été DELETE entre temps (improbable, mais possible), no-op silencieux. À retourner rowcount ou raise. |
| **F316** | repos/account_session | `list_recent(account_id, days=30)` limite hardcoded 50 | `account_session.py:201-214` | Pas paramétrable. À ajouter `limit: int = 50`. |
| **F317** | services/account | `forgot_password` ne logue pas l'IP | `account.py:175-203` | `ip_address` accepté en param mais non utilisé. Pour audit (forgot_password depuis IP suspecte), inutile. À enregistrer. |
| **F318** | services/account_session | Listage sessions actives sans filtre tenant côté admin | `account_session.py:list_by_tenant` (175-184) | OK l'usage admin, mais le service peut être appelé d'un autre contexte avec un mauvais tenant_id si caller oublie. À documenter "admin only". |
| **F319** | services/account | Pas de `delete_account` ni `anonymize_account` (RGPD) | `account.py` | Soft delete via `is_active=False` mais pas d'anonymisation des données personnelles (`first_name`, `last_name`, `email`, `address`). RGPD droit à l'oubli incomplet. À ajouter. |
| **F320** | services/account | `create_account` ne tracking pas `created_by` | `account.py:79-114` | Pour audit (admin a créé tel compte vs self-register), manque. |
| **F321** | services/account | `change_password` audit absent | `account.py:116-173` | Pas d'`audit_service.log_action` après update. RGPD/SOC2 : changements de credential doivent être audités. À ajouter. |
| **F322** | services/account | `reset_password` audit absent | `account.py:205-257` | Idem F321. |

### 3.4 Frictions P3

| ID | Couche | Friction | Citation |
|---|---|---|---|
| **F323** | models/account_oauth_identity | `id` Integer (pas BigInteger) | `account_oauth_identity.py:29` — cf F156 module 05. |
| **F324** | services/account | Comments en français mêlés EN | `account.py` divers — convention. |
| **F325** | repos/account | `email_exists` retourne `bool` au lieu d'utiliser `EXISTS` | `account.py:73-79` — devrait utiliser `select(exists(...))` SQL natif. |
| **F326** | models/account_session | `device_id: String(128)` | `account_session.py:69-73` — sans format imposé. |

---

## 4. Dépendances inter-modules / fuites

### 4.1 Couplages observés

- `Account` → standalone (juste base + mixins).
- `AccountSession` → `Account` (FK), `TenantMembership` (FK).
- `AccountOAuthIdentity` → `Account` (FK).
- `AccountService` → `repositories/{account, password_reset_token}`, `services/{hibp, notification}`, `core/{redis, security, config}`.
- `AccountSessionService` → `repositories/account_session`.

### 4.2 Confirmations forward

- **F206 module 02** + **F286 module 09** (mfa_issuer / frontend_url multi-brand) : confirmation **directe ici** (F295) — `forgot_password` n'utilise pas `tenant_settings.frontend_url`.
- **F148 module 05** (FK manquante sur tenant_id) : confirmé sur `account_session.tenant_id` (F310).
- **F157 module 05** (TenantMixin pas utilisé) : Account/AccountSession/AccountOAuthIdentity ne l'utilisent pas (par design pour Account global, mais AccountSession a tenant_id sans mixin).
- **F156 module 05** (Integer PK) : confirmé sur Account et AccountOAuthIdentity (F298, F323).
- **F210 module 07** (`MAX_SESSIONS_PER_USER` triplon) : confirmé ici (F301 — `_SESSION_TTL_SECONDS` hardcodé).
- **F259 module 09** (revoke session manquant) : confirmé (F292, F293, F304).

### 4.3 Fuites Marveline / multi-brand

Module fortement impacté :
- **F295** : URL reset password Marveline pour tous les tenants. Le **plus visible des leaks UX multi-brand**.
- **F299** : address/postal_code globales — pas de séparation tenant.

### 4.4 Forward-impact

- F303 (`touch()` UPDATE DB par requête) → confirmera dans middleware audit ou request_context (modules 04 si appelé là).

---

## 5. Recommandations de refonte

### 5.1 Priorité 1 — Sécurité credentials (P0)

1. **F292, F293** : ajouter dans `change_password` et `reset_password` :
   ```python
   # Dans change_password — preserve la session courante
   from app.repositories.account_session import AsyncAccountSessionRepository
   from app.core.redis import redis_sec
   
   session_repo = AsyncAccountSessionRepository(self.db)
   await session_repo.revoke_all_by_account(
       account_id, reason="password_changed",
       except_device_id=current_device_id,
   )
   await redis_sec.revoke_all_user_sessions(account_id)  # cascade Redis whitelist
   
   # Dans reset_password — révoque TOUTES les sessions
   await session_repo.revoke_all_by_account(account_id, reason="password_reset")
   await redis_sec.revoke_all_user_sessions(account_id)
   ```

2. **F296** : check `hashed_password is None` :
   ```python
   if not account or not account.hashed_password:
       verify_password(password, DUMMY_HASH)
       return None
   ```

### 5.2 Priorité 2 — Multi-brand reset password (P0)

3. **F295** : résoudre le `frontend_url` per-tenant :
   - **Option A (recommandée)** : `forgot_password` accepte un `tenant_id: int` dans le body. Le user spécifie le brand où il veut reset. Frontend Splendid → submit avec tenant_id=5.
   - **Option B** : extraire le tenant depuis le `Origin` header de la requête (`splendid.events` → tenant=5).
   - **Option C** : si l'account a un seul membership, utiliser ce tenant. Sinon ambigu.
   
   Implémentation Option A :
   ```python
   async def forgot_password(self, email: str, tenant_id: Optional[int] = None, ip_address: Optional[str] = None):
       email = email.lower().strip()
       # ... rate limit, lookup account
       
       frontend_url = settings.FRONTEND_URL  # fallback
       if tenant_id:
           settings_row = await AsyncTenantSettingsRepository(self.db).get(tenant_id)
           if settings_row.frontend_url:
               frontend_url = settings_row.frontend_url
       
       reset_url = f"{frontend_url}/reset-password?token={raw_token}"
       # ...
   ```

4. **F294** : déplacer l'envoi email vers Celery :
   ```python
   from app.tasks.email import send_password_reset_email_task
   send_password_reset_email_task.delay(email, reset_url)
   ```

### 5.3 Priorité 3 — Multi-brand identité (P1)

5. **F299** : décider du sort de `address` / `postal_code` global :
   - **Option A** : déplacer côté `customer` (tenant-scoped). Account ne contient que email + names + auth.
   - **Option B** : table `account_addresses` (account_id, type='home'|'billing', address) — global mais multi-adresses.

6. **F297** : exposer un endpoint atomique `register_with_membership(email, password, ..., tenant_id, role_name)` qui crée Account + Membership en une transaction.

### 5.4 Priorité 4 — Sessions (P1)

7. **F302** : enforcer `max_sessions_per_user` :
   ```python
   tenant = await self._tenant_repo.get_by_id(tenant_id)
   active = await self._repo.count_active_by_account(account_id)
   if active >= tenant.max_sessions_per_user:
       # Revoke oldest
       await self._repo.revoke_oldest_by_account(account_id, reason="max_sessions_exceeded")
   ```

8. **F303** : optimiser `touch()` :
   - Maintenir `last_active_at` en Redis (TTL court).
   - Cron 1 min flush vers DB.
   - Ou skip update si delta < 60s.

9. **F304** : cascade Redis-SEC dans `revoke_all_by_account/membership`.

10. **F310** : ajouter FK `account_session.tenant_id → tenants(id)` (cf F148 module 05).

11. **F314** : ajouter `mfa_verified_at: DateTime` à `account_session`.

### 5.5 Priorité 5 — RGPD / Audit (P1-P2)

12. **F319** : implémenter `anonymize_account` :
    ```python
    async def anonymize_account(self, account_id: int, requested_by: int):
        account = await self._repo.get_by_id(account_id)
        account.email = f"deleted-{account_id}@anonymized.local"
        account.first_name = "Deleted"
        account.last_name = "User"
        account.address = None
        account.postal_code = None
        account.hashed_password = None
        account.is_active = False
        # ... revoke sessions, audit
    ```

13. **F321, F322** : ajouter audit dans change/reset/forgot_password.

14. **F320** : `create_account` accepte `created_by: Optional[int]` pour audit.

15. **F317** : `forgot_password` enregistre `ip_address` dans audit.

### 5.6 Priorité 6 — Hygiène (P2-P3)

16. **F298, F323** : `Account.id` et `AccountOAuthIdentity.id` en BigInteger.

17. **F300** : dénormaliser `last_login_at`, `last_login_ip` sur `Account` (mis à jour dans `open()`).

18. **F305, F311** : check constraint DB `email = lower(email)`.

19. **F306, F313** : utiliser TimestampMixin sur `AccountSession` et `AccountOAuthIdentity`.

20. **F307** : ajouter `list_by_account` à `AsyncAccountOAuthIdentityRepository`.

21. **F308** : exposer exception typée `OAuthAlreadyLinked`.

### 5.7 Tests à écrire avant refonte

- **F292** : login → access_token. Change_password. Réutiliser access_token → doit échouer 401. Devrait actuellement passer (token reste valide).
- **F293** : login. Trigger forgot_password + reset_password. Réutiliser le refresh_token → doit échouer. Devrait actuellement passer.
- **F295** : `POST /forgot-password tenant_id=5` (Splendid). Email contient `https://splendid.events/...`. Devrait actuellement contenir l'URL Marveline.
- **F296** : create_account OAuth-only (hashed_password=None). Tenter login email/password → doit retourner 401. Devrait actuellement retourner 500 TypeError.
- **F302** : account avec 5 sessions actives + open() 6ème. Doit revoke la plus ancienne. Devrait actuellement créer 6 sessions.
- **F304** : `revoke_all_by_account` SQL puis vérifier que `redis_sec.is_jti_in_family(...)` retourne False pour les anciens refresh JTIs. Devrait actuellement rester True.

### 5.8 Hors-scope

- `auth.py`, `auth_v2.py` endpoints → modules suivants (auth flows complets).
- `MFA`, `WebAuthn` → module 12.
- `password_reset_token`, `oauth_v2` → module 13.

---

## 6. Verdict module 10

| Aspect | État |
|---|---|
| Convention 4 couches | ✅ Modèle + Repo + Service + (Endpoint dans modules suivants). Bonne séparation. |
| IAM v2 architecture | ✅ Account global + TenantMembership + AccountSession lié au membership = bonne base RBAC multi-tenant. |
| Sécurité credentials | **3 P0** : sessions non révoquées sur change_password (F292) / reset_password (F293), TypeError sur OAuth-only login (F296) |
| Multi-brand | **1 P0** : reset password URL Marveline pour tous tenants (F295) — confirmation directe de la promesse multi-brand non tenue dans tenant_settings.frontend_url |
| Performance | `touch()` UPDATE DB par requête (F303), pas de cache last_active_at |
| Quotas | `max_sessions_per_user` non appliqué (F302) — un user peut ouvrir 1000 sessions |
| Cascade Redis | Pas de sync revoke SQL ↔ Redis-SEC whitelist (F304) — refresh token survit |
| RGPD | Pas d'anonymisation, pas d'audit sur credential changes (F319, F321, F322) |
| Données | `address`, `postal_code` globales (F299) — ambigu RGPD multi-tenant |
| Dette | 35 nouvelles frictions : 5 P0, 14 P1, 12 P2, 4 P3 |

**Conclusion** : l'architecture IAM v2 (Account global + Membership tenant + Session liée) est **conceptuellement saine** et bien implémentée structurellement (4 indexes optimisés sur `account_sessions`, soft-revoke via `revoked_at`, isolation cross-membership). **Mais 5 P0 cassent la sécurité et l'expérience multi-brand** :
1. Sessions non révoquées sur change/reset password → fenêtre d'attaque 7j.
2. TypeError sur OAuth-only login (5xx au lieu de 401).
3. URL reset password = Marveline pour tous les tenants → confirmation directe que `tenant_settings.frontend_url` n'est pas câblé.

Les frictions P1 sur les sessions (F302 quota, F303 perf, F304 cascade Redis) sont des dettes opérationnelles à payer avant scaling.

→ Module suivant : `11-rbac.md` (auth_role, auth_role_scope, auth_scope, Permission, Scope, ROLE_*).
