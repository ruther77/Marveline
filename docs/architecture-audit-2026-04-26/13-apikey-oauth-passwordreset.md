# Module 13 — API Key / OAuth / Password Reset

> **Phase B — Identité & Sécurité.** Audit des trois mécanismes d'authentification non-password : API keys (M2M), OAuth (Google/GitHub/Facebook), tokens password reset.
>
> **Forward-références purgées :**
> - F328 (mod. 11) — divergence Permission v2 vs Scope v3 (impact direct sur `_VALID_SCOPES` API key)
> - F371 (mod. 12) — `auth_roles.mfa_required` jamais lu (OAuth bypass MFA confirmé ici)
> - F84 (mod. 03) — rate limiter pas tenant-scoped (impact `ApiKey.rate_limit`)

---

## 1. Inventaire des fichiers lus intégralement

| Fichier | LoC | Rôle |
|---|---|---|
| `app/models/api_key.py` | 124 | `ApiKey` (M2M, SHA-256 hash, scopes ARRAY) |
| `app/models/account_oauth_identity.py` | 66 | `AccountOAuthIdentity` (lien account ↔ provider OAuth) |
| `app/models/password_reset_token.py` | 76 | `PasswordResetToken` (SHA-256 hash, TTL 1h, single-use) |
| `app/services/api_key.py` | 384 | CRUD + rotate + validate_key + cache Redis |
| `app/services/oauth_v2.py` | 395 | Service OAuth IAM v2 (avec tenant context) |
| `app/repositories/api_key.py` | 204 | Sync + Async repos |
| `app/repositories/password_reset_token.py` | 214 | Sync + Async repos (consume atomique) |
| `app/repositories/account_oauth_identity.py` | 59 | Async repo OAuth identities |
| `app/api/v1/endpoints/api_keys.py` | 131 | 6 endpoints REST CRUD |
| `app/api/v1/endpoints/oauth.py` | 428 | **Endpoints OAuth legacy actuellement routés** |
| `app/schemas/api_key.py` | 167 | 5 schémas Pydantic |

**Volume total** : ~2 250 LoC. Le service `oauth_v2.py` (395 LoC) **coexiste** avec `endpoints/oauth.py` (428 LoC) — duplication massive (cf. F406).

---

## 2. Architecture observée

```
┌─────────────────────────────────────────────────────────────────────┐
│  AUTHENTIFICATION M2M : API Key                                       │
│   Header X-API-Key: mk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx     │
│        │                                                              │
│        ▼                                                              │
│   ApiKeyService.validate_key(full_key) :                             │
│        SHA-256(full_key) ──► Redis cache (key_hash[:16] truncé)      │
│              │ miss                                                   │
│              ▼                                                        │
│        SELECT * FROM api_keys WHERE key_hash=:h AND is_active=TRUE   │
│        ──► check expires_at ──► update last_used_at + last_used_ip   │
│        ──► ApiKeyClient(tenant_id, scopes) injected as principal     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  AUTHENTIFICATION USER : OAuth 2.0 (Google / GitHub / Facebook)      │
│                                                                       │
│  TWO PARALLEL FLOWS COEXISTING (cf. F406) :                          │
│                                                                       │
│  Flow A — endpoints/oauth.py (LEGACY, actuellement routé) :         │
│   GET /oauth/{provider}/authorize ──► state Redis 5 min, PKCE Google │
│   POST /oauth/{provider}/callback :                                   │
│        consume_state ──► exchange_code ──► userinfo                  │
│        ──► _lookup_or_link_user (auto-link SANS email_verified !!!) │
│        ──► require unique active membership                           │
│        ──► _issue_oauth_tokens (mfa_verified=False, no MFA gate)     │
│                                                                       │
│  Flow B — services/oauth_v2.py (IAM v2, routé via /auth/v2/*) :     │
│   authorize(provider, tenant_id) ──► state inclut tenant_id          │
│   callback(...) ──► email_verified obligatoire ──► require_active    │
│        membership(account_id, tenant_id) ──► open AccountSession     │
│        ──► issue_tokens (mfa_verified=False, no MFA gate)            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  RESET PASSWORD : Email link + token single-use                      │
│   POST /accounts/forgot-password { email }                            │
│        ──► AccountService.forgot_password (mod. 10 §F294 sync mail)  │
│        ──► token_bytes(32), SHA-256 stocké, TTL 1h                   │
│        ──► email avec lien ?token=<32 bytes>&hash_in_db=SHA-256       │
│   POST /accounts/reset-password { token, new_password }               │
│        ──► consume(SHA256(token)) FOR UPDATE atomique                │
│        ──► update password (cf. F293 mod. 10 — sessions non révoqués)│
└─────────────────────────────────────────────────────────────────────┘
```

**Trois rails complètement disjoints** :
1. **API Key** : tenant-scoped, scopes ARRAY validés contre `Permission` v2 (pas Scope v3).
2. **OAuth** : compte-scoped global (`AccountOAuthIdentity` → `account_id`), avec membership unique requis.
3. **Password reset** : compte-scoped global (`PasswordResetToken.account_id`), pas de tenant context.

Asymétries majeures (cf. mod. 10) : Account global, Membership N:N, MFA par membership, OAuth par account, API key par tenant. **Aucun de ces flows ne consulte `auth_roles.mfa_required`** (cf. F371).

---

## 3. Frictions identifiées — module 13

> Compteur global cumulé (modules 01–12) ≈ 403 frictions.
> Le module 13 ouvre à **F404**.

### 3.1 P0 — Bloquant production

#### F404 — OAuth callback **ne vérifie pas MFA** (bypass complet du second facteur)

**Constat.** `endpoints/oauth.py:269-320` (`_issue_oauth_tokens`) appelle directement :
```python
session_id = await session_service.create_session(
    db=db, user_id=..., tenant_id=..., ...,
    mfa_verified=False,  # ← jamais True
)
access_token, refresh_token, expires_in = await token_service.issue_tokens(...)
```

`services/oauth_v2.py:386-393` (`_open_session_and_issue`) idem : pas d'appel à `mfa_service.is_mfa_enabled` ni à `create_mfa_session` avant d'émettre les tokens.

**Comparer avec `services/auth_v2.py:101-128`** (login email+password) qui force le flow MFA quand `mfa_enabled=True`.

**Conséquence** : un user qui a configuré TOTP + a un compte Google lié contourne le MFA en se connectant via Google. Un attacker qui obtient un compte Google compromis (réutilisation de password ailleurs, password breach) :
1. Se connecte sur Google (compte volé).
2. Clique "Login with Google" sur Marveline.
3. Le callback OAuth résout l'identité, ouvre une session **sans aucune demande de TOTP**.
4. Token JWT émis, MFA contourné.

C'est la **chaîne F371 + F404** : `mfa_required` du rôle pas lu + OAuth ne lit pas `is_mfa_enabled`. Double couche de sécurité absente.

**Action** : injecter le MFA gate dans `_issue_oauth_tokens` :
```python
if await mfa_service.is_mfa_enabled(db, account.id, tenant_id):
    return MFARequiredResult(mfa_session_token=...)
```
Et bloquer si `auth_roles.mfa_required` mais pas de device.

---

#### F405 — OAuth legacy `_lookup_or_link_user` **n'exige PAS `email_verified`** (auto-link aveugle)

**Constat.** `endpoints/oauth.py:225-248` (flow legacy actif) :
```python
if not account:
    accounts = (await db.execute(
        select(Account).where(
            Account.email == email.lower().strip(),
            Account.is_active.is_(True),
        ).with_for_update()
    )).scalars().all()
    ...
    account = accounts[0]
    db.add(AccountOAuthIdentity(
        account_id=account.id,
        provider=provider,
        provider_subject=oauth_id,
        email_at_provider=email,
    ))
```

**Aucune vérification que l'email a été vérifié par le provider**. Un attacker qui crée un compte Google "victim@gmail.com" non vérifié (Google ne le permet plus, mais GitHub/Facebook peuvent renvoyer un email non vérifié dans certaines conditions) peut auto-link son identité OAuth attacker au compte CaroCorp de la victime → next OAuth login = attacker takes over.

`services/oauth_v2.py:331-336` exige `email_verified` :
```python
if not email_verified:
    raise HTTPException(400, detail="Email non verifie par le provider OAuth — auto-link refuse")
```

Le commentaire `# P2-23 : auto-linking uniquement si email verifie par le provider` indique que le fix existe **dans la v2** mais pas dans la v1 actuellement routée.

**Conséquence** : flow legacy = auto-link avec email non vérifié → account takeover potentiel.

**Action** : porter le check `email_verified` dans `endpoints/oauth.py:_lookup_or_link_user`. **OU** retirer le routage legacy et basculer sur OAuthV2Service partout (cf. F406).

---

#### F406 — Deux flows OAuth complets coexistent (`oauth.py` + `oauth_v2.py`)

**Constat.** Routage `app/api/v1/__init__.py:59` :
```python
api_router.include_router(oauth.router)  # OAuth 2.0 (Google, GitHub, Facebook)
```

Et `endpoints/auth_v2.py:315, 344` :
```python
return await OAuthV2Service(db).authorize(provider=provider, tenant_id=tenant_id)
...
await OAuthV2Service(db).callback(provider, body.code, body.state, ip, ua, request_id)
```

→ **Les deux flows sont actifs simultanément**. Différences :

| Aspect | `oauth.py` (legacy) | `oauth_v2.py` (IAM v2) |
|---|---|---|
| Routage | `/oauth/{provider}/...` | `/auth/v2/oauth/...` |
| State Redis contient | `provider` + `code_verifier` | `provider` + `tenant_id` + `code_verifier` |
| Tenant resolution | Membership unique requis | `tenant_id` du state |
| Auto-link | **SANS** `email_verified` | **AVEC** `email_verified` (F405) |
| Returns | `UserCompat` | `Account` + `Membership` |
| Service used | endpoint inline 230 LoC | `OAuthV2Service` class 200 LoC |
| `_PROVIDERS` dict | dupliqué l. 44-70 | dupliqué l. 41-67 |
| `_exchange_code`, `_get_userinfo`, `_pkce_challenge` | dupliqués | dupliqués |

Duplication ~280 LoC de logique métier. Toute correction (F404, F405, ajout d'un provider) doit être faite **deux fois**, sinon drift.

**Conséquence** : le frontend peut appeler indifféremment l'un ou l'autre (selon les boutons). Un user qui se connecte via `/oauth/...` n'a pas de tenant_id explicite → ambiguïté sur le membership choisi (cf. l. 261-265 : 400 si plusieurs memberships).

**Action** : (a) supprimer `endpoints/oauth.py` et router uniquement `OAuthV2Service` ; (b) extraire `_PROVIDERS` + helpers dans `app/core/oauth_providers.py` mutualisé.

---

#### F407 — Validation API key scopes contre `Permission` v2 → API keys **bloquées sur tous les scopes v3**

**Constat.** `services/api_key.py:75-90` :
```python
def _validate_scopes(self, scopes: list[str]) -> None:
    valid_scopes = {p.value for p in Permission}  # ← v2 enum, ~40 valeurs
    invalid = [s for s in scopes if s not in valid_scopes]
    if invalid:
        raise HTTPException(400, detail=f"Scopes invalides: {invalid}")
```

`schemas/api_key.py:10` même validation :
```python
_VALID_SCOPES = {p.value for p in Permission}  # ← Permission, pas Scope
```

Or `Scope` enum (62 valeurs v3) contient des scopes qui n'existent pas dans `Permission` :
- `stock:read`, `stock:write`, `stock:adjust` (v2 utilise `inventory:*`)
- `restaurant:read`, `restaurant:write` (absent de Permission)
- `epicerie:read`, `epicerie:write` (absent de Permission)
- `loyalty:read`, `loyalty:write`, `loyalty:manage` (absent de Permission)
- `users:manage`, `users:delete`, `sessions:revoke`, `devices:read`, `devices:revoke`, `audit:verify`, `billing:*`, `config:*`, `reports:*`, `deposits:*` (absent de Permission)

**Conséquence concrète** : un admin qui veut créer une API key pour la caisse Épicerie doit lui donner `epicerie:read` → 400 "Scopes invalides". L'API key est **inutilisable** pour les modules V2 (Restaurant, Épicerie, Loyalty, Stock v3, Deposits, Billing, Reports). Combiné avec F328 (require_scope dans deps.py utilise `Scope` enum), l'API key qui passerait `inventory:read` serait acceptée par le validator… mais rejetée par `require_scope(Scope.STOCK_READ)` qui exige le nom v3.

**Pourquoi P0** : casse la valeur métier des API keys (M2M caisse, intégrations partenaires) sur tous les modules récents.

**Action** : remplacer `Permission` par `Scope` dans les deux validators (service + schema). Test d'invariant : `assert all(s.value in valid_for_api_key for s in Scope)`.

---

### 3.2 P1 — Forte friction architecturale

#### F408 — `PasswordResetTokenRepository.cleanup_expired(tenant_id)` réfère un attribut **non mappé**

**Constat.** `models/password_reset_token.py:22-23` :
```
IAM v2 : lié à account_id (global). Plus de tenant_id ni user_id.
Les colonnes DB user_id/tenant_id existent encore (nullable) jusqu'au DROP en Lot 8.
```

Le model **ne déclare PAS** `tenant_id` ni `user_id` comme `Mapped[...]`. Mais `repositories/password_reset_token.py:124, 196` :
```python
tokens = (
    self.db.query(PasswordResetToken)
    .filter(
        PasswordResetToken.tenant_id == tenant_id,  # ← AttributeError au runtime
        ...
```

**Conséquence** : `cleanup_expired` lève `AttributeError: type object 'PasswordResetToken' has no attribute 'tenant_id'` dès le premier appel. Code latent (probablement appelé par tâche Celery non encore déployée, ou maintenance manuelle). Quand on l'activera = crash immédiat.

**Action** : refactor en `cleanup_expired()` sans paramètre tenant (puisque tokens sont globaux IAM v2). Si on veut filtrer par tenant, le faire via `JOIN account.memberships`.

---

#### F409 — API key cache : `key_hash[:16]` (64 bits) au lieu du full hash

**Constat.** `services/api_key.py:343, 358, 374, 381` :
```python
cache_key = f"{RedisKeys.API_KEY_CACHE}{api_key.key_hash[:16]}"
```

SHA-256 tronqué à 16 chars hex = 64 bits. Probabilité de collision dans un tenant à 10 000 keys ≈ 10⁸ / 2⁶⁴ ≈ 5×10⁻¹². Marveline n'aura jamais 10 000 keys, donc collision quasi impossible.

**Mais** : conceptuellement faux. Si collision, une key compromise A peut être confondue avec une key valide B (cache hit retourne B). Aucune raison de tronquer (la clé Redis n'a pas de coût de longueur significatif).

**Action** : `cache_key = f"{RedisKeys.API_KEY_CACHE}{api_key.key_hash}"` (full hash 64 chars).

---

#### F410 — Cache négatif API key 60s = oracle de timing pour énumération

**Constat.** `services/api_key.py:370-376` :
```python
async def _set_cache_negative(self, key_hash: str) -> None:
    cache_key = f"{RedisKeys.API_KEY_CACHE}{key_hash[:16]}"
    await redis_client.client.setex(cache_key, 60, json.dumps({"_invalid": True}))
```

Un attacker qui essaie une key inconnue → cache miss DB lookup ~5 ms ; cache hit négatif (2ᵉ tentative dans la même fenêtre) ~0.5 ms. Différence de timing de 4-5 ms permet de **distinguer** "déjà testée" (cache neg) vs "première tentative" (DB lookup). Permet une énumération horodatée.

Pas critique car les keys sont 32 chars urlsafe (256 bits) — bruteforce impossible. Mais oracle gratuit pour l'attacker.

**Action** : timing-constant pour le path négatif (artificial delay) ou supprimer le cache négatif (DB lookup à chaque fois pour clés invalides — surface acceptable).

---

#### F411 — API key `update_last_used` : write DB par requête → contention row-level

**Constat.** `core/deps.py:570-575` (mod. 04) :
```python
api_key.last_used_at = datetime.now(timezone.utc)
api_key.last_used_ip = ip_address
api_key.usage_count = (api_key.usage_count or 0) + 1
await db.flush()
```

Chaque requête API authentifiée par key = `UPDATE api_keys SET last_used_at=..., usage_count=usage_count+1 WHERE id=...`. Pour une caisse à 10 req/s, c'est 10 UPDATE/s sur la même row → lock contention si plusieurs caisses partagent la même clé.

**Action** : batch via Redis (`HINCRBY apikey:stats:{id} usage_count 1`) flush DB toutes les 60s. Ou async fire-and-forget.

---

#### F412 — `ApiKey.rate_limit` colonne définie mais **jamais consultée** (cf. F84 mod. 03)

**Constat.** `models/api_key.py:60-65` colonne `rate_limit`, `schemas/api_key.py:39-43` exposée à création. Mais le rate limiter (mod. 03/04) ne lit **pas** cette valeur — il applique un cap global identique à toutes les clés du tenant. Promesse "Rate limiting independant par API key" (docstring `models/api_key.py:29`) non tenue.

**Action** : injecter `api_key.rate_limit` dans `RateLimitMiddleware.build_key` quand principal = ApiKeyClient.

---

#### F413 — Password reset `forgot_password` envoie email synchroniquement (cf. F294 mod. 10)

Confirmé. Aucun queue Celery.

---

#### F414 — Password reset `forgot_password` utilise `settings.FRONTEND_URL` global (cf. F295 mod. 10)

Confirmé. URL Marveline pour Splendid.

---

#### F415 — `reset_password` ne révoque pas les sessions actives (cf. F293 mod. 10)

Confirmé. 7 jours de drift avec ancien refresh.

---

#### F416 — OAuth callback : `audit_service.log_login` AVANT que la session soit créée + commit

**Constat.** `endpoints/oauth.py:280-298` :
```python
await audit_service.log_login(user_id=..., success=True, ...)
session_id = await session_service.create_session(...)
await db.commit()
```

L'audit log est créé puis `create_session` peut échouer (Redis down, contraintes) → audit committed en DB (après le commit final), mais session inexistante. Inversion d'ordre : on log "login success" avant que le login soit techniquement réussi.

**Action** : `log_login` après `create_session`, avant `issue_tokens`.

---

#### F417 — `OAuthV2Service.authorize(tenant_id)` accepte n'importe quel tenant_id sans vérification

**Constat.** `services/oauth_v2.py:205-239` :
```python
async def authorize(self, provider: str, tenant_id: int) -> dict:
    cfg = _require_provider_v2(provider)
    state = secrets.token_urlsafe(32)
    state_data: dict = {"provider": provider, "tenant_id": tenant_id}
    ...
```

Aucune vérification que `tenant_id` existe ou est actif. Un attacker peut générer une `auth_url` pour n'importe quel `tenant_id`. À la callback, le state retourne ce tenant_id → `MembershipService.require_active(account_id, tenant_id)` → 403 si membership inexistant. OK, pas d'escalation.

**Mais** : un attacker peut **énumérer** les tenant_id valides en observant la réponse (auth_url générée même pour tenant_id inexistant). Léger info disclosure.

**Action** : `await tenant_repo.exists(tenant_id)` avant de signer le state.

---

#### F418 — `oauth.py` `_PROVIDERS` et `oauth_v2.py` `_PROVIDERS_V2` divergent éventuellement

**Constat.** Cf. F406. Lignes 44-70 de `oauth.py` et 41-67 de `oauth_v2.py` : copie identique aujourd'hui, mais aucune contrainte. Si on ajoute `apple` dans v2 sans v1 → frontend `/oauth/providers` ne le liste pas, frontend `/auth/v2/oauth/...` ne fonctionne pas à 100%.

**Action** : extraire `app/core/oauth_providers.py` import unique.

---

#### F419 — `account_oauth_identity.email_at_provider` PII en clair

**Constat.** `models/account_oauth_identity.py:50-54` : `String(255)` pas chiffré. Cf. mod. 09 F-future + RGPD. Pour Google/GitHub/Facebook = même email que `accounts.email`, donc duplication, mais reste PII.

**Action** : chiffrer ou supprimer (snapshot informatif rarement consulté).

---

#### F420 — `AccountOAuthIdentity` sans `TimestampMixin` (`updated_at` manquant)

**Constat.** `models/account_oauth_identity.py:9` héritage `Base` seul. `linked_at` mappé manuellement. Si on re-link (changement provider_subject ?), pas de trace.

---

#### F421 — `AccountOAuthIdentity.provider` String(50) sans enum CHECK ni validation Pydantic

**Constat.** Aucun `CHECK (provider IN ('google', 'github', 'facebook'))`. Insertion `provider="GOOGLE"` (majuscule) ou `provider="apple"` (non implémenté) accepté. Drift silencieux.

**Action** : enum DB `oauth_provider_enum` ou `CHECK (provider IN (...))`.

---

#### F422 — OAuth `_lookup_or_link_user` (legacy) returns `UserCompat`, `oauth_v2._resolve_account` returns `Account` — type drift

**Constat.** Cf. F406. Deux signatures de retour différentes pour la même opération métier. Endpoints dépendants doivent connaître quel flow → couplage.

---

#### F423 — Aucun `logout` OAuth (token Google reste valide chez le provider)

**Constat.** Aucun endpoint `POST /oauth/{provider}/revoke`. Quand un user fait `POST /auth/logout`, sa session locale est révoquée mais Google garde le token actif jusqu'à expiration naturelle (~1h). L'attacker qui aurait volé le token Google reste connecté côté Google.

Pas P0 car la session locale est révoquée (l'attacker ne peut pas faire `Login with Google` sans repasser par Google qui a un token Google valide → mais Google ne demande plus le password = re-login transparent).

**Action** : appeler `revoke_token` du provider à logout (Google a un endpoint, GitHub, Facebook aussi).

---

#### F424 — `OAuthV2Service.authorize` ne vérifie pas que l'`account_id` (anonyme à ce stade) a un membership dans `tenant_id`

**Constat.** À l'`authorize`, on n'a pas encore l'account → on stocke `tenant_id` dans le state aveuglément. À la `callback`, on vérifie le membership. OK pour l'authentification, mais un user **sans membership** dans le tenant cible passe par le coût de l'aller-retour OAuth pour finir en 403.

UX dégradée, pas un bug sécu.

**Action** : (optionnel) demander login email d'abord pour vérifier membership avant authorize.

---

#### F425 — `_PROVIDERS["facebook"]` returns "name" non vérifié (`graph.facebook.com/me?fields=...,name`) sans check pseudo

Pas une faille mais un cas où l'identité Facebook peut être un pseudo non vérifié → `userinfo.get("name")` peut être un nickname.

---

### 3.3 P2 — Friction modérée

#### F426 — `ApiKey.created_by` BigInteger non FK (orphelin sur suppression admin)

**Constat.** `models/api_key.py:73-77` : `BigInteger nullable=False` sans FK. Commentaire l. 76 : "plain int depuis IAM v2 drop_legacy". Trace historique préservée en perdant l'intégrité référentielle.

`membership_id` (l. 80-86) ajouté ensuite avec FK + `ondelete=SET NULL`. Cohabitation : `created_by` (mort) + `membership_id` (vivant) — colonne morte à dropper.

**Action** : drop `created_by` après vérification que tous les `membership_id` sont peuplés.

---

#### F427 — `ApiKey.scopes` ARRAY(String(50)) sans contrainte de longueur de liste

**Constat.** Une API key peut avoir `scopes = ["x:y"] * 10000` → 10k strings. Probabilité faible mais surface DoS (chaque request revérifie `set(scopes)`).

**Action** : `CHECK (array_length(scopes, 1) <= 100)`.

---

#### F428 — `_get_from_cache` `except Exception: return None` → cache miss silencieux (FAIL-OPEN)

**Constat.** `services/api_key.py:351-353` :
```python
except Exception:
    logger.debug("Redis cache miss for API key (error)")
    return None
```

Aucune métrique, aucun warning. Si Redis down → cascade DB lookup pour chaque requête API → 5× plus de charge DB silencieuse.

**Action** : log WARNING + métrique Prometheus `api_key_cache_error_total`.

---

#### F429 — `OAuth.providers` endpoint sans rate limit (info disclosure mineure)

**Constat.** `endpoints/oauth.py:332-355` (`/oauth/providers`) sans auth, sans rate limit. Permet d'énumérer les providers actifs côté serveur. Info disclosure mineure.

---

#### F430 — `state_data` Redis JSON sans signature (pas HMAC)

**Constat.** `services/oauth_v2.py:235` et `endpoints/oauth.py:385` : `await redis_sec.store_oauth_state(state, state_data, ttl=300)`. Le `state` est un token aléatoire 32 bytes, mais `state_data` est juste JSON. Si attacker compromet Redis → peut modifier `tenant_id` du state pour rediriger un user vers un autre tenant.

Pas P0 car il faut compromettre Redis-SEC. Mais une signature HMAC ajoute une couche.

---

#### F431 — `KEY_PREFIX_MARKER = "mk_live_"` hardcodé dans le service (devrait être dans `constants/business.py` ou `constants/security.py`)

---

#### F432 — `REDIS_API_KEY_TTL = 300` dans le service (devrait être `Settings.API_KEY_CACHE_TTL`)

---

#### F433 — `password_reset_token.email` colonne en clair (PII)

**Constat.** `models/password_reset_token.py:53-57`. RGPD compatible (durée 1h) mais pourrait être omis (récupérable depuis `account.email`).

---

#### F434 — `PASSWORD_RESET_TTL_SECONDS = 3600` dans repository (devrait être `Settings`)

---

#### F435 — `ApiKey.expires_at` jamais nettoyé (no cleanup task)

Tokens expirés s'accumulent ad vitam.

---

#### F436 — `ApiKey.usage_count` BigInteger sans RAZ → lecture historique uniquement (pas analytics fenêtrée)

---

#### F437 — `prefix_exists` query non utilisée dans le service (dead method)

**Constat.** `repositories/api_key.py:102-121` (sync) + `:179-184` (async) : `prefix_exists(prefix, tenant_id)`. Aucun appel dans `services/api_key.py` ni endpoints. Code mort.

---

### 3.4 P3 — Cosmétique / dette légère

#### F438 — Comments `§04-AUTH-FLOWS §4.4` référence externe doc

#### F439 — `from datetime import datetime, timezone` import dans le corps de `update_last_used` (l. 134, 187)

#### F440 — `_get_github_email` URL extra dans `cfg["emails_url"]` — dépendance dure GitHub

#### F441 — `_pkce_challenge` (oauth.py) et `_pkce_challenge_v2` (oauth_v2.py) — fonction identique dupliquée

---

## 4. Synthèse module 13

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 4 | F404 (OAuth bypass MFA), F405 (auto-link sans email_verified legacy), F406 (deux flows OAuth), F407 (API key scopes Permission v2 only) |
| P1 | 18 | F408 → F425 |
| P2 | 12 | F426 → F437 |
| P3 | 4 | F438 → F441 |
| **Total module 13** | **38** | F404 → F441 |

**Compteur cumulé après module 13** : ≈ 403 + 38 = **441 frictions** (55 P0, 181 P1, 157 P2, 48 P3).

---

## 5. Forward-références à traiter

- **Module 99 (registry)** : la **chaîne F371 + F404** (rôle MFA jamais lu + OAuth bypass) est un vecteur d'évasion MFA majeur, à signaler en synthèse.
- **Module 14+** : pour chaque endpoint admin sensible, vérifier que les API keys ne peuvent pas y accéder via scope v2 (`Permission`). Tester `Scope.X` requis vs `Permission.X` attribué.
- **Module 21 (Sessions, à venir si non couvert mod. 10)** : confirmer le statut de `oauth.py` (legacy actif) vs `oauth_v2.py` (cible) — décision migration nécessaire.

---

## 6. Décision architecturale recommandée

> **Triptyque P0 immédiat** :
> 1. **Injecter MFA gate dans OAuth callback** (F404) — `if mfa_service.is_mfa_enabled(...) → MFARequiredResult` avant `_issue_oauth_tokens`. Sans ce fix, le MFA n'est qu'un théâtre pour les comptes OAuth-linked.
> 2. **Supprimer `endpoints/oauth.py` legacy** (F405 + F406) — bascule complète sur `OAuthV2Service`. Frontend mis à jour avec un seul endpoint canonique. Bonus : supprime ~280 LoC dupliquées.
> 3. **API keys : valider contre `Scope` enum v3** (F407) — sans ce fix, les API keys sont inutilisables sur Restaurant/Épicerie/Loyalty/Stock.
>
> **Refactor structurel** :
> - Extraire `app/core/oauth_providers.py` (mutualiser `_PROVIDERS`, `_pkce_challenge`, `_exchange_code`, `_get_userinfo`).
> - Drop `password_reset_tokens.tenant_id` colonne legacy + corriger `cleanup_expired` signature (F408).
> - Batch async API key `usage_count` via Redis HINCRBY (F411) — supprime contention DB.
> - Tester en CI : "API key avec scope `restaurant:read` créée → endpoint Restaurant accessible".
