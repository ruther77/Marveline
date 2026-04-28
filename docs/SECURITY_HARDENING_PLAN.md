# Plan de durcissement securite — CaroCorp / Marveline

Audit 2026-03-21. Decisions architecture actees. Code final pour chaque correction.
Aucun "a verifier", "considerer", "plus tard". Pret a executer de bout en bout.

Liste nettoyee : P1-09 (CSRF TTL) retire (deja corrige). P2-22 (OAuth CSRF) retire (correctement exempte). P1-16 (Celery broker) retire (Redis 127.0.0.1 uniquement).

---

## Decisions architecture actees

| Sujet | Decision |
|---|---|
| RLS PostgreSQL | `SET LOCAL app.current_tenant_id` + policies sur 48 tables TenantMixin |
| MFA Recovery | Suppression du code JSON blob apres usage (pas de table dediee) |
| Rate Limit P0 | FAIL-CLOSED strict (503 si Redis down) |
| Token Binding | IP subnet /24 + User-Agent hash dans claim JWT `cbh` |
| `@cached()` | Supprimer (code mort, jamais appele) |
| `decode_access_token()` | Forcer son usage dans `deps.py` a la place de `decode_token()` |

---

## PHASE 1 — P0 Bloquants

### P0-01 — Rate limiter FAIL-CLOSED strict

**Fichier** : `app/core/rate_limiter.py:142-154`

```python
# REMPLACER le bloc except
except Exception as e:
    logger.critical("Rate limiter Redis DOWN — FAIL-CLOSED (503): %s", e)
    return False, {
        "error": "service_unavailable",
        "detail": "Security service unavailable",
        "retry_after": 30,
    }
```

---

### P0-02 — Secrets dev : defaults vides + validation stricte

**Fichier** : `app/core/config.py`

Remplacer les 5 defaults :
```python
PASSWORD_PEPPER: str = ""        # etait "dev_pepper_CHANGER_EN_PROD_min32chars"
ENCRYPTION_KEY: str = ""         # etait "dev_encryption_key_32bytes_CHANGE"
TOTP_DEV_MASTER_KEY: str = ""   # etait "dev_totp_master_key_CHANGER_EN_PROD_32ch"
AUDIT_HMAC_KEY: str = ""        # etait "dev_audit_hmac_key_CHANGER_EN_PROD_32ch"
WG_INTERNAL_API_KEY: str = ""   # etait "dev_wg_internal_key_CHANGER_EN_PROD"
DATABASE_URL: str = ""           # etait "postgresql+psycopg2://caro:dev_local@..."
```

Ajouter dans `model_post_init` (debut de la methode) :
```python
critical = ["PASSWORD_PEPPER", "ENCRYPTION_KEY", "AUDIT_HMAC_KEY", "DATABASE_URL"]
for name in critical:
    val = getattr(self, name)
    if not val:
        raise RuntimeError(f"{name} requis. Definir dans .env")
    if name != "DATABASE_URL" and len(val) < 32:
        raise RuntimeError(f"{name} trop court (min 32 chars)")
```

Mettre a jour `.env.example` avec les noms des variables obligatoires.

---

## PHASE 2 — P1 Auth & Tokens

### P1-10 — `decode_token()` verify_aud:False + confusion access/refresh

**Fichier** : `app/core/security.py:187-206`

Ajouter validation type/audience post-decode :
```python
def decode_token(token: str) -> dict:
    payload = jwt.decode(token, _get_public_key(), **_decode_kwargs)
    token_type = payload.get("type")
    if token_type == "access":
        aud = payload.get("aud")
        if aud != settings.JWT_AUDIENCE:
            raise TokenInvalid(f"Access token audience mismatch: {aud}")
    elif token_type == "refresh":
        aud = payload.get("aud")
        expected_refresh_aud = f"{settings.JWT_AUDIENCE}:refresh"
        if aud != expected_refresh_aud:
            raise TokenInvalid(f"Refresh token audience mismatch: {aud}")
    return payload
```

**Fichier** : `app/core/deps.py` — remplacer `decode_token` par `decode_access_token` dans `get_current_user` :
```python
# Ligne ~259
payload = decode_access_token(access_token)  # etait decode_token(access_token)
```

---

### P1-07 — Refresh token sans claim `aud`

**Fichier** : `app/core/security.py` (create_refresh_token)

Ajouter `aud` au refresh :
```python
payload = {
    ...
    "aud": f"{settings.JWT_AUDIENCE}:refresh",
    "type": "refresh",
}
```

---

### P1-11 — Bare except au logout

**Fichier** : `app/services/auth_v2.py:213-216`

```python
try:
    await self._session_svc.revoke(session_id, membership_id, reason="logout")
except HTTPException as e:
    if e.status_code == 404:
        logger.debug("Session deja revoquee (idempotent)")
    else:
        logger.warning("Revocation session echouee: %s %s", e.status_code, e.detail)
```

---

### P1-14 — Bare except token decode au logout

**Fichier** : `app/api/v1/endpoints/auth.py:214-221`

```python
try:
    payload = decode_token(access_token)
    mid_raw = payload.get("mid")
    if mid_raw:
        membership_id = int(mid_raw)
except (TokenExpired, TokenInvalid) as e:
    logger.debug("Token decode au logout (attendu): %s", type(e).__name__)
except Exception as e:
    logger.warning("Token decode inattendu au logout: %s", e)
```

---

### P1-17 — Token invalidation au changement mot de passe

**Fichier** : `app/services/account.py` (methode change_password, ~ligne 170)

Ajouter apres `account.hashed_password = new_hash` :
```python
# Revoquer TOUTES les sessions sauf la courante
from app.core.redis import redis_sec
sessions_index_key = f"user_sessions_index:{account.id}"
session_ids = await redis_sec.client.smembers(sessions_index_key)
for sid in session_ids:
    sid_str = sid.decode() if isinstance(sid, bytes) else sid
    if sid_str == current_session_id:
        continue
    await redis_sec.revoke_single_session(account.id, sid_str)
logger.info("Sessions revoquees apres changement mdp pour account=%d (sauf session=%s)",
            account.id, current_session_id)
```

**Fichier** : `app/api/v1/endpoints/auth.py` ou `auth_v2.py` (endpoint change-password)

Passer `current_session_id` depuis le JWT claim `sid` :
```python
session_id = payload.get("sid")
await account_service.change_password(..., current_session_id=session_id)
```

---

### P1-12 — Lua revoke_all_user_tokens cle whitelist

**Fichier** : `app/lua/revoke_all_user_tokens.lua:23`

```lua
-- AVANT
local wl_key = 'whitelist:refresh:' .. user_id .. ':' .. session_ref

-- APRES
local parts = {}
for part in string.gmatch(session_ref, '([^:]+)') do
    table.insert(parts, part)
end
local device_id = parts[1] or ''
local session_id = parts[2] or ''
local wl_key = 'whitelist:refresh:' .. user_id .. ':' .. device_id .. ':' .. session_id
```

Verifier le meme pattern dans :
- `app/lua/logout_device.lua`
- `app/lua/logout_other_sessions.lua`
- `app/lua/revoke_single_session.lua`

---

### P1-04 — Fallback RBAC sans alerte

**Fichier** : `app/core/deps.py:610`

```python
if not jwt_scopes:
    logger.warning(
        "RBAC fallback: JWT scopes absents pour user=%s role=%s — utilisation ROLE_SCOPES_FALLBACK",
        user_id, role,
    )
    scopes = get_role_scopes(role, None)
```

---

### P1-05 — require_scope typo = silent fail

**Fichier** : `app/core/deps.py` (factory require_scope)

Ajouter validation au moment de la declaration :
```python
def require_scope(scope: Scope):
    if not isinstance(scope, Scope):
        raise TypeError(
            f"require_scope attend un Scope enum, recu {type(scope).__name__}: {scope!r}"
        )
    # ... reste de la factory
```

L'usage `require_scope(Scope.RESERVATIONS_READ)` passe. L'usage `require_scope("typo")` crash a l'import — pas au runtime.

---

### P1-06 — jti:meta TTL sans buffer

**Fichier** : `app/core/redis.py:204-210`

```python
async def store_jti_meta(self, jti_access: str, exp_timestamp: int,
                         ttl_seconds: int | None = None) -> bool:
    if ttl_seconds is None:
        # access_lifetime (900s) + clock_skew (30s) + buffer (60s) = 990s
        ttl_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 90
    key = f"{RedisKeys.JTI_META}{jti_access}"
    await self.client.set(key, str(exp_timestamp), ex=ttl_seconds)
    return True
```

---

### P1-08 — Health probes pas exemptees

**Fichier** : `app/middleware/security.py` (RateLimitMiddleware)

Ajouter `/metrics` a EXEMPT_PATHS :
```python
EXEMPT_PATHS = {
    HealthEndpoints.BASE,
    HealthEndpoints.READY,
    HealthEndpoints.LIVE,
    PublicEndpoints.DOCS,
    PublicEndpoints.REDOC,
    PublicEndpoints.OPENAPI,
    "/metrics",  # Prometheus scraping
}
```

---

### P1-13 — Incoherence FAIL-OPEN vs FAIL-CLOSED

**Fichier** : `app/constants/security.py`

Ajouter la documentation de la strategie :
```python
# Strategie fail-safe unifiee — Redis indisponible
#
# FAIL-CLOSED (securite > disponibilite) :
#   - Rate limiter general          → 503
#   - Brute force lock              → bloque login
#   - CSRF validation               → bloque mutation
#   - Token whitelist/blacklist     → bloque refresh/access
#   - TOTP rate limit              → bloque verification
#
# FAIL-OPEN (disponibilite > securite) :
#   - Cache produits/clients        → query DB directe
#   - Feature flags                 → defaults hardcodes
#   - HIBP check                    → accepte le mot de passe
#   - Scope cache                   → fallback statique
```

Aligner rate_limiter.py sur FAIL-CLOSED (cf. P0-01 deja fait).

---

### P1-02 — Cache merge sans verification tenant

**Fichier** : `app/repositories/base.py` (AsyncBaseRepository, apres merge)

Ajouter dans `get_by_id` apres le merge :
```python
async def get_by_id(self, entity_id: int, tenant_id: int):
    instance = await self._cache_get_or_db(entity_id, tenant_id)
    if instance and hasattr(instance, 'tenant_id'):
        if instance.tenant_id != tenant_id:
            logger.critical(
                "CROSS-TENANT DETECTED: %s#%d tenant=%d attendu=%d",
                self._model.__name__, entity_id, instance.tenant_id, tenant_id,
            )
            return None
    return instance
```

---

### P1-03 — @cached() code mort

**Fichier** : `app/core/cache.py:298-376`

Supprimer le decorateur `cached` et la classe `CacheConfig` associee (lignes 298-376).

---

### P1-18 — Pas de rate limiting TOTP

**Fichier** : `app/api/v1/endpoints/mfa.py` (endpoint verify)

Ajouter au debut de la fonction :
```python
TOTP_MAX_ATTEMPTS = 5
TOTP_LOCKOUT_SECONDS = 300

async def verify_totp(...):
    lockout_key = f"totp_lockout:{current_user.id}"
    attempts_raw = await redis_sec.client.get(lockout_key)
    if attempts_raw and int(attempts_raw) >= TOTP_MAX_ATTEMPTS:
        raise HTTPException(429, detail={"retry_after": TOTP_LOCKOUT_SECONDS})

    # ... verification TOTP existante ...

    if not valid:
        await redis_sec.client.incr(lockout_key)
        await redis_sec.client.expire(lockout_key, TOTP_LOCKOUT_SECONDS)
        raise HTTPException(401, detail="Code TOTP invalide")

    # Succes — reset
    await redis_sec.client.delete(lockout_key)
```

---

### P1-19 — Uploads StaticFiles XSS

**Fichier** : `app/main.py` (middleware HTTP, ajouter AVANT le mount /uploads)

```python
@app.middleware("http")
async def secure_uploads_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/uploads/"):
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["Content-Disposition"] = "attachment"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response
```

---

### P1-20 — /receipt/{token} sans rate limit

**Fichier** : `app/api/v1/endpoints/receipt.py`

Ajouter au debut de la fonction :
```python
import uuid as uuid_mod
from app.core.rate_limiter import check_rate_limit

@router.get("/{token}")
async def get_receipt(token: str, request: Request, ...):
    # Valider format
    try:
        uuid_mod.UUID(token)
    except ValueError:
        raise HTTPException(404)

    # Rate limit : 10 req/min par IP
    client_ip = request.client.host if request.client else "unknown"
    rl_key = f"rate:receipt:{client_ip}"
    count = await redis_sec.client.incr(rl_key)
    if count == 1:
        await redis_sec.client.expire(rl_key, 60)
    if count > 10:
        raise HTTPException(429, detail="Too many requests")

    # ... reste du handler ...
```

---

## PHASE 3 — P1 Multi-tenant RLS

### P1-01 — PostgreSQL RLS sur 48 tables

**Fichier** : `app/core/database.py`

Ajouter event listener pour setter le tenant_id dans la session PostgreSQL :
```python
from sqlalchemy import event, text
import contextvars

_current_tenant_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    '_current_tenant_id', default=None
)

def set_tenant_context(tenant_id: int):
    _current_tenant_id.set(tenant_id)

def clear_tenant_context():
    _current_tenant_id.set(None)

@event.listens_for(async_engine.sync_engine, "before_cursor_execute")
def _inject_tenant_id(conn, cursor, statement, parameters, context, executemany):
    tid = _current_tenant_id.get()
    if tid is not None:
        cursor.execute(f"SET LOCAL app.current_tenant_id = '{tid}'")
```

**Fichier** : `app/core/deps.py` (dans get_current_user, apres extraction du tenant_id)

```python
from app.core.database import set_tenant_context
set_tenant_context(current_user.tenant_id)
```

**Fichier** : nouvelle migration Alembic `xxxx_enable_rls_all_tables.py`

48 tables avec TenantMixin. Migration :
```python
TENANT_TABLES = [
    "products", "customers", "reservations", "invoices", "deposits",
    "devis", "ventes", "inventory_movements", "payments",
    "product_bundles", "bundle_items", "product_categories",
    "containers", "container_assignments", "container_items",
    "damage_types", "delivery_zones", "evenements",
    "invoice_charges", "invoice_credit_notes",
    "inventory_movement_damages", "movement_item_units",
    "pricing_rules", "product_collections", "product_images",
    "product_maintenances", "product_variants", "relances",
    "stock_items", "stock_managements",
    "suppliers", "supplier_orders", "supplier_order_lines",
    "api_keys",
    # Restaurant
    "restaurant_categorie_ingredients", "restaurant_ingredients",
    "restaurant_alerte_stocks", "restaurant_instance_preparations",
    "restaurant_ligne_commandes", "restaurant_commandes",
    "restaurant_recette_type_preparation", "restaurant_type_preparations",
    "restaurant_sides", "restaurant_mouvement_stocks",
    "restaurant_variantes_plats", "restaurant_tables",
    # Epicerie
    "epicerie_produits", "epicerie_stock", "epicerie_stock_movements",
    "epicerie_ventes", "epicerie_vente_lignes", "epicerie_supply_orders",
    # Finance
    "finance_invoices", "finance_payments",
]

def upgrade():
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (tenant_id = current_setting('app.current_tenant_id', true)::int)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::int)
        """)

def downgrade():
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
```

Note : `current_setting('app.current_tenant_id', true)` — le `true` retourne NULL si pas defini (evite erreur). Les queries admin sans tenant context verront tout (superuser bypass RLS).

---

## PHASE 4 — Token Binding (M-02)

**Fichier** : `app/core/security.py`

Ajouter fonction de calcul du binding hash :
```python
import hashlib
import ipaddress

def compute_client_binding_hash(ip: str, user_agent: str) -> str:
    """Hash IP subnet /24 + User-Agent pour token binding."""
    try:
        addr = ipaddress.ip_address(ip)
        if isinstance(addr, ipaddress.IPv4Address):
            subnet = str(ipaddress.IPv4Network(f"{ip}/24", strict=False))
        else:
            subnet = str(ipaddress.IPv6Network(f"{ip}/48", strict=False))
    except ValueError:
        subnet = ip
    raw = f"{subnet}|{user_agent}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]
```

**Dans** `create_access_token()` :
```python
def create_access_token(sub, tid, did, sid, role, scopes, mid, cbh=None, ...):
    payload = {
        ...
        "cbh": cbh,  # client binding hash
    }
```

**Dans** `app/core/deps.py` (get_current_user, apres decode) :
```python
cbh_expected = compute_client_binding_hash(
    request.client.host if request.client else "",
    request.headers.get("user-agent", ""),
)
cbh_token = payload.get("cbh")
if cbh_token and cbh_token != cbh_expected:
    logger.warning(
        "Token binding mismatch: user=%s expected=%s got=%s ip=%s",
        payload.get("sub"), cbh_expected, cbh_token, request.client.host,
    )
    raise HTTPException(401, detail="Client binding mismatch")
```

**Dans** les endpoints login (auth.py, auth_v2.py) :
```python
cbh = compute_client_binding_hash(
    request.client.host if request.client else "",
    request.headers.get("user-agent", ""),
)
access_token = create_access_token(..., cbh=cbh)
```

---

## PHASE 5 — P2 Securite applicative

### P2-01 + P2-12 — Audit trail enrichi

**Fichier** : `app/models/audit_log.py`

Ajouter colonnes (migration expand) :
```python
client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
request_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
request_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
```

**Fichier** : `app/middleware/audit.py`

Ajouter dans la creation de l'audit entry :
```python
audit_data["client_ip"] = request.client.host if request.client else None
audit_data["user_agent"] = (request.headers.get("user-agent") or "")[:256]
audit_data["request_method"] = request.method
audit_data["request_path"] = str(request.url.path)[:512]
```

---

### P2-13 — Lectures liste non auditees

**Fichier** : `app/middleware/audit.py`

Ajouter :
```python
SENSITIVE_LIST_PATHS = frozenset({
    "/api/v1/customers",
    "/api/v1/invoices",
    "/api/v1/audit",
    "/api/v1/users",
    "/api/v1/deposits",
})

# Dans le middleware, apres la reponse :
if request.method == "GET" and any(request.url.path.rstrip("/") == p for p in SENSITIVE_LIST_PATHS):
    if response.status_code < 300:
        await _log_audit(db, user_id, tenant_id, "LIST_SENSITIVE", ...)
```

---

### P2-02 + P2-03 — Cache race condition + soft-delete

**Fichier** : `app/repositories/base.py`

Ajouter lock court apres invalidation :
```python
async def _invalidate_cache(self, entity_id: int, tenant_id: int):
    key = self._cache_key(entity_id, tenant_id)
    lock_key = f"cache_lock:{key}"
    # Lock 2s pour empecher re-population avant propagation
    await self.cache.set(lock_key, "1", ex=2)
    await self.cache.delete(key)

async def _cache_get(self, entity_id: int, tenant_id: int):
    key = self._cache_key(entity_id, tenant_id)
    lock_key = f"cache_lock:{key}"
    # Si lock actif, skip cache (force DB)
    if await self.cache.exists(lock_key):
        return None
    return await self.cache.get(key)
```

---

### P2-04 — Scope cache sans invalidation

**Fichier** : `app/core/redis.py`

Ajouter methode :
```python
async def invalidate_scope_cache(self, role_name: str) -> None:
    key = f"rbac:scope:cache:{role_name}"
    await self.client.delete(key)
    logger.info("RBAC scope cache invalidated role=%s", role_name)
```

Appeler dans tout endpoint admin qui modifie les role_scopes.

---

### P2-05 — Confusion require_scope variants

**Fichier** : `app/core/deps.py`

Renommer pour clarifier :
```python
# require_scope       → accepte User + ApiKeyClient (endpoints API)
# require_scope_user  → accepte User uniquement (endpoints UI)
# Ajouter docstring explicite sur chaque factory
```

---

### P2-06 — Refresh sans sliding window

**Fichier** : `app/services/token.py` (dans la methode refresh)

Apres rotation reussie :
```python
# Sliding window : re-etendre le TTL whitelist a 7j
wl_key = f"whitelist:refresh:{user_id}:{device_id}:{session_id}"
await self.redis.expire(wl_key, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)
```

---

### P2-07 — Recovery codes MFA sans anti-replay

**Fichier** : `app/services/mfa.py`

```python
async def use_recovery_code(self, code: str, device: MFADevice) -> bool:
    if not device.recovery_codes_hash:
        return False
    codes = json.loads(device.recovery_codes_hash)
    for i, stored_hash in enumerate(codes):
        if bcrypt.checkpw(code.encode(), stored_hash.encode()):
            codes.pop(i)  # Supprimer le code utilise
            device.recovery_codes_hash = json.dumps(codes)
            await self.db.flush()
            remaining = len(codes)
            logger.info("Recovery code utilise pour device=%d (%d restants)", device.id, remaining)
            return True
    return False
```

---

### P2-08 — Step-up TTL trop long

**Fichier** : `app/services/mfa.py`

```python
STEP_UP_TTL_SECONDS = 300  # etait 900 (15 min) → 5 min
```

---

### P2-09 — Login rate limit par IP trop strict

**Fichier** : `app/core/rate_limit_utils.py`

Changer la cle de rate limit login pour utiliser l'email (pas l'IP) :
```python
# Pour le scope LOGIN :
# Cle = email (pas IP) pour supporter multi-device derriere NAT
def get_login_rate_key(request: Request) -> str:
    body = getattr(request.state, "parsed_body", {})
    email = body.get("email", "")
    return f"rate:login:email:{email}" if email else f"rate:login:ip:{request.client.host}"
```

---

### P2-11 — X-E2E-Bypass en DEBUG

**Fichier** : `app/middleware/security.py`

```python
# AVANT
if settings.DEBUG and request.headers.get("X-E2E-Bypass") == "true":

# APRES
E2E_BYPASS_ENABLED = os.environ.get("E2E_BYPASS_ENABLED", "").lower() == "true"
if E2E_BYPASS_ENABLED and request.headers.get("X-E2E-Bypass") == "true":
```

En `.env` : `E2E_BYPASS_ENABLED=true` uniquement pour les tests E2E. Jamais en prod.

---

### P2-15 — /metrics public

**Fichier** : `app/main.py` (endpoint /metrics)

```python
@app.get("/metrics")
async def metrics(request: Request):
    client_ip = request.client.host if request.client else ""
    metrics_key = request.headers.get("X-Metrics-Key", "")
    if client_ip not in ("127.0.0.1", "::1") and metrics_key != settings.METRICS_API_KEY:
        raise HTTPException(403)
    # ... generation metriques ...
```

**Config** : `METRICS_API_KEY: str = ""` dans config.py.

---

### P2-16 + P2-17 + P3-14 — Validation uploads (magic bytes + CSV injection)

**Fichier** : `app/core/upload_validator.py` (nouveau)

```python
from fastapi import HTTPException

MAGIC_SIGNATURES = {
    b'\xff\xd8\xff': '.jpg',
    b'\x89PNG\r\n\x1a\n': '.png',
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_CSV_ROWS = 10_000
FORMULA_CHARS = frozenset({'=', '+', '-', '@', '\t', '\r'})


def validate_image(content: bytes) -> str:
    """Valide image par magic bytes. Retourne extension reelle. Raise 400/413."""
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(413, detail=f"Fichier trop volumineux (max {MAX_IMAGE_SIZE // 1024 // 1024}MB)")
    for magic, ext in MAGIC_SIGNATURES.items():
        if content[:len(magic)] == magic:
            return ext
    # WebP : bytes 0-3 = RIFF, bytes 8-11 = WEBP
    if content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        return '.webp'
    raise HTTPException(400, detail="Format image invalide. Acceptes : JPG, PNG, WebP")


def sanitize_csv_value(value: str) -> str:
    """Neutralise les formules CSV (=, +, @, -)."""
    if value and value[0] in FORMULA_CHARS:
        return "'" + value
    return value
```

**Fichier** : `app/api/v1/endpoints/operations.py:177`

```python
from app.core.upload_validator import validate_image
content = await file.read()
ext = validate_image(content)
filename = f"damage_{uuid.uuid4().hex}{ext}"
```

**Fichier** : `app/api/v1/endpoints/products.py:466` (upload image)

Meme pattern : `validate_image(content)`.

**Fichier** : `app/api/v1/endpoints/products.py:953` et `customers.py:577` (CSV import)

```python
from app.core.upload_validator import sanitize_csv_value, MAX_CSV_ROWS

for i, row in enumerate(reader):
    if i >= MAX_CSV_ROWS:
        raise HTTPException(400, detail=f"CSV trop volumineux (max {MAX_CSV_ROWS} lignes)")
    sanitized = {k: sanitize_csv_value(v.strip()) for k, v in row.items() if v}
    # ... traitement avec sanitized ...
```

---

### P2-18 — CSRF timing leak

**Fichier** : `app/middleware/security.py:114-131`

```python
async def _validate_csrf(self, token: str | None, session_id: str) -> bool:
    expected = await redis_sec.get_csrf_token(session_id) or ""
    actual = token or ""
    # Toujours compare_digest meme si vide/court — pas de early return
    return hmac.compare_digest(actual, expected)
```

---

### P2-19 — jti:meta TTL

Deja couvert par P1-06.

---

### P2-20 — Versions deps partiellement pinned

**Fichier** : `pyproject.toml`

```toml
PyJWT = "~2.9.0"
cryptography = "~44.0.0"
argon2-cffi = "~23.1.0"
redis = "~5.2.0"
```

---

### P2-21 — PIN lockout par device_id seulement

**Fichier** : `app/api/v1/endpoints/auth_v2.py:409-420`

Ajouter lockout global cross-device :
```python
PIN_GLOBAL_MAX_ATTEMPTS = 15
PIN_GLOBAL_LOCKOUT_SECONDS = 1800  # 30 min

# Apres resolution de account_id :
global_key = f"pin_lockout_global:{account_id}"
global_attempts = await redis_sec.client.get(global_key)
if global_attempts and int(global_attempts) >= PIN_GLOBAL_MAX_ATTEMPTS:
    raise HTTPException(429, detail={"retry_after": PIN_GLOBAL_LOCKOUT_SECONDS})

# ... verification PIN ...

# Echec : incrementer les deux compteurs
await redis_sec.client.incr(device_lockout_key)
await redis_sec.client.expire(device_lockout_key, PIN_LOCKOUT_WINDOW_SECONDS)
await redis_sec.client.incr(global_key)
await redis_sec.client.expire(global_key, PIN_GLOBAL_LOCKOUT_SECONDS)
```

---

### P2-23 — OAuth auto-linking sans email_verified

**Fichier** : `app/services/oauth_v2.py:326-334`

```python
email_verified = user_info.get("email_verified", False)
if not email_verified:
    raise HTTPException(400, detail="Email non verifie par le provider OAuth")

account = await self._account_repo.get_active_by_email(email)
```

---

### P2-24 — Upload lu entier en memoire

**Fichier** : `app/api/v1/endpoints/products.py:473`

```python
# Verifier Content-Length AVANT de lire
content_length = int(request.headers.get("content-length", 0))
if content_length > MAX_IMAGE_SIZE:
    raise HTTPException(413, detail="Fichier trop volumineux")

content = await file.read()
# Double check (Content-Length peut etre forge)
if len(content) > MAX_IMAGE_SIZE:
    raise HTTPException(413, detail="Fichier trop volumineux")
```

---

## PHASE 6 — P3 Durcissement

### P3-01 — Cache versioning

**Fichier** : `app/repositories/base.py`

```python
CACHE_VERSION = "v2"

def _cache_key(self, entity_id: int, tenant_id: int) -> str:
    return f"{CACHE_VERSION}:{self._entity_name}:{tenant_id}:{entity_id}"
```

---

### P3-02 — require_scope retourne Union

**Fichier** : `app/core/deps.py`

```python
from typing import Union
Principal = Union[UserCompat, ApiKeyClient]

def get_principal_tenant_id(principal: Principal) -> int:
    return principal.tenant_id
```

---

### P3-03 — Clock skew 30s

**Fichier** : `app/core/security.py`

```python
"leeway": timedelta(seconds=15)  # etait 30
```

---

### P3-05 — Rate limit coordination

Deja implicitement coordonnee via Redis unique partage. Rien a faire.

---

### P3-07 — Audit types d'action

**Fichier** : `app/middleware/audit.py`

Ajouter `DELETE` comme type distinct :
```python
if request.method == "DELETE":
    action = "DELETE"
elif request.method == "POST":
    action = "CREATE"
elif request.method in ("PUT", "PATCH"):
    action = "UPDATE"
```

---

### P3-08 — CORS DEBUG ajoute tous les ports LAN

**Fichier** : `app/core/config.py:176-208`

```python
# AVANT : scan toutes les IPs LAN
for ip in local_ips:
    for port in dev_ports:

# APRES : localhost uniquement
for port in dev_ports:
    for host in ("localhost", "127.0.0.1"):
        origin = f"http://{host}:{port}"
        if origin not in existing_origins:
            added_origins.append(origin)
```

---

### P3-09 — 422 expose structure schema

**Fichier** : `app/middleware/exception_handler.py:135-159`

```python
if settings.DEBUG:
    formatted_errors = [
        {"field": ".".join(str(p) for p in e.get("loc", [])),
         "message": e.get("msg", "Validation error"),
         "type": e.get("type", "unknown")}
        for e in raw_errors
    ]
else:
    formatted_errors = [{"message": "Validation error"}]
```

---

### P3-10 — Upload filename fragile

Deja couvert par P2-16 (validate_image ignore filename client).

---

### P3-11 — DEBUG desactive HTTPS cookies

**Fichier** : `app/core/config.py` (validate_production_secrets)

```python
if not self.DEBUG:
    if not self.COOKIE_SECURE:
        raise RuntimeError("COOKIE_SECURE doit etre True en production")
```

---

### P3-12 — HIBP fail-open monitoring

**Fichier** : `app/services/hibp.py:59-63`

```python
except Exception as exc:
    logger.warning("HIBP API indisponible — check skip (FAIL-OPEN): %s", exc)
    # Metrique pour monitoring
    from app.core.health import health_registry
    health_registry.record_dependency_failure("hibp")
    return False
```

---

### P3-13 — poetry.lock non versionne

Retirer `poetry.lock` du `.gitignore` si present, puis `git add poetry.lock`.

---

### P3-15 + P3-16 — DB sans TLS + sans pool_recycle

**Fichier** : `app/core/database.py`

```python
engine_kwargs = {
    "pool_size": settings.DB_POOL_SIZE,
    "max_overflow": settings.DB_MAX_OVERFLOW,
    "pool_pre_ping": True,
    "pool_recycle": 3600,  # recycler connexions toutes les heures
    "echo": settings.DEBUG,
}
if settings.DB_SSL_MODE:
    engine_kwargs["connect_args"] = {"sslmode": settings.DB_SSL_MODE}

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
```

**Config** : `DB_SSL_MODE: str = ""` (vide en dev, `"require"` en prod).

---

## PHASE 7 — Manques architecture

### M-03 — WebAuthn/FIDO2

Scope : ajouter support WebAuthn comme alternative au TOTP.

**Nouveaux fichiers** :
- `app/models/webauthn_credential.py` — table `webauthn_credentials`
- `app/services/webauthn.py` — registration + authentication via `py_webauthn`
- `app/api/v1/endpoints/webauthn.py` — endpoints register/verify
- `app/schemas/webauthn.py` — schemas Pydantic

**Dependance** : `py-webauthn = "~2.1.0"` dans pyproject.toml.

**Modele** :
```python
class WebAuthnCredential(Base, TimestampMixin):
    __tablename__ = "webauthn_credentials"
    id: int (PK)
    account_id: int (FK accounts.id)
    credential_id: bytes
    public_key: bytes
    sign_count: int
    device_name: str
    created_at: datetime
    last_used_at: datetime | None
```

---

### M-04 — Rotation cles JWT (kid)

**Fichier** : `app/core/kms.py`

Ajouter `kid` (key ID) au JWKS :
```python
def get_jwks_response() -> dict:
    kid = hashlib.sha256(public_key_pem).hexdigest()[:16]
    return {
        "keys": [{
            "kty": "RSA",
            "kid": kid,
            "use": "sig",
            "alg": "RS256",
            "n": ...,
            "e": ...,
        }]
    }
```

**Fichier** : `app/core/security.py`

Ajouter `kid` dans le header JWT :
```python
jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})
```

Lors du decode, selectionner la cle par `kid` dans le JWKS.

---

### M-05 — Adaptive MFA

**Fichier** : `app/services/auth_v2.py` (login)

Ajouter detection de nouveau device/IP :
```python
async def _check_adaptive_mfa(self, account_id: int, ip: str, device_id: str) -> bool:
    """Retourne True si MFA step-up requis (nouveau device ou IP inhabituelle)."""
    # Verifier si le device est connu
    known_devices = await self._session_repo.get_recent_devices(account_id, days=30)
    if device_id not in known_devices:
        return True
    # Verifier si l'IP est dans un subnet connu
    known_ips = await self._session_repo.get_recent_ips(account_id, days=30)
    current_subnet = str(ipaddress.IPv4Network(f"{ip}/24", strict=False))
    known_subnets = {str(ipaddress.IPv4Network(f"{kip}/24", strict=False)) for kip in known_ips}
    if current_subnet not in known_subnets:
        return True
    return False
```

---

### M-06 — DB TLS

Deja couvert par P3-15.

---

### M-07 — Whitelist IP partenaires

**Fichier** : `app/core/config.py`

```python
TRUSTED_PARTNER_IPS: list[str] = []  # ex: ["203.0.113.0/24"]
```

**Fichier** : `app/core/rate_limiter.py`

```python
import ipaddress

def _is_trusted_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return any(addr in ipaddress.ip_network(cidr) for cidr in settings.TRUSTED_PARTNER_IPS)

# Dans check_rate_limit :
if _is_trusted_ip(client_ip):
    return True, {"trusted": True}
```

---

## Ordre d'execution

```
PHASE 1 (J1)     : P0-01, P0-02
PHASE 2 (J2-J4)  : P1-10, P1-07, P1-11, P1-14, P1-17, P1-12,
                    P1-04, P1-05, P1-06, P1-08, P1-13,
                    P1-02, P1-03, P1-18, P1-19, P1-20
PHASE 3 (J5-J6)  : P1-01 (RLS 48 tables)
PHASE 4 (J7)     : Token binding (M-02)
PHASE 5 (J8-J12) : Tous les P2
PHASE 6 (J13-J14): Tous les P3
PHASE 7 (J15+)   : M-03 WebAuthn, M-04 JWT kid, M-05 Adaptive MFA, M-07 IP whitelist
```

## Verification

```bash
# Tests securite complets
docker compose run --rm --entrypoint "" api python -m pytest tests/security/ -v

# Tests integration
docker compose run --rm --entrypoint "" api python -m pytest tests/integration/ -v

# Verifier RLS
docker compose exec db psql -U marveline -d marveline -c "SELECT schemaname, tablename, policyname FROM pg_policies ORDER BY tablename;"

# Verifier aucun endpoint sans auth
grep -rn "router\.\(get\|post\|put\|patch\|delete\)" app/api/v1/endpoints/ | grep -v require_scope | grep -v get_current | grep -v "health\|receipt\|jwks\|openid\|csrf"

# Scan vulnerabilites deps
pip-audit --strict
```
