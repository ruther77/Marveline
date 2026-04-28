# Architecture cible — refonte structurelle

> **Méthode** : intégrer les 1 154 frictions des 35 modules audités dans une conception qui les élimine **par classes de problèmes**, pas friction par friction. Construit en blocs cohérents validés ensemble.

---

## Décisions structurantes (validées)

| # | Décision | Choix | Conséquence |
|---|---|---|---|
| **Q1** | Ledger immutability | **Trigger DB** `BEFORE UPDATE/DELETE → RAISE` | Promesses code-only (commentaires "JAMAIS UPDATE") deviennent garanties DB. Couvre AuditLog, PointsLedger, RevenueLedger, PaymentLedger, EpicerieStockMovement, MouvementStockRestaurant, VenteLedger. |
| **Q2** | RLS PostgreSQL | **Oui** `USING (tenant_id = current_setting('app.tenant_id')::bigint)` | Filtre tenant enforced DB-side. Repository Python qui oublie le filtre = SELECT vide, plus jamais leak cross-tenant via repo bug. |
| **Q3** | Multi-pays / devise | **France métropole 12 mois** | TVA 20/10/5.5% restent, EUR partout. **Multi-tenant France maintenu** (DEVUP héberge N tenants par vertical : Marveline, Splendid, MassaCorp, futurs) : identité (issuer, SMTP, MFA name, branding) reste **tenant-scopée** — chaque tenant a sa propre signature. Concept "multi-brand intra-tenant" abandonné Bloc 7 Q43=B. La Réunion / outre-mer / Sénégal = sujet ultérieur. |
| **Q4** | Audit / outbox | **Outbox pattern** | `audit_outbox` insert dans la TX métier + worker async réplique vers `audit_log`. Plus de perte silencieuse. Pattern étendu à toute action "marquée comme faite" (relance.status='sent', etc.). |
| **Q5** | Sync repos | **Suppression** | `BaseRepository` async devient unique. Celery tasks portent `asyncio.run()` wrapper. F168 (cache cassé sync) éliminé par construction. |

---

# Bloc 1 — Foundations (modules 01-08)

> **Périmètre** : `app/core/`, `app/middleware/`, `app/models/base.py`, `app/repositories/base.py`, `app/constants/`, `app/schemas/base.py + common.py`. ~12 000 LoC, 232 frictions auditées (F1-F231 + F232-F254).

## 1.1 Patterns à éradiquer (8)

| # | Pattern | Modules | Fix structurel |
|---|---|---|---|
| P-01 | RLS contourné | 01, 02, 06 | Décisions Q1+Q2 → policies SQL natives |
| P-02 | Identité Marveline hardcodée | 01, 02, 07 | tenant_settings + tenant_brand lookup |
| P-03 | Cache cassé + secrets cachés | 01, 05, 06 | Q5 (sync supprimé) + `__cacheable__`/`__cache_excluded_fields__` |
| P-04 | Chaîne middlewares mal ordonnée | 03, 04 | RequestContext en outermost, JWT décodé 1× |
| P-05 | Multi-tenant invisible ops | 03, 04 | Labels `app_code` + bucket sur métriques + key Redis tenant-scopée |
| P-06 | Audit non-atomique | 01, 04 | Q4 → Outbox pattern |
| P-07 | Cycles imports résolus par lazy | 01, 02, 03, 06 | Découpage `core/auth/` + `core/storage/` + injection explicite |
| P-08 | Conventions partielles (58% adoption) | 05, 06, 08 | Linter custom au CI : tout modèle hérite TenantMixin si tenant-scopé, tout schema hérite BaseSchema |

## 1.2 Architecture cible

### 1.2.1 `app/core/` re-découpé

```
app/core/
├── config/
│   ├── __init__.py           # exports Settings agrégé
│   ├── security.py           # SecuritySettings (JWT keys, encryption, hash params)
│   ├── database.py           # DatabaseSettings (pool size, timeouts)
│   ├── redis.py              # RedisSettings (sec + cache URLs)
│   ├── auth_providers.py     # OAuth Google/GitHub/Facebook
│   ├── integrations.py       # Boxtal, Apple/Google Wallet, Sentry
│   └── app.py                # AppSettings (FRONTEND_URL, CORS_ORIGINS, DEBUG)
│
├── database/
│   ├── engines.py            # async_engine seul (Q5 : sync supprimé)
│   ├── session.py            # AsyncSessionLocal, get_async_db, get_async_db_context
│   ├── rls.py                # set_tenant_context() avec paramètre lié — F01 fixé
│   └── slow_query.py         # listener (constantes dans constants/limits.py)
│
├── auth/
│   ├── principal.py          # Principal Protocol, ApiKeyClient (UserCompat supprimé)
│   ├── dependencies.py       # get_current_user, get_current_principal, get_current_account
│   ├── authz.py              # require_scope (Permission/UserCompat supprimés)
│   ├── types.py              # Type aliases GÉNÉRÉS depuis Scope enum (boucle)
│   ├── jwt/
│   │   ├── encode.py         # create_access/refresh_token avec kid header
│   │   ├── decode.py         # decode via kid → key registry, audience required
│   │   ├── kms.py            # KMS-backed key loading + JWKS endpoint
│   │   └── client_binding.py # CBH 128 bits
│   └── password/
│       ├── hashing.py        # Argon2id+pepper (DUMMY_HASH lazy, F63 fixé)
│       ├── policy.py         # validate_password (un seul chemin, F64 fixé)
│       └── common.py         # COMMON_PASSWORDS chargé depuis fichier + brand_codes DB
│
├── storage/
│   ├── redis_sec_client.py   # AsyncRedis wrapper FAIL-CLOSED, 50 LoC
│   ├── redis_cache_client.py # AsyncRedis wrapper FAIL-OPEN, 30 LoC
│   └── stores/               # 1 fichier par domaine fonctionnel
│       ├── csrf_store.py
│       ├── refresh_token_store.py
│       ├── access_blacklist_store.py
│       ├── token_family_store.py
│       ├── session_store.py
│       ├── device_store.py
│       ├── brute_force_store.py
│       ├── credential_stuffing_store.py
│       ├── oauth_state_store.py
│       └── degradation_store.py
│   # Tous les stores prennent tenant_id en paramètre — F84/F208 fixés
│
├── permissions/
│   ├── scope.py              # Scope enum (~62 entrées) — Permission v2 supprimé
│   ├── role.py               # auth_role table-driven, ROLE_HIERARCHY DB-side
│   └── decorators.py         # require_scope, require_stepup
│
├── observability/
│   ├── logging.py            # SENSITIVE_FIELDS étendu (F85 fixé), exact match (F86 fixé)
│   ├── metrics.py            # avec labels app_code + tenant_bucket
│   ├── health.py             # check_postgres async, timeout 1s, Celery/SMTP/WG inclus
│   └── tracing.py            # OpenTelemetry stub (à activer Phase 2)
│
├── crypto/
│   ├── kms.py                # KMS_KEY_TOTP / KMS_KEY_ACCESS branchés (F48/F49 fixés)
│   ├── envelope.py           # encrypt_totp_secret avec key_version utilisé (F52 fixé)
│   └── validators.py         # XSS/SQL patterns RÉDUITS aux exacts (F58 fixé)
│
└── exceptions.py             # consomme constants/errors.py (F204 fixé), messages FR
```

**Ce qui disparaît** :
- `core/deps.py` (1066 LoC) → éclaté en `core/auth/`
- `core/redis.py` (831 LoC) → éclaté en `core/storage/`
- `core/health.py` → migré vers `core/observability/health.py` (refondu async + Celery/SMTP/WG inclus)
- `core/metrics.py` → migré vers `core/observability/metrics.py` (avec labels tenant_bucket)
- `core/logging.py` → migré vers `core/observability/logging.py`
- `core/slow_query.py` → migré vers `core/database/slow_query.py`
- `BaseRepository` sync → fusionné dans `AsyncBaseRepository` qui devient `BaseRepository`
- `cache_service` Pydantic + `CacheServiceSync` (jamais existé) → un seul cache async
- `UserCompat` (110 LoC) → consommateurs migrés vers `(Account, Membership)` direct ou `Principal` Protocol selon contexte

### 1.2.2 `app/models/base.py` enrichi

```python
class Base(DeclarativeBase):
    __cacheable__: ClassVar[bool] = True
    __cache_excluded_fields__: ClassVar[set[str]] = set()
    
    def to_dict(self, *, exclude_relations: bool = True, redact: bool = True) -> dict:
        # filtre __cache_excluded_fields__ par défaut → F150/F169 fixés
        ...
    
    def __repr__(self) -> str:
        # standard avec class_name + id + tenant_id si présent → F151 fixé
        ...

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class TenantMixin:
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="RESTRICT"),  # F148 fixé
        nullable=False,
        index=True,
    )
    
    @declared_attr
    def __table_args__(cls):
        # Ajoute automatiquement CHECK + RLS policy via migration helper
        return (
            CheckConstraint("tenant_id > 0", name=f"check_{cls.__tablename__}_tenant_positive"),
        )

class SoftDeleteMixin:
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="t", nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # F154 fixé
    deleted_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    def soft_delete(self, deleted_by_id: int) -> None: ...
    def restore(self) -> None: ...
```

**Modèles à secrets** : `__cacheable__ = False` (Account, MFADevice, WebAuthnCredential, ApiKey) → jamais cachés.

### 1.2.3 `app/repositories/base.py` simplifié

```python
class AbstractBaseRepository(Generic[T]):
    """Helpers partagés : filtres, cache key generation, tenant guard."""
    model_class: ClassVar[Type[T]]  # F186 fixé : plus de param redondant
    
    def _apply_filters(self, query, filters):
        # Opérateur inconnu → raise ValueError (F171 fixé)
        ...

class BaseRepository(AbstractBaseRepository[T]):  # async-only depuis Q5
    def __init__(self, db: AsyncSession): ...
    
    async def get_by_id(self, id: int, tenant_id: int, *, include_inactive: bool = False) -> Optional[T]:
        # 1. cache lookup (await)
        # 2. post-merge tenant verification (F170 porté ici depuis async)
        # 3. raise CRITICAL si mismatch
        ...
    
    async def update(self, obj: T) -> T:
        # lock anti-race 2s + invalidate cache
        ...
    
    async def hard_delete(self, id: int, tenant_id: int, *, force: bool = False) -> None:
        # Refuse si SoftDeleteMixin sauf force=True (F176 fixé)
        ...
```

### 1.2.4 Chaîne middlewares — ordre cible

```
Outermost (premier inbound)
  1. MetricsMiddleware             # mesure durée totale, lit request.state APRÈS call_next
  2. TimingMiddleware
  3. TrustedHostMiddleware
  4. CORSMiddleware                # StrictCORS fusionné (defense-in-depth supprimée)
  5. RequestContextMiddleware      ◄── DÉPLACÉ ICI (P-04 fixé)
       décode JWT 1× → request.state.jwt_claims
       résout API key (cache fingerprint Redis 60s)
       set_tenant_context(tenant_id)
  6. DegradedModeMiddleware        # MGET batch 4 clés + cache local 5s
  7. RateLimitMiddleware           # key tenant-scopée
  8. AppEnforcementMiddleware      # lit jwt_claims.app_code, plus de DB lookup
  9. CSRFProtectionMiddleware      # lit jwt_claims.sid
  10. SecurityHeadersMiddleware
  11. GZipMiddleware
  12. AuditOutboxMiddleware        # marque inception action, l'audit réel est en TX métier
Innermost (handler)
```

JWT décodé 1× au lieu de 6×. RLS context posé une seule fois. Audit en TX métier (Q4).

### 1.2.5 `app/constants/` — defaults seuls

Tout ce qui est tenant-spécifique migre en `tenant_settings` (DB) ou `tenant_brand` (DB) :

```
app/constants/business.py  →  reste : enums (UserRole, ReservationStatus, etc.)
                              SUPPRIME : DEPOSIT_RATE, ADVANCE_PAYMENT_PERCENT, TVA_RATE,
                                         HOURLY_RATE_*, LATE_RETURN_PENALTY_RATE, etc.
                                         (deviennent defaults dans seed migration tenant Marveline)

app/constants/loyalty.py   →  RÉDUIT (pas SUPPRIMÉ intégralement)
                              SUPPRIME : seuils tier (`SILVER_THRESHOLD`, etc.) → table loyalty_program (tenant-scoped)
                              SUPPRIME : `POINTS_EXPIRY_MONTHS`, etc. → tenant_settings.loyalty
                              CONSERVE : constantes anti-fraude globales (Bloc 3 §3.2.13) :
                                MAX_LOYALTY_MULTIPLIER = 3.0          (Q15=A)
                                LOYALTY_DAILY_EARN_CAP_POINTS = 5000  (Q16=B)
                                LOYALTY_MONTHLY_EARN_CAP_POINTS = 50000  (Q16=B)
                              Ces caps anti-fraude restent globaux DEVUP (pas négociables par tenant)

app/constants/security.py  →  reste : SecurityHeaders, BruteForceThresholds (defaults),
                                      Argon2Params, PasswordPolicy
                              SUPPRIME : MFAConfig.ISSUER_NAME (→ tenant_brand.display_name)
                              FIX : RedisKeys helpers callables uniformément avec tenant_id

app/constants/limits.py    →  ÉCLATÉ : PaginationLimits, SecurityLimits, TokenLimits
                              SUPPRIME doublons avec settings (F210 fixé)

app/constants/errors.py    →  ÉCLATÉ : 17 sous-classes par domaine
                              Source unique : exceptions.py consomme ErrorMessages
```

### 1.2.6 `app/schemas/base.py + common.py`

```python
# base.py
class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        # json_encoders Decimal SUPPRIMÉ (Pydantic 2 gère, F232 fixé)
    )

class CreateSchemaBase(BaseSchema): pass        # F238 ajouté
class UpdateSchemaBase(BaseSchema): pass        # idem
class ResponseSchemaBase(IDSchema, TimestampSchema): pass  # SANS tenant_id (F239 fixé)
class FullResponseSchema(IDSchema, TimestampSchema, TenantSchema, SoftDeleteSchema): pass

# common.py
class ErrorResponse(BaseSchema):
    # Aligné EXACTEMENT sur middleware/exception_handler.create_error_response (F233 fixé)
    success: bool = False
    error: str
    message: str
    detail: str | dict
    details: Optional[dict] = None
    errors: Optional[list[ErrorDetail]] = None
    request_id: Optional[str] = None

class PaginationParams(BaseSchema):  # plus BaseModel direct (F240 fixé)
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=Limits.DEFAULT_PAGE_SIZE, ge=1, le=Limits.MAX_PAGE_SIZE)
    # le=MAX en Field → 422 explicite, plus de silent cap (F241 fixé)
```

**Linter CI** : `assert all(issubclass(cls, BaseSchema) for cls in scan_app_schemas())`. Bloque toute PR avec un schema héritant de `BaseModel` direct.

## 1.3 Migration ordonnée

| Sprint | Périmètre | Tests requis |
|---|---|---|
| **B1.S1** (2 sem) | Q5 sync→async + Q1 triggers ledger immutability + F01 (RLS f-string) + F02 (API key set_tenant_context) | Tous tests existants verts + nouveau test "API key sans tenant context = repos retournent vide" + "UPDATE audit_logs raise" |
| **B1.S2** (2 sem) | Q2 RLS policies sur 62 tables + TenantMixin avec FK + types harmonisés (Integer→BigInteger sur 14 modèles) | Test "INSERT tenant_id=999 fails" + "session sans set_tenant_context = SELECT vide" |
| **B1.S3** (2 sem) | Q4 Outbox pattern + AuditMiddleware refondu + RequestContextMiddleware déplacé outermost | Test "mutation rollback → audit_outbox aussi rollback" + "JWT décodé 1×/req" |
| **B1.S4** (2 sem) | Stores Redis éclatés + auth/ découpé + UserCompat supprimé | Test régression auth complète + perf "JWT decode count ≤ 1" |
| **B1.S5** (2 sem) | constants/ ménage + schemas BaseSchema linter CI + métriques labels app_code | Test "ErrorResponse schema = middleware output" + dashboard Grafana par app_code |

**Total Bloc 1 : 10 semaines de dev senior**.

---

# Bloc 2 — Identité & Tenant (modules 09-13)

> **Périmètre** : `Tenant`, `TenantBrand`, `TenantSettings`, `TenantMembership`, `Account`, `AccountSession`, `AccountOAuthIdentity`, RBAC (`auth_roles`, `auth_scopes`, `Permission`/`Scope`), MFA/WebAuthn/PIN, API keys, OAuth, password reset. **187 frictions cumulées (F255-F441), 30 P0**.

## Décisions structurantes Bloc 2 (validées)

| # | Décision | Choix | Conséquence |
|---|---|---|---|
| **Q3 (rappel)** | Multi-pays | **France métropolitaine stricte** | TVA 20/10/5.5% standards FR. DOM/outre-mer/Sénégal = phase ultérieure. |
| **Q6** | Modèle auth | **`auth_factor` unifié par membership** | Suppression MFADevice / WebAuthnCredential / TrustedDevice + `pin_hash` global → table unique `auth_factor(membership_id, type='TOTP'\|'FIDO'\|'PIN', ...)`. Symétrie **multi-tenant** : un user avec `TenantMembership` sur 2 tenants distincts (ex: Marveline + Splendid post Q43=B) configure 2 jeux d'auth_factor séparés (un par membership). Migration data lourde. |
| **Q7** | `address`/`postal_code` Account | **Migrer vers Customer (tenant-scoped)** | Account ne porte plus que email + names + auth. Adresses tenant-scopées. RGPD : purge cascade par tenant naturelle. |
| **Q8** | OAuth legacy `oauth.py` | **Supprimer immédiatement** | Drop `endpoints/oauth.py` (~280 LoC), frontend migre vers `/auth/v2/oauth/*`. Élimine F405 (auto-link sans email_verified) + F406 (duplication). |
| **Q9** | `auth_roles` tenant-scoped | **6 rôles globaux fixes** | Pas de rôles custom par tenant. F348 accepté comme dette acceptable : DEVUP héberge des tenants partageant des rôles métier homogènes (admin / manager / staff / viewer / api / superadmin) — pas besoin de N rôles custom par tenant. Si besoin émerge avec un nouveau vertical (ex: `autour_de_table` avec rôles spécifiques), évolution table `auth_roles_per_vertical` plus tard. |
| **Q10** | RBAC fail strategy | **Fallback statique conservé** (FAIL-OPEN) | `ROLE_SCOPES_FALLBACK` reste comme safety net. F329 (DB jamais lue au login) fixé en passant `db` à `TokenService.issue_tokens` — DB devient bien la source de vérité quand disponible. |
| **Q11** | OAuth re-link auto | **Refuser, exiger unlink explicite** | Si `provider_subject` change pour un account déjà lié, raise `OAuthRelinkBlocked` au lieu de re-lier silencieusement. Anti-account-takeover. |

## Architecture cible Bloc 2

### 2.1 Provisioning atomique
`TenantService.provision()` crée en une seule transaction : `Tenant` + `TenantBrand` (palette obligatoire) + `TenantSettings` (defaults dispatch par `app_code`) + `TenantMembership` initial pour le `provisioned_by`. Outbox audit (Q4). **Résout F255-F258, F266, F267, F273**.

### 2.2 Table `verticals` — fin du hardcode 6 endroits
> **Renommé Bloc 7** : auparavant `apps` → maintenant `verticals` (sémantique alignée Bloc 7 §7.1).

```python
class Vertical(Base, TimestampMixin):
    code: Mapped[str] = primary_key  # 'location' | 'epicerie' | 'restaurant' | 'autour_de_table' | …
    jwt_audience_pattern: Mapped[str]  # ex: 'location-{tenant_id}'
    degraded_redis_key_prefix: Mapped[str]
    react_module_name: Mapped[str]   # frontend module à charger
    enabled: Mapped[bool] = True
```
`Tenant.vertical` devient FK `verticals(code)` (post-Bloc 7). `Tenant.app_code` reste UNIQUE per-instance (ex: `marveline`, `splendid`, `massacorp_epi`). `JWT_AUDIENCES`, `_APP_PREFIX_MAP`, `RateLimitScope` lus depuis `verticals` au boot. **Résout F257, F284**.

### 2.3 RBAC simplifié — Scope v3 unique
Suppressions :
- `Permission` enum v2 (40 valeurs) → `Scope` enum v3 seul (62 valeurs)
- `ROLE_HIERARCHY`, `ROLE_PERMISSIONS` v2
- `core/deps.require_permission`, `require_scope_user` variantes
- `app/models/user_role.py` + repo (legacy IAM v1, dead — F339)

Conservé :
- `ROLE_SCOPES_FALLBACK` (Q10=A) mais **utilisé uniquement comme safety net DB+Redis down**.
- `TokenService.issue_tokens(db: AsyncSession, ...)` — db obligatoire pour lire `auth_role_scopes`.

Ajouté :
- Table `auth_vertical_scopes(vertical_code FK, scope_name FK)` — un scope `restaurant:write` n'est attribuable qu'aux tenants `vertical='restaurant'`. Filtre à l'émission JWT. **Résout F331**. (Renommé Bloc 7 : auparavant `auth_app_scopes`.)
- `RBACService` classe (mod F346) regroupe `get_role_scopes`, `can_manage_role`, `invalidate_role_cache`.

Migration `INVENTORY → STOCK` (F328) : alias temporaire 6 mois pendant qu'on migre les endpoints.

#### Catalogue des Scopes v3 (62 entrées)

Source unique : `app/permissions/scope.py`. Liste structurée par domaine (référencée par §4.2.6, §4.2.7, §6.2.6, §6.2.13, §6.2.16) :

```python
class Scope(StrEnum):
    # Identity / Account / Session
    ACCOUNTS_READ = 'accounts:read'
    ACCOUNTS_WRITE = 'accounts:write'
    ACCOUNTS_DELETE = 'accounts:delete'
    SESSIONS_READ = 'sessions:read'
    SESSIONS_REVOKE = 'sessions:revoke'
    MFA_MANAGE = 'mfa:manage'
    
    # Customer (PII séparé)
    CUSTOMERS_READ = 'customers:read'
    CUSTOMERS_READ_PII = 'customers:read_pii'        # Bloc 4 §4.2.7
    CUSTOMERS_WRITE = 'customers:write'
    CUSTOMERS_DELETE = 'customers:delete'
    CUSTOMERS_IMPORT = 'customers:import'
    
    # Catalogue
    PRODUCTS_READ = 'products:read'                  # Bloc 4 §4.2.6
    PRODUCTS_WRITE = 'products:write'
    PRODUCTS_DELETE = 'products:delete'
    CATEGORIES_MANAGE = 'categories:manage'
    BUNDLES_MANAGE = 'bundles:manage'
    
    # Pricing
    PRICING_READ = 'pricing:read'                    # F533 fix
    PRICING_WRITE = 'pricing:write'
    
    # Stock & Inventory
    STOCK_READ = 'stock:read'                        # ex-INVENTORY (alias 6 mois)
    STOCK_WRITE = 'stock:write'
    STOCK_TRANSFER = 'stock:transfer'
    
    # Reservations / Devis (vertical='location')
    RESERVATIONS_READ = 'reservations:read'
    RESERVATIONS_WRITE = 'reservations:write'
    RESERVATIONS_CANCEL = 'reservations:cancel'
    DEVIS_READ = 'devis:read'
    DEVIS_WRITE = 'devis:write'
    DEVIS_CONVERT = 'devis:convert'
    
    # Invoice / Payment / Relance
    INVOICES_READ = 'invoices:read'
    INVOICES_WRITE = 'invoices:write'
    INVOICES_EMIT = 'invoices:emit'
    PAYMENTS_RECORD = 'payments:record'
    RELANCES_READ = 'relances:read'
    RELANCES_TRIGGER = 'relances:trigger'
    
    # Vente directe / POS (vertical='epicerie')
    VENTES_READ = 'ventes:read'
    VENTES_WRITE = 'ventes:write'
    VENTES_REFUND = 'ventes:refund'
    
    # Restaurant (vertical='restaurant')
    COMMANDES_READ = 'commandes:read'
    COMMANDES_WRITE = 'commandes:write'
    COMMANDES_PAY = 'commandes:pay'
    INSTANCES_LAUNCH = 'instances:launch'
    
    # Loyalty
    LOYALTY_READ = 'loyalty:read'
    LOYALTY_ADJUST = 'loyalty:adjust'
    
    # Supplier / Procurement
    SUPPLIERS_READ = 'suppliers:read'
    SUPPLIERS_WRITE = 'suppliers:write'
    SUPPLIER_ORDERS_RECEIVE = 'supplier_orders:receive'
    
    # Cross-cutting
    AUDIT_READ = 'audit:read'                        # Bloc 6 §6.2.6
    AUDIT_READ_PII = 'audit:read_pii'                # PII clear-text dans audit
    FEATURES_READ = 'features:read'
    FEATURES_WRITE = 'features:write'
    PRINTER_PRINT = 'printer:print'                  # Bloc 6 §6.2.13
    VPN_READ = 'vpn:read'
    VPN_WRITE = 'vpn:write'
    VPN_ADMIN = 'vpn:admin'
    EVENEMENTS_READ = 'evenements:read'
    EVENEMENTS_WRITE = 'evenements:write'
    
    # Admin / superadmin DEVUP
    ADMIN_READ = 'admin:read'                        # Bloc 6 §6.2.16
    ADMIN_TENANT_PROVISION = 'admin:tenant_provision'
    ADMIN_FEATURE_FLAGS = 'admin:feature_flags'
```

**Test invariant CI** `tools/check_scope_catalog.py` : tout `require_scope(X)` dans le code doit avoir un X défini dans cette enum. Aucune string libre.

### 2.4 MFA enforcement systémique
Décorateur `@require_recent_mfa_or_stepup` sur tous endpoints destructifs :
- `DELETE /mfa`, `DELETE /webauthn/credentials/{id}`, `DELETE /accounts/me`
- `PATCH /accounts/me/password`, `PATCH /accounts/me/email`
- `POST /admin/tenants/{id}/offboard`

OAuth callback ajoute le MFA gate (parité avec login email/password). `role.mfa_required` lu au login : si vrai mais pas de device → `MFASetupRequired`. PIN lockout réel (Redis-SEC INCR + EXPIRE 5min après 3 échecs). **Résout F365-F372, F385-F387**.

### 2.5 Sessions cascade revoke — helper unifié
```python
async def revoke_all_sessions_for_account_tenant(
    db, account_id, tenant_id, reason, *, except_device_id=None
) -> int:
    # 1. SQL : UPDATE account_sessions SET revoked_at = now()
    # 2. Redis-SEC : remove refresh JTIs + add access JTIs to blacklist
    # 3. Outbox audit : MASS_SESSION_REVOKE
```
Appelé par : `change_password` (sauf current_device), `reset_password` (toutes), `MembershipService.suspend/revoke`, `OAuth.relink` (si différent provider_subject — Q11). **Résout F259, F292, F293, F304**.

### 2.6 Identity per-tenant propagée (white-label)
> **Renommé Bloc 7** : "multi-brand" → "white-label per-tenant". Q43=B verrouille 1 tenant = 1 identité (pas de multi-brand intra-tenant).

- `RequestContextMiddleware` charge `tenant` (cache Redis 60s) → `request.state.tenant`.
- `AccountService.forgot_password(email, tenant_id)` lit `tenant.frontend_url` (NOT NULL après refonte). Email envoyé via Celery `EmailGateway` (cf. Bloc 3 §3.2.12).
- `WebAuthnService(db, tenant_id)` lit `tenant.frontend_url` pour `RP_ID` et `expected_origin`.
- `MFAConfig.ISSUER_NAME` supprimé → `tenant.brand_display_name` pour le label TOTP.
- Domaine DKIM/SPF par tenant : `tenant.brand_dkim_domain` (ex: `marveline.fr`, `splendid-events.fr`, `massacorp.fr`).
- **Résout F206, F286, F295, F368, F369**.

### 2.7 Modèle `auth_factor` unifié (Q6=B)
```python
class AuthFactor(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "auth_factors"
    id: BigInteger PK
    membership_id: BigInteger FK tenant_memberships ON DELETE CASCADE
    type: Enum('TOTP', 'FIDO', 'PIN')
    
    # TOTP
    encrypted_secret: bytes nullable
    totp_secret_nonce: bytes nullable
    totp_encrypted_dek: bytes nullable
    totp_key_version: str nullable
    recovery_codes_hash: JSON nullable
    
    # FIDO
    credential_id: bytes nullable
    public_key: bytes nullable
    sign_count: int nullable
    aaguid: UUID nullable
    
    # PIN
    pin_hash: str nullable
    pin_attempts: int default 0
    pin_locked_until: datetime nullable
    
    # Common
    label: str
    last_used_at: datetime nullable
    
    CHECK (
      (type='TOTP' AND encrypted_secret IS NOT NULL) OR
      (type='FIDO' AND credential_id IS NOT NULL) OR
      (type='PIN' AND pin_hash IS NOT NULL)
    )
```
Migration data : `MFADevice` → `auth_factor(type='TOTP')`, `WebAuthnCredential` (account → membership via membership unique) → `auth_factor(type='FIDO')`, `accounts.pin_hash` + `TrustedDevice` → `auth_factor(type='PIN')`. **Résout F375, F394, F395**.

### 2.8 Account allégé (Q7=B)
`Account` ne porte plus que :
- `id, external_id, email (citext)`, `hashed_password`, `first_name`, `last_name`, `is_active`, `password_change_required`, `created_at`, `updated_at`.

Supprimés :
- `address` → `Customer.address` (tenant-scoped, déjà existant — voir mod 14)
- `postal_code` → `Customer.postal_code`
- `pin_hash` → `auth_factor(type='PIN', membership_id=...)`

`Customer` devient le seul propriétaire des PII tenant-scopées. **Résout F299, F319 (RGPD anonymize cascade par tenant)**.

## 2.9 Migration ordonnée Bloc 2

| Sprint | Périmètre | Tests requis |
|---|---|---|
| **B2.S1** (1 sem) | Hotfixes : F255 (await async), F407 (API key Scope), F408 (cleanup_expired AttributeError), F370 (webauthn stepup key) | E2E `POST /admin/provision/degraded/enable` ; API key avec `epicerie:read` accède endpoint |
| **B2.S2** (2 sem) | Provisioning atomique + table `apps` + drop `endpoints/oauth.py` | `provision` crée tous les artifacts en 1 TX ; OAuth via `/auth/v2/oauth/*` uniquement |
| **B2.S3** (2 sem) | RBAC unifié : suppression Permission v2, `RBACService` classe, `auth_vertical_scopes` table (renommée Bloc 7), F329 fix (db param) | `Permission` enum supprimé compile ; user du tenant marveline (vertical=location) n'a pas `restaurant:*` dans JWT |
| **B2.S4** (2 sem) | MFA enforcement décorateur + sessions cascade revoke + white-label per-tenant identity (Q43=B) | `DELETE /mfa` sans recent stepup → 401 ; `change_password` révoque les autres sessions ; `forgot_password` tenant Splendid utilise URL `splendid-events.fr` (lookup `Tenant.frontend_url`) |
| **B2.S5** (3 sem) | `auth_factor` unifié + migration data + `Account` allégé | Migration : `MFADevice` rows → `auth_factor`, etc. ; `Account.address` colonne dropée après backfill `Customer.address` |

**Total Bloc 2 : 10 semaines**.

---

---

# Bloc 3 — Ledger & Money (modules 17, 18, 20, 21, 22, 23, 25)

> **Volume audité** : ~15 200 LoC, **~270 frictions, ~50 P0 estimés**.
> Domaines : Devis, Réservation, Acompte (Deposit), Facture/Paiement, Vente directe, Relance, Fidélité.
> **Constat fondamental** : aucun pattern transverse cohérent. Chaque domaine a réinventé son FSM, son ledger, sa capture TVA, son cancel-cascade. Le code suit une discipline orale (« promesse immutable ») sans enforcement DB.

## 3.1 Patterns transverses à éradiquer (validés par lecture)

| # | Pattern | Frictions | Conséquence observée |
|---|---|---|---|
| **TR-1** | FSM bypass systémique (mutation directe sans guard) | F558, F559, F601, F604, F672, F687, F729 | Tout statut peut être réécrit sans matrice ; aucun audit. Devis `accepted` qui repasse `pending` silencieusement. |
| **TR-2** | Race conditions sans `FOR UPDATE`/advisory lock | F559, F601, F792, F793, F794 | Ledger points incohérent si 2 commandes concurrentes (`balance_after` divergent), stock négatif possible. |
| **TR-3** | TVA hardcoded fallback `0.20` | F561, F698, F728 | Splendid Events (autre régime) → facture incorrecte. Capture TVA seulement dans Vente, jamais Devis ni Résa ligne. |
| **TR-4** | Audit logs absents sur opérations sensibles | F673, F685, F714, F722, F753, F805 | Auto-retain Deposit, adjust_points admin, add_charge → pas de trace. |
| **TR-5** | Cancel non-cascadé | F603, F620, F687 | Annuler une résa ne libère pas le stock, ne refund pas le deposit, ne génère pas la credit_note. |
| **TR-6** | Invoice immutability violée par `add_charge` | F697, F700 | Mute une facture émise — illégal fiscalement (France). |
| **TR-7** | Immutabilité « code-only » sans trigger DB | F715, F795 | Un admin psql peut altérer points_ledger / invoice sans laisser trace. |
| **TR-8** | Modèles dupliqués `app/models/finance/` | F715 | Deux sources de vérité Invoice — risque confusion ORM. |
| **TR-9** | `reference` UNIQUE global cross-tenant | F605 | RES-2026-00001 d'un tenant bloque le même numéro chez un autre tenant. Casse l'isolation. |
| **TR-10** | Pas d'`expire job` (devis, points, relance) | F562, F750, F796 | Devis `pending` éternels ; points jamais expirés ; relance marquée `sent` sans envoi email réel. |
| **TR-11** | `timedelta(days=30 * N)` au lieu de `relativedelta(months=N)` | F797 | Drift -5 j/an cumulé. |
| **TR-12** | `reserve_stock` manquant à conversion devis→résa | F558 | Devis convertis sans réservation effective de stock. |
| **TR-13** | Multipliers fidélité cumulatifs sans cap | F807 | VIP×1.5 × Flash×3 → ×4.5, anti-fraude inexistant. |
| **TR-14** | Pas de `PricingEngine` centralisé | F560 | Calcul prix réinventé dans Devis, Résa, Vente — divergences. |
| **TR-15** | Email outbound inexistant (relance fictive) | F750 | Relance `status='sent'` sans aucun envoi réel. |

## 3.2 Architecture cible — patterns canoniques

### 3.2.1 `FSM` helper class — toute transition tracée
```python
# app/core/fsm.py
class FSM(Generic[State]):
    transitions: dict[State, set[State]]  # défini par sous-classe
    
    @classmethod
    def assert_transition(cls, from_: State, to: State) -> None:
        if to not in cls.transitions.get(from_, set()):
            raise IllegalTransition(f"{from_} → {to} forbidden")
    
    @classmethod
    @asynccontextmanager
    async def transit(cls, db, entity, *, from_: State, to: State, actor_id: UUID, payload: dict):
        cls.assert_transition(from_, to)
        # advisory lock + UPDATE + audit outbox event en 1 TX
```
- Sous-classes : `DevisFSM`, `ReservationFSM`, `DepositFSM`, `InvoiceFSM`, `VenteFSM`, `RelanceFSM`.
- **CHECK constraint DB** sur la colonne `status` + **trigger BEFORE UPDATE** qui vérifie `OLD.status → NEW.status` est dans la matrice.
- **Résout** : TR-1 sur les 6 domaines.

### 3.2.2 Advisory locks systématiques sur ledgers et stock
- `pg_advisory_xact_lock(hashtext('member:' || member_id))` avant `credit_points`/`credit_revenue`.
- `SELECT ... FOR UPDATE` sur `stock_management` lors `reserve_stock`/`release_stock`.
- `SELECT ... FOR UPDATE` sur `devis` à conversion.
- **Counter atomique** : `UPDATE loyalty_members SET transaction_count = transaction_count + 1 WHERE id = :id` (jamais read-modify-write Python).
- **Résout** : TR-2.

### 3.2.3 `tva_rate_snapshot` NOT NULL sur toutes les lignes
Toute ligne facturable porte la TVA capturée à l'émission :
```python
class DevisLine(Base): tva_rate_snapshot: Mapped[Decimal]  # Numeric(5, 4) NOT NULL
class ReservationLine(Base): tva_rate_snapshot: Mapped[Decimal]
class VenteLine(Base): tva_rate_snapshot: Mapped[Decimal]
class InvoiceLine(Base): tva_rate_snapshot: Mapped[Decimal]
```
Plus aucun fallback `0.20`. Source : `Product.tva_rate_id` → `tva_rate.rate` au moment de l'ajout en ligne.
- **Résout** : TR-3.

### 3.2.4 `PricingEngine` centralisé
```python
# app/services/pricing/engine.py
class PricingEngine:
    def quote(self, lines: list[Line], discounts: list[Discount], tenant: Tenant) -> Quote:
        # Snapshot complet : prix HT, TVA, formule, discount cumulatif (additif, jamais multiplicatif)
        # Source unique pour Devis, Reservation, Vente
```
- Discount **additif** (somme des %), jamais multiplicatif (résout F565).
- Snapshot retourné = exactement ce qui est inscrit en ligne.
- **Résout** : TR-14.

### 3.2.5 Outbox + DB triggers immutabilité
```sql
CREATE TRIGGER points_ledger_immutable
  BEFORE UPDATE OR DELETE ON points_ledger
  FOR EACH ROW EXECUTE FUNCTION raise_immutable();

-- Idem : revenue_ledger, payment_ledger, invoice (après emission), invoice_line, vente
```
- `raise_immutable()` lève `RAISE EXCEPTION 'immutable_table'`.
- Combiné avec **Outbox** (Q4 verrouillé Bloc 1) : toute mutation FSM publie un event audit transactionnel.
- **Résout** : TR-4, TR-7.

### 3.2.6 Conversion Devis → Réservation atomique (Q12=A : Invoice émise immédiatement)
```python
async def convert_devis_to_reservation(devis_id, actor_id):
    async with db.begin():
        devis = await db.execute(select(Devis).where(...).with_for_update())
        DevisFSM.assert_transition(devis.status, 'converted')
        
        # 1. Lock stock + reserve avant tout
        await stock_service.reserve(reservation_id, lines, db)
        
        # 2. Insert Reservation (status='confirmed' selon Q12=A)
        resa = Reservation(devis_id=devis.id, status='confirmed', ...)
        # 3. Émettre Invoice IMMÉDIATEMENT (Q12=A : confirmed → invoice.status='emitted', pas draft)
        invoice = await invoice_service.create_emitted_from_reservation(resa, db)
        # 4. FSM transition + outbox audit
        await DevisFSM.transit(db, devis, from_=devis.status, to='converted', ...)
```
- **Q12=A verrouillé** : facture émise dès la signature du devis (pas à la livraison). Workflow paiement comptant à signature. Pour Vente directe : invoice émise à `paid` (différent flux). Cf. §3.6 Q12 pour rationale.
- **Résout** : TR-12.

### 3.2.7 Cancel cascade explicite
`ReservationCancelService.cancel(resa_id, reason)` orchestre dans 1 TX :
1. `ReservationFSM.transit('cancelled')`
2. `stock_service.release(resa_id)` (par reservation_id, cf. STOCK-RELEASE-BLIND-01)
3. `deposit_service.refund_or_retain(resa_id, policy)`
4. `invoice_service.create_credit_note(invoice_id, full=True)` si facture émise
5. Outbox event `ReservationCancelled` → relance email auto si acompte payé
- **Résout** : TR-5.

### 3.2.8 `Invoice` immutable post-émission, `add_charge` interdit
- `Invoice.status='emitted'` → trigger DB bloque tout UPDATE sur `total_*`, `lines`, `tva_*`.
- Modification = `CreditNote` annulant + nouvelle `Invoice`. Conforme article 289 CGI.
- Suppression endpoint `POST /invoices/{id}/charges` après migration.
- **Résout** : TR-6.

### 3.2.9 Modèle Invoice canonique unique
- Suppression complète `app/models/finance/` (duplicates).
- Source unique : `app/models/invoice.py`.
- Mise à jour des imports + script `tools/check_no_finance_legacy.py` en CI.
- **Résout** : TR-8.

### 3.2.10 `reference` UNIQUE per-tenant
- Migration : DROP `UNIQUE (reference)` → CREATE `UNIQUE (tenant_id, reference)` sur `reservation`, `devis`, `invoice`, `vente`.
- Générateur : `RES-{TENANT_PREFIX}-{YYYY}-{SEQ}` ou `RES-{YYYY}-{SEQ}` (séquence par tenant).
- **Résout** : TR-9.

### 3.2.11 Celery jobs ledger
| Task | Cadence | Action |
|---|---|---|
| `expire_devis_task` | hourly | `Devis.status='pending' AND expires_at < now()` → FSM `expired` |
| `expire_points_task` | daily 03:00 | Insert `PointsLedger(type='expire', amount=-X)` pour entries `expires_at < now()` ; respect immutability |
| `dunning_orchestrator_task` | daily 06:00 | Read `Relance(status='due')` → `EmailGateway.send()` → si 200 → `status='sent'` ; si fail → `status='failed'` retry |
| `loyalty_revenue_window_recompute` | daily 04:00 | Recalcule `current_tier` Marveline tiered (TR-glissante) |
- **Résout** : TR-10.

### 3.2.12 `EmailGateway` abstraction outbound
```python
class EmailGateway(Protocol):
    async def send(self, to: str, subject: str, body_html: str, tenant_id: int) -> EmailResult: ...

class PostmarkGateway(EmailGateway): ...  # Q18=A verrouillé
class SmtpGateway(EmailGateway): ...      # fallback / dev
```
- Injection DI via `Depends(get_email_gateway)`.
- Relance `status='sent'` **uniquement** après réponse OK gateway.
- White-label per-tenant : sender depuis `Tenant.brand_email_from` (lookup par `tenant_id`). Chaque tenant a sa propre signature DKIM/SPF (`tenant.brand_dkim_domain`). Q43=B : Marveline et Splendid sont 2 tenants distincts → 2 senders distincts (`noreply@marveline.fr`, `noreply@splendid-events.fr`). Pas de concept "brand" intra-tenant.
- **Résout** : TR-15.

### 3.2.13 Caps fidélité anti-fraude
- `MAX_LOYALTY_MULTIPLIER = 3.0` constante (Q15=A verrouillée).
- `LOYALTY_DAILY_EARN_CAP_POINTS = 5000` (Q16=B verrouillée).
- `LOYALTY_MONTHLY_EARN_CAP_POINTS = 50000` (Q16=B verrouillée).
- Service `LoyaltyEarnLimiter.check(member_id, requested)` avant `credit_points`.
- **Résout** : TR-13.

### 3.2.14 `relativedelta` partout
- Remplacement systématique `timedelta(days=30 * N)` → `relativedelta(months=N)`.
- Audit linter custom (ruff plugin) qui interdit `timedelta(days=30` dans `app/services/`.
- **Résout** : TR-11.

### 3.2.15 `LedgerEntryMixin` partagé
```python
class LedgerEntryMixin:
    """Mixin pour PointsLedger, RevenueLedger, PaymentLedger."""
    id: Mapped[UUID]
    tenant_id: Mapped[UUID]
    member_id: Mapped[UUID]  # ou customer_id selon
    entry_type: Mapped[str]
    amount: Mapped[int]            # cents (BigInteger) ou points (Integer)
    balance_after: Mapped[int]
    related_entity_type: Mapped[str | None]
    related_entity_id: Mapped[UUID | None]
    metadata_json: Mapped[dict]
    created_at: Mapped[datetime]
    actor_id: Mapped[UUID | None]
```
- Convention unique pour tout ledger : append-only, balance_after dénormalisé, advisory_lock_key dérivé de `member_id`/`customer_id`.

### 3.2.16 Préparation e-invoicing UE (France 2026 PDP)
Ajout colonnes nullables sur `Invoice` dès Sprint B3.S1 (préparation, pas activation) :
- `electronic_invoice_id: str | None` — ID PDP
- `peppol_id: str | None`
- `chorus_pro_id: str | None` (B2G)
- `e_invoice_status: enum('not_emitted', 'submitted', 'accepted', 'rejected') | None`
- **Verrouillé Q19=A** (cf. §3.6) : prep schéma maintenant, activation différée 2026-09-01 via feature flag `einvoicing_enabled`.

## 3.3 Architecture finale par domaine

| Domaine | Modules | Pattern appliqué |
|---|---|---|
| **Devis** | 17 | DevisFSM (9 états), PricingEngine, expire_devis_task, conversion atomique |
| **Reservation** | 18 | ReservationFSM (10 états), advisory lock, cancel cascade, reference per-tenant |
| **Deposit** | 20 | DepositFSM (NONE→HELD→RELEASED\|RETAINED), audit Outbox sur auto-retain |
| **Invoice/Payment** | 21 | InvoiceFSM (draft→emitted→paid\|cancelled), trigger immutable, CreditNote pour rectif, Payment append-only |
| **Vente directe** | 22 | VenteFSM (7 états), tva_rate_snapshot capturé, PaymentLedger via LedgerEntryMixin |
| **Relance** | 23 | RelanceFSM, EmailGateway réel, dunning_orchestrator_task |
| **Loyalty** | 25 | PointsLedger immutable trigger, advisory lock credit_*, caps anti-fraude, relativedelta, expire_points_task |

## 3.4 Migration ordonnée Bloc 3

| Sprint | Périmètre | Tests requis |
|---|---|---|
| **B3.S1** (1 sem) | Hotfixes : F750 (relance email), F792-F794 (advisory lock loyalty), F697 (interdiction add_charge), F605 (reference per-tenant), suppression `app/models/finance/` | Relance avec gateway mocké → 200 = `sent` ; 2 `credit_points` concurrents balance correct ; `add_charge` sur invoice émise → 409 |
| **B3.S2** (2 sem) | `FSM` helper class + DB triggers immutability + matrices CHECK status. Migration des 7 domaines vers FSM helper. | Tentative UPDATE sur `points_ledger` via psql → exception ; transition illégale Devis → 409 |
| **B3.S3** (2 sem) | `PricingEngine` + `tva_rate_snapshot` NOT NULL sur Devis/Resa/Vente/Invoice lines. Backfill historique. | Splendid avec TVA 0.10 → ligne portée correctement ; discount cumul additif vérifié |
| **B3.S4** (2 sem) | Conversion Devis→Résa atomique (reserve_stock + invoice draft) + Cancel cascade explicite + Deposit FSM | Cancel résa libère stock, refund deposit, génère credit_note ; conversion partielle rollback complet |
| **B3.S5** (2 sem) | Celery jobs : expire_devis, expire_points, dunning_orchestrator + caps fidélité + EmailGateway prod | Devis J+30 → expired ; points expirés rentrent en ledger ; cap journalier earn enforced |
| **B3.S6** (1 sem) | e-invoicing schema prep + suppression definitive duplicates legacy | Migration colonnes Peppol/ChorusPro nullables ; CI bloque imports `app/models/finance/` |

**Total Bloc 3 : 10 semaines**.

## 3.5 Questions à valider avant lock Bloc 3

| # | Question | Options | Recommandation |
|---|---|---|---|
| **Q12** | Émission `Invoice` à quel statut Reservation ? | A) `confirmed` (signature) — facture immédiate, paiement comptant<br>B) `delivered` (sortie matériel) — TVA exigible à livraison<br>C) Configurable par tenant | **B** pour Marveline (BtoC location, TVA exigible à la livraison) ; **A** pour Vente directe |
| **Q13** | Méthode de valorisation stock pour CMP (coût moyen pondéré) | A) **PMP** (recalcul à chaque entrée)<br>B) **FIFO** (sortie au plus ancien lot)<br>C) Standard cost (prix fixe par produit) | **A** pour épicerie (rotation rapide) ; **C** pour Marveline (location, pas de COGS) |
| **Q14** | Acompte à conversion devis→résa | A) Optionnel, défaut 0%<br>B) Obligatoire 30%<br>C) Configurable par tenant (`Tenant.deposit_policy`) | **C** pour souplesse per-tenant (chaque tenant a sa politique acompte) |
| **Q15** | Cap multiplier fidélité | A) 3.0<br>B) 5.0<br>C) 10.0 | **A** anti-fraude |
| **Q16** | Cap journalier `LOYALTY_DAILY_EARN_CAP_POINTS` | A) 1000 / 10000<br>B) 5000 / 50000<br>C) Pas de cap, monitoring seul | **B** |
| **Q17** | Délai expiration devis par défaut | A) J+15<br>B) J+30<br>C) J+60<br>D) Configurable par tenant | **D** défaut J+30 |
| **Q18** | EmailGateway provider production | A) Postmark (fiable, transac)<br>B) Sendgrid<br>C) AWS SES<br>D) SMTP custom (OVH) | **A** Postmark (déliverabilité B2B) |
| **Q19** | e-invoicing UE (France 2026 — gros B2B sept. 2026, PME 2027) | A) Schema prep maintenant (colonnes nullables)<br>B) Attendre PDP final 2026<br>C) Skip (pas concerné si <facturation B2B) | **A** prep maintenant, activation 2026 |
| **Q20** | Multi-monnaie | A) EUR strict (lock Decimal)<br>B) Schema multi-currency dès maintenant<br>C) Modal selon tenant | **A** France métropole stricte (cf. Bloc 1 Q3) |

## 3.6 Décisions verrouillées Bloc 3 (2026-04-27)

| # | Réponse | Conséquence architecture |
|---|---|---|
| **Q12** | **A** — émission Invoice à `confirmed` (signature) **[Note revirement vs reco initiale B]** | Conversion Devis→Résa atomique : `reserve_stock` + `Reservation(status='confirmed')` + `Invoice(status='emitted')` en 1 TX. Paiement comptant à signature. **Vente directe** : invoice émise à `paid`. Section 3.2.6 mise à jour. **Note revirement** : la reco initiale était B (`delivered` / TVA exigible à livraison cohérent BtoC location). Le user a choisi A pour **simplification flux paiements** : émission à signature unifie épicerie/restaurant/location sur un seul modèle. Pour Marveline, l'exigibilité TVA reste OK car émission ≠ encaissement (la facture peut être émise sans paiement immédiat, l'exigibilité TVA suit le paiement encaissé pour les services). |
| **Q13** | **A** — PMP partout (épicerie + Marveline) | `inventory_movement` porte `unit_cost_at_entry_cents` ; `stock_management.weighted_avg_cost_cents` recalculé `WAC_new = (qty_old × WAC_old + qty_in × cost_in) / (qty_old + qty_in)`. Pour Marveline, le `unit_cost` représente le coût d'amortissement par usage (utilisé dans rapport rentabilité, pas dans facturation client). |
| **Q14** | **C avec défaut acompte ON** — `Customer.requires_deposit` boolean (défaut `true`) overridable par client | Modèle : `Customer.requires_deposit: bool = True`, `Customer.deposit_override_pct: Decimal | None`. Service `DepositPolicyService.resolve(customer, tenant) -> Decimal` retourne le % à exiger (0 si `requires_deposit=False`, sinon `deposit_override_pct ?? Tenant.default_deposit_pct ?? 30%`). UI Marveline : checkbox "Client régulier — pas d'acompte" sur fiche Customer. |
| **Q15** | **A** — `MAX_LOYALTY_MULTIPLIER = 3.0` | Constante en `app/constants/loyalty.py`. Service clamp le multiplier final. |
| **Q16** | **B** — 5000 / jour, 50000 / mois | Constantes `LOYALTY_DAILY_EARN_CAP_POINTS = 5000`, `LOYALTY_MONTHLY_EARN_CAP_POINTS = 50000`. `LoyaltyEarnLimiter` consulte `points_ledger` sur fenêtre. |
| **Q17** | **D** — Configurable par tenant, défaut J+30 | `Tenant.devis_default_expiry_days: int = 30`. Override par devis : `Devis.expires_at` modifiable jusqu'à émission. Task `expire_devis_task` lit `expires_at`. |
| **Q18** | **A** — Postmark | Implémentation `PostmarkGateway`. `Tenant.postmark_server_token` stocké chiffré (KMS). **Domaines DKIM/SPF par tenant** (1 tenant = 1 domaine, post Q43=B) : ex. `marveline.fr` (tenant marveline), `splendid-events.fr` (tenant splendid), `massacorp.fr` (tenants massacorp_epi + massacorp_resto). Configurés via `Tenant.brand_dkim_domain`. |
| **Q19** | **A** — Schema e-invoicing préparé maintenant | Sprint B3.S6 ajoute colonnes nullables. Activation différée à 2026-09-01 (PME). Service stub `EInvoicingService` no-op tant que `feature_flag.einvoicing_enabled=False`. |
| **Q20** | **A** — EUR strict | Pas de colonne `currency` ajoutée. Decimal partout. Vérifié cohérent avec Bloc 1 Q3 (France métropole). |

**Bloc 3 verrouillé. Total : 10 semaines de migration, 7 domaines convergent vers patterns canoniques (FSM helper + DB triggers + Outbox + ledger mixin + PricingEngine + EmailGateway).**

---

---

# Bloc 4 — Catalogue & Stock (modules 14, 15, 16, 19, 24, 26)

> **Volume audité** : ~14 540 LoC, **~195 frictions, ~31 P0 estimés**.
> Domaines : Customer, Product/Variant/Bundle/Category, Pricing, Inventory/StockItem, Évenements/Incidents, Supplier.
> **Constat fondamental** : le catalogue est cassé sur 3 axes simultanés : (a) catégorie schizophrène (string CHECK + table Category orpheline), (b) stock à 3 sources de vérité contradictoires, (c) catalogue mono-brand impossible à éclater pour Splendid. La PricingEngine ment à la simulation. Le moteur de stock physique (StockItem) n'a pas de FSM gardée. Patterns Bloc 3 (FSM helper, advisory locks, audit Outbox, EmailGateway) directement réapplicables.

## 4.1 Patterns transverses à éradiquer (au-delà des Bloc 3)

| # | Pattern | Frictions | Conséquence |
|---|---|---|---|
| **TR-16** | Catégorie schizophrène : `Product.category String CHECK 20` + table `Category` orpheline jamais référencée | F485, F489 | ~600 LoC code mort. Multi-app bloqué : ajouter une catégorie Restaurant/Épicerie = migration Alembic + CHECK redo. |
| **TR-17** | Stock à 3 sources de vérité (`Product.available_quantity` denorm + `SUM(variants)` sync + `stock_items`) | F497, F498 | Drift garanti. Marquer 5 stock_items en damaged ne décrémente pas `Product.available_quantity`. |
| **TR-18** | `Product.tva_rate float default 0.20` (Marveline-spécifique stocké par produit) | F487, F509 | Restaurant 10% / Épicerie 5,5% = produit créé avec 20% par défaut → facture invalide. Float = perte précision. |
| **TR-19** | RBAC contourné sur 5 endpoints `GET /products*` (`get_current_user` au lieu de `require_scope`) | F486 | User avec uniquement `customers:read` accède au catalogue intégral. Avec API key (F407) effet amplifié. |
| **TR-20** | Pas de `brand_code` sur catalogue (Product/Bundle/Category) | F488, F514 | Marveline et Splendid dans même tenant → catalogues mélangés impossibles à séparer. |
| **TR-21** | PricingEngine `÷100` vs `/pricing/simulate` `÷10000` + cumul vs first | F530, F532 | Admin simule -10%, devis applique -100×. Catastrophe facturation. |
| **TR-22** | StockItem FSM non gardée : `transition_status` accepte n'importe quelle valeur | F640, F642 | `damaged → reserved` silencieux ; `retired → available` possible. |
| **TR-23** | `release_n(reservation_id=None)` libère aveuglément items d'autres résa | F641 | BUG-FIX 2026-04-25 partiel : signature accepte toujours None. |
| **TR-24** | `event_id Integer nullable sans FK` (table `evenements` existe pourtant mod 24) | F644, F652 | Reference orpheline. |
| **TR-25** | `Mapped[str]` couplé `DateTime(timezone=True)` (annotation typing fausse) | F648, F649, F771 | mypy/IDE crash sur `scheduled_date.date()`. Récurrent 3 modules. |
| **TR-26** | PII non chiffré : `notes`, `contact_name`, `description`, `address` Text en clair | F454, F651, F667, F779, F786, F832, F841 | RGPD : un user `customers:read` voit allergies, anniversaires, références familiales en clair. |
| **TR-27** | Pas de UNIQUE `reference` per-tenant sur Supplier/SupplierOrder/Evenement | F767, F826, F827 | Doublons silencieux. |
| **TR-28** | Pas de `CHECK (qty_received + qty_damaged + qty_missing ≤ qty_ordered)` | F829 | Bilans absurdes possibles à la réception. |
| **TR-29** | Auto-sync stock après réception fournisseur ABSENT (commentaire mensonger) | F830 | Réception physique ≠ stock système. |
| **TR-30** | RFM dupliqué 3× (endpoints/customers.py:173, 251, 331) | F443 | Drift segmentation = email envoyé à mauvaise cohorte. |
| **TR-31** | CSV import commit/ligne (10 000 lignes = 10 000 TX) | F446 | 30 min sur RDS, HTTP timeout. |
| **TR-32** | `email_exists`/`sku_exists` filtre soft-deleted vs UNIQUE strict DB | F447, F501 | IntegrityError 500 au lieu de 409 propre. |
| **TR-33** | `Product.requires_advance_booking_days` par produit (devrait être par catégorie) | F496 | "90 pour nappages, 0 sinon" dupliqué sur N rows. |
| **TR-34** | Bundle : pas de `check_availability(qty)` ni `bundle_unit_price_cents` | F500, F510 | Bundle "Mariage 100 personnes" réservable même si 30 verres manquent. Facturation détaillée impossible. |
| **TR-35** | Hiérarchie Category : pas de cycle prevention, pas de depth max | F493, F494 | Boucle parent_id possible → stack overflow. |
| **TR-36** | Audit log absent sur `delete_*` partout | F456, F522, F541, F774, F835 | Pattern récurrent : aucune action destructive tracée. |
| **TR-37** | `condition` Product (4 valeurs `neuf/bon/use/hors_service`) ≠ MovementItem (4 valeurs `perfect/good/damaged/missing`) | F495, F650 | Vocabulaire divergent inter-modules. Typo `'use'` (verb anglais) historique. |
| **TR-38** | Send email synchrone `notification_service.send_plain_email` (cf. F294, F442) | F442, F480 | Couvert Bloc 3 §3.2.12 + Bloc 6 §6.2.1 via `EmailGateway` Postmark. **Périmètre inclut** : `send_rfm_campaign`, `forgot_password`, `send_supplier_order_confirmation`, `send_reservation_confirmed`, et toute campagne RFM. Toutes les voies email convergent vers le gateway unique. |

## 4.2 Architecture cible — patterns canoniques

### 4.2.1 `Category` devient FK obligatoire de `Product` (drop string CHECK)
```python
class Category(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "categories"
    id: Mapped[int]
    tenant_id: Mapped[int]
    parent_id: Mapped[int | None]   # FK self ondelete=SET NULL
    code: Mapped[str]               # canonical lower_snake (ex: 'assiettes')
    name: Mapped[str]               # libellé i18n
    depth: Mapped[int]              # 0..5, calculé par trigger
    tva_rate: Mapped[Decimal]       # Numeric(5,4) — TR-18 résout F487
    advance_booking_days: Mapped[int] = 0  # ex-F496 sur Product → ici
    cleaning_fee_cents_default: Mapped[int | None]
    brand_code: Mapped[str | None]  # NULL = toutes brands (TR-20)
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'code', name='uq_categories_tenant_code'),
        CheckConstraint('depth <= 5', name='ck_categories_depth_max'),
    )

class Product(Base, ...):
    category_id: Mapped[int]   # NOT NULL après backfill
    # tva_rate, advance_booking_days, default cleaning_fee : DROP, dérivés Category
```
- **Trigger BEFORE INSERT/UPDATE** sur `categories` : refus si introduit cycle (parcours récursif `WITH RECURSIVE`).
- **Migration** : seed Category avec les 20 valeurs Marveline existantes (`code='assiettes'`, `tva_rate=0.20`, etc.) ; pour chaque `Product` lookup `category_id` depuis sa string ; après backfill, `ALTER TABLE products DROP COLUMN category, DROP CONSTRAINT check_product_category_valid` + nouveau `category_id NOT NULL`.
- **Code mort supprimé** : ~600 LoC `services/category.py` deviennent vivants. Aucun supprimé, juste cohérent.
- **Résout** : TR-16, TR-18, TR-33.

### 4.2.2 `StockItem` source unique de vérité, vue matérialisée pour la quantité
```sql
CREATE MATERIALIZED VIEW product_stock_view AS
SELECT
    si.tenant_id, si.product_id, si.variant_id,
    COUNT(*) FILTER (WHERE si.status = 'available')                 AS available,
    COUNT(*) FILTER (WHERE si.status = 'reserved')                  AS reserved,
    COUNT(*) FILTER (WHERE si.status IN ('on_location'))            AS on_location,
    COUNT(*) FILTER (WHERE si.status IN ('damaged', 'in_repair'))   AS unavailable,
    COUNT(*) FILTER (WHERE si.status != 'retired')                  AS total_active
FROM stock_items si
WHERE si.retired = FALSE
GROUP BY si.tenant_id, si.product_id, si.variant_id;

CREATE UNIQUE INDEX ON product_stock_view (tenant_id, product_id, variant_id);
```
- **REFRESH MATERIALIZED VIEW CONCURRENTLY** sur trigger AFTER INSERT/UPDATE/DELETE de `stock_items` (debounced 5 sec via Redis lock).
- Drop colonnes `Product.available_quantity`, `Product.stock_quantity`, `ProductVariant.available_quantity`, `ProductVariant.stock_quantity`.
- Drop fonction `sync_available_from_variants` complète.
- `Product.available_quantity` exposé en API via `selectinload(Product.stock_view)` (vue lue, jamais écrite).
- **Résout** : TR-17.

### 4.2.3 `StockItemFSM` (cohérent FSM helper Bloc 3)
```python
class StockItemFSM(FSM[str]):
    transitions = {
        'available':   {'reserved', 'damaged', 'in_repair', 'retired'},
        'reserved':    {'available', 'on_location', 'damaged'},
        'on_location': {'available', 'damaged'},
        'damaged':     {'in_repair', 'retired'},
        'in_repair':   {'available', 'retired'},
        'retired':     set(),  # terminal
    }
```
- `transition_n(items, from_, to_, reservation_id, actor_id)` — `reservation_id` **NOT NULL** côté Python (ValueError si None).
- `release_n(reservation_id=...)` **mandatory positional**.
- CHECK constraint DB sur `stock_items.status` + trigger BEFORE UPDATE qui valide `OLD.status → NEW.status` dans la matrice.
- **Résout** : TR-22, TR-23.

### 4.2.4 ~~`brand_code` sur tout le catalogue~~ **[OBSOLÈTE Bloc 7 — Q43=B verrouille 2 tenants distincts Marveline/Splendid]**

> **REVU 2026-04-27 — drop intégral suite Q43=B.** Cette section décrivait un mécanisme `brand_code` (NULL = toutes brands) pour partager le catalogue entre Marveline et Splendid au sein d'un même tenant. Or **Q43=B verrouille 2 tenants distincts** : Marveline et Splendid ont chacun leur propre tenant et leur propre catalogue. Le concept `brand_code` Catalogue n'a plus de sens.
>
> **À supprimer du schema/code** :
> - Colonnes `Product.brand_code`, `Category.brand_code`, `Bundle.brand_code`, `ProductCollection.brand_code`.
> - Colonne `Tenant.is_multi_brand` (concept de multi-brand intra-tenant).
> - Header frontend `X-Brand-Code` (drop du middleware).
> - Filtres repository `WHERE brand_code IS NULL OR brand_code = :current_brand`.
>
> **Remplacement** : chaque tenant possède son catalogue propre (cohérent Bloc 5 Q29=A — référentiel ETL split per-tenant). Si Marveline et Splendid veulent partager des templates produits, mécanisme `catalogue_shared_template` cross-tenant en read-only seed (cf. §7.2 Bloc 7).
>
> **Migration** : ajoutée Sprint **B7.S2** (1 sem) — drop colonnes + cleanup endpoints + tests CI invariant `aucun brand_code`.
>
> ~~**Résout** : TR-20.~~ — TR-20 réinterprété par Bloc 7 (Q43=B).

### 4.2.5 `PricingEngine` unique (fusion engine + simulate)

> **Note nommage** : harmonisation Bloc 3 §3.2.4. Nom canonique = `PricingEngine` (cohérent avec le code source `services/pricing_engine.py` actuel). Le terme `PricingService` est abandonné.

- Fusionner `services/pricing_engine.py` + endpoints `/pricing/simulate` derrière une seule classe `PricingEngine.calculate(lines, customer, event_date) -> PricingResult`.
- `discount_pct: Numeric(5,4)` (ex: `0.10` pour 10%) — convention unique, pas `÷100` ni `÷10000`. Migration backfill : convertir Integer existant.
- Enum DB natif `pricing_rule_type` (`flat | per_day | tiered | volume | seasonal | custom`) + `pricing_applies_to` (`product | category | all`).
- Modèle d'application : **cumul additif** des règles matchant (cohérent Bloc 3 §3.2.4 + discount cumul additif F565). `simulate` retourne le même résultat que `apply`.
- CHECK `valid_from <= valid_to` ; CHECK `discount_pct BETWEEN 0 AND 1`.
- `applies_to='category'` câble enfin sur `category_id` FK (TR-16 résout TR-21).
- Endpoint `/pricing/simulate` → `Scope.PRICING_READ` (pas WRITE — F533).
- Cache Redis 5 min sur `_get_active_rules(tenant_id)` — clé per-tenant (plus de `brand_code` après Bloc 7).
- **Résout** : TR-21.

### 4.2.6 `require_scope` sur tous les endpoints catalogue
- Remplacement systématique des 5 occurrences `Depends(get_current_user)` → `require_scope(Scope.PRODUCTS_READ)`.
- Test invariant CI `tools/check_endpoint_scopes.py` qui parse l'AST et garantit que tout `@router.{get,post,patch,delete}` a un `Depends(require_scope(...))` (sauf whitelist `/health`, `/metrics` — couvert Bloc 6).
- **Résout** : TR-19.

### 4.2.7 PII chiffrement systématique
- `EncryptedField(KMSContext)` sur `Customer.notes`, `Supplier.notes`, `Supplier.contact_name`, `EventIncident.description`, `Evenement.notes`, `MovementItem.condition_notes`, `StockItem.notes`.
- Décryptage automatique via `Mapped[str]` accessor (transparent ORM-side).
- Scope séparé `customers:read_pii` requis pour les endpoints qui exposent `notes`.
- Migration : backfill envelope encryption sur les rows existantes (script Celery `migrate_pii_encryption_task`).
- **Résout** : TR-26.

### 4.2.8 `reference` UNIQUE per-tenant sur tous les domaines (étend TR-9 Bloc 3)
- `Supplier.code UNIQUE (tenant_id, code)`, `SupplierOrder.reference UNIQUE (tenant_id, reference)`, `Evenement.reference UNIQUE (tenant_id, reference)`, `EventIncident.reference UNIQUE (tenant_id, reference)`.
- Format unifié : `{PREFIX}-{YYYY}-{SEQ}` avec séquence per-tenant (`reservation_seq`, `evenement_seq`, etc.).
- **Résout** : TR-27.

### 4.2.9 SupplierOrder workflow correct (CHECK + trigger sync stock)
```sql
ALTER TABLE supplier_order_receipt_lines ADD CONSTRAINT
  ck_qty_consistency CHECK (
    qty_received + qty_damaged + qty_missing <= qty_ordered_for_line
  );
```
- Trigger `AFTER INSERT ON supplier_order_receipt_lines` :
  1. Crée `inventory_movement(type='supplier_receipt', ...)`.
  2. Insert N rows `stock_items(status='available')` (qty_received).
  3. Insert M rows `stock_items(status='damaged')` (qty_damaged).
  4. Outbox event `SupplierReceiptCompleted`.
- **Résout** : TR-28, TR-29.

### 4.2.10 RFMService extrait + view matérialisée
```python
# app/services/rfm.py
class RFMService:
    @staticmethod
    def compute_segment(recency_days: int, frequency: int, monetary_cents: int) -> RFMSegment:
        # Logique unique extraite des 3 lieux dupliqués
```
- Constantes `RFM_CHAMPION_RECENCY=30`, etc. dans `app/constants/business.py`.
- Enum `RFMSegment` (StrEnum) partagé schemas.
- Vue matérialisée `customer_rfm_view` rafraîchie quotidiennement (`refresh_rfm_view_task` Celery, 03:30).
- Test invariant CI : "endpoint `/customers/rfm` et `/customers/{id}/rfm-profile` retournent le même segment pour le même customer".
- **Résout** : TR-30.

### 4.2.11 Bundle complet : `check_availability` + `bundle_unit_price_cents`
```python
class BundleItem(Base):
    bundle_unit_price_cents: Mapped[int | None]  # NULL = prorata depuis Bundle.price
    
class BundleService:
    async def check_availability(bundle_id, qty, event_date) -> BundleAvailability:
        # Pour chaque item, vérifie product_stock_view.available >= item.quantity * qty
        # Retourne {available: bool, missing_items: [{product_id, missing_qty}]}
```
- `BundleService.calculate_price` priorise `variant.price_per_day_cents` sur `product.price_per_day_cents` (F499 résout).
- `add_item` : variant_id obligatoire si product **a déjà eu** des variants (column `Product.has_variants_history bool`, lifecycle, pas dépendant de l'état actuel — F506).
- **Résout** : TR-34.

### 4.2.12 CSV import bulk + Celery async
- `repositories/customer.py:CustomerRepository.bulk_create(rows)` avec `insert(...).on_conflict_do_nothing(index_elements=['tenant_id', 'email'])`.
- Endpoint `POST /customers/import` retourne `{task_id, status: 'queued'}` immédiatement, lance `import_customers_task.delay()`.
- Endpoint `GET /imports/{task_id}/status` pour suivre.
- `_CUSTOMER_CSV_FIELDS` étendu : `siret`, `vat_number`, `notes`, `company_name`.
- Pré-validation conditionnelle (individual exige first_name+last_name).
- **Résout** : TR-31.

### 4.2.13 `email_exists` / `sku_exists` cohérents avec UNIQUE DB
- Drop le filtre `is_active` dans les helpers `*_exists` → cohérent avec UNIQUE strict.
- Migration UNIQUE sur `Customer.email`, `Product.sku`, `Product.name`, `Product.slug` : reste strict (pas de partial WHERE).
- Au restore d'un soft-deleted, si conflit existe → 409 propre côté service avant restore.
- **Résout** : TR-32.

### 4.2.14 Validators FR (SIRET Luhn + VAT VIES)
- `app/core/validators.py` : `validate_siret_luhn(value: str) -> bool`.
- `validate_vat_vies(value: str, *, strict: bool=False)` — strict appelle l'API VIES (avec rate limit + cache Redis 24h).
- Pydantic `field_validator` sur `CustomerCreate.siret`, `CustomerCreate.vat_number`.
- **Verrouillé Q26=A** (cf. §4.6) : strict (refus à création), override admin via header `X-Force-Validation-Override: siret` (loggué Outbox audit).

### 4.2.15 `Customer.country` ISO 3166-2 alpha-2
- `Customer.country: Mapped[str] = String(2)` (`'FR'`, `'BE'`, `'CH'`).
- Default `tenant_settings.default_country` (déjà `'FR'` pour Marveline).
- Migration : convertir `"France"` → `"FR"`, `"FRANCE"` → `"FR"`, etc. via dict de mapping.
- Cohérent Q3 Bloc 1 (France métropole stricte 12 mois) — préparation expansion européenne.

### 4.2.16 `condition` vocabulaire unifié inter-modules
Choix d'un seul vocabulaire pour `Product.condition` ET `MovementItem.condition` :
```python
class ItemCondition(StrEnum):
    NEW = 'new'           # ex: 'neuf'
    GOOD = 'good'         # ex: 'bon' / 'perfect'
    USED = 'used'         # ex: 'use' (typo) → 'used'
    DAMAGED = 'damaged'   # ajout vs status quo Product
    OUT_OF_SERVICE = 'out_of_service'  # ex: 'hors_service'
    MISSING = 'missing'   # MovementItem only (lifecycle distinct)
```
- Migration data : `'use'` → `'used'`, `'neuf'` → `'new'`, `'bon'` → `'good'`, `'hors_service'` → `'out_of_service'`, `'perfect'` → `'good'`.
- ENUM PostgreSQL natif `item_condition` partagé.
- **Résout** : TR-37.

### 4.2.17 `Mapped[datetime]` strict (drop `Mapped[str]` couplé DateTime)
- Audit AST : `tools/check_mapped_datetime.py` qui parse et signale `Mapped[str]` couplé `DateTime(...)`.
- Fix : `scheduled_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)`.
- 7 occurrences identifiées modules 19 + 24.
- **Résout** : TR-25.

### 4.2.18 Audit log delete cascade (extend Outbox Bloc 1)
- Décorateur `@audit_action(event='ENTITY_DELETED')` sur `delete_*` services partout (Customer, Product, Bundle, Category, Supplier, Evenement, EventIncident, IncidentAction, PricingRule).
- Outbox event publié transactionnellement.
- **Résout** : TR-36.

### 4.2.19 `event_id` FK propre + cascade
- `InventoryMovement.event_id: ForeignKey('evenements.id', ondelete='SET NULL')` — table existe (mod 24), supprimer le commentaire mensonger.
- Idem `MovementItem.event_item_id` si applicable.
- **Résout** : TR-24.

### 4.2.20 Index trigram pg_trgm sur recherche
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX customers_search_idx ON customers
  USING gin (lower(coalesce(first_name, '') || ' ' || coalesce(last_name, '') || ' ' ||
                   coalesce(company_name, '') || ' ' || coalesce(email, '')) gin_trgm_ops);

CREATE INDEX products_search_idx ON products
  USING gin (lower(coalesce(name, '') || ' ' || coalesce(sku, '')) gin_trgm_ops);
```
- Lag UI typeahead réduit de ~200ms à ~5ms.

## 4.3 Architecture finale par domaine

| Domaine | Modules | Pattern appliqué |
|---|---|---|
| **Customer** | 14 | RFMService + view matérialisée, CSV bulk Celery, ISO country, SIRET Luhn, PII encrypted notes, audit delete |
| **Product/Variant/Bundle/Category** | 15 | Category FK obligatoire, ~~brand_code partout~~ **[OBSOLÈTE Bloc 7 Q43=B — drop intégral]**, tva_rate sur Category, view matérialisée stock, Bundle.check_availability |
| **Pricing** | 16 | `PricingEngine` unique (fusion engine+simulate, nommage harmonisé Bloc 3), discount_pct Numeric(5,4) cumul additif, enum DB rule_type, scope READ pour simulate |
| **Inventory/StockItem** | 19 | StockItemFSM gardée, release_n reservation_id obligatoire, event_id FK propre, Mapped[datetime] strict |
| **Évenements/Incidents** | 24 | UNIQUE reference per-tenant, FSM CHECK enum status, _transition partout, audit log, PII description encrypted |
| **Supplier** | 26 | UNIQUE supplier per-tenant, CHECK qty consistency, trigger auto-sync stock à réception, PII contact_name encrypted |

## 4.4 Migration ordonnée Bloc 4

| Sprint | Périmètre | Tests requis |
|---|---|---|
| **B4.S1** (1 sem) | Hotfixes : F486 (`require_scope` 5 endpoints), F530 (PricingEngine ÷100 unifié), F641 (release_n obligatoire), UNIQUE reference per-tenant (F767/F826/F827) | User sans `products:read` → 403 ; simulate vs apply même résultat ; release_n sans reservation_id → ValueError |
| **B4.S2** (2 sem) | StockItemFSM + matrice transitions DB-enforced + release_n strict + view matérialisée `product_stock_view` + drop colonnes denormalized + StockItem cohérent supplier receipts (CHECK qty + trigger sync) | `damaged → reserved` → 409 ; supplier receipt 100 reçus → 100 stock_items créés + view refresh ; `Product.available_quantity` introuvable |
| **B4.S3** (2 sem) | Category FK obligatoire sur Product + drop CHECK 20 valeurs + tva_rate sur Category + cycle prevention trigger + depth max 5. **NB : `brand_code` retiré de ce sprint, drop intégral via B7.S2 (Bloc 7 Q43=B).** | Migration 200 produits Marveline → category_id ; cycle parent_id refusé ; tva dérivée Category ; tenant Marveline voit son catalogue isolé (pas de partage Splendid) |
| **B4.S4** (2 sem) | `PricingEngine` unique (fusion engine+simulate) + Numeric(5,4) discount_pct + enum DB rule_type + cache Redis + RFMService + customer_rfm_view + trigram pg_trgm + ISO country + SIRET Luhn + VAT VIES | invariant CI engine == simulate ; recherche 50k customers <50ms ; SIRET 12345678901234 → 422 |
| **B4.S5** (1 sem) | PII chiffrement (notes, contact_name, description) via EncryptedField + scope `customers:read_pii` + audit_action decorator partout (delete cascade) + condition vocabulary unifié | Migration `'use'` → `'used'` complète ; user sans `customers:read_pii` voit `notes='[encrypted]'` ; delete_customer émet AuditLog row |
| **B4.S6** (1 sem) | CSV import bulk Celery + Bundle.check_availability + bundle_unit_price_cents + Mapped[datetime] strict + cleanup `email_exists` cohérent UNIQUE DB | 10k lignes import <30 sec async ; bundle Mariage 100 verres avec stock 80 → 409 ; `Mapped[str]` + DateTime → CI bloque |

**Total Bloc 4 : 9 semaines**.

## 4.5 Questions à valider avant lock Bloc 4

| # | Question | Options | Recommandation |
|---|---|---|---|
| **Q21** | Migration `Product.category` string → `category_id` FK | A) Migration brutale (drop string, FK NOT NULL) avec backfill seed<br>B) Phase de coexistence (FK nullable + CHECK string conservé) puis cleanup<br>C) Garder `Product.category` string + ajouter `category_id` FK orpheline (status quo léger) | **A** propre, scriptable une fois |
| **Q22** | Source de vérité stock | A) `StockItem` only + view matérialisée<br>B) `Product.available_quantity` colonne maintenue par triggers depuis `stock_items`<br>C) Status quo (3 sources, doc en surface) | **A** matérialisée, refresh debounced 5s |
| **Q23** | Portage du `tva_rate` | A) Sur `Category` (par catégorie tva)<br>B) Sur `Tenant.settings.tva_rate_default` + override per-product<br>C) Sur `Product` (status quo) | **A** + override Product nullable rare cas |
| **Q24** | `brand_code` Catalogue : visibilité par défaut | A) `NULL = visible toutes brands` (catalogue partagé inclusif)<br>B) `NULL = caché` (strict, force assignation)<br>C) `NULL` interdit (NOT NULL) | **A** : flexible Marveline+Splendid sans duplication |
| **Q25** | Modèle Pricing rules application | A) **Cumul additif** (somme des % matchant) — cohérent Bloc 3 F565<br>B) Premier matching (status quo `simulate`)<br>C) Exclusive avec priorité explicite (`PricingRule.priority`) | **A** cohérent Bloc 3 |
| **Q26** | SIRET/VAT validators stricts | A) **Strict** (Luhn invalide → 422 à la création)<br>B) Warning seul (création OK + flag `siret_invalid`)<br>C) Désactivé (validation longueur/format only) | **A** sauf override admin (`force_siret=true`) |
| **Q27** | Seuils RFM | A) Constants globaux (cf. `app/constants/business.py`)<br>B) Per-tenant via `tenant_settings.rfm_thresholds JSONB`<br>C) Per-brand (catalogue Splendid B2B vs Marveline B2C) | **A** d'abord, **B** si demande Splendid |
| **Q28** | Chiffrement PII (`notes`, `description`, `contact_name`) | A) Obligatoire systémique (`EncryptedField` + scope `*:read_pii`)<br>B) Opt-in via `tenant_settings.pii_encryption_enabled`<br>C) Désactivé (status quo) | **A** RGPD strict |

## 4.6 Décisions verrouillées Bloc 4 (2026-04-27)

| # | Réponse | Conséquence architecture |
|---|---|---|
| **Q21** | **A** — migration brutale `Product.category` → `category_id FK NOT NULL` | Sprint B4.S3 : seed Category 20 valeurs Marveline + backfill `category_id` per Product + `ALTER TABLE products DROP COLUMN category, DROP CONSTRAINT check_product_category_valid`. Migration unique, pas de phase de coexistence. |
| **Q22** | **A** — StockItem unique source de vérité + `product_stock_view` matérialisée | Drop `Product.available_quantity`, `Product.stock_quantity`, `ProductVariant.available_quantity`. Refresh debounced 5s via Redis lock. Drop fonction `sync_available_from_variants`. |
| **Q23** | **A** — `tva_rate` sur `Category` (Numeric(5,4)) | `Category.tva_rate Numeric(5,4) NOT NULL`. `Product.tva_rate` colonne supprimée. Si exception métier (un produit avec TVA différente), override possible via `Product.tva_rate_override Numeric(5,4) NULL`. Capture du snapshot à la ligne (cf. Bloc 3 TR-3). |
| **Q24** | ~~**A** — `brand_code NULL = visible toutes brands`~~ **[OBSOLÈTE Bloc 7 — Q43=B]** | ~~Catalogue inclusif partagé Marveline+Splendid par défaut.~~ **Décision invalidée** : Q43=B verrouille 2 tenants distincts (Marveline / Splendid), donc plus de concept multi-brand intra-tenant. **Drop intégral** des colonnes `brand_code` (Product/Category/Bundle/Collection) + `Tenant.is_multi_brand` + header `X-Brand-Code`. Migration via Sprint **B7.S2** (1 sem). Cf. §7.2 + §7.6 pour détail. |
| **Q25** | **A** — Cumul additif des règles Pricing | Cohérent Bloc 3 F565 (discount cumul additif). `PricingEngine.calculate` somme les `discount_pct` matchant (clamp 0..1). Élimine drift engine vs simulate. |
| **Q26** | **A** — SIRET Luhn strict | `validate_siret_luhn` raise `422 SIRET invalide` à la création. Override admin via header `X-Force-Validation-Override: siret` (loggué Outbox audit). |
| **Q27** | **B** — Seuils RFM per-tenant via `tenant_settings.rfm_thresholds JSONB` | Schema Pydantic `RFMThresholds` valide la structure : `{champion_recency_days, champion_frequency, loyal_recency_days, loyal_frequency, potential_recency_days, at_risk_recency_days, monetary_high_cents}`. Constants globaux `app/constants/business.py:RFM_DEFAULTS` servent de **fallback** si `tenant_settings.rfm_thresholds IS NULL`. `RFMService.compute_segment(tenant_settings, recency, frequency, monetary)` lit les seuils du settings + applique les defaults. UI admin : page `Tenant Settings → Fidélité` permet d'ajuster (Splendid B2B premium long cycle ≠ Marveline B2C). View matérialisée `customer_rfm_view` recalcule par tenant avec ses propres seuils. |
| **Q28** | **A** — PII chiffrement obligatoire | `EncryptedField` (envelope KMS, Bloc 1) sur `Customer.notes`, `Supplier.notes`, `Supplier.contact_name`, `EventIncident.description`, `Evenement.notes`, `MovementItem.condition_notes`, `StockItem.notes`. Scope `customers:read_pii` séparé pour exposer en clair. Migration Celery `migrate_pii_encryption_task` chiffre les rows existantes. |

**Bloc 4 verrouillé. Total : 9 semaines de migration, 6 domaines convergent (Customer, Catalog, Pricing, Stock, Évenements, Supplier).**

**Cumul après 4 blocs verrouillés** (séquentiel) : Bloc 1 (10) + Bloc 2 (10) + Bloc 3 (10) + Bloc 4 (9) = **39 semaines** de migration, ~870 frictions résorbées (sur ~1154 totales).

---

---

# Bloc 5 — Multi-app verticals (modules 28 Épicerie, 29 Restaurant, 30 Catalogue partagé / cross-domain)

> **Volume audité** : ~21 460 LoC, **~130 frictions, ~26 P0 estimés**.
> Domaines : Épicerie (POS + stock + transferts + ETL réception), Restaurant (cuisine + marmites + commandes + tables + ETL TAIYAT), Catalogue partagé (référentiel ETL alimentaire cross-tenant + transferts cross-domain).
> **Constat fondamental** : trois catalogues parallèles (Product Marveline / EpicerieProduit / IngredientRestaurant) coexistent sans modèle unifié. Le **référentiel ETL** (CatalogueProduit + CategorieProduit + EtlCorrectionHistory) est cross-tenant **sans `tenant_id`** — Marveline, Épicerie, Restaurant écrivent dedans → fuite cross-tenant + overwrite silent. Un bug critique runtime (F906 `AttributeError quantite_par_portion`) bloque actuellement le lancement de toute marmite avec recette. Le restaurant ne crée **aucune** `FinanceInvoice` à l'encaissement → audit fiscal échoue.

## 5.1 Patterns transverses à éradiquer (au-delà Bloc 3+4)

| # | Pattern | Frictions | Conséquence |
|---|---|---|---|
| **TR-39** | Référentiel ETL **sans `tenant_id`** : `CatalogueProduit`, `CategorieProduit`, `EtlCorrectionHistory` cross-tenant | F874, F957, F959, F962 | Marveline modifie un prix → Épicerie+Restaurant impactés silencieusement. Correction history apprend cross-tenant = fuite de connaissance métier (un concurrent SaaS verrait les corrections de l'autre). Admin désactive une catégorie globalement → tous les tenants cassés. |
| **TR-40** | Cross-tenant FK invalidées : `IngredientEpicerieMapping.produit_id` peut pointer vers un tenant épicerie tiers | F924, F925, F965 | Mapping resto→épicerie non vérifié → fuite stock. `InternalTransfer.dest_tenant_id` non validé. `TransferRequest.target_tenant_id` idem. |
| **TR-41** | Race condition stock épicerie : `valider_transfert` sans `with_for_update` | F871 | Deux workers décrémentent stock concurrent → un perdu. Pattern Bloc 3 TR-2 répliqué. |
| **TR-42** | Annulation sans réintégration stock (resto + épicerie) | F908, F909 | `LigneCommande.delete` ne restitue ni portions marmite ni protéine ni side. `CommandeService.annuler` idem. Stock définitivement perdu. |
| **TR-43** | `CommandeRestaurant.payer` ne crée **aucune** `FinanceInvoice` | F910 | CA restaurant uniquement dans `restaurant_commandes`. Pas de livre comptable. Audit fiscal impossible. Asymétrie avec épicerie. |
| **TR-44** | `EpicerieVente.annuler_vente` ne génère pas d'avoir | F872 | Stock revient mais facture reste `PAYEE`. Reporting TVA + CA divergent. |
| **TR-45** | Double consommation protéine (recette TypePreparation + VariantePlat.ingredient_proteine_id) | F913 | Si admin remplit naïvement les deux, le poulet est consommé 2× pour le même plat. |
| **TR-46** | Catalogue cross-tenant : prix overwrite silent sans audit ni history | F874, F962, F977 | `_handle_ean_match` update `prix_unitaire_cts` du dernier import. Pas de `CatalogueProduitPriceHistory`. |
| **TR-47** | `lignes_data JSONB` non versionné | F875, F966 | Schema `LigneParsee` change → imports historiques cassés à la re-validation. |
| **TR-48** | Celery `run_etl_import` sans `tenant_id` arg | F960 | Validation tenant via `EtlImport.target_tenant_id` non vérifié → forge possible. |
| **TR-49** | Celery `run_etl_import` non idempotent | F964 | Retry après commit partiel double-import. ETL-DUPE-01 partiellement résolu. |
| **TR-50** | `_global_idf` singleton module-level mutable | F967 | Deux imports parallèles écrasent l'IDF mid-batch → scores Soft TF-IDF incohérents. |
| **TR-51** | Auto-création silent `FinanceVendor` sur typo vendor_code | F980 | Référentiel pollué silencieusement. |
| **TR-52** | `stock_alerte=0` default = aucune alerte ne déclenche jamais | F907 | Feature alerte cassée par défaut sur tous les ingrédients ETL TAIYAT. Badge UI inutilisable. |
| **TR-53** | `categorie_code String` (pas `ForeignKey()` SQL) sur 3 catalogues | F956 | Migration M00 rename → produits orphelins silencieux. |
| **TR-54** | `TransferRequest` workflow cassé en milieu : `APPROVED → FULFILLED` côté code absent | F923 | `fulfilled_transfer_id` jamais setté. Épicerie ne peut pas confirmer fulfillement. |
| **TR-55** | `_TENANT_RESTAURANT = 3` hardcoded dans services restaurant | F944, F945 | Service singleton tenant unique. Multi-restaurant impossible. Couplage très fort. |
| **TR-56** | TVA `0.20` Marveline-spécifique propagée partout (`EpicerieProduit.taux_tva default=2000`, `VariantePlat.taux_tva default=550`) | F891, F927, F958 | Continuation TR-18 Bloc 4. Outre-mer/Sénégal Splendid → factures invalides. |
| **TR-57** | F906 bug runtime critique : `_verifier_et_consommer_recette` accède `ligne.quantite_par_portion` inexistant | F906 | **Production bloquée** : tout `POST /instances` (lancement marmite) avec recette → `AttributeError 500`. Restaurant ne peut PAS lancer une marmite. |
| **TR-58** | `encaisser.check_stock=False` par défaut | F870 | Vente passe → IntegrityError 500 (CHECK `stock_apres>=0`) au lieu de 409 propre. UX caissier cassée. |
| **TR-59** | `lookup_correction_history` Layer 0 retourne toujours `None` (placeholder) | F976 | Apprentissage classification cassé. Vrai lookup dupliqué inline → confusion architecturale. |
| **TR-60** | `_FINAL_CATEGORIES` frozenset hardcoded ~91 codes Python ↔ table `categories_produit` | F987 | Drift garanti si admin ajoute catégorie en DB → classification rejette code valide. |
| **TR-61** | `EtlImport` statut `ECHEC` absent (100% erreurs → `PARTIEL` mensonger) | F986 | UI affiche "partiellement importé" alors que rien n'est passé. |

## 5.2 Architecture cible — patterns canoniques

### 5.2.1 Référentiel ETL `tenant_id NOT NULL` (rupture)
```python
class CatalogueProduit(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    tenant_id: Mapped[int]   # NOT NULL — partition stricte
    # ... reste inchangé
    __table_args__ = (
        UniqueConstraint('tenant_id', 'ean', name='uq_catalogue_produit_tenant_ean'),
    )

class CategorieProduit(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    tenant_id: Mapped[int]   # NOT NULL
    # ... reste inchangé

class EtlCorrectionHistory(Base, TimestampMixin, TenantMixin):
    tenant_id: Mapped[int]   # NOT NULL — apprentissage strictement per-tenant
```
- **Migration** : pour chaque tenant ayant fait du ETL (épicerie + restaurant), créer son `CatalogueProduit` propre. Backfill à partir du dernier `EtlImport` par tenant.
- **Seed M00** : créer table `categorie_produit_seed` (read-only, pas de tenant) avec les 91 catégories canoniques. Au provisioning d'un nouveau tenant épicerie/restaurant, copie de seed → `categorie_produits` per-tenant.
- **Résout** : TR-39, TR-46.

### 5.2.2 Trigger DB cross-tenant validation
```sql
CREATE OR REPLACE FUNCTION validate_internal_transfer_tenants() RETURNS trigger AS $$
DECLARE
    src_app text; dst_app text;
BEGIN
    SELECT app_code INTO src_app FROM tenants WHERE id = NEW.tenant_id;
    SELECT app_code INTO dst_app FROM tenants WHERE id = NEW.dest_tenant_id;
    IF src_app != 'epicerie' OR dst_app != 'restaurant' THEN
        RAISE EXCEPTION 'invalid cross-tenant transfer: % → %', src_app, dst_app;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_internal_transfer_tenants
    BEFORE INSERT OR UPDATE ON internal_transfers
    FOR EACH ROW EXECUTE FUNCTION validate_internal_transfer_tenants();

-- Pareil : ingredient_epicerie_mappings (resto→épicerie), transfer_requests
```
- Pour `IngredientEpicerieMapping`, le trigger valide que `produit_id` appartient au tenant épicerie jumelé via `tenant_settings.epicerie_tenant_id`.
- **Résout** : TR-40.

### 5.2.3 Hotfix critique F906 (Sprint 1 obligatoire)
```python
# AVANT (bugué)
qtite_requise = Decimal(str(ligne.quantite_par_portion)) * nb_portions

# APRÈS
qtite_requise = (
    Decimal(str(ligne.quantite_par_batch))
    * Decimal(nb_portions) / Decimal(tp.portions_par_batch)
)
```
- Test E2E `POST /instances` avec recette définie → 200 + portions_restantes correctes.
- **Résout** : TR-57.

### 5.2.4 Cancel cascade unifié vente/commande (étend Bloc 3 TR-5)
```python
# app/services/epicerie/vente.py
async def annuler_vente(vente_id: int, reason: str, actor_id: int):
    async with db.begin():
        vente = await self._lock_vente(vente_id)
        EpicerieVenteFSM.assert_transition(vente.statut, 'ANNULEE')
        # 1. Reverse stock movements (mvts AJUSTEMENT +)
        for ligne in vente.lignes:
            await self._mvt_repo.create_compensating(ligne, vente.id, actor_id)
        # 2. Generate credit note (FinanceInvoice type=CREDIT_NOTE)
        await self._invoice_service.create_credit_note(vente.invoice_id, reason)
        # 3. FSM transit + Outbox audit
        await EpicerieVenteFSM.transit(db, vente, ..., to='ANNULEE')

# app/services/restaurant/commande.py
async def annuler_commande(commande_id: int, reason: str, actor_id: int):
    async with db.begin():
        cmd = await self._lock_commande(commande_id)
        # 1. Itère les lignes ENVOYEE/LANCEE/PRETE
        for ligne in cmd.lignes:
            if ligne.statut_plat in ('ENVOYEE', 'LANCEE', 'PRETE'):
                await self._reintegrer_ligne(ligne, actor_id)
        # 2. Si commande PAYEE → credit note
        if cmd.statut == 'PAYEE':
            await self._invoice_service.create_credit_note(cmd.invoice_id, reason)
        # 3. FSM transit
        await CommandeRestaurantFSM.transit(db, cmd, to='ANNULEE')
```
- `_reintegrer_ligne` : INSERT mouvement compensatoire (`type='inventaire'` quantité +) sur ingrédient + protéine + side ingredient + INCREMENT `portions_restantes` instance_preparation.
- **Résout** : TR-42, TR-44.

### 5.2.5 `FinanceInvoice CLIENT_RESTAURANT` à `payer`
```python
async def payer(commande_id: int, payload: PayerCommandeIn, actor_id: int):
    async with db.begin():
        cmd = await self._lock_commande(commande_id)
        CommandeRestaurantFSM.assert_transition(cmd.statut, 'PAYEE')
        # 0. Validation totaux: somme fractions == total_ttc + pourboire
        total_attendu = cmd.total_ttc_cts + payload.pourboire_cts
        total_fractions = sum(f.montant_cts for f in payload.fractions)
        if total_fractions != total_attendu:
            raise FractionnementInvalide(total_attendu, total_fractions)
        # 1. Snapshot totaux
        cmd.sous_total_cts, cmd.tva_cts, cmd.total_ttc_cts = ...
        # 2. Création FinanceInvoice
        invoice = await self._invoice_service.create_from_commande(
            cmd, type='CLIENT_RESTAURANT',
            reference=f'CMD-RESTO-{cmd.id}',
        )
        cmd.invoice_id = invoice.id
        # 3. FSM transit + Outbox audit
        await CommandeRestaurantFSM.transit(db, cmd, to='PAYEE')
```
- Convergence vers `Invoice` canonique (Bloc 3) avec `app_code='restaurant'`.
- **Résout** : TR-43, F911.

### 5.2.6 Protéine XOR (recette OU variante, jamais les deux)
```sql
ALTER TABLE variantes_plats ADD CONSTRAINT ck_protein_xor_recipe
  CHECK (
    ingredient_proteine_id IS NULL  -- recette gère
    OR NOT EXISTS (
      SELECT 1 FROM recettes_type_preparation rtp
      WHERE rtp.type_preparation_id = type_preparation_id
        AND rtp.ingredient_id = ingredient_proteine_id
    )
  );
```
- Service-level validator complète (CHECK avec subquery limitée par PG).
- Décision : si la protéine est dans `RecetteTypePreparation` → consommée au lancement marmite ; sinon `VariantePlat.ingredient_proteine_id` → consommée au service ligne.
- **Résout** : TR-45.

### 5.2.7 Versioning `lignes_data JSONB`
```python
class EtlImport(Base):
    lignes_data: Mapped[dict | None]  # {"version": int, "lines": [...]}
    lignes_data_schema_version: Mapped[int]  # 1, 2, 3...

# app/services/catalogue/lignes_data_migrator.py
class LignesDataMigrator:
    @staticmethod
    def deserialize(raw: dict, target_version: int = CURRENT_VERSION) -> list[LigneParsee]:
        version = raw.get('version', 1)
        while version < target_version:
            raw = MIGRATIONS[version](raw)
            version += 1
        return [LigneParsee(**line) for line in raw['lines']]
```
- Migrators handler par version transition (`v1_to_v2(raw)` etc.).
- **Résout** : TR-47.

### 5.2.8 Celery tasks tenant-aware obligatoires
```python
@celery_app.task(name='app.tasks.etl_tasks.run_etl_import', max_retries=1)
def run_etl_import(tenant_id: int, etl_import_id: int, ...):
    # Advisory lock per import_id (idempotence)
    with advisory_xact_lock(f'etl_import:{etl_import_id}'):
        etl_import = db.get(EtlImport, etl_import_id)
        if etl_import.tenant_id != tenant_id:
            raise TenantMismatch(...)
        if etl_import.statut != 'PENDING':
            return  # idempotent retry
        # ...
```
- **Linter custom CI** `tools/check_celery_tenant_arg.py` : tout `@celery_app.task` qui touche table `TenantMixin` doit avoir `tenant_id` arg + assert match.
- **Résout** : TR-48, TR-49.

### 5.2.9 `IdfCorpus` injection per-call (drop singleton)
```python
# AVANT
_global_idf: dict[str, float] = {}
def build_idf_from_candidates(...): _global_idf.update(...)

# APRÈS
@dataclass
class IdfCorpus:
    df: dict[str, int]
    n_docs: int
    def idf(self, token: str) -> float: ...

def build_idf(candidates: list[str]) -> IdfCorpus: ...
def compute_similarity_smart(a: str, b: str, corpus: IdfCorpus) -> float: ...
```
- État partagé éliminé. Import parallèle safe.
- **Résout** : TR-50.

### 5.2.10 Vendor matching strict (drop auto-create silent)
```python
async def resolve_vendor(vendor_code: str, tenant_id: int) -> FinanceVendor | None:
    vendor = await self._vendor_repo.get_by_code(vendor_code, tenant_id)
    if vendor is None:
        # Au lieu d'auto-create : queue admin
        await self._etl_repo.update_statut(etl_import_id, 'AWAITING_VENDOR_MATCH')
        await self._notification_service.notify_admin(
            tenant_id, f'Vendor inconnu : {vendor_code}'
        )
        raise VendorMatchPending(vendor_code)
    return vendor
```
- Endpoint admin `POST /etl/imports/{id}/resolve-vendor` avec choix : (a) link vers vendor existant, (b) create new vendor explicit.
- **Résout** : TR-51.

### 5.2.11 Smart `stock_alerte` default
```python
async def compute_default_threshold(ingredient_id: int) -> Decimal:
    # Rolling p10 conso 30 jours (ou fallback categorie default)
    p10 = await self._mvt_repo.percentile_consommation(ingredient_id, days=30, p=10)
    if p10 is None:
        cat = await self._cat_repo.get_by_id(ingredient.categorie_id)
        return cat.stock_alerte_default or Decimal('1.0')
    return p10
```
- À la création ingrédient (ETL TAIYAT) : `stock_alerte = compute_default_threshold(ingredient_id)`.
- Recompute hebdomadaire via Celery `recompute_stock_alertes_task`.
- **Résout** : TR-52.

### 5.2.12 `categorie_code → categorie_id FK NOT NULL`
- Migration sur `CatalogueProduit`, `EpicerieProduit`, `IngredientRestaurant` :
  1. Add `categorie_id Integer NULL` + FK `categories_produit.id ondelete=RESTRICT`.
  2. Backfill `UPDATE ... SET categorie_id = (SELECT id FROM categories_produit WHERE code = categorie_code AND tenant_id = ...)`.
  3. ALTER COLUMN `categorie_id NOT NULL`.
  4. DROP COLUMN `categorie_code`.
- **Résout** : TR-53.

### 5.2.13 `TransferRequest` workflow complet
```python
class TransferRequestFSM(FSM[str]):
    transitions = {
        'PENDING':   {'APPROVED', 'REJECTED', 'CANCELLED'},
        'APPROVED':  {'FULFILLED', 'CANCELLED'},
        'FULFILLED': set(),
        'REJECTED':  set(),
        'CANCELLED': set(),
    }

# Endpoints
POST /transfer-requests/{id}/approve    # admin épicerie
POST /transfer-requests/{id}/reject     # admin épicerie + reason
POST /transfer-requests/{id}/fulfill    # auto via création InternalTransfer
POST /transfer-requests/{id}/cancel     # demandeur restaurant
```
- `TransferRequestService.fulfill(request_id)` :
  1. Vérifie statut == APPROVED.
  2. Crée `InternalTransfer(epicerie → restaurant)` correspondant.
  3. `transfer_request.fulfilled_transfer_id = internal_transfer.id`.
  4. FSM transit FULFILLED.
- **Résout** : TR-54.

### 5.2.14 Drop `_TENANT_RESTAURANT = 3` hardcoded
- `services/restaurant/dashboard.py:_load_uplift_pct(tenant_id)` — paramètre explicite.
- `services/restaurant/reception_etl.py` — supprimer assert `tenant_id == 3`.
- Service multi-restaurant ready. Un nouveau tenant restaurant peut être provisionné sans patcher le code.
- **Résout** : TR-55.

### 5.2.15 TVA dérivée Category + tenant_settings (continuation Bloc 4 Q23)
- `EpicerieProduit.taux_tva` → DROP. Read via `Category.tva_rate` (Bloc 4).
- `IngredientRestaurant.taux_tva_cents` → DROP. Read via `Category.tva_rate * 10000`.
- `VariantePlat.taux_tva` → DROP. Read via `Category.tva_rate`. **Pas d'override per-variante** : si une exception métier existe (un plat avec TVA différente de sa catégorie), c'est rare et passe par `Product.tva_rate_override Numeric(5,4) NULL` au niveau Product (cohérent Bloc 4 §4.6 Q23) — pas par VariantePlat. Drop `VariantePlat.tva_rate_override` non décidé.
- `tenant_settings.country_code` (Bloc 1 Q3 = France strict) influence `Category.tva_rate` defaults au provisioning.
- Snapshot capture sur la ligne (cohérent Bloc 3 TR-3) : `EpicerieVenteLigne.tva_rate_snapshot`, `LigneCommandeRestaurant.tva_rate_snapshot`.
- **Résout** : TR-56.

### 5.2.16 `CatalogueProduitPriceHistory` table (audit prix cross-import)
```python
class CatalogueProduitPriceHistory(Base, TimestampMixin, TenantMixin):
    catalogue_produit_id: Mapped[int]
    etl_import_id: Mapped[int]
    prix_unitaire_cts_old: Mapped[int | None]
    prix_unitaire_cts_new: Mapped[int]
    taux_tva_centieme_old: Mapped[int | None]
    taux_tva_centieme_new: Mapped[int]
    source_fournisseur: Mapped[str]
    changed_at: Mapped[datetime]
```
- Trigger `AFTER UPDATE ON catalogue_produits` qui INSERT row si prix change.
- UI admin : page `Historique prix produit` lit cette table.
- **Résout** : TR-46 (continuation).

### 5.2.17 `_FINAL_CATEGORIES` frozenset éliminé
- Source de vérité unique = table `categories_produit` (per-tenant après TR-39).
- `services/catalogue/etl_import_service.py` lit `categories_produit` au démarrage worker, cache Redis 5 min, invalidation sur `INSERT/UPDATE/DELETE` via Outbox event.
- Drop frozenset Python.
- **Résout** : TR-60.

### 5.2.18 `EtlImport` statut `ECHEC` explicite + `lookup_correction_history` Layer 0 fixé
- Statut `ECHEC` : si `nb_erreur == len(lignes)`. Statut `PARTIEL` : si `0 < nb_erreur < len(lignes)`. Statut `SUCCES` : si `nb_erreur == 0`.
- `lookup_correction_history(designation_norm, tenant_id)` réimplémenté correctement, supprimer le placeholder l. 727-743 + dédupliquer le code inline.
- **Résout** : TR-59, TR-61.

### 5.2.19 `encaisser.check_stock=True` par défaut
- Hotfix Sprint 1 : `payload.check_stock` default `True`. Service-level guard 409 propre avant l'INSERT (pas d'IntegrityError 500).
- **Résout** : TR-58.

## 5.3 Architecture finale par domaine

| Domaine | Modules | Pattern appliqué |
|---|---|---|
| **Épicerie** | 28 | EpicerieVenteFSM, cancel cascade avec credit note, `with_for_update` transferts, `check_stock=True` default, FK exhaustives `MouvementStock.{vente_id, supply_order_id, transfer_id}`, EAN UNIQUE partiel |
| **Restaurant** | 29 | Hotfix F906 `quantite_par_batch`, CommandeRestaurantFSM, FinanceInvoice CLIENT_RESTAURANT à `payer`, cancel cascade ligne+commande avec réintégration stock, protéine XOR, `_TENANT_RESTAURANT` drop |
| **Catalogue partagé / cross-domain** | 30 | `tenant_id NOT NULL` sur référentiel ETL, trigger DB cross-tenant validation, Celery tenant-aware + advisory lock, `IdfCorpus` per-call, vendor matching strict queue, `categorie_id FK`, `lignes_data` versioning, `CatalogueProduitPriceHistory`, statut ECHEC explicite |

## 5.4 Migration ordonnée Bloc 5

| Sprint | Périmètre | Tests requis |
|---|---|---|
| **B5.S1** (1 sem) | **Hotfixes critiques production** : F906 (`quantite_par_batch` + formule), F870 (`check_stock=True` default), F908+F909 (cancel ligne/commande avec réintégration stock), F910 (`FinanceInvoice CLIENT_RESTAURANT` à `payer`), F911 (validation total fractions==total) | E2E lancement marmite avec recette → 200 + portions correctes ; cancel ligne ENVOYEE → portions restituées ; `payer` crée Invoice + Outbox event |
| **B5.S2** (2 sem) | `tenant_id NOT NULL` sur référentiel ETL (CatalogueProduit, CategorieProduit, EtlCorrectionHistory) + migration backfill par tenant + seed `categorie_produit_seed` global read-only + trigger DB cross-tenant validation FK (3 triggers) | Marveline modifie un prix CatalogueProduit → Épicerie/Restaurant pas impactés ; `IngredientEpicerieMapping.produit_id` cross-tenant tiers → trigger refuse |
| **B5.S3** (2 sem) | FSM helper appliqué (EpicerieVenteFSM, CommandeRestaurantFSM, LigneCommandeFSM, EtlImportFSM, EtlConflictFSM, InternalTransferFSM, TransferRequestFSM) + cancel cascade unifié + protéine XOR (CHECK + service-level) | Transition illégale `OUVERTE → ANNULEE` direct → 409 ; protéine définie 2× (recette+variante) → 422 |
| **B5.S4** (2 sem) | Celery tenant-aware (linter CI + arg `tenant_id` partout) + advisory lock idempotence ETL + `IdfCorpus` per-call + vendor matching strict queue (`AWAITING_VENDOR_MATCH`) + `lignes_data_schema_version` + migrator | retry ETL après commit partiel → idempotent ; 2 imports parallèles → IDF non écrasé ; vendor inconnu → status AWAITING + email admin |
| **B5.S5** (1 sem) | `categorie_code → categorie_id FK NOT NULL` migration backfill + drop `_FINAL_CATEGORIES` frozenset + statut ECHEC explicite ETL + `lookup_correction_history` fixé + `_TENANT_RESTAURANT = 3` drop | M00 rename → produits raise FK violation au lieu d'orphelins ; ETL 100% erreurs → statut ECHEC ; restaurant tenant_id=5 fonctionne |
| **B5.S6** (1 sem) | `TransferRequest.fulfill` workflow complet + smart `stock_alerte` default + `CatalogueProduitPriceHistory` table + Decimal end-to-end (drop float `quantite × prix_cts`) + TVA dérivée Category | TransferRequest APPROVED → fulfill crée InternalTransfer ; `stock_alerte` calculé p10 ; price change ETL → row PriceHistory écrite |

**Total Bloc 5 : 9 semaines**.

## 5.5 Questions à valider avant lock Bloc 5

| # | Question | Options | Recommandation |
|---|---|---|---|
| **Q29** | Référentiel ETL alimentaire (CatalogueProduit) | A) **Split per-tenant** : chaque tenant épicerie/restaurant a son propre catalogue (rupture isolation totale)<br>B) Shared cross-tenant + table pivot `catalogue_produit_per_tenant` (prix par tenant)<br>C) Status quo (cross-tenant overwrite) | **A** rupture propre, isolation complète. La duplication de quelques milliers de produits par tenant est triviale vs. risque de fuite cross-tenant (RGPD + concurrence SaaS) |
| **Q30** | Architecture catalogues produit (Marveline `Product` / `EpicerieProduit` / `IngredientRestaurant`) | A) **Garder 3 modèles distincts** (status quo vertical isolation)<br>B) Unifier en 1 seul `Product` étendu avec `app_code` (refonte radicale)<br>C) 2 catalogues : Marveline location (mobilier) + FoodCatalog unifié (épi+resto) | **A** maintenant, **B** comme objectif horizon 18 mois après stabilisation des 5 blocs. Les sémantiques différent (location/jour vs vente/kg vs portion cuisinée). |
| **Q31** | Consommation protéine restaurant | A) **Recette TypePreparation** seul (consommée au lancement marmite, plus de `VariantePlat.ingredient_proteine_id`)<br>B) **VariantePlat.ingredient_proteine_id** seul (consommée au service ligne, plus de protéine dans recette)<br>C) Configurable par plat via flag `protein_consumed_at='batch_launch' | 'line_service'` | **A** : aligné cuisine pro (la marmite contient TOUTE sa protéine ; le service décrémente portions, pas ingredients). Drop colonne `VariantePlat.ingredient_proteine_id` après backfill. |
| **Q32** | Approval workflow `TransferRequest` (resto → épicerie) | A) **Approval automatique** par stock check (`>= qty disponible`)<br>B) **Approval manuelle** par admin épicerie systématique<br>C) Hybride (auto si <= seuil, sinon manuel) | **C** : auto pour réapprovisionnement quotidien (fluidité service midi/soir), manuel pour grosses qty (>= 80% stock épicerie disponible) |
| **Q33** | Vendor matching ETL si `vendor_code` inconnu | A) **Auto-create + flag** `vendor_unverified=True` (vélocité ETL)<br>B) **Bloquer import → AWAITING_VENDOR_MATCH** queue admin (rigueur référentiel)<br>C) Status quo (auto silent) | **B** : référentiel propre vaut 5 min admin par nouvelle facture. Sinon dédup nightmare. |
| **Q34** | `_TENANT_RESTAURANT = 3` hardcoded | A) **Drop** (multi-restaurant ready maintenant)<br>B) **Garder + documenter** (mono-restaurant assumé pour 12 mois)<br>C) **Flag `tenant.is_restaurant=True`** pour autoriser | **A** : nettoyage technique facile, prépare expansion (Marveline pourrait acquérir un 2e restaurant). |
| **Q35** | `EtlImport` statut `ECHEC` | A) **Ajouter** ECHEC quand 100% erreurs (PARTIEL réservé à 1-99% erreurs)<br>B) Garder `PARTIEL` avec `nb_erreur` exposé en UI<br>C) Statut `ROLLED_BACK` séparé | **A** : sémantique claire. UI affiche message correct. |

## 5.6 Décisions verrouillées Bloc 5 (2026-04-27)

| # | Réponse | Conséquence architecture |
|---|---|---|
| **Q29** | **A** — Split référentiel ETL per-tenant | `CatalogueProduit`, `CategorieProduit`, `EtlCorrectionHistory` `tenant_id NOT NULL`. Migration : pour chaque tenant épicerie/restaurant existant, dupliquer le référentiel ETL. Seed M00 global read-only `categorie_produit_seed` (91 codes canoniques) copié vers `categorie_produits` per-tenant au provisioning. Isolation totale, RGPD safe. |
| **Q30** | **A** — Garder 3 modèles distincts (status quo) | `Product` (Marveline location) ≠ `EpicerieProduit` ≠ `IngredientRestaurant`. Sémantique différente justifie. **Horizon 18 mois** : envisager unification `Product` + `app_code` après stabilisation des 5 blocs. Pas dans la roadmap actuelle. |
| **Q31** | **A** — Protéine consommée au lancement marmite (recette seul) | Drop colonne `VariantePlat.ingredient_proteine_id` après backfill. Drop colonne `VariantePlat.quantite_proteine`. La protéine = ligne dans `RecetteTypePreparation`. Marmite "Carry poulet" contient ses 5kg poulet à `lancer_marmite()`, le service ligne décrémente uniquement `portions_restantes`. CHECK constraint XOR devient inutile (variante n'a plus de protéine). Migration data : convertir les `(variante.ingredient_proteine_id, variante.quantite_proteine)` en lignes `RecetteTypePreparation` pour le `type_preparation_id` lié. |
| **Q32** | **A** — Approval automatique par stock check | `TransferRequestService.approve()` automatique : si stock épicerie disponible >= qty demandée → APPROVED. Sinon → REJECTED avec message "stock insuffisant". Pas de seuil hybride. Simplifie le workflow. **Risque** : double approval simultané pour 2 requests sur même produit qui dépassent ensemble le stock → mitigé par `pg_advisory_xact_lock(produit_id)` au moment du check. Pas de queue manuelle admin. UI restaurant voit l'approbation/rejet immédiat. |
| **Q33** | **B** — `AWAITING_VENDOR_MATCH` queue admin | `_resolve_vendor_id` ne crée plus auto. Si vendor_code inconnu → `EtlImport.statut = 'AWAITING_VENDOR_MATCH'` + email admin tenant. Endpoint `POST /etl/imports/{id}/resolve-vendor` avec choix : (a) link vers vendor existant, (b) create new vendor explicit. Référentiel propre, dédup évitée. |
| **Q34** | **A** — Drop `_TENANT_RESTAURANT = 3` hardcoded | `services/restaurant/dashboard.py:_load_uplift_pct(tenant_id)` paramètre explicite. `services/restaurant/reception_etl.py` : drop assert `tenant_id == 3`. Service multi-restaurant ready. Provisioning d'un 2e tenant restaurant possible sans patch code. |
| **Q35** | **A** — Statut `ECHEC` explicite | `_compute_final_statut` : `nb_erreur == len(lignes)` → `ECHEC` ; `0 < nb_erreur < len(lignes)` → `PARTIEL` ; `nb_erreur == 0` → `SUCCES`. Migration matrice transitions FSM `EtlImport`. UI affiche "Échec import" au lieu de "Partiellement importé" mensonger. |

**Bloc 5 verrouillé. Total : 9 semaines de migration, 3 domaines convergent (Épicerie, Restaurant, Catalogue partagé). Hotfixes critiques production en Sprint 1 (F906 + F870 + F910).**

**Cumul après 5 blocs verrouillés** (séquentiel) : 39 + Bloc 5 (9) = **48 semaines** de migration, ~1000 frictions résorbées (sur ~1154 totales).

---

---

# Bloc 6 — Cross-cutting (modules 27 Notification, 31 Audit, 32 Feature Flag, 33 Celery, 34 Printer/VPN, 35 Health/Metrics)

> **Volume audité** : ~6 980 LoC, **~177 frictions, ~32 P0 estimés**.
> Domaines : Email/Notification, Audit RGPD/SOC2, Feature flags, Orchestration Celery, Printer ESC/POS + VPN WireGuard, Health/Metrics Prometheus.
> **Constat fondamental** : la couche transverse est faite de théâtre. **AuditMiddleware** ouvre une transaction parallèle → audit perdu silencieusement quand l'audit échoue. **HMAC** ne couvre pas `changes` → falsifiable post-hoc. **`auto_suspend_uncertified`** est un no-op (compliance théâtre SOC2). **Relance** marque `sent` sans envoyer l'email. **`/metrics`** est public sans auth (reconnaissance attaquant + business data leak). **`/health`** ne détecte pas event loop bloqué (liveness ment, K8s ne redémarre jamais). **Queue `loyalty`** s'empile indéfiniment dans Redis (pas dans `task_routes`). Bug critique production identifié : F1058 (relance fictive). Patterns Bloc 3 (Outbox audit + EmailGateway) directement réapplicables.

## 6.1 Patterns transverses à éradiquer (au-delà Bloc 3+4+5)

| # | Pattern | Frictions | Conséquence |
|---|---|---|---|
| **TR-62** | SMTP synchrone bloquant `smtplib.SMTP()` | F848 | Worker FastAPI bloqué 500ms-3s/email. 100 emails simultanés = 5 min worker mort. Racine de F442, F294, F614, F1058. |
| **TR-63** | Pas de TLS/auth SMTP en prod (`starttls()`, `login()` absents) | F849 | Email clair → MITM. Relai externe (SendGrid/SES) impossible. |
| **TR-64** | `send_password_reset_email` HTML inline anglais hardcoded | F851, F867 | Drift i18n : le user paramètre français, reçoit anglais. |
| **TR-65** | `Notification` model legacy (Column style sync, pas de Mixins, FK manquante) | F850 | Convention CaroCorp violée. SQLAlchemy 2.0 strict cassera. |
| **TR-66** | `AuditMiddleware` ouvre TX séparée → audit perdu si DB pool exhausted | F1000, F1005 | RGPD Article 30 violé. Mutations existent sans trace. Pool exhaustion sous charge. |
| **TR-67** | HMAC ne couvre pas `changes` → falsifiable post-hoc | F1001 | Théâtre de sécurité. Attaquant DB-direct mute le `changes` JSON sans invalider HMAC. |
| **TR-68** | Login échec **non audité par middleware** (`/auth/login` exclu) | F1002 | Repose sur appel explicite oubliable. Brute-force passe sans trace. |
| **TR-69** | `SENSITIVE_PATTERNS` incomplets (manque reservations, MFA, devis, fidélité, sessions) | F1003 | Audit RGPD incomplet sur PII. |
| **TR-70** | Audit `description` + `changes` PII en clair | F1007, F1008 | Audit logs eux-mêmes deviennent source PII. |
| **TR-71** | Pas d'export RGPD Article 15 | F1015 | Droit d'accès = workflow manuel admin. |
| **TR-72** | Pas de purge >7 ans (Celery task absente) | F1016 | Croissance illimitée table audit → impact perf. |
| **TR-73** | Audit 4xx absent (`ATTEMPT_DENIED` non capturé) | F1019 | Forensics impossible sur tentatives malveillantes. |
| **TR-74** | Feature flag fail-safe ambigu (cache+DB down) | F1031 | Inversion sécurité possible : `disable_dangerous_feature` → DB down → feature redevient active. |
| **TR-75** | `hashlib.md5` pour bucketing rollout | F1032 | Flake8/Bandit security alert. |
| **TR-76** | Pas d'audit log feature flag CRUD | F1033 | Kill-switch sécurité activable sans trace. |
| **TR-77** | Queue `loyalty` mal routée (pas dans `task_routes`) | F1053 | Tasks loyalty s'empilent indéfiniment dans Redis. |
| **TR-78** | Mix sync/async/legacy DB sessions Celery (4 patterns) | F1054 | Dette technique massive. SQLAlchemy 2.0 strict cassera. |
| **TR-79** | `auto_suspend_uncertified` no-op compliance fail | F1055 | SOC2 §10 violé. Compliance théâtre. |
| **TR-80** | Relance marquée `sent` sans envoi email réel | F1058 | **Bug critique production**. Faux signal massif. Couvert par Bloc 3 EmailGateway. |
| **TR-81** | Print ticket sans nom_commerce silent (DB error) | F1059 | Ticket non-conforme légalement. |
| **TR-82** | Print endpoint sans `require_scope` | F1089 | RBAC contourné. DoS papier possible. |
| **TR-83** | Print sans audit log | F1090 | Preuve fiscale sans trace. |
| **TR-84** | `WireGuardClient` httpx **sync** dans handler async | F1091 | Threadpool exhausted si WG service lent → API entière inaccessible. |
| **TR-85** | Pas de connection pooling httpx (Client per-call) | F1092 | Handshake TCP+TLS chaque appel WG. Latence × 3. |
| **TR-86** | `WG_INTERNAL_API_KEY` plain header (pas mTLS) | F1094 | Sniffer sidecar compromis. Pas de rotation. |
| **TR-87** | `/metrics` public sans auth | F1122 | Reconnaissance attaquant + business data leak (réservations, conversions). |
| **TR-88** | Status page leak `EMERGENCY_BYPASS` | F1123 | Signal d'attaque exposé aux clients anonymes. |
| **TR-89** | Health check sync DB session dans app async | F1124 | Sous charge, latence health check 500ms → K8s redémarre pod inutilement. |
| **TR-90** | `/health` ne détecte pas event loop bloqué | F1125 | Liveness ment. K8s ne redémarre jamais un pod gelé. |
| **TR-91** | Cardinality blow-up via 404 paths arbitraires | F1126 | DoS Prometheus → OOM kill scraper. |
| **TR-92** | Pas de label `tenant_id` sur metrics RED | F1128, F1131 | Multi-tenancy invisible. SLO par tenant impossible. |
| **TR-93** | DegradedMode lit Redis chaque requête sans cache | F1133 | 1k req/s = 1k Redis GET/s pour la même donnée. |
| **TR-94** | Pas de DLQ Celery (task disparaît après retries) | F1068 | Aucune visibilité ops sur tâches mortes. |
| **TR-95** | Pas de Celery beat heartbeat | F1070 | Beat process meurt silencieusement → toutes tâches périodiques cessent sans alerte. |
| **TR-96** | Pas d'OpenTelemetry distributed tracing | F1138 | Debug latency cross-service (api → Celery → WG) aveugle. |
| **TR-97** | `db_queries_total`, `redis_commands_total` jamais incrémentés | F1127, F1141 | Théâtre observabilité. Dashboards Grafana vides. |

## 6.2 Architecture cible — patterns canoniques

### 6.2.1 `EmailGateway` Postmark async unifié (cohérent Bloc 3 Q18)
```python
# app/services/email/gateway.py
class EmailGateway(Protocol):
    async def send(self, payload: EmailPayload) -> EmailResult: ...

class PostmarkGateway:
    def __init__(self, server_token: str, http: AsyncClient): ...
    async def send(self, payload): ...

# Wrap NotificationService
class NotificationService:
    def __init__(self, gateway: EmailGateway, template_engine: Jinja2): ...
    async def send_password_reset(self, account_id, *, lang='fr'):
        ctx = await self._build_context(account_id, lang)
        body = self._template_engine.render(f'password_reset.{lang}.html.j2', ctx)
        return await self._gateway.send(EmailPayload(to=ctx.email, subject=ctx.subject, html=body))
```
- **Drop** `_send_email` sync. **Drop** HTML inline anglais.
- **Drop** import couplé `_DEFAULT_BRAND` from `services/invoice_pdf` (F856).
- Tous les emails passent par templates Jinja2 i18n `app/templates/emails/{key}.{lang}.html.j2`.
- `Customer.preferred_language: Mapped[str] = 'fr'` ajouté.
- **White-label per-tenant** (Q43=B verrouillé Bloc 7) : sender depuis `Tenant.brand_email_from` lookup par `tenant_id`. Chaque tenant = 1 signature DKIM/SPF (`Tenant.brand_dkim_domain`). Marveline = `noreply@marveline.fr`, Splendid = `noreply@splendid-events.fr`, MassaCorp Épi/Resto = `noreply@massacorp.fr`. Pas de concept "brand" intra-tenant.
- Celery task `send_email_task` async wrap autour gateway pour les batchs.
- **Résout** : TR-62, TR-63, TR-64.

### 6.2.2 `Notification` + `NotificationLog` v2.0 (drop legacy)
```python
class Notification(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """In-app notification (cloche UI)."""
    id: Mapped[int]
    tenant_id: Mapped[int]
    account_id: Mapped[int]  # FK accounts.id ondelete=CASCADE
    type: Mapped[str]
    title: Mapped[str]
    message: Mapped[str]  # EncryptedField (PII)
    link: Mapped[str | None]
    is_read: Mapped[bool] = False
    read_at: Mapped[datetime | None]
    
class NotificationLog(Base, TimestampMixin, TenantMixin):
    """Audit envois email/SMS/push (séparé de in-app)."""
    id: Mapped[int]
    tenant_id: Mapped[int]
    account_id: Mapped[int | None]
    customer_id: Mapped[int | None]
    channel: Mapped[str]  # email | sms | push | in_app
    template_key: Mapped[str]
    recipient: Mapped[str]
    gateway_message_id: Mapped[str | None]  # Postmark MessageID
    status: Mapped[str]  # pending | sent | bounced | failed
    error: Mapped[str | None]
    sent_at: Mapped[datetime | None]
```
- Bounce tracking : webhook Postmark → update `NotificationLog.status='bounced'` + flag `Customer.email_invalid=True` (F860).
- Footer RGPD unsubscribe link auto sur templates marketing (F859).
- Index `(tenant_id, account_id, is_read)` (F865).
- **Résout** : TR-65, F854, F859, F860.

### 6.2.3 Audit refondu : service-level + Outbox (drop AuditMiddleware mutations)
```python
# AuditMiddleware ne capture PLUS les mutations.
# Il garde uniquement les READ_SENSITIVE (côté lecture).

# Toutes les mutations passent par les services qui appellent :
async def update_customer(customer_id, payload, actor):
    async with db.begin():
        before = customer.to_audit_dict()
        # ... mutation
        after = customer.to_audit_dict()
        await audit_service.log_update(
            entity_type='Customer', entity_id=customer_id,
            before=before, after=after, actor=actor,
        )
        # Outbox event publié transactionnellement (Bloc 1 Q4)
```
- Si la mutation rollback, l'audit aussi (atomicité).
- Décorateur `@audit_action(entity='Customer')` factorise le pattern dans tous les services.
- **Résout** : TR-66, F1010 (changes capture côté service).

### 6.2.4 HMAC chaîné (blockchain ledger audit)
```python
class AuditLog(Base):
    # ...
    prev_hmac: Mapped[str | None]  # SHA-256 hex du précédent audit du même tenant
    hmac_signature: Mapped[str]    # SHA-256 hex couvrant TOUT
    
    @staticmethod
    def compute_hmac(prev_hmac, canonical_payload, key):
        msg = (prev_hmac or '') + json_canonical(canonical_payload)
        return hmac.new(key, msg.encode(), 'sha256').hexdigest()
```
- Le `canonical_payload` inclut `action, entity_type, entity_id, changes, description, account_id, tenant_id, request_id, created_at`.
- Insert d'un audit lit le dernier `hmac_signature` du tenant (advisory lock par tenant_id), calcule new_hmac, INSERT.
- DB trigger `BEFORE UPDATE OR DELETE ON audit_logs RAISE EXCEPTION` (cohérent Bloc 3 TR-7).
- Job nightly `verify_audit_chain_task` parcourt et alerte sur rupture chaîne.
- KMS-managed HMAC key avec versioning (`v1$hmac` format) — rotation safe.
- **Résout** : TR-67, F1001, F1011.

### 6.2.5 `SENSITIVE_PATTERNS` étendu + `ATTEMPT_DENIED` 4xx
```python
# app/constants/audit.py
SENSITIVE_READ_PATTERNS = [
    r'^/api/v1/customers/\d+',
    r'^/api/v1/customers/\d+/history',
    r'^/api/v1/invoices/\d+',
    r'^/api/v1/users/\d+',
    r'^/api/v1/reservations/\d+',
    r'^/api/v1/devis/\d+',
    r'^/api/v1/mfa/\w+',
    r'^/api/v1/sessions/\d+',
    r'^/api/v1/loyalty/members/\d+',
    r'^/api/v1/audit',  # méta-audit
]

# Capture 4xx auth/forbidden + 422 validation suspect
ATTEMPT_DENIED_STATUSES = {401, 403, 422}
```
- Middleware audite avec catégorie `ATTEMPT_DENIED` (avec masking password si POST /auth/login).
- Login échec : retirer `/auth/login` de `EXCLUDED_PATHS` + capture body avec masking.
- **Résout** : TR-68, TR-69, TR-73.

### 6.2.6 PII envelope encryption sur audit `changes` + `description`
- `EncryptedField(KMSContext)` sur `AuditLog.changes` (JSONB chiffré au repos) et `AuditLog.description`.
- Scope séparé `audit:read_pii` requis pour exposer en clair côté `GET /audit`.
- Auditeur sans `read_pii` voit `changes={"<encrypted>"}` + description masquée.
- Migration Celery `migrate_audit_pii_encryption_task`.
- **Résout** : TR-70, F1014.

### 6.2.7 Export RGPD Article 15
```python
@router.post('/me/export', dependencies=[Depends(require_authenticated)])
async def request_personal_data_export(format: Literal['csv', 'json']):
    task = export_personal_data_task.delay(account_id, format)
    return {'task_id': task.id, 'status': 'queued'}

# Celery task (async)
@celery_app.task
async def export_personal_data_task(account_id, format):
    # 1. Aggrège : Customer + Reservations + Invoices + AuditLog + LoyaltyMember
    # 2. Export ZIP signed S3 URL (24h TTL)
    # 3. Email user avec lien download
```
- **Résout** : TR-71.

### 6.2.8 Purge >7 ans automatique
```python
@celery_app.task
async def purge_audit_logs_older_than_7y_task():
    cutoff = now() - relativedelta(years=7)
    # Avant DELETE : verify_audit_chain (HMAC chaîne intact)
    # Backup S3 + DELETE
```
- Cron mensuel.
- Avant suppression, archive S3 chiffré (compliance possible audit ultérieur).
- **Résout** : TR-72.

### 6.2.9 Feature flag fail-safe explicite
```python
# app/constants/feature_flags.py
FALLBACK_VALUES: dict[str, bool] = {
    'mfa_enabled': True,                   # safe-by-default
    'dangerous_feature': False,
    'einvoicing_enabled': False,
    # ... tout flag ENRÔLÉ avec son fallback explicite
}

class FeatureFlagService:
    async def is_enabled(self, name, tenant_id):
        try:
            return await self._read_cache_or_db(name, tenant_id)
        except (RedisError, DBError):
            fallback = FALLBACK_VALUES.get(name)
            if fallback is None:
                logger.error('flag %s no fallback', name)
                return False
            metrics.feature_flag_fallback_total.labels(flag=name).inc()
            return fallback
```
- **Test invariant CI** : tout flag présent en DB doit avoir une entrée dans `FALLBACK_VALUES`. Sinon CI rouge.
- `hashlib.md5` → `hashlib.sha256` (drop crypto faible, F1032).
- **Résout** : TR-74, TR-75.

### 6.2.10 Audit Feature flag CRUD + history table
```python
class FeatureFlagHistory(Base, TimestampMixin, TenantMixin):
    flag_id: Mapped[int]
    actor_account_id: Mapped[int]
    field_changed: Mapped[str]  # is_enabled | rollout_pct | target_tenants
    value_before: Mapped[str]
    value_after: Mapped[str]
    reason: Mapped[str | None]
```
- Trigger `AFTER UPDATE ON feature_flags` insère row history.
- Audit log explicite via `audit_service.log_update` dans le service.
- `target_tenants` ARRAY → table M:N `feature_flag_tenants` avec FK `tenants.id ondelete=CASCADE` (drop ARRAY orphan, F1034).
- **Résout** : TR-76, F1039, F1034.

### 6.2.11 Celery : RabbitMQ broker + queue `loyalty` + standardisation async + DLQ natif + heartbeat (Q42=B verrouillé)
**Décision Q42=B** : migration broker Redis → RabbitMQ. Drop la queue Redis `dead_letter` (option A initiale). DLQ natif AMQP via `x-dead-letter-exchange`.

**Configuration Celery cible** :
```python
# celery_app.py
celery_app = Celery(
    'devup',
    broker=settings.CELERY_BROKER_URL,           # amqp://devup:***@rabbitmq:5672/devup_vhost
    backend=settings.CELERY_RESULT_BACKEND,      # redis://redis:6379/1 (résultats restent Redis)
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    timezone='Europe/Paris',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    task_acks_late=True,                         # Q42=B : message ack après succès task (fiabilité)
    worker_prefetch_multiplier=1,                # Q42=B : 1 message à la fois pour tasks longues
    worker_max_tasks_per_child=1000,
    task_default_queue='default',
    task_queues=(
        # Queues normales avec DLX RabbitMQ natif
        Queue('default',       Exchange('default'),       routing_key='default',
              queue_arguments={'x-dead-letter-exchange': 'dlx'}),
        Queue('notifications', Exchange('notifications'), routing_key='notifications',
              queue_arguments={'x-dead-letter-exchange': 'dlx'}),
        Queue('invoicing',     Exchange('invoicing'),     routing_key='invoicing',
              queue_arguments={'x-dead-letter-exchange': 'dlx'}),
        Queue('loyalty',       Exchange('loyalty'),       routing_key='loyalty',
              queue_arguments={'x-dead-letter-exchange': 'dlx'}),       # AJOUTÉ
        Queue('etl',           Exchange('etl'),           routing_key='etl',
              queue_arguments={'x-dead-letter-exchange': 'dlx'}),
        Queue('printing',      Exchange('printing'),      routing_key='printing',
              queue_arguments={'x-dead-letter-exchange': 'dlx'}),       # AJOUTÉ
        Queue('exports',       Exchange('exports'),       routing_key='exports',
              queue_arguments={'x-dead-letter-exchange': 'dlx'}),
        # DLQ : reçoit les messages morts via x-dead-letter-exchange
        Queue('dead_letter',   Exchange('dlx'),           routing_key='#'),
    ),
)

task_routes = {
    'app.tasks.notifications.*': {'queue': 'notifications'},
    'app.tasks.invoicing.*':    {'queue': 'invoicing'},
    'app.tasks.loyalty.*':       {'queue': 'loyalty'},     # AJOUTÉ
    'app.tasks.etl_tasks.*':     {'queue': 'etl'},
    'app.tasks.printing.*':      {'queue': 'printing'},    # AJOUTÉ
    'app.tasks.restaurant_export.*': {'queue': 'exports'},
}

# tools/check_celery_queues.py (CI)
def assert_routes_consumed():
    declared = set(route['queue'] for route in task_routes.values())
    consumed = set(get_worker_queues_from_compose())
    assert declared.issubset(consumed), f'queue mismatch: {declared - consumed}'
```

**Migration broker (Sprint dédié B6.S7)** :
1. Déploiement RabbitMQ parallèle Redis broker (Docker Compose `rabbitmq:3.13-management` + healthcheck).
2. UI RabbitMQ Management activée (port 15672) pour observabilité ops.
3. Drain progressif : workers existants vident la queue Redis ; nouveaux workers consomment RabbitMQ uniquement.
4. Switch `CELERY_BROKER_URL` env quand Redis queues vides.
5. Cleanup Redis queues anciennes.

**Reste sur Redis** : `CELERY_RESULT_BACKEND` (statuts/résultats tasks), cache app, sessions, rate limiter. Séparation broker (RabbitMQ) ≠ backend (Redis) standard Celery.

- **Standardisation async** : drop sync sessions. Pattern unique :
  ```python
  @celery_app.task
  def my_task(tenant_id, ...):
      return async_to_celery(_run_async, tenant_id, ...)
  
  async def _run_async(tenant_id, ...):
      async with AsyncSessionLocal() as db:
          # ...
  ```
  + `_WORKER_LOOP` persistant pour éviter recréer event loop.
- **DLQ natif RabbitMQ** : `dead_letter` queue reçoit automatiquement les messages morts (NACK + max_retries épuisés) via `x-dead-letter-exchange`. Métrique Prometheus `celery_dlq_total{task_name}` via consumer dédié qui lit DLQ + republie vers manual replay si admin valide.
- **Beat heartbeat** : task `beat_heartbeat_task` cron 1 min publie `celery_beat_alive_seconds` Gauge. AlertManager si pas de heartbeat depuis 2 min.
- **Jitter beat schedule** : `+- 30s` aléatoire pour éviter empilement à 09:00 UTC (F1083).
- `cleanup_expired_sessions_task` ajouté (F1076).
- **Résout** : TR-77, TR-78, TR-94, TR-95.

### 6.2.12 Hotfix `auto_suspend_uncertified` (compliance honnête)
- Décision Q39 : **soit** implémenter table `access_reviews` + suspension réelle ; **soit** retirer du beat schedule.
- Recommandation : implémenter (compliance SOC2 §10 promis aux clients).
- Implémentation : `AccessReview` model (review_id, account_id, reviewer_id, reviewed_at, decision: 'certified' | 'rejected') + `auto_suspend_uncertified` lit les accounts sans certification depuis 30 jours → `account.is_active=False` + `audit_service.log_action('USER_SUSPENDED_UNCERTIFIED')`.
- **Résout** : TR-79.

### 6.2.13 Print ticket : scope + audit + circuit breaker (Q41=B FR strict)
```python
@router.post('/print/ticket', dependencies=[Depends(require_scope(Scope.PRINTER_PRINT))])
async def print_ticket(
    payload: PrintTicketIn,
    principal: Account = Depends(get_current_principal),
):
    await audit_service.log_action(
        action='PRINT_TICKET_ENQUEUED',
        entity_type='Ticket', entity_id=payload.numero_ticket,
        ...,
    )
    task = print_ticket_task.delay(payload.dict(), principal.active_tenant_id)
    return {'task_id': task.id}

# Circuit breaker via Redis
class PrinterCircuitBreaker:
    async def call(self, host, port, fn):
        key = f'cb:printer:{host}:{port}'
        state = await redis.get(key)
        if state == 'OPEN':
            raise PrinterUnavailable('circuit open')
        try:
            result = await fn()
            await redis.delete(key)  # reset on success
            return result
        except PrintError:
            failures = await redis.incr(f'{key}:failures')
            if failures >= 3:
                await redis.setex(key, 60, 'OPEN')
            raise
```
- Audit en succès/échec dans la task Celery.
- **FR strict (Q41=B)** : `EUR` + `cp858` + virgule décimale française **hardcoded** assumés. Pas de paramètres `currency` ni `codepage`. Si expansion future (Sénégal Splendid, etc.) → refonte ad-hoc à ce moment-là.
- Ventilation paiement ticket : si `mode_paiement='mix'`, render fractions (F1097, conformité arrêté 28 mai 2019).
- Mention légale FR auto-conforme selon `Invoice.tva_regime` (F1108).
- **Résout** : TR-81, TR-82, TR-83.

### 6.2.14 `WireGuardClient` httpx async + connection pool + JWT signé
```python
class WireGuardClient:
    _http_client: AsyncClient | None = None
    
    @classmethod
    async def get_client(cls) -> AsyncClient:
        if cls._http_client is None:
            cls._http_client = AsyncClient(
                base_url=settings.WG_SERVICE_URL,
                timeout=10.0,
                limits=Limits(max_connections=20, max_keepalive_connections=10),
            )
        return cls._http_client
    
    def _build_auth_token(self, tenant_id, actor_id) -> str:
        # JWT RS256 signé court (5 min), claims tenant_id + actor_id
        return jwt_encode({'tid': tenant_id, 'aid': actor_id, 'exp': now() + 5*60},
                          settings.WG_JWT_PRIVATE_KEY)
    
    async def list_peers(self, tenant_id, actor_id):
        token = self._build_auth_token(tenant_id, actor_id)
        client = await self.get_client()
        resp = await client.get('/peers', headers={'Authorization': f'Bearer {token}'})
        # ...
```
- Endpoints `async def` uniformément.
- WG microservice valide JWT signé avec public key (rotation KMS safe).
- Tenant guard `peer_id` : avant retourner peer, vérifier `peer.tenant_id == request.tenant_id` côté WG service. Si pas garanti, ajouter check côté app.
- Retry policy + backoff exponential (F1101).
- **Résout** : TR-84, TR-85, TR-86.

### 6.2.15 `/metrics` auth mTLS (Q40=B verrouillé)
**Décision Q40=B** : mTLS pur via service mesh (Istio/Linkerd) ou nginx-ingress avec mTLS configuré. Drop totalement Basic auth + IP whitelist.

**Implémentation** :
```python
@router.get('/metrics')
async def metrics_endpoint(
    request: Request,
    _: None = Depends(verify_client_certificate),
):
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def verify_client_certificate(request: Request):
    """Vérifie le certificat client mTLS injecté par le service mesh."""
    # Service mesh (Istio) injecte X-Forwarded-Client-Cert
    # nginx-ingress avec ssl_verify_client on injecte ssl_client_s_dn
    cert_subject = request.headers.get('X-Forwarded-Client-Cert', '')
    if not cert_subject:
        raise HTTPException(401, 'mTLS client cert required')
    if not _matches_allowed_spiffe_id(cert_subject, settings.PROMETHEUS_ALLOWED_SPIFFE_IDS):
        raise HTTPException(403, 'unauthorized client cert')
```

**Infra requise (à coordonner avec roadmap ops DEVUP)** :
- Cluster K8s avec service mesh ou nginx-ingress mTLS-aware.
- `cert-manager` pour rotation auto certs serveur+clients.
- Prometheus scraper deployé avec client cert dans son `ServiceAccount` (volume mount cert-manager).
- SPIFFE ID whitelist via env `PROMETHEUS_ALLOWED_SPIFFE_IDS` (CSV).
- **Pas de** `tenant_settings` : `/metrics` est endpoint global infrastructure, credentials infra-level uniquement (pas tenant-scopés).

**Sprint impact** : Sprint B6.S6 = 2 sem au lieu de 1 (déploiement infra mTLS).
- **Résout** : TR-87.

### 6.2.16 Status page sanitize + health 100% async + cardinality whitelist
```python
@router.get('/health/status')
async def public_status():
    """Status PUBLIC — pas d'info sensible."""
    db_ok = await check_postgres_async(db)
    redis_ok = await check_redis_async(redis)
    if not db_ok or not redis_ok:
        return {'status': 'down'}
    # Pas de degradation_level exposé
    is_degraded = await DegradedModeService.is_degraded()
    return {'status': 'degraded' if is_degraded else 'operational'}

@router.get('/admin/health/status', dependencies=[Depends(require_scope(Scope.ADMIN_READ))])
async def admin_status():
    """Status ADMIN — détails complets."""
    return {
        'status': ...,
        'degradation_level': ...,
        'components': {...},
        'incidents': [...],
    }

@router.get('/health/live')
async def liveness():
    await asyncio.sleep(0)  # yield test : event loop bloqué → timeout
    return {'status': 'ok'}

# MetricsMiddleware : cardinality cap
def _normalize_path(path: str) -> str:
    for pattern, replacement in PATH_NORMALIZATION_PATTERNS:
        if pattern.match(path):
            return replacement
    return 'other'  # cap cardinality
```
- **Résout** : TR-88, TR-89, TR-90, TR-91.

### 6.2.17 Labels `tenant_id` cap + DegradedMode cache PUB/SUB
- `http_requests_total{method, path, status, tenant_id}` avec cap : si `tenant_id` non whitelisté (top 100 tenants actifs), label = `'other'`.
- `DegradedModeService` : LRU 5s + Redis SUBSCRIBE channel `degraded_mode_change` pour invalidation event-driven.
- **Résout** : TR-92, TR-93.

### 6.2.18 OpenTelemetry distributed tracing + db/redis instrumentation
```python
# app/core/tracing.py
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def init_tracing(app):
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    RedisInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
```
- Export OTLP → Tempo/Jaeger.
- Trace_id propagé api → Celery → WG via header `traceparent`.
- `db_queries_total` et `redis_commands_total` automatiquement incrémentés via instrumentation OTel + adapter custom.
- `celery_task_duration_seconds{task_name, status}` Histogram via Celery signals.
- **Résout** : TR-96, TR-97.

## 6.3 Architecture finale par domaine

| Domaine | Modules | Pattern appliqué |
|---|---|---|
| **Notification** | 27 | EmailGateway Postmark async, templates Jinja2 i18n, NotificationLog audit envois, bounce tracking, RGPD unsubscribe |
| **Audit** | 31 | Service-level dans TX métier (drop middleware mutations), HMAC chaîné blockchain + DB triggers immutability, SENSITIVE étendu, ATTEMPT_DENIED 4xx, PII encryption changes, export RGPD Article 15, purge >7y |
| **Feature flag** | 32 | Fail-safe explicite FALLBACK_VALUES, sha256, audit CRUD + history table, FK `feature_flag_tenants` M:N, LRU + PUB/SUB invalidation |
| **Celery** | 33 | **Broker RabbitMQ** (Q42=B), queue loyalty + printing routées + CI check, async sessions standardisées, **DLQ natif AMQP** via `x-dead-letter-exchange`, beat heartbeat, fanout per-tenant, jitter, cleanup_expired_sessions, auto_suspend réel |
| **Printer/VPN** | 34 | `require_scope(PRINTER_PRINT)` + audit log, circuit breaker Redis, WireGuard httpx async + pool + JWT signé court, **FR strict (Q41=B)** : EUR + cp858 hardcoded |
| **Health/Metrics** | 35 | **`/metrics` mTLS pur (Q40=B)** via service mesh, status page sanitize, health 100% async + yield test, cardinality whitelist, label tenant_id cap, OpenTelemetry tracing, db/redis instrumentation |

## 6.4 Migration ordonnée Bloc 6

| Sprint | Périmètre | Tests requis |
|---|---|---|
| **B6.S1** (1 sem) | **Hotfixes critiques** : F848 (Celery email task wrap NotificationService), F849 (TLS + auth SMTP), F1058 (relance email réel via EmailGateway), F1053 (queue loyalty routée), F1089 (require_scope print), F1055 décision Q39 (implémenter ou retirer beat) | Email envoyé asynchrone via Celery → 200 ; relance status='sent' uniquement si gateway 200 ; queue loyalty consommée par worker |
| **B6.S2** (2 sem) | Audit refondu : service-level + Outbox dans TX métier (drop middleware mutations) + HMAC chaîné blockchain + DB triggers immutability + SENSITIVE_PATTERNS étendu + ATTEMPT_DENIED 4xx + PII envelope encryption changes/description | UPDATE audit_logs via psql → exception ; chain integrity verify nightly ; auditeur sans `audit:read_pii` voit `changes='[encrypted]'` |
| **B6.S3** (1 sem) | Feature flag : fail-safe FALLBACK_VALUES (CI invariant) + sha256 + audit log CRUD + FeatureFlagHistory + table M:N feature_flag_tenants (drop ARRAY orphan) + LRU + Redis PUB/SUB invalidation | DB+Redis down → flag retourne FALLBACK ; modif flag → row history insérée ; `target_tenants` row déléguée |
| **B6.S4** (2 sem) | Celery refacto : standardisation async sessions (drop sync) + beat heartbeat + Prometheus celery_task_duration_seconds + jitter beat schedule + fanout per-tenant invoicing + cleanup_expired_sessions_task + advisory lock expire_points (cohérent Bloc 3). **NB : DLQ déplacée Sprint B6.S7 (RabbitMQ).** | beat down 2 min → AlertManager ; tasks invoicing fanout per-tenant en parallèle ; expire_points sans race |
| **B6.S5** (1 sem) | Print + VPN : audit log enqueue/result + circuit breaker Redis + httpx async pool WG + JWT signé court (rotation KMS) + tenant guard peer_id + ventilation paiement ticket + mention légale FR auto. **FR strict (Q41=B) : pas de prep multi-pays.** | imprimante offline 3 fails → CB ouvert 60s ; user A peut pas voir peer user B ; ticket mix card+espèces → ventilation render |
| **B6.S6** (2 sem) | Observability : **`/metrics` mTLS pur (Q40=B)** via service mesh ou nginx-ingress + cert-manager rotation + status page sanitize + health 100% async + yield test + cardinality whitelist (`'other'`) + label `tenant_id` cap top 100 + OpenTelemetry tracing (FastAPI+SQLA+Redis+Celery+httpx) + db/redis instrumentation auto + RGPD export Article 15 + purge >7y | `/metrics` 401 sans cert client ; client cert SPIFFE ID validé ; clients anonymes voient `status: 'operational'` (pas EMERGENCY_BYPASS) ; trace_id propagé api→Celery→WG ; export user → ZIP S3 link 24h |
| **B6.S7** (1 sem) | **Migration broker Redis → RabbitMQ (Q42=B)** : déploiement RabbitMQ 3.13-management parallèle Redis broker + healthcheck + UI Management port 15672 + drain progressif Redis queues + switch `CELERY_BROKER_URL=amqp://...` + DLQ natif via `x-dead-letter-exchange` + métrique `celery_dlq_total{task_name}` + cleanup Redis queues anciennes | Tasks Celery routées via RabbitMQ ; max_retries épuisé → message dans queue `dead_letter` ; UI Management accessible aux ops ; result_backend reste Redis |

**Total Bloc 6 : 10 semaines** (vs 9 prévues — +1 sem RabbitMQ Q42=B).

## 6.5 Questions à valider avant lock Bloc 6

| # | Question | Options | Recommandation |
|---|---|---|---|
| **Q36** | Migration AuditMiddleware → service-level | A) **Full migration** (drop middleware mutations, tout via services + Outbox)<br>B) Hybride (middleware fallback si service oublie l'appel)<br>C) Status quo (middleware orphelin TX) | **A** : architecture propre. Risque oubli service mitigé par décorateur `@audit_action` factorisé. |
| **Q37** | OpenTelemetry distributed tracing | A) **Activer maintenant** (Sprint B6.S6)<br>B) Attendre besoin ops urgent<br>C) Skip (surcharge dev) | **A** : multi-service distribué, debug latency aveugle sans. Coût bas (lib auto-instrument). |
| **Q38** | Export RGPD Article 15 | A) **Async via Celery + S3 signed URL 24h**<br>B) Sync StreamingResponse direct<br>C) Workflow manuel admin (status quo) | **A** : pour gros utilisateurs (5 ans d'historique = MB), sync HTTP timeout. Async safe. |
| **Q39** | `auto_suspend_uncertified` | A) **Implémenter réel** (table access_reviews + suspension)<br>B) Retirer du beat (compliance honnête, pas de cron qui ment)<br>C) Status quo (no-op, log warning) | **A** : SOC2 §10 promis aux clients. Implémentation bloque ~3 jours dev. |
| **Q40** | `/metrics` auth | A) **Basic auth + IP whitelist** (simple, environnement Docker)<br>B) mTLS pur (rigueur, prod K8s avec service mesh)<br>C) Reverse-proxy filtre côté infra (nginx) | **A** maintenant, **B** quand passage K8s + service mesh. |
| **Q41** | Multi-pays printer (codepage, currency, mention légale) | A) **Schema prêt maintenant** (FR uniquement actif, params Tenant.country/currency)<br>B) Strict FR jusqu'à expansion (refonte plus tard)<br>C) Implémentation complète multi-pays maintenant | **A** : préparation peu coûteuse, cohérent Bloc 3 e-invoicing prep, futur Splendid Sénégal éventuel. |
| **Q42** | DLQ Celery | A) **Redis-based simple** (queue `dead_letter` + manual replay endpoint)<br>B) RabbitMQ migration (plus robuste, mais migration broker complète)<br>C) Pas de DLQ (status quo) | **A** : Redis déjà infra, complexité minimale, suffit pour visibilité ops. RabbitMQ horizon 18 mois si besoin. |

## 6.6 Décisions verrouillées Bloc 6 (2026-04-27)

| # | Réponse | Conséquence architecture |
|---|---|---|
| **Q36** | **A** — Full migration audit service-level + Outbox | Drop AuditMiddleware sur les mutations (POST/PUT/PATCH/DELETE). Garde middleware sur READ_SENSITIVE seulement. Décorateur `@audit_action(entity='X')` factorise le pattern dans tous les services. CI invariant : tout service de mutation doit avoir un appel `audit_service.log_*` ou décorateur (AST check). |
| **Q37** | **A** — OpenTelemetry activé Sprint B6.S6 | Instrumentation FastAPI + SQLAlchemy + Redis + Celery + httpx via libs `opentelemetry-instrumentation-*`. Export OTLP → Tempo (open-source) ou Datadog si budget. Trace_id propagé api → Celery → WG via header `traceparent`. |
| **Q38** | **A** — Export RGPD async Celery + S3 signed URL 24h | `POST /me/export` enqueue task → `export_personal_data_task` génère ZIP (Customer + Reservations + Invoices + AuditLog + LoyaltyMember + …) → upload S3 chiffré → email user lien signed URL 24h TTL. Endpoint `GET /me/exports/{task_id}/status` pour suivi. |
| **Q39** | **A** — `auto_suspend_uncertified` implémenté réel | Création table `access_reviews` (review_id, account_id, reviewer_id, reviewed_at, decision). Task lit accounts sans certification depuis 30j → `account.is_active=False` + `audit_service.log_action('USER_SUSPENDED_UNCERTIFIED')`. Sprint B6.S1 (~3 jours dev). Compliance SOC2 §10 honnête. |
| **Q40** | **B** — mTLS pur sur `/metrics` | Décision forte : passage mTLS implique infra K8s + service mesh (Istio/Linkerd) ou nginx-ingress avec mTLS configuré. Plus rigoureux que Basic+IP. **Implication ops** : déploiement nouveau (Sprint B6.S6 = 2 sem au lieu de 1). Cert-manager pour rotation auto. Prometheus scraper avec client cert. **Cohérent avec Q40 = avenir K8s production-grade**. |
| **Q41** | **B** — Strict FR (drop schema multi-pays prep printer) | Drop `_fmt_cts(currency=...)` paramétré. Drop codepage configurable. `EUR` + `cp858` + virgule décimale française **hardcoded** assumés. Mention légale FR auto selon `Invoice.tva_regime`. Si expansion future (Sénégal Splendid, etc.) → refonte ad-hoc à ce moment-là, pas de prep maintenant. **Simplifie Sprint B6.S5**. |
| **Q42** | **B** — RabbitMQ migration (drop Redis broker) | **Migration broker majeure**. Conséquences : (1) nouveau service infra `rabbitmq` (Docker Compose + healthcheck) ; (2) `CELERY_BROKER_URL=amqp://...` ; (3) résultats backend reste Redis (séparation broker ≠ backend) ; (4) DLQ natif RabbitMQ via `x-dead-letter-exchange` ; (5) Celery `task_acks_late=True` + `worker_prefetch_multiplier=1` pour fiabilité ; (6) UI RabbitMQ Management activé pour ops ; (7) migration ordonnée : déploiement RabbitMQ parallèle Redis broker, drain Redis queues, switch progressif. **Risque** : plus complexe que Redis pour ops simple. **Justification** : robustesse production-grade alignée Q40 mTLS. **Sprint dédié B6.S7** (1 sem) ajouté pour migration. |

**Bloc 6 verrouillé. Total : 10 semaines de migration (vs 9 prévues — +1 sem RabbitMQ).**

**Cumul après 6 blocs verrouillés** (séquentiel) : 48 + Bloc 6 (10) = **58 semaines de migration**, ~1154 frictions résorbées (couverture intégrale).

---

# Bloc 7 — Refonte sémantique DEVUP / vertical / tenant (clarification 2026-04-27)

> **Décision majeure user 2026-04-27** : "FUTUR PROJ" est la plateforme **DEVUP** (société de développement, SIRET 99903696500013), pas Marveline. Marveline / Épicerie / Restaurant ne sont pas des "apps" enum fixes — ce sont des **modèles métier (verticals)** dont chaque instance = 1 tenant client. Le SaaS DEVUP héberge N tenants regroupés par M verticals.

## 7.0 Questions à valider Bloc 7

| # | Question | Options | Recommandation |
|---|---|---|---|
| **Q43** | Marveline + Splendid : 1 ou 2 tenants ? | A) **1 seul tenant** Marveline avec 2 brands (`brand_code='marveline'`/`'splendid'`). Justifié si entité juridique commune.<br>B) **2 tenants distincts** `marveline` + `splendid`. Catalogues 100% séparés. Drop `brand_code` Bloc 4.<br>C) Configurable par déploiement (les 2 patterns coexistent). | **B** : entités juridiques séparées, catalogues séparés, comptabilité séparée. Cohérent avec multi-tenant DEVUP. |
| **Q44** | Header AppSelector | A) **DEVUP marque universelle** (tu présentes la plateforme à tes clients). Header "DEVUP — Plateforme SaaS" + sélecteur tenant.<br>B) **White-label per-tenant** (chaque client voit "Marveline" / "MassaCorp" sans mention DEVUP).<br>C) **Hybride** : white-label par défaut côté UI client + footer discret "Powered by DEVUP". | **A+C** : DEVUP visible côté admin/AppSelector page racine, white-label per-tenant côté UI client + footer discret. |
| **Q45** | Méthodologie de finalisation | A) Réécrire architecture-cible.md avec sémantique DEVUP/vertical/tenant en révisant les sections Bloc 1+2+4 antérieures.<br>B) Finaliser Bloc 6 d'abord, puis section dédiée `## 7. Refonte sémantique` qui clarifie tout en bloc.<br>C) Note explicite la clarification dans une section et continuer. | **A+C** : refonte sections Bloc 1-4 + section 7 dédiée + tableau §7.6 listant les révisions à appliquer. |

## 7.0bis Décisions verrouillées Bloc 7 (2026-04-27)

| # | Réponse | Conséquence architecture |
|---|---|---|
| **Q43** | **B** — 2 tenants distincts Marveline + Splendid | Drop **intégral** `brand_code` (Product/Category/Bundle/Collection) + `Tenant.is_multi_brand` + header `X-Brand-Code`. Catalogue strictement per-tenant (cohérent Bloc 5 Q29=A). Marveline et Splendid ont 2 ID tenants distincts, 2 catalogues, 2 comptabilités, 2 signatures DKIM (`marveline.fr` et `splendid-events.fr`). Migration Sprint **B7.S2** : drop colonnes + cleanup endpoints + migration data si actuellement multi-brand intra-tenant. **Invalide Q24=A Bloc 4**. |
| **Q44** | **A+C** — DEVUP marque universelle (admin) + white-label hybride (client) | (A) Page racine `/` post-login = AppSelector listant les `TenantMembership` du user, header "DEVUP — Plateforme SaaS", sélecteur tenant groupé par vertical. Pour superadmins DEVUP : bandeau admin "DEVUP — [vertical]" visible. (C) Côté UI client après sélection tenant : white-label complet (`tenant.brand_display_name` + `brand_logo_url`), footer discret "Powered by DEVUP" (lien commercial). Path frontend : `/{tenant_app_code}/...`. Cookie `devup_session` cross-tenant + `devup_active_tenant_id` pin. **Frontend monorepo** : 1 module React **par vertical** (pas par app_code). |
| **Q45** | **A+C** — Refonte sections Bloc 1-4 + section 7 dédiée + révisions §7.6 | §7.6 liste les révisions à appliquer dans tous les blocs antérieurs. Sections marquées `[REVU 2026-04-27 — obsolète QXX]` directement dans leur bloc d'origine. Évite la confusion d'un doc à 2 sources de vérité. |

## 7.1 Modèle conceptuel verrouillé

```
DEVUP (SIRET 99903696500013 — opérateur SaaS)
  ├── Verticals (modèles métier extensibles)
  │     ├── 'location'           — événementiel/vaisselle/mobilier (Marveline, Splendid)
  │     ├── 'epicerie'           — POS épicerie alimentaire (MassaCorp Épi, futurs clients)
  │     ├── 'restaurant'         — cuisine + commandes + tables (MassaCorp Resto, L'Incontournable, …)
  │     ├── 'autour_de_table'    — nouveau modèle prévu (catalogue + packs spécifiques)
  │     └── … (extensible : ajouter un vertical = 1 migration + module React)
  │
  └── Tenants (1 instance = 1 client)
        ├── tenant_id=2  vertical='location'    app_code='marveline'        country='FR'
        ├── tenant_id=3  vertical='location'    app_code='splendid'         country='FR'
        ├── tenant_id=4  vertical='epicerie'    app_code='massacorp_epi'    country='FR'
        ├── tenant_id=5  vertical='restaurant'  app_code='massacorp_resto'  country='FR'
        ├── tenant_id=6  vertical='autour_de_table' app_code='atdt'         country='FR'
        ├── tenant_id=7  vertical='epicerie'    app_code='client_x_epi'     country='FR'  (futur)
        └── …
```

## 7.2 Q43=B verrouillé — Marveline + Splendid = 2 tenants distincts

**Conséquence directe** : le concept `brand_code` introduit en Bloc 4 (Q24=A `NULL = visible toutes brands`) **devient obsolète** pour le multi-brand cross-tenant.

**Réinterprétation Bloc 4 Q24** :
- **Drop** `Product.brand_code`, `Category.brand_code`, `Bundle.brand_code`, `ProductCollection.brand_code`.
- Chaque tenant possède son catalogue propre (cohérent Bloc 5 Q29=A — référentiel ETL split per-tenant).
- Si Marveline et Splendid veulent partager une partie de leur catalogue (ex: chaises Louis XV identiques), **mécanisme à venir** : table `catalogue_shared_template` (templates de produits réutilisables) cross-tenant en read-only seed (M00 pattern), mais **PAS** de partage runtime — chaque tenant copie le template à provisioning.
- Le concept "multi-brand" n'existe plus que pour la **différenciation visuelle/email** : chaque tenant a sa propre signature DKIM/SPF, ses propres templates email, son propre logo.

**`Tenant` schema cible** (révision Bloc 1) :
```python
class Tenant(Base, TimestampMixin, SoftDeleteMixin):
    id: Mapped[int]
    app_code: Mapped[str]               # UNIQUE — identifiant instance ('marveline', 'splendid', 'massacorp_epi', …)
    vertical: Mapped[str]               # enum extensible ('location', 'epicerie', 'restaurant', 'autour_de_table', …)
    country_code: Mapped[str]           # 'FR' strict (Q3 Bloc 1)
    legal_name: Mapped[str]             # raison sociale (Marveline SARL, Splendid Events SAS, MassaCorp)
    siret: Mapped[str | None]
    vat_number: Mapped[str | None]
    
    # White-label settings (Q44=A+C : DEVUP visible côté admin, footer discret côté client)
    brand_display_name: Mapped[str]     # 'Marveline', 'Splendid Events'
    brand_logo_url: Mapped[str | None]
    brand_email_from: Mapped[str]       # 'noreply@marveline.fr', 'noreply@splendid-events.fr'
    brand_dkim_domain: Mapped[str]
    brand_primary_color: Mapped[str]    # '#A52A2A'
    
    # Settings JSONB (TVA defaults, RFM thresholds, deposit policy, etc.)
    settings: Mapped[dict]
    
    # E-invoicing (Bloc 3 Q19) prep
    peppol_id: Mapped[str | None]
    chorus_pro_id: Mapped[str | None]
    
    __table_args__ = (
        UniqueConstraint('app_code', name='uq_tenant_app_code'),
        CheckConstraint("vertical IN ('location', 'epicerie', 'restaurant', 'autour_de_table')",
                        name='ck_tenant_vertical'),
        # vertical CHECK extensible : nouvelle migration ajoute valeurs
    )
```

**Migration data Bloc 1+2+4 (révisée)** :
- `Tenant` table existante : ajouter colonne `vertical NOT NULL` (backfill : `marveline/splendid → 'location'`, `epicerie → 'epicerie'`, `restaurant → 'restaurant'`).
- Drop CHECK enum existant `app_code IN ('marveline', 'epicerie', 'restaurant', 'lesplendid')` → remplacer par UNIQUE + CHECK regex `^[a-z][a-z0-9_]+$`.
- Splendid : provisionner comme **tenant distinct** depuis Marveline (migration data si actuellement multi-brand intra-tenant — à confirmer audit data).

## 7.3 RBAC `vertical`-scoped (révision Bloc 2)

Les scopes RBAC (cohérent Bloc 2 Q9=A — ROLE_SCOPES_FALLBACK) sont par **vertical**, pas par `app_code` :
- `location:read`, `location:write`, `location:admin` — applicable à tous tenants `vertical='location'` (Marveline, Splendid, futurs).
- `epicerie:*`, `restaurant:*`, `autour_de_table:*` — idem.
- Le scope est résolu dans le JWT selon le tenant courant : `Account → TenantMembership(tenant_id) → vertical → scopes vertical:*`.

**`TenantMembership.role`** reste 6 rôles fixes (Bloc 2 Q9=A). Pas changé.

## 7.4 AppSelector frontend (Q44=A+C verrouillé)

> **Q44=A+C — DEVUP marque universelle + white-label hybride**.

```
┌──────────────────────────────────────────────────────────────┐
│  DEVUP — Plateforme SaaS (header admin / AppSelector page)  │
│  Bonjour [user.first_name]                                   │
│                                                              │
│  Vos tenants accessibles :                                   │
│    📍 Location                                               │
│       └─ Marveline (FR)         → load /location app        │
│       └─ Splendid Events (FR)   → load /location app         │
│                                                              │
│    🏪 Épicerie                                               │
│       └─ MassaCorp Épicerie     → load /epicerie app         │
│                                                              │
│    🍽️ Restaurant                                             │
│       └─ MassaCorp Restaurant   → load /restaurant app       │
│       └─ L'Incontournable       → load /restaurant app       │
│                                                              │
│    🪑 Autour de Table (NEW)                                  │
│       └─ Atdt Showroom         → load /autour_de_table app  │
└──────────────────────────────────────────────────────────────┘

Côté UI client (après sélection tenant) :
┌──────────────────────────────────────────────────────────────┐
│  [Logo Marveline]    Marveline — Tableau de bord            │
│  ...                                                         │
│  ...                                                         │
│  ─────────────────────────────────────────────────────────  │
│                                Powered by DEVUP   ← discret │
└──────────────────────────────────────────────────────────────┘
```

**Implémentation** :
- Frontend monorepo : 1 module React **par vertical** (pas par app_code). Le module `vertical/location/` sert pour Marveline ET Splendid avec branding dynamique (logo, couleur, nom) lu depuis `tenant.brand_*`.
- Page racine `/` (post-login) = AppSelector listant les `TenantMembership` du user. Si 1 seul → redirect direct au tenant. Si N → choix.
- Header admin DEVUP : bandeau "DEVUP — [vertical]" visible uniquement aux users avec `role='superadmin'` (ops DEVUP internes).
- Header client : white-label `tenant.brand_display_name` + logo. Footer "Powered by DEVUP" discret (lien vers page DEVUP commercial).
- Path frontend : `/{tenant_app_code}/...` (ex: `/marveline/reservations`, `/massacorp_resto/commandes`). Plus de `/restaurant/*` global — c'est `/massacorp_resto/*` (instance) et le React module location est chargé via `tenant.vertical`.
- Cookie SSO `devup_session` (cross-tenant authent) + cookie scope `devup_active_tenant_id` qui pin le tenant courant.

## 7.5 Provisioning d'un nouveau tenant client

Workflow DEVUP (toi en tant qu'éditeur SaaS) :
```
POST /admin/devup/tenants/provision
  body: {
    app_code: 'client_x_resto', vertical: 'restaurant',
    legal_name: 'Client X SAS', country_code: 'FR',
    brand_display_name: 'Client X', brand_logo_url: 'https://...',
    brand_email_from: 'noreply@clientx.fr', brand_dkim_domain: 'clientx.fr',
    brand_primary_color: '#A52A2A',
    admin_account_email: 'admin@clientx.fr',
    # Settings tenant (Bloc 3 verrouillés)
    deposit_policy: { default_pct: 0.30, requires_deposit: true },     # Q14=C
    devis_default_expiry_days: 30,                                     # Q17=D
    rfm_thresholds: { champion_recency: 30, champion_frequency: 5, ... },  # Q27=B
    postmark_server_token: '<KMS encrypted>'                           # Q18=A
  }
  →
  Atomic transaction (Bloc 1 Q4 Outbox) :
    1. INSERT tenants (id=auto, vertical, app_code, brand_*, country='FR', …)
    2. INSERT tenant_settings (rfm_thresholds, default_deposit_pct, devis_default_expiry_days,
                                tva_rate_default selon vertical, postmark_server_token KMS, …)
    3. Seed defaults vertical-specific :
       - location  : seed Category (20 codes location, tva_rate=0.20 chacun), Tenant.settings['tva_rate_default']=0.20
       - epicerie  : seed Category (91 codes alimentaire copiés depuis categorie_produit_seed M00 read-only,
                                     tva_rate=0.055 default), Tenant.settings['tva_rate_default']=0.055
       - restaurant: seed Category alimentaire + types_preparation defaults (cf. Bloc 5),
                     Tenant.settings['tva_rate_default']=0.10 (TVA restauration sur place)
       - autour_de_table : seed catalogue spécifique vertical
    4. CREATE Account admin + TenantMembership(role='admin')
    5. Generate password reset token + Send welcome email via EmailGateway (Q18=A Postmark)
    6. Outbox event 'TenantProvisioned' → notification ops DEVUP (audit log + Slack/email DEVUP)
```

**Time-to-onboard nouveau client** = ~10 minutes (au lieu de migration manuelle Alembic actuellement). Aligné Bloc 1 Q1=A (Foundations re-découpé) + Bloc 5 Q29=A (catalogue split per-tenant).

## 7.6 Impact sur les blocs 1-6 (révisions à appliquer)

| Bloc | Section impactée | Révision | État |
|---|---|---|---|
| Bloc 1 | Décisions structurantes Q3 | Reformuler "Multi-brand France maintenu" → "Multi-tenant France maintenu" + identité tenant-scopée | ✅ Appliqué |
| Bloc 1 | §1.2.1 "Ce qui disparaît" | Ajouter `core/health.py`, `core/metrics.py`, `core/logging.py`, `core/slow_query.py` migrations vers nouveaux dossiers | ✅ Appliqué |
| Bloc 1 | §1.2.5 `app/constants/loyalty.py` | Préciser "RÉDUIT" (pas SUPPRIMÉ intégralement) — caps anti-fraude conservés | ✅ Appliqué |
| Bloc 1 | `Tenant` schema | Ajouter `vertical NOT NULL`, drop CHECK enum strict `app_code`, élargir `app_code` à UNIQUE + regex `^[a-z][a-z0-9_]+$`, ajouter `brand_*` colonnes | ⏳ Sprint B7.S1 |
| Bloc 1 | Provisioning atomique (Q1=A) | Étendre seed vertical-specific (4 verticals, extensible) — détaillé §7.5 | ✅ Spécifié §7.5 |
| Bloc 2 | Décisions Q6/Q9 | Reformuler "multi-brand" → "multi-tenant" / "verticals" | ✅ Appliqué |
| Bloc 2 | §2.6 Multi-brand identity | Renommé "Identity per-tenant propagée (white-label)" — DKIM domain par tenant | ✅ Appliqué |
| Bloc 2 | §2.3 RBAC scopes | Confirmer scopes par `vertical:*` (location, epicerie, restaurant, autour_de_table) — pas par `app_code`. Table `auth_app_scopes` renommée `auth_vertical_scopes` | ⏳ Sprint B7.S1 |
| Bloc 3 | §3.2.6 Conversion Devis→Résa | Q12=A : Invoice **émise** (pas draft) à conversion | ✅ Appliqué |
| Bloc 3 | §3.2.12 EmailGateway | Drop "Multi-brand : Marveline vs Splendid". Reformulé "white-label per-tenant" | ✅ Appliqué |
| Bloc 3 | §3.2.13 caps fidélité | Drop "à confirmer Q15/Q16" — verrouillés A et B | ✅ Appliqué |
| Bloc 3 | §3.6 Q12 | Note revirement A vs reco initiale B documentée | ✅ Appliqué |
| Bloc 3 | §3.6 Q18 DKIM | Domaine par tenant (1 tenant = 1 domaine), drop `carocorp.fr` non listé | ✅ Appliqué |
| Bloc 4 | §4.1 TR-38 | "à confirmer périmètre" tranché — couvert §6.2.1 | ✅ Appliqué |
| Bloc 4 | §4.2.4 `brand_code` | **OBSOLÈTE Q43=B** annoté + drop intégral colonnes + drop `Tenant.is_multi_brand` + drop header `X-Brand-Code` | ✅ Annoté, drop sprint B7.S2 |
| Bloc 4 | §4.2.5 `PricingService` | Renommé `PricingEngine` (cohérent code source + Bloc 3 §3.2.4) | ✅ Appliqué |
| Bloc 4 | §4.3 + §4.4 B4.S3 | Annotations OBSOLÈTE brand_code + reformulation tests | ✅ Appliqué |
| Bloc 4 | §4.6 Q24 | Annoté OBSOLÈTE Bloc 7 | ✅ Appliqué |
| Bloc 5 | §5.2.15 `VariantePlat.tva_rate_override` | Drop colonne non décidée — exception passe par `Product.tva_rate_override` (Bloc 4 §4.6 Q23) | ✅ Appliqué |
| Bloc 5 | Routing TAIYAT INCONTOURNABLE/NOUTAM | Toujours valide : ETL TAIYAT route selon `target_tenant_id` (vertical='restaurant' vs 'epicerie') — extensible à futurs tenants | ✅ Aligné |
| Bloc 6 | §6.2.1 EmailGateway | "Multi-brand sender Marveline/Splendid" → "white-label per-tenant" | ✅ Appliqué |
| Bloc 6 | §6.2.11 Celery DLQ | DLQ Redis → DLQ natif RabbitMQ (Q42=B) | ✅ Appliqué |
| Bloc 6 | §6.2.13 Print ticket | `UserCompat` → `Account` Principal + drop multi-pays prep (Q41=B FR strict) | ✅ Appliqué |
| Bloc 6 | §6.2.15 `/metrics` auth | Basic+IP → mTLS pur (Q40=B) + drop typo "Postmark" + drop `tenant_settings` (creds globaux) | ✅ Appliqué |
| Bloc 6 | §6.4 sprints | Ajout B6.S7 RabbitMQ migration (1 sem) + total 10 sem | ✅ Appliqué |
| Bloc 6 | §6.3 tableau récap | Annotations Q40=B mTLS, Q41=B FR strict, Q42=B RabbitMQ | ✅ Appliqué |
| Bloc 6 | AppSelector frontend | Nouveau composant à créer. Pas dans les modules audités (frontend = autre repo). À ajouter dans Sprint B7.S3 (~2 sem effort) | ⏳ Sprint B7.S3 |

## 7.7 Sprint additionnel B7 (refonte sémantique)

| Sprint | Périmètre | Tests requis |
|---|---|---|
| **B7.S1** (1 sem) | Migration `Tenant.vertical NOT NULL` + backfill + drop CHECK enum app_code + RBAC scope mapping `vertical:*` | Tenant marveline → vertical='location' ; user marveline a `location:*` dans JWT pas `marveline:*` |
| **B7.S2** (1 sem) | Drop `brand_code` Catalogue (Product/Category/Bundle/Collection) + migration data + cleanup endpoints | Repository `WHERE brand_code = X` supprimé partout ; tests CI invariant : aucun `brand_code` dans schemas |
| **B7.S3** (2 sem) | Refonte AppSelector frontend : page racine listant `TenantMembership` groupés par vertical + white-label per-tenant + footer "Powered by DEVUP" | User avec 3 memberships (Marveline + MassaCorp Épi + MassaCorp Resto) voit 3 cards groupées par vertical |
| **B7.S4** (1 sem) | Provisioning workflow `POST /admin/devup/tenants/provision` + seed vertical-specific + welcome email | Provisioner tenant 'client_x_resto' en 10 min via API, admin reçoit email setup |

**Total Bloc 7 : 5 semaines** (peut paralléliser partiellement avec Bloc 6).

## 7.8 Diagramme Gantt + recalcul effort total

**Total séquentiel arithmétique** : Bloc 1 (10) + Bloc 2 (10) + Bloc 3 (10) + Bloc 4 (9) + Bloc 5 (9) + Bloc 6 (10) + Bloc 7 (5) = **63 semaines** (~14,5 mois) en séquentiel pur, équipe 1 dev backend.

**Plan parallélisé recommandé (équipe 2-3 dev backend + 1 dev frontend + 1 ops)** :

```
Semaine    1...10....20....30....40....45
           ├─── Bloc 1 ───┤                              foundations bloquant tout
                          ├─── Bloc 2 ───┤               IAM bloquant Bloc 3+
                                         ├─── Bloc 3 ───┤  ledger + money (dev1)
                                         ├─── Bloc 4 ───┤  catalogue (dev2)
                                         ├─── Bloc 5 ───┤  multi-app (dev3, après hotfix Sprint1)
                                                    ├──── Bloc 6 ────┤  cross-cutting (dev1+ops)
                                                    ├── Bloc 7 ───┤    sémantique DEVUP (dev2+frontend)
```

**Total parallélisé réaliste** : **~42-45 semaines** (~10-11 mois) avec 3 devs backend en parallèle sur Bloc 3/4/5 + ops K8s+RabbitMQ pendant Bloc 6 + frontend pendant Bloc 7.S3 (AppSelector).

**Dépendances critiques (séquentielles obligatoires)** :
- Bloc 1 (Foundations) **bloque** Bloc 2 (auth_factor s'appuie sur core/auth/ refondu)
- Bloc 2 (Identity) **bloque** Bloc 3-6 (RBAC scopes, MFA, sessions)
- **Sprint 1 hotfixes** (cross-blocs B3.S1 + B5.S1 + B6.S1) **bloque tout feature work** — F906 + F1058 + F870 + auto_suspend critiques production

**Indépendances exploitables** :
- Bloc 3 ↔ Bloc 4 ↔ Bloc 5 partiellement parallélisables (domaines métier indépendants)
- Bloc 7 ↔ Bloc 4 partiellement parallélisables (refonte sémantique tenant ≠ corrections catalogue, sauf B7.S2 drop brand_code qui dépend de B4.S3)
- Bloc 6 ↔ Bloc 7 parallèles (cross-cutting ops vs sémantique)

**Cumul global révisé** : **63 semaines séquentielles** (~14,5 mois) ou **42-45 semaines parallélisées** (~10-11 mois) avec équipe 3 devs + 1 ops + 1 frontend.

---

# 🎯 Synthèse globale finale (2026-04-27)

## Décisions architecturales verrouillées

**45 questions répondues** sur 7 blocs (Q1-Q45 + sub-décisions transverses).

**~1154 frictions** identifiées sur l'audit code → **~140 P0 bloquants** identifiés → **plan de migration en 7 blocs / 36 sprints / 63 semaines séquentiel ou ~42-45 semaines parallélisé** (cf. §7.8 diagramme Gantt).

**Patterns canoniques transverses introduits** (à appliquer partout) :
1. **`FSM` helper class** + matrice transitions DB-enforced (Bloc 3) — éradique 7+ FSM bypass
2. **Advisory locks systématiques** (`pg_advisory_xact_lock`, `with_for_update`) — éradique 5+ race conditions ledger
3. **`tva_rate_snapshot NOT NULL`** sur toutes lignes facturables — élimine fallback 0.20 hardcoded
4. **Outbox pattern** pour audit transactionnel (Bloc 1 Q4)
5. **DB triggers `BEFORE UPDATE/DELETE RAISE EXCEPTION`** sur ledgers (PointsLedger, RevenueLedger, PaymentLedger, Invoice, AuditLog)
6. **HMAC chaîné blockchain** sur AuditLog — drop théâtre sécurité
7. **`PricingEngine` unifié** (cumul additif, fusion engine + simulate) — drop divergence engine vs simulate
8. **`StockItem` source unique de vérité** + view matérialisée — drop 3 sources contradictoires
9. **`Category` FK obligatoire** + cycle prevention — drop CHECK enum 20 valeurs
10. **PII envelope encryption** (KMS) sur `notes`, `description`, `contact_name`, audit `changes`
11. **`reference UNIQUE per-tenant`** (drop UNIQUE global cross-tenant)
12. **`relativedelta(months=N)`** partout (drop `timedelta(days=30 * N)`)
13. **`EmailGateway` Postmark async** — drop SMTP sync bloquant (résout 4 frictions racines)
14. **Audit service-level dans TX métier** — drop AuditMiddleware orphelin
15. **OpenTelemetry distributed tracing** (FastAPI + SQLA + Redis + Celery + httpx)
16. **Référentiel ETL `tenant_id NOT NULL`** — drop catalogue cross-tenant fuite
17. **Triggers DB cross-tenant validation** (InternalTransfer, IngredientEpicerieMapping, TransferRequest)
18. **Celery tasks tenant-aware obligatoire** + linter CI + advisory lock idempotence
19. **`Tenant.vertical`** schema extensible — drop enum 4 apps fixes (Bloc 7)
20. **DEVUP white-label hybride** — drop concept "multi-brand intra-tenant"

## Risques & dépendances majeures

- **Sprint B5.S1 critique** : 3 hotfixes production (F906 marmite cassée, F1058 relance fictive, F870 vente check_stock) — à livrer en priorité absolue.
- **Migration RabbitMQ (Q42=B)** : risque ops élevé. Période de coexistence Redis broker + RabbitMQ + drain progressif.
- **Migration mTLS `/metrics` (Q40=B)** : nécessite infra K8s + service mesh. À aligner avec roadmap infra DEVUP.
- **Migration `Product.category` → FK + drop `brand_code`** : risque data migration sur 200+ produits Marveline. Sprint B4.S3 + B7.S2 séquentiels.
- **Compliance SOC2** : `auto_suspend_uncertified` réel en B6.S1 + chain audit verify B6.S2 — préparation audit externe possible Q3 2026.

## Ordre de migration recommandé (priorité métier)

1. **Sprint 1 (semaine 1)** : Hotfixes critiques cross-blocs (B3.S1 + B5.S1 + B6.S1 fusionnés) — **STOP TOUT FEATURE** jusqu'à livraison
2. **Sprints 2-12 (Bloc 3 + Bloc 5)** : Ledger & Money + Multi-app correctness — fondations métier solides
3. **Sprints 13-21 (Bloc 4 + Bloc 7)** : Catalogue/Stock + sémantique DEVUP — peut paralléliser
4. **Sprints 22-31 (Bloc 1 + Bloc 2)** : Foundations + Identity refonte — moins urgent, gros effort
5. **Sprints 32-41 (Bloc 6)** : Cross-cutting observability + audit refondu

## Conclusion

L'audit révèle un système **fonctionnel mais structurellement fragile** : 1154 frictions, ~140 P0 bloquants, 23 patterns transverses canoniques à introduire. La cible est **scalable** (multi-tenant DEVUP avec verticals extensibles), **conforme** (RGPD Article 30 réel + SOC2 §10 honnête + e-invoicing UE prêt), **observable** (OpenTelemetry + métriques tenant-aware + audit blockchain), **résiliente** (FSM partout + advisory locks + DLQ RabbitMQ + circuit breakers).

**Le plan en 7 blocs est exécutable sur ~10-11 mois (parallélisé)** ou ~14-15 mois (séquentiel pur) avec une équipe de 2-3 dev backend + 1 dev frontend + 1 ops. Cf. §7.8 pour le diagramme Gantt et les dépendances. Les dépendances critiques sont les hotfixes Sprint 1 (production cassée) et la migration mTLS/RabbitMQ (infra K8s à mettre en place en parallèle des Blocs 3-5).

**Architecture-cible.md verrouillée 2026-04-27.** Document de référence pour toute décision architecturale future.
