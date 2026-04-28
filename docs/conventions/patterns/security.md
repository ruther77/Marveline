# Patterns — Sécurité

## OWASP Top 10 — Contrôles

| Risque | Contrôle |
|---|---|
| Injection SQL | SQLAlchemy ORM — jamais de `.execute(raw_sql % user_input)` |
| Auth Broken | JWT + MFA + session rotation |
| XSS | React escaping natif, CSP headers |
| IDOR | Filtre `tenant_id` dans chaque query repo |
| Misconfiguration | Variables d'env, pas de debug en prod |
| Logging insuffisant | Audit log sur toutes mutations sensibles |

## SSRF Prevention

```python
import ipaddress
from urllib.parse import urlparse

BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}
ALLOWED_SCHEMES = {"https"}

def validate_external_url(url: str) -> str:
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Scheme {parsed.scheme} not allowed. Use HTTPS.")

    hostname = parsed.hostname
    if hostname in BLOCKED_HOSTS:
        raise ValueError("Access to metadata endpoint is forbidden")

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError("Private/internal IP addresses are not allowed")
    except ValueError as e:
        if "not allowed" in str(e) or "forbidden" in str(e):
            raise
        # hostname valide (pas une IP) → OK

    return url
```

## Field-Level Encryption (Données Sensibles)

```python
from cryptography.fernet import Fernet
import base64

class FieldEncryptor:
    def __init__(self, key: bytes):
        self.fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        return self.fernet.decrypt(encrypted.encode()).decode()

encryptor = FieldEncryptor(settings.FIELD_ENCRYPTION_KEY)

class PaymentInfo(Base, TimestampMixin):
    _card_last4_encrypted: Mapped[str] = mapped_column(String(500), nullable=False)

    @property
    def card_last4(self) -> str:
        return encryptor.decrypt(self._card_last4_encrypted)

    @card_last4.setter
    def card_last4(self, value: str) -> None:
        self._card_last4_encrypted = encryptor.encrypt(value)
```

## Re-authentification (Actions Sensibles)

```python
from datetime import datetime, timedelta

REAUTH_REQUIRED_ACTIONS = {"change_password", "delete_account", "export_data"}
REAUTH_WINDOW_MINUTES = 15

def require_recent_auth(action: str):
    def dependency(current_user = Depends(get_current_user)):
        if action in REAUTH_REQUIRED_ACTIONS:
            last_verified = current_user.last_password_verified_at
            if not last_verified or datetime.utcnow() - last_verified > timedelta(minutes=REAUTH_WINDOW_MINUTES):
                raise HTTPException(
                    status_code=403,
                    detail="Recent authentication required. Please verify your password."
                )
        return current_user
    return dependency

@router.delete("/account")
async def delete_account(
    current_user = Depends(require_recent_auth("delete_account")),
):
    ...
```

## ReDoS Protection

```python
import re
import signal
from contextlib import contextmanager

class RegexTimeoutError(Exception):
    pass

@contextmanager
def regex_timeout(seconds: float = 0.1):
    def handler(signum, frame):
        raise RegexTimeoutError("Regex timeout")
    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)

# Patterns sécurisés — éviter les groupes répétés imbriqués
SAFE_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
SAFE_PHONE_PATTERN = re.compile(r"^\+?[0-9\s\-\(\)]{7,20}$")
SAFE_ALPHANUMERIC = re.compile(r"^[a-zA-Z0-9\-_]{1,100}$")

def validate_with_timeout(pattern: re.Pattern, value: str) -> bool:
    try:
        with regex_timeout(0.1):
            return bool(pattern.match(value))
    except RegexTimeoutError:
        logger.warning("ReDoS attempt detected: pattern=%s value_len=%d", pattern.pattern, len(value))
        return False
```

## CSP Nonce (Content Security Policy)

```python
import secrets
from fastapi import Request

def generate_csp_nonce() -> str:
    return secrets.token_urlsafe(16)

@app.middleware("http")
async def add_csp_header(request: Request, call_next):
    nonce = generate_csp_nonce()
    request.state.csp_nonce = nonce
    response = await call_next(request)
    csp = (
        f"default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self' 'nonce-{nonce}'; "
        f"img-src 'self' data: https:; "
        f"connect-src 'self' https://api.marveline.com; "
        f"frame-ancestors 'none';"
    )
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
```

## mTLS (Mutual TLS entre Services)

```python
# Pour les communications inter-services sensibles
import httpx

mtls_client = httpx.AsyncClient(
    cert=("/path/to/client.crt", "/path/to/client.key"),
    verify="/path/to/ca.crt",
)

async def call_internal_service(path: str, data: dict) -> dict:
    response = await mtls_client.post(
        f"https://internal-service:8443{path}",
        json=data,
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()
```

## Rate Limiting — Sliding Window Lua

```lua
-- Script Lua Redis (atomique, multi-instance)
-- KEYS[1] = clé rate limit, ARGV[1] = window_seconds, ARGV[2] = max_requests
local key = KEYS[1]
local window = tonumber(ARGV[1])
local max_requests = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local window_start = now - window * 1000

redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local count = redis.call('ZCARD', key)

if count >= max_requests then
    return 0  -- Rejeté
end

redis.call('ZADD', key, now, now)
redis.call('EXPIRE', key, window)
return 1  -- Accepté
```

```python
RATE_LIMIT_SCRIPT = redis_client.register_script(LUA_SCRIPT)

def check_rate_limit(identifier: str, window_seconds: int, max_requests: int) -> bool:
    now_ms = int(time.time() * 1000)
    key = f"rate_limit:{identifier}"
    result = RATE_LIMIT_SCRIPT(keys=[key], args=[window_seconds, max_requests, now_ms])
    return bool(result)
```

## Matrice Sécurité

| Menace | Contrôle | Priorité |
|---|---|---|
| SSRF | Validation URL + blocklist IP | P0 |
| SQL Injection | ORM uniquement, pas de raw SQL | P0 |
| Cross-tenant | Filtre tenant_id dans chaque repo | P0 |
| Auth Broken | JWT + MFA + rotation | P0 |
| ReDoS | Patterns simplifiés + timeout | P1 |
| Field Encryption | Fernet sur données très sensibles | P1 |
| XSS | CSP Nonce + React escaping | P1 |
| Re-auth | Actions sensibles = vérif 15min | P1 |
| mTLS | Communications inter-services | P2 |
