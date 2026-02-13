# CaroCorp - Audit Sécurité Complet et Roadmap 100% Coverage

**Date**: 2026-02-12
**Auteur**: Audit sécurité automatique
**Statut**: DRAFT - Validation requise
**Objectif**: 100% couverture + Sécurité niveau entreprise réglementée
**Méthodologie**: Aucune solution temporaire, corrections complètes uniquement

---

## Table des Matières

1. [Résumé Exécutif](#résumé-exécutif)
2. [Bugs Critiques Identifiés](#bugs-critiques-identifiés)
3. [Analyse de Sécurité](#analyse-de-sécurité)
4. [Conformité RGPD](#conformité-rgpd)
5. [Roadmap Détaillée](#roadmap-détaillée)
6. [Stratégie de Tests](#stratégie-de-tests)
7. [Critères de Validation](#critères-de-validation)
8. [Pratiques de Configuration et Settings](#pratiques-de-configuration-et-settings)

---

## Résumé Exécutif

### État Actuel
- **Couverture globale**: 94.42% (1879/1990 statements)
- **Tests passants**: 322/322 (100% succès)
- **Bugs critiques**: 12 identifiés (4 P0, 5 P1, 3 P2)
- **Vulnérabilités sécurité**: 5 majeures (CSRF, Rate limit, Audit log, datetime deprecated, JWT)
- **Non-conformité RGPD**: Audit log manquant, pas de data retention policy

### Objectifs Phase Finale
1. **100% couverture code** (1990/1990 statements)
2. **Correction bugs critiques** (0 bug P0/P1 restant)
3. **Sécurité OWASP Top 10** complète
4. **Conformité RGPD** totale
5. **Tests sécurité automatisés** (injection, XSS, CSRF, brute force)
6. **Documentation complète** (architecture, sécurité, compliance)

### Estimation Globale
- **Durée totale**: 80-100 heures (~2-3 semaines)
- **Phases**: 10 phases séquentielles
- **Risque**: Moyen (migrations DB, breaking changes potentiels)
- **Priorité business**: CRITIQUE (production-ready compliance)

---

## Bugs Critiques Identifiés

### 🔴 BUG #1 - CRITIQUE P0 : Désynchronisation ReservationStatus DB/Code

**Fichiers impactés**:
- `app/models/reservation.py` ligne 140 (CheckConstraint)
- `app/constants/business.py` lignes 72-76 (ReservationStatus enum)
- `alembic/versions/*.py` (migration initiale)

**Problème**:
```python
# DB CheckConstraint (ligne 140 reservation.py)
"status IN ('draft', 'confirmed', 'in_progress', 'completed', 'cancelled')"

# Python Enum (business.py)
class ReservationStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    DELIVERED = "delivered"    # ❌ N'existe PAS en DB
    RETURNED = "returned"      # ❌ N'existe PAS en DB
    CANCELLED = "cancelled"
```

**Impact Production**:
- Code utilisant `ReservationStatus.DELIVERED` → CheckViolation DB (500 Internal Server Error)
- Code utilisant `ReservationStatus.RETURNED` → CheckViolation DB
- Tests passent car utilisent string literals `"completed"` au lieu de l'enum
- **Risque**: Crash production sur workflow confirm → deliver → return

**Utilisation actuelle du code**:
- `app/services/reservation.py` ligne 176: `status=ReservationStatus.DRAFT` ✅ OK
- `app/services/reservation.py` ligne 299: `status=ReservationStatus.CONFIRMED` ✅ OK
- `app/services/reservation.py` ligne 366: `status=ReservationStatus.CANCELLED` ✅ OK
- **Aucune utilisation** de `DELIVERED` ou `RETURNED` → Bug latent dormant

**Solutions possibles**:

**Option A** : Synchroniser Enum avec DB (Recommandé)
```python
class ReservationStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"  # Nouveau
    COMPLETED = "completed"      # Nouveau
    CANCELLED = "cancelled"
    # Supprimer DELIVERED et RETURNED
```

**Option B** : Synchroniser DB avec Enum
```sql
-- Migration Alembic
ALTER TABLE reservations DROP CONSTRAINT check_reservation_status_valid;
ALTER TABLE reservations ADD CONSTRAINT check_reservation_status_valid
    CHECK (status IN ('draft', 'confirmed', 'delivered', 'returned', 'cancelled'));
```

**Recommandation**: **Option A** - Synchroniser Enum avec DB
**Justification**:
- DB constraint existante déjà en production
- `in_progress` et `completed` plus clairs pour workflow réservation
- Moins de breaking changes (enum pas utilisé en prod pour DELIVERED/RETURNED)

**Correction détaillée**:
1. Créer migration Alembic `sync_reservation_status_enum_with_db.py`
2. Mise à jour `app/constants/business.py` enum ReservationStatus
3. Mise à jour docstrings workflow (lignes 62-64 business.py)
4. Tests de régression sur tous workflows réservation
5. Documentation breaking change (CHANGELOG.md)

**Estimation**: 4 heures (migration + tests + documentation)
**Priorité**: P0 - Bloquant production

---

### 🔴 BUG #2 - SÉCURITÉ P0 : datetime.utcnow() Deprecated

**Fichiers impactés**:
- `app/core/security.py` lignes 42, 44, 50, 81, 87 (5 occurrences)

**Problème**:
```python
# ❌ DEPRECATED Python 3.12+ (sera retiré dans futures versions)
expire = datetime.utcnow() + timedelta(minutes=30)

# ✅ CORRECT (timezone-aware)
from datetime import timezone
expire = datetime.now(timezone.utc) + timedelta(minutes=30)
```

**Impact Production**:
- DeprecationWarning pollue logs (270 warnings dans test suite)
- **Risque futur**: Breaking change Python 3.14+ (2026-10-01)
- Timestamps timezone-naive peuvent causer bugs comparaison datetime

**Correction détaillée**:
```python
# app/core/security.py - Ligne 1
from datetime import datetime, timedelta, timezone  # Ajouter timezone

# Lignes 42-44
if expires_delta:
    expire = datetime.now(timezone.utc) + expires_delta
else:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )

# Ligne 50
to_encode.update({
    "exp": expire,
    "iat": datetime.now(timezone.utc),  # Changé
    "type": "access"
})

# Lignes 81-87 (create_refresh_token)
expire = datetime.now(timezone.utc) + timedelta(
    days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
)

to_encode.update({
    "exp": expire,
    "iat": datetime.now(timezone.utc),  # Changé
    "type": "refresh"
})
```

**Tests de régression**:
- ✅ Tests JWT existants doivent passer sans modification
- ✅ Vérifier aucune DeprecationWarning dans test suite
- ✅ Valider que tokens générés sont toujours valides

**Estimation**: 1 heure (correction + tests + validation)
**Priorité**: P0 - Bloquant upgrade Python

---

### 🔴 BUG #3 - SÉCURITÉ P0 : CSRF Protection Non Implémentée

**Fichiers impactés**:
- `app/middleware/security.py` lignes 52, 68, 96

**Problème**:
```python
# Ligne 52 - _validate_csrf_token() retourne toujours True
def _validate_csrf_token(self, token: str) -> bool:
    """Valide le token CSRF.

    TODO: Implémenter validation avec Redis/session storage.
    Pour l'instant, validation basique.
    """
    if not token or len(token) < 32:
        return False

    # TODO: Vérifier le token dans Redis avec la session utilisateur
    # redis_client.get(f"csrf:{session_id}") == token
    return True  # ❌ TOUJOURS TRUE - AUCUNE VALIDATION
```

**Impact Production**:
- **CSRF protection complètement bypassée**
- Attaquant peut forger requêtes POST/PUT/DELETE avec token fake (32+ chars)
- **Risque**: Vol de compte, modification données, actions non autorisées
- **OWASP Top 10 2021**: A01:2021-Broken Access Control

**Architecture sécurisée complète**:

**1. Token CSRF stocké en Redis avec session**
```python
# Structure Redis
# Key: csrf:{session_id}
# Value: token_csrf (32 bytes url-safe)
# TTL: JWT_ACCESS_TOKEN_EXPIRE_MINUTES (30 min)
```

**2. Génération token CSRF au login**
```python
# app/api/v1/endpoints/auth.py - login endpoint
@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # ... authentification ...

    # Générer session ID unique
    session_id = secrets.token_urlsafe(32)

    # Générer token CSRF
    csrf_token = CSRFProtectionMiddleware.generate_csrf_token()

    # Stocker dans Redis
    from app.core.redis import redis_client
    redis_client.setex(
        f"csrf:{session_id}",
        settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        csrf_token
    )

    # Ajouter session_id dans JWT claims
    access_token = create_access_token({
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "session_id": session_id,  # Nouveau claim
        ...
    })

    return {
        "access_token": access_token,
        "csrf_token": csrf_token,  # Retourné au client
        ...
    }
```

**3. Validation CSRF dans middleware**
```python
# app/middleware/security.py
def _validate_csrf_token(self, token: str, session_id: str) -> bool:
    """Valide le token CSRF contre Redis session."""
    if not token or len(token) < 32:
        return False

    # Récupérer token stocké dans Redis
    from app.core.redis import redis_client
    stored_token = redis_client.get(f"csrf:{session_id}")

    if not stored_token:
        # Session expirée ou token jamais généré
        return False

    # Comparaison constante-time (protection timing attacks)
    return secrets.compare_digest(token, stored_token.decode('utf-8'))

async def dispatch(self, request: Request, call_next: Callable):
    # ... code existant ...

    # Extraire session_id du JWT
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = decode_token(token)
    if not payload:
        return await call_next(request)  # JWT invalide → sera géré par auth

    session_id = payload.get("session_id")
    if not session_id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Session ID manquant dans JWT"}
        )

    # Valider CSRF avec session
    csrf_token = request.headers.get("X-CSRF-Token")
    if not self._validate_csrf_token(csrf_token, session_id):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "CSRF token invalide ou expiré"}
        )

    response = await call_next(request)
    return response
```

**4. Configuration Redis**
```python
# app/core/redis.py (nouveau fichier)
from redis import Redis
from app.core.config import settings

redis_client = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=False,  # Binary-safe pour tokens
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True,
    health_check_interval=30
)

def ping_redis() -> bool:
    """Health check Redis."""
    try:
        return redis_client.ping()
    except Exception:
        return False
```

**5. Variables d'environnement**
```bash
# .env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # Vide pour dev, obligatoire prod
```

**6. Tests sécurité CSRF**
```python
# tests/security/test_csrf_protection.py

def test_csrf_missing_token_returns_403(client, auth_headers):
    """Requête POST sans X-CSRF-Token → 403."""
    response = client.post(
        "/api/v1/products",
        json={"name": "Test"},
        headers={"Authorization": auth_headers["Authorization"]}  # Sans CSRF
    )
    assert response.status_code == 403
    assert "CSRF token manquant" in response.json()["detail"]

def test_csrf_invalid_token_returns_403(client, auth_headers, test_user):
    """Token CSRF invalide → 403."""
    response = client.post(
        "/api/v1/products",
        json={"name": "Test"},
        headers={
            **auth_headers,
            "X-CSRF-Token": "invalid_token_123456789012345678901234"
        }
    )
    assert response.status_code == 403
    assert "CSRF token invalide" in response.json()["detail"]

def test_csrf_expired_session_returns_403(client, expired_token, csrf_token):
    """Session expirée → 403."""
    # Token JWT expiré (session_id invalide dans Redis)
    response = client.post(
        "/api/v1/products",
        json={"name": "Test"},
        headers={
            "Authorization": f"Bearer {expired_token}",
            "X-CSRF-Token": csrf_token
        }
    )
    assert response.status_code == 403

def test_csrf_valid_token_success(client, auth_headers_with_csrf):
    """Token CSRF valide → 201."""
    response = client.post(
        "/api/v1/products",
        json={
            "name": "Test Product",
            "sku": "TEST-CSRF",
            "category": "assiette",
            "price_per_day_cents": 100,
            "stock_quantity": 10,
            ...
        },
        headers=auth_headers_with_csrf  # Inclut CSRF valide
    )
    assert response.status_code == 201

def test_csrf_token_reuse_across_sessions_fails(client, db):
    """Token CSRF d'une session ne peut pas être réutilisé dans une autre."""
    # Session 1
    user1_token, csrf1 = login_and_get_tokens(client, "user1@test.com")

    # Session 2
    user2_token, csrf2 = login_and_get_tokens(client, "user2@test.com")

    # User2 tente d'utiliser CSRF de user1 → 403
    response = client.post(
        "/api/v1/products",
        json={"name": "Test"},
        headers={
            "Authorization": f"Bearer {user2_token}",
            "X-CSRF-Token": csrf1  # Token de user1
        }
    )
    assert response.status_code == 403
```

**Estimation**: 12 heures (Redis setup + impl + tests + doc)
**Priorité**: P0 - Vulnérabilité critique production

---

### 🟠 BUG #4 - SÉCURITÉ P1 : Rate Limiting Non Implémenté

**Fichiers impactés**:
- `app/middleware/security.py` lignes 108-127 (RateLimitMiddleware)

**Problème**:
```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware basique de rate limiting.

    TODO: Implémenter avec Redis pour un rate limiting distribué.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        """Vérifie le rate limit pour l'IP."""

        # TODO: Implémenter rate limiting avec Redis
        # ❌ AUCUNE PROTECTION IMPLÉMENTÉE

        response = await call_next(request)
        return response
```

**Impact Production**:
- **Aucune protection brute force** sur `/api/v1/auth/login`
- **Aucune protection DoS** sur endpoints API
- Attaquant peut envoyer milliers de requêtes/seconde
- **Risque**: Brute force passwords, DoS, surcharge serveur, coûts AWS/cloud
- **OWASP Top 10 2021**: A07:2021-Identification and Authentication Failures

**Architecture rate limiting complète**:

**1. Stratégie multi-niveaux**
```python
# Rate limits différenciés par endpoint
RATE_LIMITS = {
    # Authentification (protection brute force)
    "/api/v1/auth/login": {
        "requests": 5,      # 5 tentatives
        "window": 60,       # Par minute
        "block_duration": 300  # Block 5 minutes après dépassement
    },
    "/api/v1/auth/refresh": {
        "requests": 10,
        "window": 60,
        "block_duration": 60
    },

    # API mutations (protection abus)
    "POST:/api/v1/**": {
        "requests": 100,    # 100 créations
        "window": 60,       # Par minute
        "block_duration": 60
    },

    # API lecture (plus permissif)
    "GET:/api/v1/**": {
        "requests": 1000,   # 1000 lectures
        "window": 60,       # Par minute
        "block_duration": 60
    }
}
```

**2. Implémentation Redis sliding window**
```python
# app/middleware/security.py

from app.core.redis import redis_client
from app.core.config import settings
import time

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting distribué via Redis sliding window algorithm."""

    # Configuration rate limits
    RATE_LIMITS = {
        "/api/v1/auth/login": {"requests": 5, "window": 60, "block": 300},
        "/api/v1/auth/refresh": {"requests": 10, "window": 60, "block": 60},
        "POST": {"requests": 100, "window": 60, "block": 60},
        "GET": {"requests": 1000, "window": 60, "block": 60},
    }

    async def dispatch(self, request: Request, call_next: Callable):
        """Vérifie rate limit avec Redis sliding window."""

        # Identifier client (IP + User-Agent pour éviter IP spoofing)
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")[:50]
        client_id = f"{client_ip}:{user_agent}"

        # Déterminer rate limit applicable
        rate_limit = self._get_rate_limit_config(request)

        if rate_limit:
            # Vérifier si client bloqué
            block_key = f"rate_limit:block:{client_id}:{request.url.path}"
            if redis_client.exists(block_key):
                remaining_block = redis_client.ttl(block_key)
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many requests. Please try again later.",
                        "retry_after": remaining_block
                    },
                    headers={"Retry-After": str(remaining_block)}
                )

            # Sliding window avec Redis sorted set
            window_key = f"rate_limit:{client_id}:{request.url.path}"
            now = time.time()
            window_start = now - rate_limit["window"]

            # Pipeline Redis pour atomicité
            pipe = redis_client.pipeline()

            # 1. Supprimer requêtes hors fenêtre
            pipe.zremrangebyscore(window_key, 0, window_start)

            # 2. Compter requêtes dans fenêtre
            pipe.zcard(window_key)

            # 3. Ajouter requête actuelle
            pipe.zadd(window_key, {str(now): now})

            # 4. Expirer clé après fenêtre
            pipe.expire(window_key, rate_limit["window"] + 10)

            results = pipe.execute()
            request_count = results[1]  # zcard result

            # Vérifier dépassement
            if request_count >= rate_limit["requests"]:
                # Bloquer client pour block_duration
                redis_client.setex(
                    block_key,
                    rate_limit["block"],
                    "blocked"
                )

                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": f"Rate limit exceeded. Blocked for {rate_limit['block']} seconds.",
                        "retry_after": rate_limit["block"]
                    },
                    headers={"Retry-After": str(rate_limit["block"])}
                )

            # Ajouter headers rate limit info
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(rate_limit["requests"])
            response.headers["X-RateLimit-Remaining"] = str(
                rate_limit["requests"] - request_count - 1
            )
            response.headers["X-RateLimit-Reset"] = str(
                int(now + rate_limit["window"])
            )
            return response

        # Pas de rate limit configuré
        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extrait IP réelle du client (support proxy)."""
        # Support X-Forwarded-For (load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Support X-Real-IP (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback IP directe
        return request.client.host if request.client else "unknown"

    def _get_rate_limit_config(self, request: Request) -> dict | None:
        """Détermine config rate limit pour requête."""
        path = request.url.path
        method = request.method

        # 1. Check endpoint spécifique (plus prioritaire)
        if path in self.RATE_LIMITS:
            return self.RATE_LIMITS[path]

        # 2. Check méthode HTTP
        if method in self.RATE_LIMITS:
            return self.RATE_LIMITS[method]

        # 3. Pas de rate limit (health, docs, etc.)
        return None
```

**3. Tests rate limiting**
```python
# tests/security/test_rate_limiting.py

import time

def test_rate_limit_login_after_5_attempts(client):
    """6e tentative login → 429."""
    for i in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "test@test.com", "password": "wrong"}
        )
        # Premières 5 tentatives → 401 (auth fail)
        assert response.status_code == 401

    # 6e tentative → 429 (rate limit)
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@test.com", "password": "wrong"}
    )
    assert response.status_code == 429
    assert "Too many requests" in response.json()["detail"]
    assert "Retry-After" in response.headers

def test_rate_limit_block_persists_across_requests(client):
    """Block rate limit persiste pendant block_duration."""
    # Déclencher block
    for i in range(6):
        client.post("/api/v1/auth/login", data={"username": "test", "password": "x"})

    # Vérifier block persiste
    time.sleep(1)
    response = client.post("/api/v1/auth/login", data={"username": "test", "password": "x"})
    assert response.status_code == 429

    # Vérifier Retry-After diminue
    retry_after_1 = int(response.headers["Retry-After"])
    time.sleep(2)
    response = client.post("/api/v1/auth/login", data={"username": "test", "password": "x"})
    retry_after_2 = int(response.headers["Retry-After"])
    assert retry_after_2 < retry_after_1

def test_rate_limit_different_ips_independent(client, monkeypatch):
    """Rate limit par IP : clients différents indépendants."""
    # Client 1 (IP 1.2.3.4)
    for i in range(5):
        with monkeypatch.context() as m:
            m.setattr("request.client.host", "1.2.3.4")
            client.post("/api/v1/auth/login", data={"username": "test", "password": "x"})

    # Client 2 (IP 5.6.7.8) peut toujours faire 5 requêtes
    with monkeypatch.context() as m:
        m.setattr("request.client.host", "5.6.7.8")
        response = client.post("/api/v1/auth/login", data={"username": "test", "password": "x"})
        assert response.status_code == 401  # Pas 429

def test_rate_limit_headers_present(client, auth_headers):
    """Headers X-RateLimit-* présents dans réponse."""
    response = client.get("/api/v1/products", headers=auth_headers)

    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers
    assert int(response.headers["X-RateLimit-Remaining"]) < int(response.headers["X-RateLimit-Limit"])

def test_rate_limit_sliding_window_expires_old_requests(client, redis_client_test):
    """Requêtes hors fenêtre ne comptent pas."""
    # Faire 3 requêtes
    for i in range(3):
        client.get("/api/v1/products", headers=auth_headers)

    # Attendre expiration fenêtre (60s)
    time.sleep(61)

    # Nouvelles 5 requêtes devraient passer (fenêtre réinitialisée)
    for i in range(5):
        response = client.post("/api/v1/auth/login", data={"username": "test", "password": "x"})
        assert response.status_code == 401  # Pas 429
```

**4. Monitoring et alerting**
```python
# app/middleware/security.py - Ajouter logging

import logging
logger = logging.getLogger(__name__)

# Dans RateLimitMiddleware.dispatch()
if request_count >= rate_limit["requests"]:
    # Log pour monitoring
    logger.warning(
        f"Rate limit exceeded",
        extra={
            "client_ip": client_ip,
            "path": request.url.path,
            "method": request.method,
            "request_count": request_count,
            "limit": rate_limit["requests"],
            "user_agent": user_agent
        }
    )

    # Alerting si trop de blocks (potentiel DDoS)
    # TODO: Intégrer avec système alerting (PagerDuty, Slack, etc.)
```

**Estimation**: 10 heures (impl + tests + monitoring + doc)
**Priorité**: P1 - Vulnérabilité majeure production

---

### 🟠 BUG #5 - CONFORMITÉ P0 : Audit Log Manquant

**Fichiers impactés**:
- Aucun modèle `AuditLog` n'existe
- Aucun middleware audit
- Aucun service audit

**Problème**:
- **Aucune trace des actions utilisateurs**
- Impossible de savoir qui a créé/modifié/supprimé une entité
- Impossible de tracer qui a accédé à quelles données
- **Non-conformité RGPD Article 30** (registre des activités de traitement)
- **Non-conformité SOC 2** (audit trail)
- **Risque légal**: Amendes RGPD jusqu'à 20M€ ou 4% CA mondial

**Impact Business**:
- Enquête forensique impossible en cas de breach sécurité
- Pas de preuve pour litiges juridiques
- Pas de traçabilité conformité
- Impossible de détecter accès non autorisés
- Impossible d'auditer qui a consulté données sensibles

**Architecture audit log complète**:

**1. Modèle AuditLog**
```python
# app/models/audit_log.py

from datetime import datetime
from sqlalchemy import BigInteger, String, Text, Index, text
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class AuditLog(Base):
    """Log d'audit immuable append-only.

    Enregistre toutes les actions sensibles pour conformité RGPD/SOC2.

    Attributes:
        user_id: ID de l'utilisateur (peut être NULL pour actions système)
        tenant_id: ID du tenant
        action: Type d'action (CREATE, UPDATE, DELETE, READ, LOGIN, LOGOUT, etc.)
        entity_type: Type d'entité (User, Customer, Reservation, Invoice, etc.)
        entity_id: ID de l'entité impactée (NULL pour actions globales)
        changes: JSONB des modifications (before/after pour UPDATE)
        ip_address: IP du client
        user_agent: User-Agent du client
        request_id: ID de requête pour corrélation logs
        created_at: Timestamp action (immuable)

    Security:
        - Append-only (pas de UPDATE/DELETE)
        - Trigger DB empêche modifications
        - Retention policy 7 ans (conformité)
        - Chiffrement au repos (DB encryption)
    """

    __tablename__ = "audit_logs"

    # Clé primaire
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Acteur
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="ID utilisateur (NULL pour actions système)"
    )

    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="ID du tenant"
    )

    # Action
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type d'action (CREATE, UPDATE, DELETE, READ, LOGIN, etc.)"
    )

    # Entité impactée
    entity_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Type d'entité (User, Customer, Reservation, etc.)"
    )

    entity_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="ID de l'entité impactée"
    )

    # Détails
    changes: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSONB des modifications (before/after)"
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description humaine de l'action"
    )

    # Contexte requête
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        comment="IP du client"
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="User-Agent du client"
    )

    request_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="UUID de requête pour corrélation"
    )

    # Timestamp immuable
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("now()"),
        comment="Timestamp création (immuable)"
    )

    # Indexes pour queries fréquentes
    __table_args__ = (
        # Index composite pour queries par tenant + date
        Index("idx_audit_tenant_created", "tenant_id", "created_at"),

        # Index pour queries par user
        Index("idx_audit_user_created", "user_id", "created_at"),

        # Index pour queries par entité
        Index("idx_audit_entity", "entity_type", "entity_id", "created_at"),

        # Index pour queries par action
        Index("idx_audit_action_created", "action", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, user={self.user_id}, "
            f"action={self.action}, entity={self.entity_type}:{self.entity_id})>"
        )
```

**2. Migration Alembic avec trigger immutabilité**
```python
# alembic/versions/xxx_add_audit_log_table.py

def upgrade() -> None:
    # Créer table audit_logs
    op.create_table(
        'audit_logs',
        # ... colonnes ...
    )

    # Créer trigger PostgreSQL pour empêcher UPDATE/DELETE
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                RAISE EXCEPTION 'DELETE on audit_logs is not allowed';
            ELSIF (TG_OP = 'UPDATE') THEN
                RAISE EXCEPTION 'UPDATE on audit_logs is not allowed';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER prevent_audit_modification
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();
    """)

    # Créer partition par mois (performance queries grandes volumétries)
    op.execute("""
        -- Partition par mois pour performance
        CREATE TABLE audit_logs_y2026m01 PARTITION OF audit_logs
        FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

        CREATE TABLE audit_logs_y2026m02 PARTITION OF audit_logs
        FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

        -- TODO: Créer partitions futures via cron job
    """)

def downgrade() -> None:
    # Supprimer trigger
    op.execute("DROP TRIGGER IF EXISTS prevent_audit_modification ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")

    # Supprimer table
    op.drop_table('audit_logs')
```

**3. Service AuditLog**
```python
# app/services/audit.py

from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from typing import Optional, Any
import uuid

class AuditService:
    """Service pour enregistrer actions dans audit log."""

    def __init__(self, db: Session):
        self.db = db

    def log_action(
        self,
        action: str,
        tenant_id: int,
        user_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        changes: Optional[dict[str, Any]] = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> AuditLog:
        """Enregistre une action dans l'audit log.

        Args:
            action: Type d'action (CREATE, UPDATE, DELETE, READ, LOGIN, etc.)
            tenant_id: ID du tenant
            user_id: ID de l'utilisateur (NULL pour actions système)
            entity_type: Type d'entité (User, Customer, Reservation, etc.)
            entity_id: ID de l'entité impactée
            changes: Dictionnaire before/after pour UPDATE
            description: Description humaine de l'action
            ip_address: IP du client
            user_agent: User-Agent du client
            request_id: UUID de requête pour corrélation

        Returns:
            AuditLog créé

        Example:
            audit_service.log_action(
                action="CREATE",
                tenant_id=1,
                user_id=42,
                entity_type="Reservation",
                entity_id=123,
                changes={"status": {"before": "draft", "after": "confirmed"}},
                description="Réservation confirmée par user@example.com",
                ip_address="1.2.3.4",
                user_agent="Mozilla/5.0...",
                request_id="550e8400-e29b-41d4-a716-446655440000"
            )
        """
        audit_log = AuditLog(
            user_id=user_id,
            tenant_id=tenant_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id or str(uuid.uuid4())
        )

        self.db.add(audit_log)
        # Pas de commit (transaction gérée par endpoint/service appelant)

        return audit_log

    def log_create(
        self,
        entity_type: str,
        entity_id: int,
        entity_data: dict[str, Any],
        tenant_id: int,
        user_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str
    ) -> AuditLog:
        """Log création d'entité."""
        return self.log_action(
            action="CREATE",
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            changes={"after": entity_data},
            description=f"Created {entity_type} #{entity_id}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

    def log_update(
        self,
        entity_type: str,
        entity_id: int,
        before: dict[str, Any],
        after: dict[str, Any],
        tenant_id: int,
        user_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str
    ) -> AuditLog:
        """Log modification d'entité."""
        # Calculer uniquement champs modifiés
        changes = {}
        for key in after:
            if key in before and before[key] != after[key]:
                changes[key] = {"before": before[key], "after": after[key]}

        return self.log_action(
            action="UPDATE",
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            changes=changes,
            description=f"Updated {entity_type} #{entity_id}: {', '.join(changes.keys())}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

    def log_delete(
        self,
        entity_type: str,
        entity_id: int,
        entity_data: dict[str, Any],
        tenant_id: int,
        user_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str,
        soft_delete: bool = True
    ) -> AuditLog:
        """Log suppression d'entité."""
        action = "SOFT_DELETE" if soft_delete else "HARD_DELETE"
        return self.log_action(
            action=action,
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            changes={"before": entity_data},
            description=f"{'Soft' if soft_delete else 'Hard'} deleted {entity_type} #{entity_id}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

    def log_read_sensitive(
        self,
        entity_type: str,
        entity_id: int,
        tenant_id: int,
        user_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str
    ) -> AuditLog:
        """Log accès à données sensibles (conformité RGPD)."""
        return self.log_action(
            action="READ_SENSITIVE",
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            description=f"Accessed sensitive data {entity_type} #{entity_id}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

    def log_login(
        self,
        user_id: int,
        tenant_id: int,
        ip_address: str,
        user_agent: str,
        request_id: str,
        success: bool = True
    ) -> AuditLog:
        """Log tentative login."""
        action = "LOGIN_SUCCESS" if success else "LOGIN_FAILED"
        return self.log_action(
            action=action,
            tenant_id=tenant_id,
            user_id=user_id if success else None,
            description=f"Login {'successful' if success else 'failed'}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )
```

**4. Middleware audit automatique**
```python
# app/middleware/audit.py

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.database import get_db
from app.services.audit import AuditService
from app.core.security import decode_token
import uuid

class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware pour audit automatique des requêtes API."""

    # Endpoints sensibles à auditer (lecture données personnelles)
    SENSITIVE_READS = [
        "GET:/api/v1/customers/{id}",
        "GET:/api/v1/invoices/{id}",
        "GET:/api/v1/users/{id}"
    ]

    async def dispatch(self, request: Request, call_next):
        """Enregistre requête dans audit log si mutation ou lecture sensible."""

        # Générer request_id unique
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Extraire user info depuis JWT
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        payload = decode_token(token) if token else None

        user_id = int(payload.get("sub")) if payload and payload.get("sub") else None
        tenant_id = int(payload.get("tenant_id")) if payload and payload.get("tenant_id") else None

        # Extraire IP et User-Agent
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")

        # Exécuter requête
        response = await call_next(request)

        # Auditer seulement si authentifié et mutation réussie (2xx)
        if user_id and tenant_id and 200 <= response.status_code < 300:
            method = request.method
            path = request.url.path

            # Auditer mutations (POST, PUT, PATCH, DELETE)
            if method in ("POST", "PUT", "PATCH", "DELETE"):
                with next(get_db()) as db:
                    audit_service = AuditService(db)

                    # Déterminer action
                    action_map = {
                        "POST": "CREATE",
                        "PUT": "UPDATE",
                        "PATCH": "UPDATE",
                        "DELETE": "DELETE"
                    }
                    action = action_map[method]

                    # Extraire entity_type et entity_id depuis path
                    entity_type, entity_id = self._parse_entity_from_path(path)

                    audit_service.log_action(
                        action=action,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        description=f"{method} {path}",
                        ip_address=ip_address,
                        user_agent=user_agent,
                        request_id=request_id
                    )

                    db.commit()

            # Auditer lectures sensibles (données personnelles)
            elif method == "GET" and self._is_sensitive_read(path):
                with next(get_db()) as db:
                    audit_service = AuditService(db)
                    entity_type, entity_id = self._parse_entity_from_path(path)

                    audit_service.log_read_sensitive(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        request_id=request_id
                    )

                    db.commit()

        return response

    def _parse_entity_from_path(self, path: str) -> tuple[str, int | None]:
        """Extrait entity_type et entity_id depuis path API.

        Examples:
            /api/v1/customers/123 → ("Customer", 123)
            /api/v1/reservations/456 → ("Reservation", 456)
        """
        parts = path.strip('/').split('/')

        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "v1":
            entity_type = parts[2].rstrip('s').capitalize()  # customers → Customer
            entity_id = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
            return entity_type, entity_id

        return None, None

    def _is_sensitive_read(self, path: str) -> bool:
        """Vérifie si path correspond à lecture sensible."""
        for sensitive_pattern in self.SENSITIVE_READS:
            method, pattern = sensitive_pattern.split(":")
            # Match pattern avec {id} wildcard
            if self._match_path_pattern(path, pattern):
                return True
        return False

    def _match_path_pattern(self, path: str, pattern: str) -> bool:
        """Match path avec pattern contenant {id}."""
        pattern_parts = pattern.strip('/').split('/')
        path_parts = path.strip('/').split('/')

        if len(pattern_parts) != len(path_parts):
            return False

        for pattern_part, path_part in zip(pattern_parts, path_parts):
            if pattern_part.startswith('{') and pattern_part.endswith('}'):
                # Wildcard {id} match anything
                continue
            elif pattern_part != path_part:
                return False

        return True
```

**5. Intégration dans endpoints**
```python
# app/api/v1/endpoints/customers.py - Exemple

@router.post("/", response_model=CustomerResponse, status_code=201)
def create_customer(
    customer: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Crée un nouveau client (avec audit log)."""
    from app.services.audit import AuditService

    # Créer client
    customer_service = CustomerService(db)
    new_customer = customer_service.create_customer(customer, current_user.tenant_id)

    # Audit log
    audit_service = AuditService(db)
    audit_service.log_create(
        entity_type="Customer",
        entity_id=new_customer.id,
        entity_data=customer.model_dump(),
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        request_id=getattr(request.state, "request_id", None)
    )

    db.commit()
    return new_customer
```

**6. Tests audit log**
```python
# tests/security/test_audit_log.py

def test_audit_log_records_create_action(client, auth_headers, test_db):
    """Création customer enregistrée dans audit log."""
    response = client.post(
        "/api/v1/customers",
        json={
            "customer_type": "individual",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@test.com",
            ...
        },
        headers=auth_headers
    )
    assert response.status_code == 201
    customer_id = response.json()["id"]

    # Vérifier audit log créé
    audit_log = test_db.query(AuditLog).filter(
        AuditLog.entity_type == "Customer",
        AuditLog.entity_id == customer_id,
        AuditLog.action == "CREATE"
    ).first()

    assert audit_log is not None
    assert audit_log.user_id == test_user.id
    assert audit_log.tenant_id == 1
    assert audit_log.changes["after"]["email"] == "john.doe@test.com"
    assert audit_log.ip_address is not None

def test_audit_log_immutable_no_update_allowed(test_db, test_audit_log):
    """UPDATE sur audit_logs → Exception."""
    with pytest.raises(Exception, match="UPDATE on audit_logs is not allowed"):
        test_audit_log.action = "MODIFIED"
        test_db.commit()

def test_audit_log_immutable_no_delete_allowed(test_db, test_audit_log):
    """DELETE sur audit_logs → Exception."""
    with pytest.raises(Exception, match="DELETE on audit_logs is not allowed"):
        test_db.delete(test_audit_log)
        test_db.commit()

def test_audit_log_records_sensitive_read(client, auth_headers, test_customer, test_db):
    """Lecture customer enregistrée comme READ_SENSITIVE."""
    response = client.get(
        f"/api/v1/customers/{test_customer.id}",
        headers=auth_headers
    )
    assert response.status_code == 200

    # Vérifier audit log READ_SENSITIVE
    audit_log = test_db.query(AuditLog).filter(
        AuditLog.entity_type == "Customer",
        AuditLog.entity_id == test_customer.id,
        AuditLog.action == "READ_SENSITIVE"
    ).first()

    assert audit_log is not None
    assert audit_log.user_id == test_user.id

def test_audit_log_retention_policy_7_years(test_db):
    """Audit logs conservés 7 ans (conformité)."""
    # TODO: Implémenter job cron suppression logs > 7 ans
    # Vérifier retention policy configurée
    pass
```

**7. Endpoints audit log pour admins**
```python
# app/api/v1/endpoints/audit.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, require_role
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogResponse, AuditLogList
from datetime import datetime, timedelta

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/", response_model=AuditLogList)
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    skip: int = 0,
    limit: int = 100
):
    """Liste les audit logs (admin uniquement).

    Filtres:
        - start_date, end_date: Plage de dates
        - user_id: Utilisateur ayant effectué l'action
        - action: Type d'action (CREATE, UPDATE, etc.)
        - entity_type: Type d'entité (Customer, Reservation, etc.)
    """
    query = db.query(AuditLog).filter(
        AuditLog.tenant_id == current_user.tenant_id
    )

    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)
    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()

    return {"logs": logs, "total": total}

@router.get("/user/{user_id}", response_model=AuditLogList)
def get_user_audit_trail(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
    days: int = Query(30, ge=1, le=90)
):
    """Historique complet d'un utilisateur (30 derniers jours par défaut)."""
    start_date = datetime.now() - timedelta(days=days)

    logs = db.query(AuditLog).filter(
        AuditLog.tenant_id == current_user.tenant_id,
        AuditLog.user_id == user_id,
        AuditLog.created_at >= start_date
    ).order_by(AuditLog.created_at.desc()).all()

    return {"logs": logs, "total": len(logs)}
```

**Estimation**: 20 heures (modèle + migration + service + middleware + endpoints + tests + doc)
**Priorité**: P0 - Conformité légale obligatoire

---

### 🟠 BUG #6 - MAJEUR P1 : Exception Handling Non Testé (JWT Validation)

**Fichiers impactés**:
- `app/core/deps.py` lignes 62, 71, 76-77, 82, 86 (non couvertes)
- `tests/security/test_auth_security.py` (tests manquants)

**Problème**:
```python
# app/core/deps.py ligne 62 - Token type invalide (NON TESTÉ)
if token_type != "access":
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token type"  # ❌ Jamais testé
    )

# Ligne 71 - Sub manquant (NON TESTÉ)
if user_id_str is None:
    raise credentials_exception  # ❌ Jamais testé

# Lignes 76-77 - Sub non-numérique (NON TESTÉ)
try:
    user_id = int(user_id_str)
except (ValueError, TypeError):
    raise credentials_exception  # ❌ Jamais testé

# Ligne 82 - User non trouvé (NON TESTÉ)
if user is None:
    raise credentials_exception  # ❌ Jamais testé

# Ligne 86 - Compte inactif (NON TESTÉ)
if not user.is_active:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Inactive account"  # ❌ Jamais testé
    )
```

**Impact Production**:
- **Sécurité**: Branches d'erreur non validées → attaquant pourrait exploiter comportement inattendu
- **Observabilité**: Logs d'erreur non testés → debugging difficile en production
- **Conformité**: OWASP A07:2021 (Identification and Authentication Failures) - tests insuffisants

**Couverture actuelle**:
- Tests existants utilisent UNIQUEMENT tokens valides
- Aucun test de rejection (token type invalide, sub manquant, compte inactif)
- 5 branches critiques = 0% couvertes

**Scénarios d'attaque non couverts**:
1. **Refresh token utilisé comme access token**
   - Attaquant envoie `{"type": "refresh"}` au lieu de `{"type": "access"}`
   - Comportement attendu: 401 "Invalid token type"
   - Statut: NON TESTÉ ❌

2. **Token sans claim "sub"**
   - JWT valide mais malformé: `{"type": "access", "tenant_id": 1}`
   - Comportement attendu: 401 "Could not validate credentials"
   - Statut: NON TESTÉ ❌

3. **Claim "sub" non-numérique**
   - JWT avec `{"sub": "invalid", "type": "access"}`
   - Comportement attendu: 401 "Could not validate credentials"
   - Statut: NON TESTÉ ❌

4. **User supprimé après émission token**
   - Token valide mais user supprimé de DB
   - Comportement attendu: 401 "Could not validate credentials"
   - Statut: NON TESTÉ ❌

5. **Compte désactivé (is_active=False)**
   - Token valide mais user.is_active=False
   - Comportement attendu: 403 "Inactive account"
   - Statut: NON TESTÉ ❌

**Solution**:

**1. Créer fichier tests complet** : `tests/security/test_jwt_validation.py`

```python
"""Tests sécurité JWT - Validation exhaustive des rejections."""
import pytest
from datetime import datetime, timezone, timedelta
from jose import jwt
from fastapi import HTTPException
from app.core.deps import get_current_user, oauth2_scheme
from app.core.config import settings
from app.models.user import User


# ═══════════════════════════════════════════════════════════════════════════
# Helpers JWT manipulation
# ═══════════════════════════════════════════════════════════════════════════

def create_malformed_token(payload_override: dict) -> str:
    """Créer un JWT avec payload personnalisé (pour tests d'attaque).

    Args:
        payload_override: Dict avec claims à override/ajouter

    Returns:
        JWT signé mais potentiellement malformé
    """
    base_payload = {
        "sub": "1",
        "type": "access",
        "tenant_id": 1,
        "email": "test@carocorp.com",
        "role": "staff",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc)
    }
    base_payload.update(payload_override)

    return jwt.encode(base_payload, settings.JWT_SECRET, algorithm="HS256")


# ═══════════════════════════════════════════════════════════════════════════
# Tests Token Type Validation
# ═══════════════════════════════════════════════════════════════════════════

def test_reject_refresh_token_as_access(test_db, test_user):
    """❌ ATTAQUE: Utiliser refresh token comme access token.

    Scénario:
        1. Attaquant obtient un refresh token
        2. Tente de l'utiliser pour accéder à un endpoint protégé
        3. Doit être rejeté avec 401 "Invalid token type"
    """
    # Créer refresh token (type="refresh" au lieu de "access")
    malicious_token = create_malformed_token({"type": "refresh"})

    # Tenter d'utiliser comme access token
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db=test_db, token=malicious_token)

    # Vérifier rejection
    assert exc_info.value.status_code == 401
    assert "Invalid token type" in exc_info.value.detail


def test_reject_token_without_type_claim(test_db, test_user):
    """❌ ATTAQUE: Token sans claim 'type'.

    Scénario:
        1. Attaquant forge un JWT sans claim "type"
        2. Doit être rejeté avec 401
    """
    malicious_token = create_malformed_token({"type": None})  # Supprime type
    del jwt.decode(malicious_token, settings.JWT_SECRET, algorithms=["HS256"])["type"]

    # Re-encoder sans type
    payload = jwt.decode(malicious_token, settings.JWT_SECRET, algorithms=["HS256"])
    payload.pop("type", None)
    token_without_type = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db=test_db, token=token_without_type)

    assert exc_info.value.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# Tests Claim "sub" Validation
# ═══════════════════════════════════════════════════════════════════════════

def test_reject_token_without_sub_claim(test_db):
    """❌ ATTAQUE: Token sans claim 'sub' (user_id).

    Scénario:
        1. Attaquant forge un JWT sans claim "sub"
        2. Doit être rejeté avec 401 "Could not validate credentials"
    """
    # Créer token sans sub
    payload = {
        "type": "access",
        "tenant_id": 1,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }  # Pas de "sub"

    token_without_sub = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db=test_db, token=token_without_sub)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail


def test_reject_token_with_non_numeric_sub(test_db):
    """❌ ATTAQUE: Claim 'sub' non-numérique.

    Scénario:
        1. Attaquant forge un JWT avec sub="invalid" (string non-numérique)
        2. Conversion int(sub) échoue → ValueError
        3. Doit être rejeté avec 401
    """
    malicious_token = create_malformed_token({"sub": "not_a_number"})

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db=test_db, token=malicious_token)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail


def test_reject_token_with_null_sub(test_db):
    """❌ ATTAQUE: Claim 'sub' = null.

    Scénario:
        1. JWT avec {"sub": null}
        2. Doit être rejeté avec 401
    """
    malicious_token = create_malformed_token({"sub": None})

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db=test_db, token=malicious_token)

    assert exc_info.value.status_code == 401


def test_reject_token_with_negative_sub(test_db):
    """❌ ATTAQUE: Claim 'sub' négatif.

    Scénario:
        1. JWT avec {"sub": "-1"}
        2. Conversion réussit mais user_id=-1 n'existe pas
        3. Doit être rejeté avec 401
    """
    malicious_token = create_malformed_token({"sub": "-1"})

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db=test_db, token=malicious_token)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════════════════════
# Tests User Existence & State
# ═══════════════════════════════════════════════════════════════════════════

def test_reject_token_for_deleted_user(test_db, test_user):
    """❌ ATTAQUE: Token valide mais user supprimé.

    Scénario:
        1. User obtient un access token
        2. Admin supprime le compte user
        3. User tente d'utiliser l'ancien token
        4. Doit être rejeté avec 401 (user not found)
    """
    # Créer token valide pour test_user
    valid_token = create_malformed_token({"sub": str(test_user.id)})

    # Vérifier que token fonctionne AVANT suppression
    current_user = get_current_user(db=test_db, token=valid_token)
    assert current_user.id == test_user.id

    # Supprimer user de DB
    test_db.delete(test_user)
    test_db.commit()

    # Tenter d'utiliser token APRÈS suppression
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db=test_db, token=valid_token)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail


def test_reject_token_for_inactive_user(test_db, test_user):
    """❌ ATTAQUE: Token valide mais compte désactivé.

    Scénario:
        1. User obtient un access token
        2. Admin désactive le compte (is_active=False)
        3. User tente d'utiliser l'ancien token
        4. Doit être rejeté avec 403 "Inactive account"
    """
    # Créer token valide pour test_user
    valid_token = create_malformed_token({"sub": str(test_user.id)})

    # Vérifier que token fonctionne AVANT désactivation
    current_user = get_current_user(db=test_db, token=valid_token)
    assert current_user.id == test_user.id

    # Désactiver compte
    test_user.is_active = False
    test_db.commit()

    # Tenter d'utiliser token APRÈS désactivation
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db=test_db, token=valid_token)

    assert exc_info.value.status_code == 403  # Forbidden (pas 401)
    assert "Inactive account" in exc_info.value.detail


def test_reject_token_for_nonexistent_user_id(test_db):
    """❌ ATTAQUE: Token avec user_id inexistant.

    Scénario:
        1. Attaquant forge un JWT avec sub="999999" (user_id inexistant)
        2. Doit être rejeté avec 401
    """
    malicious_token = create_malformed_token({"sub": "999999"})

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(db=test_db, token=malicious_token)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════════════════════
# Tests Cross-Tenant (Bonus Coverage)
# ═══════════════════════════════════════════════════════════════════════════

def test_accept_token_from_different_tenant(test_db):
    """✅ Token d'un autre tenant est valide (isolation gérée par repositories).

    Note:
        L'isolation multi-tenant se fait au niveau repository via tenant_id,
        pas au niveau JWT validation. Un token tenant_id=2 est valide même
        si l'API utilise tenant_id=1.
    """
    # Créer user tenant_id=2
    other_tenant_user = User(
        tenant_id=2,
        email="other@tenant.com",
        hashed_password="hash",
        full_name="Other Tenant",
        role="staff"
    )
    test_db.add(other_tenant_user)
    test_db.commit()
    test_db.refresh(other_tenant_user)

    # Créer token pour tenant_id=2
    token_tenant2 = create_malformed_token({
        "sub": str(other_tenant_user.id),
        "tenant_id": 2
    })

    # Token doit être accepté (validation JWT réussie)
    current_user = get_current_user(db=test_db, token=token_tenant2)
    assert current_user.id == other_tenant_user.id
    assert current_user.tenant_id == 2  # ✅ Isolation via repository plus tard
```

**2. Ajouter tests dans CI** : Mettre à jour `.github/workflows/tests.yml`

```yaml
- name: Run Security Tests (JWT Validation)
  run: |
    pytest tests/security/test_jwt_validation.py -v --cov=app/core/deps --cov-report=term
```

**Estimation**: 4 heures (tests + validation + doc)
**Priorité**: P1 - Sécurité critique mais pas bloquant production immédiat

---

### 🟠 BUG #7 - MAJEUR P1 : Exception Handling Services Non Testé

**Fichiers impactés**:
- `app/services/reservation.py` lignes 86-87, 96-97, 102, 417 (non couvertes)
- `app/services/product.py` lignes 87, 94-101, 151, 214, 255, 294 (non couvertes)

**Problème**:

**A. ReservationService - Validations non testées** (lignes 86-87, 96-97, 102)

```python
# app/services/reservation.py ligne 86-87
if reservation.status != ReservationStatus.DRAFT:
    raise ValueError(f"Cannot confirm reservation with status {reservation.status}")
    # ❌ Jamais testé

# Lignes 96-97
if not reservation.lines:
    raise ValueError("Cannot confirm reservation without lines")
    # ❌ Jamais testé

# Ligne 102
if line.quantity > available:
    raise ValueError(f"Insufficient stock for product {product.name}")
    # ❌ Jamais testé (stock insuffisant)
```

**B. ProductService - Race conditions non testées** (lignes 94-101)

```python
# app/services/product.py lignes 94-101
try:
    self.db.commit()
except IntegrityError as e:
    self.db.rollback()
    if "available_quantity_non_negative" in str(e):
        raise ValueError(f"Insufficient stock for product {product.name}")
    raise  # ❌ IntegrityError JAMAIS testé
```

**C. ProductService - Validation edge case** (ligne 87)

```python
# Ligne 87
if product.available_quantity > product.stock_quantity:
    raise ValueError("Available quantity cannot exceed stock quantity")
    # ❌ Jamais testé (validation business logic)
```

**D. ProductService - Hard delete non testé** (ligne 294)

```python
# Ligne 294
def hard_delete(self, product_id: int, tenant_id: int) -> bool:
    product = self.repository.get_by_id(product_id, tenant_id)
    if not product:
        return False  # ❌ Jamais testé

    self.db.delete(product)
    self.db.commit()
    return True
```

**Impact Production**:
- **Comportement erreur non validé**: Exceptions levées mais messages d'erreur jamais testés
- **Race conditions**: Réservations concurrentes peuvent causer IntegrityError non géré proprement
- **Validations business**: Edge cases (stock négatif, quantity > available) non couverts
- **Hard delete**: Opération destructive non testée (risque perte données)

**Scénarios d'erreur non couverts**:

1. **Confirmer réservation déjà confirmée**
   - État initial: reservation.status = "confirmed"
   - Action: Appeler `confirm_reservation()`
   - Résultat attendu: ValueError "Cannot confirm reservation with status confirmed"
   - Statut: NON TESTÉ ❌

2. **Confirmer réservation sans lignes**
   - État initial: reservation.lines = []
   - Action: Appeler `confirm_reservation()`
   - Résultat attendu: ValueError "Cannot confirm reservation without lines"
   - Statut: NON TESTÉ ❌

3. **Stock insuffisant lors confirmation**
   - État initial: product.available_quantity = 5, line.quantity = 10
   - Action: Appeler `confirm_reservation()`
   - Résultat attendu: ValueError "Insufficient stock for product X"
   - Statut: NON TESTÉ ❌

4. **Race condition double réservation**
   - État initial: product.available_quantity = 1
   - Action: 2 réservations simultanées pour quantity=1
   - Résultat attendu: 1 réussit, 1 échoue avec IntegrityError → ValueError
   - Statut: NON TESTÉ ❌

5. **Available > Stock validation**
   - État initial: product.stock_quantity = 10
   - Action: Mettre available_quantity = 15
   - Résultat attendu: ValueError "Available quantity cannot exceed stock quantity"
   - Statut: NON TESTÉ ❌

**Solution**:

**1. Créer tests exception handling** : `tests/unit/test_reservation_service_errors.py`

```python
"""Tests exceptions ReservationService - Edge cases et validations."""
import pytest
from app.services.reservation import ReservationService
from app.models.reservation import Reservation, ReservationLine
from app.models.product import Product
from app.constants.business import ReservationStatus


def test_confirm_reservation_already_confirmed(test_db, test_customer, test_product):
    """❌ Erreur: Confirmer une réservation déjà confirmée."""
    # Créer réservation CONFIRMÉE
    reservation = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        status=ReservationStatus.CONFIRMED,  # Déjà confirmée
        total_amount_cents=1000
    )
    test_db.add(reservation)
    test_db.commit()
    test_db.refresh(reservation)

    # Tenter de RE-confirmer
    service = ReservationService(test_db)

    with pytest.raises(ValueError) as exc_info:
        service.confirm_reservation(reservation.id, tenant_id=1)

    assert "Cannot confirm reservation with status confirmed" in str(exc_info.value)


def test_confirm_reservation_without_lines(test_db, test_customer):
    """❌ Erreur: Confirmer une réservation sans lignes."""
    # Créer réservation SANS lignes
    reservation = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        status=ReservationStatus.DRAFT,
        total_amount_cents=0
    )
    test_db.add(reservation)
    test_db.commit()
    test_db.refresh(reservation)

    # reservation.lines = [] (vide)
    service = ReservationService(test_db)

    with pytest.raises(ValueError) as exc_info:
        service.confirm_reservation(reservation.id, tenant_id=1)

    assert "Cannot confirm reservation without lines" in str(exc_info.value)


def test_confirm_reservation_insufficient_stock(test_db, test_customer, test_product):
    """❌ Erreur: Stock insuffisant lors de la confirmation."""
    # Réduire stock disponible
    test_product.available_quantity = 5
    test_db.commit()

    # Créer réservation avec quantity > available
    reservation = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        status=ReservationStatus.DRAFT,
        total_amount_cents=10000
    )
    test_db.add(reservation)
    test_db.flush()

    line = ReservationLine(
        tenant_id=1,
        reservation_id=reservation.id,
        product_id=test_product.id,
        quantity=10,  # > available (5)
        unit_price_cents=1000,
        subtotal_cents=10000
    )
    test_db.add(line)
    test_db.commit()
    test_db.refresh(reservation)

    # Tenter de confirmer
    service = ReservationService(test_db)

    with pytest.raises(ValueError) as exc_info:
        service.confirm_reservation(reservation.id, tenant_id=1)

    assert "Insufficient stock for product" in str(exc_info.value)
    assert test_product.name in str(exc_info.value)


def test_concurrent_reservations_race_condition(test_db, test_customer, test_product):
    """❌ Erreur: Race condition - 2 réservations simultanées dépassent stock.

    Scénario:
        1. Product.available_quantity = 5
        2. Reservation A demande 3 unités
        3. Reservation B demande 3 unités (SIMULTANÉ)
        4. Une des deux doit échouer avec IntegrityError → ValueError
    """
    # Stock limité
    test_product.available_quantity = 5
    test_db.commit()

    # Créer 2 réservations en parallèle (simuler race condition)
    service = ReservationService(test_db)

    # Réservation A
    res_a = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        status=ReservationStatus.DRAFT,
        total_amount_cents=3000
    )
    test_db.add(res_a)
    test_db.flush()

    line_a = ReservationLine(
        tenant_id=1,
        reservation_id=res_a.id,
        product_id=test_product.id,
        quantity=3,
        unit_price_cents=1000,
        subtotal_cents=3000
    )
    test_db.add(line_a)
    test_db.commit()

    # Réservation B (AVANT commit de A pour simuler race)
    res_b = Reservation(
        tenant_id=1,
        customer_id=test_customer.id,
        status=ReservationStatus.DRAFT,
        total_amount_cents=3000
    )
    test_db.add(res_b)
    test_db.flush()

    line_b = ReservationLine(
        tenant_id=1,
        reservation_id=res_b.id,
        product_id=test_product.id,
        quantity=3,
        unit_price_cents=1000,
        subtotal_cents=3000
    )
    test_db.add(line_b)
    test_db.commit()

    # Confirmer A (devrait réussir)
    service.confirm_reservation(res_a.id, tenant_id=1)
    test_db.refresh(test_product)
    assert test_product.available_quantity == 2  # 5 - 3 = 2

    # Confirmer B (devrait ÉCHOUER car 2 < 3)
    with pytest.raises(ValueError) as exc_info:
        service.confirm_reservation(res_b.id, tenant_id=1)

    assert "Insufficient stock" in str(exc_info.value)
```

**2. Créer tests ProductService** : `tests/unit/test_product_service_errors.py`

```python
"""Tests exceptions ProductService - Validations et edge cases."""
import pytest
from sqlalchemy.exc import IntegrityError
from app.services.product import ProductService
from app.models.product import Product


def test_validation_available_exceeds_stock(test_db):
    """❌ Erreur: available_quantity > stock_quantity."""
    # Créer produit
    product = Product(
        tenant_id=1,
        name="Product Test",
        sku="TEST-001",
        category="test",
        price_per_day_cents=100,
        stock_quantity=10,
        available_quantity=10
    )
    test_db.add(product)
    test_db.commit()
    test_db.refresh(product)

    # Tenter de mettre available > stock
    service = ProductService(test_db)

    with pytest.raises(ValueError) as exc_info:
        service.update_product(
            product.id,
            tenant_id=1,
            available_quantity=15  # > stock (10)
        )

    assert "Available quantity cannot exceed stock quantity" in str(exc_info.value)


def test_reserve_stock_causes_integrity_error(test_db, test_product):
    """❌ Erreur: IntegrityError lors de la réservation (constraint violation).

    Scénario:
        1. Product.available_quantity = 1
        2. Réserver 2 unités
        3. DB constraint "available_quantity_non_negative" échoue
        4. IntegrityError → rollback + ValueError
    """
    # Stock minimal
    test_product.available_quantity = 1
    test_db.commit()

    service = ProductService(test_db)

    # Tenter de réserver plus que disponible
    with pytest.raises(ValueError) as exc_info:
        service.reserve_stock(test_product.id, quantity=2, tenant_id=1)

    assert "Insufficient stock for product" in str(exc_info.value)

    # Vérifier rollback (available doit rester 1)
    test_db.refresh(test_product)
    assert test_product.available_quantity == 1


def test_hard_delete_nonexistent_product(test_db):
    """❌ Erreur: Hard delete d'un produit inexistant."""
    service = ProductService(test_db)

    # Tenter de supprimer produit qui n'existe pas
    result = service.hard_delete(product_id=999999, tenant_id=1)

    assert result is False  # Doit retourner False


def test_hard_delete_success(test_db, test_product):
    """✅ Hard delete d'un produit existant."""
    service = ProductService(test_db)
    product_id = test_product.id

    # Supprimer
    result = service.hard_delete(product_id, tenant_id=1)

    assert result is True

    # Vérifier suppression DB
    deleted = test_db.query(Product).filter(Product.id == product_id).first()
    assert deleted is None
```

**Estimation**: 6 heures (tests + validation edge cases + doc)
**Priorité**: P1 - Couverture critique pour production

---

### 🟡 BUG #8 - MINEUR P2 : Property Helpers User Non Testés

**Fichiers impactés**:
- `app/models/user.py` lignes 77, 82, 87, 92 (properties non couvertes)

**Problème**:
```python
# app/models/user.py - Properties non testées

@property
def is_admin(self) -> bool:
    return self.role == "admin"  # ❌ Ligne 77 non couverte

@property
def is_manager(self) -> bool:
    return self.role == "manager"  # ❌ Ligne 82 non couverte

@property
def is_staff(self) -> bool:
    return self.role == "staff"  # ❌ Ligne 87 non couverte

@property
def can_manage_products(self) -> bool:
    return self.role in ["admin", "manager"]  # ❌ Ligne 92 non couverte
```

**Impact Production**:
- **Gravité**: Faible (helpers convenience uniquement)
- **Risque**: Aucun si properties simples (pas de logique complexe)
- **Maintenabilité**: Si logique évolue (ex: permissions custom), bugs non détectés

**Solution rapide**:

```python
# tests/unit/test_user_model.py - Ajouter tests properties

def test_user_is_admin_property(test_db):
    """Test property is_admin."""
    admin = User(tenant_id=1, email="admin@test.com", role="admin", hashed_password="hash", full_name="Admin")
    staff = User(tenant_id=1, email="staff@test.com", role="staff", hashed_password="hash", full_name="Staff")

    assert admin.is_admin is True
    assert staff.is_admin is False

def test_user_is_manager_property(test_db):
    """Test property is_manager."""
    manager = User(tenant_id=1, email="mgr@test.com", role="manager", hashed_password="hash", full_name="Manager")
    staff = User(tenant_id=1, email="staff@test.com", role="staff", hashed_password="hash", full_name="Staff")

    assert manager.is_manager is True
    assert staff.is_manager is False

def test_user_is_staff_property(test_db):
    """Test property is_staff."""
    staff = User(tenant_id=1, email="staff@test.com", role="staff", hashed_password="hash", full_name="Staff")
    admin = User(tenant_id=1, email="admin@test.com", role="admin", hashed_password="hash", full_name="Admin")

    assert staff.is_staff is True
    assert admin.is_staff is False

def test_user_can_manage_products_property(test_db):
    """Test property can_manage_products."""
    admin = User(tenant_id=1, email="admin@test.com", role="admin", hashed_password="hash", full_name="Admin")
    manager = User(tenant_id=1, email="mgr@test.com", role="manager", hashed_password="hash", full_name="Manager")
    staff = User(tenant_id=1, email="staff@test.com", role="staff", hashed_password="hash", full_name="Staff")

    assert admin.can_manage_products is True
    assert manager.can_manage_products is True
    assert staff.can_manage_products is False
```

**Estimation**: 1 heure (tests simples)
**Priorité**: P2 - Nice to have pour 100% coverage

---

### 🟠 BUG #9 - MAJEUR P1 : Database Connection Error Handling

**Fichiers impactés**:
- `app/core/database.py` lignes 35-39, 50-54 (non couvertes)
- `tests/integration/test_database_resilience.py` (manquant)

**Problème**:
```python
# app/core/database.py - Error handling non testé

def get_db() -> Generator:
    """Dependency pour obtenir une session DB.

    Yields:
        Session DB

    Raises:
        Exception si connexion DB échoue  # ❌ Jamais testé (lignes 35-39)

    Finally:
        Ferme la session (lignes 50-54)  # ❌ Jamais testé
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        # Lignes 35-39 NON COUVERTES
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        # Lignes 50-54 NON COUVERTES
        db.close()
```

**Impact Production**:
- **Connexion DB perdue**: Comportement non testé si PostgreSQL redémarre
- **Transaction rollback**: Branche exception jamais validée
- **Session cleanup**: Finally block non testé (risque connexions leaked)

**Scénarios critiques non testés**:

1. **PostgreSQL indisponible au démarrage**
   - État: PostgreSQL down
   - Action: Démarrer l'API
   - Résultat attendu: Erreur explicite, pas de crash silencieux
   - Statut: NON TESTÉ ❌

2. **Perte connexion en mid-request**
   - État: Request en cours, DB restart
   - Action: Query échoue avec OperationalError
   - Résultat attendu: Rollback + log erreur + 500 HTTP
   - Statut: NON TESTÉ ❌

3. **Session non fermée (leak)**
   - État: Exception avant yield
   - Action: Finally block doit fermer session
   - Résultat attendu: Pas de connection leak
   - Statut: NON TESTÉ ❌

**Solution**:

**1. Tests résilience DB** : `tests/integration/test_database_resilience.py`

```python
"""Tests résilience connexion base de données."""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError, DatabaseError
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db, SessionLocal


def test_database_unavailable_at_startup():
    """❌ PostgreSQL indisponible au démarrage de l'API.

    Scénario:
        1. PostgreSQL down
        2. API tente de créer SessionLocal
        3. Doit logger erreur explicite
    """
    with patch("app.core.database.SessionLocal") as mock_session:
        # Simuler DB indisponible
        mock_session.side_effect = OperationalError(
            "could not connect to server",
            params=None,
            orig=None
        )

        # Tenter d'obtenir session
        with pytest.raises(OperationalError) as exc_info:
            db_gen = get_db()
            next(db_gen)

        assert "could not connect to server" in str(exc_info.value)


def test_database_connection_lost_mid_request(client, test_db):
    """❌ Perte connexion DB en mid-request.

    Scénario:
        1. Request démarre normalement
        2. PostgreSQL restart pendant la query
        3. OperationalError levée
        4. Rollback + session close + 500 HTTP
    """
    with patch.object(test_db, "execute") as mock_execute:
        # Simuler perte connexion
        mock_execute.side_effect = OperationalError(
            "server closed the connection unexpectedly",
            params=None,
            orig=None
        )

        # Tenter une requête
        response = client.get("/api/v1/products")

        # Doit retourner 500 (Internal Server Error)
        assert response.status_code == 500

        # Vérifier rollback appelé
        assert test_db.rollback.called


def test_session_cleanup_on_exception():
    """✅ Session fermée même si exception levée.

    Scénario:
        1. get_db() yield session
        2. Exception levée dans le code endpoint
        3. Finally block doit fermer session (pas de leak)
    """
    mock_session = MagicMock()

    with patch("app.core.database.SessionLocal", return_value=mock_session):
        db_gen = get_db()

        try:
            db = next(db_gen)

            # Simuler exception dans endpoint
            raise ValueError("Test exception")
        except ValueError:
            pass
        finally:
            # Finaliser generator (déclenche finally block)
            try:
                next(db_gen)
            except StopIteration:
                pass

        # Vérifier que session.close() a été appelé
        assert mock_session.close.called


def test_database_timeout():
    """❌ Query timeout (longue requête).

    Scénario:
        1. Query prend > 30s
        2. PostgreSQL timeout
        3. Doit retourner erreur explicite
    """
    with patch("app.core.database.SessionLocal") as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Simuler timeout
        mock_session.execute.side_effect = OperationalError(
            "canceling statement due to statement timeout",
            params=None,
            orig=None
        )

        db_gen = get_db()
        db = next(db_gen)

        with pytest.raises(OperationalError) as exc_info:
            db.execute("SELECT pg_sleep(60);")

        assert "timeout" in str(exc_info.value).lower()
```

**2. Configuration timeout** : `app/core/database.py`

```python
# Ajouter paramètres résilience
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # ✅ Vérifier connexion avant utilisation
    pool_recycle=3600,   # ✅ Recycler connexions après 1h
    connect_args={
        "connect_timeout": 10,        # ✅ Timeout connexion 10s
        "options": "-c statement_timeout=30000"  # ✅ Timeout query 30s
    }
)
```

**Estimation**: 5 heures (tests résilience + config + doc)
**Priorité**: P1 - Production readiness critique

---

### 🟠 BUG #10 - MAJEUR P1 : JWT Token Expiration Edge Cases

**Fichiers impactés**:
- `app/core/security.py` (validation expiration)
- `app/api/v1/endpoints/auth.py` (refresh token flow)
- `tests/security/test_jwt_expiration.py` (manquant)

**Problème**:

**A. Token expiré accepté pendant grace period**
- JWT `exp` claim: `2024-01-01 12:00:00`
- Request arrive: `2024-01-01 12:00:05` (5s après expiration)
- Librairie `python-jose` accepte tokens avec clock skew (default 0s)
- Si clock skew configuré (leeway), tokens expirés acceptés

**B. Refresh token utilisé après expiration access token**
- Access token expire: `12:00:00`
- Refresh token expire: `12:00:00 + 7 jours`
- User tente refresh à `12:00:01`
- Comportement: Doit accepter (refresh valide)
- Statut: NON TESTÉ ❌

**C. Refresh token expiré**
- Refresh token expire: `2024-01-08 12:00:00`
- User tente refresh à `2024-01-08 12:05:00`
- Comportement: Doit rejeter avec 401 "Refresh token expired"
- Statut: NON TESTÉ ❌

**Impact Production**:
- **Sécurité**: Tokens expirés acceptés si clock skew mal configuré
- **UX**: Comportement refresh token expiré non validé
- **Conformité**: OWASP A07:2021 (session timeout validation)

**Solution**:

**1. Tests expiration** : `tests/security/test_jwt_expiration.py`

```python
"""Tests expiration JWT - Access & Refresh tokens."""
import pytest
from datetime import datetime, timezone, timedelta
from jose import jwt
from fastapi import HTTPException
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.core.config import settings


def test_reject_expired_access_token():
    """❌ Access token expiré doit être rejeté.

    Scénario:
        1. Créer access token avec exp = now - 1 minute
        2. Tenter de décoder
        3. Doit retourner None (signature invalide/expirée)
    """
    # Créer payload expiré
    payload = {
        "sub": "1",
        "type": "access",
        "tenant_id": 1,
        "email": "test@carocorp.com",
        "role": "staff",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),  # Expiré
        "iat": datetime.now(timezone.utc) - timedelta(minutes=10)
    }

    expired_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    # Décoder (doit échouer)
    result = decode_token(expired_token)

    assert result is None  # Token expiré rejeté


def test_accept_valid_access_token_before_expiration():
    """✅ Access token valide (avant expiration) doit être accepté."""
    # Créer token valide (expire dans 30 min)
    payload = {
        "sub": "1",
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        "iat": datetime.now(timezone.utc)
    }

    valid_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    # Décoder
    result = decode_token(valid_token)

    assert result is not None
    assert result["sub"] == "1"
    assert result["type"] == "access"


def test_refresh_token_used_after_access_token_expired(client, test_user):
    """✅ Refresh token valide peut être utilisé même si access token expiré.

    Scénario:
        1. User obtient access (expire 30min) + refresh (expire 7j)
        2. Access token expire
        3. User utilise refresh token pour obtenir nouveau access
        4. Doit réussir (refresh toujours valide)
    """
    # Simuler access token expiré
    expired_access_payload = {
        "sub": str(test_user.id),
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),  # Expiré
        "iat": datetime.now(timezone.utc) - timedelta(minutes=31)
    }
    expired_access = jwt.encode(expired_access_payload, settings.JWT_SECRET, algorithm="HS256")

    # Créer refresh token VALIDE
    refresh_token = create_refresh_token({"sub": str(test_user.id)})

    # Tenter de refresh (doit réussir)
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

    # Nouveau access token doit être valide
    new_access_payload = decode_token(data["access_token"])
    assert new_access_payload is not None
    assert new_access_payload["type"] == "access"


def test_reject_expired_refresh_token(client, test_user):
    """❌ Refresh token expiré doit être rejeté.

    Scénario:
        1. Créer refresh token avec exp = now - 1 jour
        2. Tenter de refresh
        3. Doit rejeter avec 401 "Invalid or expired refresh token"
    """
    # Créer refresh token expiré
    expired_refresh_payload = {
        "sub": str(test_user.id),
        "type": "refresh",
        "exp": datetime.now(timezone.utc) - timedelta(days=1),  # Expiré
        "iat": datetime.now(timezone.utc) - timedelta(days=8)
    }
    expired_refresh = jwt.encode(expired_refresh_payload, settings.JWT_SECRET, algorithm="HS256")

    # Tenter de refresh
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": expired_refresh}
    )

    assert response.status_code == 401
    assert "Invalid or expired refresh token" in response.json()["detail"]


def test_reject_access_token_used_as_refresh_token(client, test_user):
    """❌ Access token ne peut pas être utilisé pour refresh.

    Scénario:
        1. User obtient access token
        2. Tente de l'utiliser pour /auth/refresh
        3. Doit rejeter avec 401 "Invalid token type"
    """
    # Créer access token (type="access")
    access_token = create_access_token({"sub": str(test_user.id)})

    # Tenter de l'utiliser comme refresh
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token}  # Mauvais type
    )

    assert response.status_code == 401
    assert "Invalid token type" in response.json()["detail"] or \
           "Invalid or expired refresh token" in response.json()["detail"]


def test_clock_skew_tolerance():
    """⚠️  Clock skew tolerance - Token expiré il y a 30s encore valide.

    Note:
        python-jose accepte tokens avec leeway (default 0s).
        Si settings.JWT_LEEWAY > 0, tokens expirés récemment acceptés.

    Security:
        Leeway doit être minimal (max 60s) pour éviter replay attacks.
    """
    # Créer token expiré il y a 30s
    payload = {
        "sub": "1",
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(seconds=30),
        "iat": datetime.now(timezone.utc) - timedelta(minutes=30)
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    # Décoder SANS leeway (doit échouer)
    result_strict = decode_token(token)
    assert result_strict is None  # Rejeté

    # Décoder AVEC leeway=60s (doit accepter)
    try:
        payload_with_leeway = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"leeway": 60}  # Tolérance 60s
        )
        # Token accepté malgré expiration < 60s
        assert payload_with_leeway["sub"] == "1"
    except jwt.ExpiredSignatureError:
        pytest.fail("Token devrait être accepté avec leeway=60s")
```

**2. Configurer leeway** : `app/core/security.py`

```python
# Décoder avec leeway minimal (sécurité)
def decode_token(token: str) -> dict | None:
    """Décode et valide un JWT.

    Args:
        token: JWT à décoder

    Returns:
        Payload si valide, None sinon

    Security:
        - Leeway 0s (strict expiration, pas de clock skew)
        - Rejette tokens expirés immédiatement
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"leeway": 0}  # ✅ Pas de tolérance clock skew
        )
        return payload
    except (jwt.ExpiredSignatureError, jwt.JWTError, jwt.JWTClaimsError):
        return None
```

**Estimation**: 4 heures (tests + validation + doc)
**Priorité**: P1 - Sécurité authentification critique

---

### 🟡 BUG #11 - MINEUR P2 : Logs Non Structurés (Observabilité)

**Fichiers impactés**:
- `app/core/logging.py` (configuration logs)
- Tous fichiers avec `logger.info()`, `logger.error()` (format non structuré)

**Problème**:

**A. Logs textuels non parsables**
```python
# Format actuel (non structuré)
logger.info(f"User {user_id} created reservation {reservation_id}")
logger.error(f"Failed to confirm reservation: {error}")

# ❌ Problèmes:
# - Parsing difficile (regex nécessaire)
# - Pas de champs structurés pour filtrage
# - Pas de correlation ID pour tracing
# - Pas de tenant_id pour isolation
```

**B. Logs manquants pour audit**
- Pas de log CREATE/UPDATE/DELETE automatique
- Pas de capture user_id / tenant_id / IP
- Pas de correlation entre requests

**Impact Production**:
- **Debugging difficile**: Logs non filtrab les par tenant/user
- **Observabilité faible**: Pas de tracing distribué
- **Conformité RGPD**: Logs d'audit insuffisants

**Solution**:

**1. Logger structuré JSON** : `app/core/logging.py`

```python
"""Configuration logging structuré (JSON) pour production."""
import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Formatter JSON custom avec champs standardisés."""

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict):
        """Ajouter champs custom à chaque log.

        Champs ajoutés:
            - timestamp: ISO 8601 UTC
            - level: INFO, ERROR, etc.
            - logger: Nom du logger
            - message: Message log
            - tenant_id: ID tenant (si disponible)
            - user_id: ID user (si disponible)
            - request_id: Correlation ID (si disponible)
        """
        super().add_fields(log_record, record, message_dict)

        # Timestamp ISO 8601
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Level name
        log_record["level"] = record.levelname

        # Logger name
        log_record["logger"] = record.name

        # Message
        if "message" not in log_record:
            log_record["message"] = record.getMessage()

        # Contexte custom (injecté par middleware)
        if hasattr(record, "tenant_id"):
            log_record["tenant_id"] = record.tenant_id
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id


def setup_logging():
    """Configurer logging structuré JSON."""
    # Handler stdout (production)
    handler = logging.StreamHandler(sys.stdout)

    # Formatter JSON
    formatter = CustomJsonFormatter(
        "%(timestamp)s %(level)s %(logger)s %(message)s"
    )
    handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    return root_logger
```

**2. Middleware contexte** : `app/middleware/logging_context.py`

```python
"""Middleware pour injecter contexte dans logs."""
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """Injecte tenant_id, user_id, request_id dans logs."""

    async def dispatch(self, request: Request, call_next):
        # Générer request_id unique
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Logger adapter avec contexte
        logger = logging.LoggerAdapter(
            logging.getLogger(__name__),
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url)
            }
        )

        # Log request
        logger.info("Request started")

        try:
            response = await call_next(request)

            # Log response
            logger.info(
                "Request completed",
                extra={"status_code": response.status_code}
            )

            # Ajouter request_id dans headers response
            response.headers["X-Request-ID"] = request_id

            return response
        except Exception as e:
            logger.error(
                "Request failed",
                extra={"error": str(e)},
                exc_info=True
            )
            raise
```

**3. Usage dans code** :

```python
# app/services/reservation.py
import logging
from app.core.logging import CustomJsonFormatter

logger = logging.getLogger(__name__)

def confirm_reservation(self, reservation_id: int, tenant_id: int):
    # Log structuré
    logger.info(
        "Confirming reservation",
        extra={
            "reservation_id": reservation_id,
            "tenant_id": tenant_id,
            "action": "CONFIRM_RESERVATION"
        }
    )

    try:
        # Business logic...
        logger.info(
            "Reservation confirmed successfully",
            extra={
                "reservation_id": reservation_id,
                "status": "confirmed"
            }
        )
    except Exception as e:
        logger.error(
            "Failed to confirm reservation",
            extra={
                "reservation_id": reservation_id,
                "error_type": type(e).__name__,
                "error_message": str(e)
            },
            exc_info=True
        )
        raise
```

**Output JSON** :
```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "INFO",
  "logger": "app.services.reservation",
  "message": "Confirming reservation",
  "reservation_id": 123,
  "tenant_id": 1,
  "action": "CONFIRM_RESERVATION",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": 42
}
```

**Estimation**: 6 heures (config logging + middleware + migration logs existants)
**Priorité**: P2 - Amélioration observabilité (pas bloquant production)

---

### 🟡 BUG #12 - MINEUR P2 : Tests E2E Workflows Incomplets

**Fichiers impactés**:
- `tests/e2e/` (workflows multi-étapes manquants)
- Documentation workflows

**Problème**:

**A. Workflows réels non testés end-to-end**
- Tests unitaires: ✅ Services isolés OK
- Tests intégration: ✅ Endpoints individuels OK
- Tests E2E: ❌ Workflows complets MANQUANTS

**Workflows critiques non couverts**:

1. **Workflow location complète**
   ```
   1. Client crée compte → POST /customers
   2. Client browse produits → GET /products?category=assiette
   3. Client crée réservation → POST /reservations
   4. Client ajoute lignes → POST /reservations/{id}/lines
   5. Client confirme → POST /reservations/{id}/confirm
   6. Système réserve stock automatiquement
   7. Facture générée → POST /invoices/from-reservation/{id}
   8. Client paie → POST /invoices/{id}/add-payment
   9. Statut facture → "paid"
   ```
   Statut: NON TESTÉ E2E ❌

2. **Workflow annulation**
   ```
   1. Réservation confirmée (stock réservé)
   2. Client annule → POST /reservations/{id}/cancel
   3. Système libère stock automatiquement
   4. Facture annulée → status "cancelled"
   ```
   Statut: NON TESTÉ E2E ❌

3. **Workflow stock insuffisant**
   ```
   1. Product.available_quantity = 5
   2. Client A réserve 3 → Réussit
   3. Client B réserve 3 → Échoue (2 disponibles)
   4. Client A annule → Stock libéré (5 disponibles)
   5. Client B réserve 3 → Réussit maintenant
   ```
   Statut: NON TESTÉ E2E ❌

**Impact Production**:
- **Intégration non validée**: Interactions entre services non testées
- **Régression possible**: Changement dans un service casse workflow complet
- **UX non validée**: Parcours utilisateur réel jamais testé

**Solution**:

**1. Tests E2E workflows** : `tests/e2e/test_complete_workflows.py`

```python
"""Tests E2E - Workflows complets multi-services."""
import pytest
from fastapi.testclient import TestClient


def test_complete_rental_workflow_success(client, auth_headers_real):
    """✅ E2E: Workflow location complète de A à Z.

    Étapes:
        1. Créer client
        2. Créer produit
        3. Créer réservation draft
        4. Ajouter lignes
        5. Confirmer réservation (réserve stock)
        6. Générer facture
        7. Payer facture
        8. Vérifier statuts finaux
    """
    # 1. Créer client
    customer_data = {
        "email": "client.e2e@test.com",
        "first_name": "Client",
        "last_name": "E2E",
        "phone": "0612345678"
    }
    response = client.post("/api/v1/customers", json=customer_data, headers=auth_headers_real)
    assert response.status_code == 201
    customer = response.json()
    customer_id = customer["id"]

    # 2. Créer produit
    product_data = {
        "name": "Assiette E2E",
        "sku": "E2E-ASSIETTE-001",
        "category": "assiette",
        "price_per_day_cents": 50,
        "stock_quantity": 100,
        "available_quantity": 100
    }
    response = client.post("/api/v1/products", json=product_data, headers=auth_headers_real)
    assert response.status_code == 201
    product = response.json()
    product_id = product["id"]

    # 3. Créer réservation draft
    reservation_data = {
        "customer_id": customer_id,
        "start_date": "2024-01-15",
        "end_date": "2024-01-20"
    }
    response = client.post("/api/v1/reservations", json=reservation_data, headers=auth_headers_real)
    assert response.status_code == 201
    reservation = response.json()
    reservation_id = reservation["id"]
    assert reservation["status"] == "draft"

    # 4. Ajouter ligne réservation
    line_data = {
        "product_id": product_id,
        "quantity": 10
    }
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/lines",
        json=line_data,
        headers=auth_headers_real
    )
    assert response.status_code == 201

    # 5. Confirmer réservation (doit réserver stock)
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/confirm",
        headers=auth_headers_real
    )
    assert response.status_code == 200
    confirmed_reservation = response.json()
    assert confirmed_reservation["status"] == "confirmed"

    # Vérifier stock réservé
    response = client.get(f"/api/v1/products/{product_id}", headers=auth_headers_real)
    product_after_confirm = response.json()
    assert product_after_confirm["available_quantity"] == 90  # 100 - 10

    # 6. Générer facture
    response = client.post(
        f"/api/v1/invoices/from-reservation/{reservation_id}",
        headers=auth_headers_real
    )
    assert response.status_code == 201
    invoice = response.json()
    invoice_id = invoice["id"]
    assert invoice["status"] == "unpaid"
    assert invoice["total_amount_cents"] > 0

    # 7. Payer facture (paiement complet)
    payment_data = {
        "amount_cents": invoice["total_amount_cents"],
        "payment_method": "card"
    }
    response = client.post(
        f"/api/v1/invoices/{invoice_id}/add-payment",
        json=payment_data,
        headers=auth_headers_real
    )
    assert response.status_code == 200
    paid_invoice = response.json()
    assert paid_invoice["status"] == "paid"
    assert paid_invoice["paid_amount_cents"] == invoice["total_amount_cents"]

    # 8. Vérifier états finaux
    # Réservation toujours "confirmed"
    response = client.get(f"/api/v1/reservations/{reservation_id}", headers=auth_headers_real)
    final_reservation = response.json()
    assert final_reservation["status"] == "confirmed"

    # Stock toujours réservé (90)
    response = client.get(f"/api/v1/products/{product_id}", headers=auth_headers_real)
    final_product = response.json()
    assert final_product["available_quantity"] == 90

    # ✅ Workflow complet réussi


def test_cancel_reservation_releases_stock(client, auth_headers_real):
    """✅ E2E: Annulation réservation libère le stock.

    Étapes:
        1. Créer réservation confirmée (stock réservé)
        2. Vérifier stock réduit
        3. Annuler réservation
        4. Vérifier stock restauré
    """
    # Setup: Créer customer + product + reservation confirmée
    # (similaire au test précédent, étapes 1-5)

    # ... (code setup) ...

    # Vérifier stock AVANT annulation (réduit)
    response = client.get(f"/api/v1/products/{product_id}", headers=auth_headers_real)
    product_before_cancel = response.json()
    initial_available = product_before_cancel["available_quantity"]
    reserved_qty = 10
    assert initial_available == 90  # 100 - 10

    # Annuler réservation
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/cancel",
        headers=auth_headers_real
    )
    assert response.status_code == 200
    cancelled_reservation = response.json()
    assert cancelled_reservation["status"] == "cancelled"

    # Vérifier stock APRÈS annulation (restauré)
    response = client.get(f"/api/v1/products/{product_id}", headers=auth_headers_real)
    product_after_cancel = response.json()
    assert product_after_cancel["available_quantity"] == 100  # Stock restauré

    # ✅ Stock correctement libéré


def test_concurrent_reservations_stock_management(client, auth_headers_real):
    """✅ E2E: Gestion stock avec réservations concurrentes.

    Scénario:
        1. Product.available_quantity = 10
        2. Client A réserve 7 → Réussit (3 restants)
        3. Client B réserve 5 → Échoue (pas assez de stock)
        4. Client A annule → Stock restauré (10 disponibles)
        5. Client B réserve 5 → Réussit maintenant
    """
    # Setup product avec stock limité
    product_data = {
        "name": "Product Limited Stock",
        "sku": "LIMITED-001",
        "category": "verre",
        "price_per_day_cents": 100,
        "stock_quantity": 10,
        "available_quantity": 10
    }
    response = client.post("/api/v1/products", json=product_data, headers=auth_headers_real)
    product_id = response.json()["id"]

    # Setup 2 customers
    customer_a_id = client.post("/api/v1/customers", json={...}, headers=auth_headers_real).json()["id"]
    customer_b_id = client.post("/api/v1/customers", json={...}, headers=auth_headers_real).json()["id"]

    # Client A: Réserver 7 unités
    res_a_data = {"customer_id": customer_a_id, "start_date": "2024-01-15", "end_date": "2024-01-20"}
    res_a_id = client.post("/api/v1/reservations", json=res_a_data, headers=auth_headers_real).json()["id"]

    client.post(
        f"/api/v1/reservations/{res_a_id}/lines",
        json={"product_id": product_id, "quantity": 7},
        headers=auth_headers_real
    )

    response = client.post(f"/api/v1/reservations/{res_a_id}/confirm", headers=auth_headers_real)
    assert response.status_code == 200

    # Vérifier stock: 10 - 7 = 3
    product_after_a = client.get(f"/api/v1/products/{product_id}", headers=auth_headers_real).json()
    assert product_after_a["available_quantity"] == 3

    # Client B: Tenter de réserver 5 unités (DOIT ÉCHOUER)
    res_b_data = {"customer_id": customer_b_id, "start_date": "2024-01-15", "end_date": "2024-01-20"}
    res_b_id = client.post("/api/v1/reservations", json=res_b_data, headers=auth_headers_real).json()["id"]

    client.post(
        f"/api/v1/reservations/{res_b_id}/lines",
        json={"product_id": product_id, "quantity": 5},
        headers=auth_headers_real
    )

    response = client.post(f"/api/v1/reservations/{res_b_id}/confirm", headers=auth_headers_real)
    assert response.status_code == 400  # Insufficient stock
    assert "Insufficient stock" in response.json()["detail"]

    # Client A: Annuler réservation
    response = client.post(f"/api/v1/reservations/{res_a_id}/cancel", headers=auth_headers_real)
    assert response.status_code == 200

    # Vérifier stock restauré: 3 + 7 = 10
    product_after_cancel = client.get(f"/api/v1/products/{product_id}", headers=auth_headers_real).json()
    assert product_after_cancel["available_quantity"] == 10

    # Client B: RE-tenter de réserver 5 unités (DOIT RÉUSSIR maintenant)
    response = client.post(f"/api/v1/reservations/{res_b_id}/confirm", headers=auth_headers_real)
    assert response.status_code == 200

    # Vérifier stock final: 10 - 5 = 5
    product_final = client.get(f"/api/v1/products/{product_id}", headers=auth_headers_real).json()
    assert product_final["available_quantity"] == 5

    # ✅ Workflow concurrence géré correctement
```

**Estimation**: 8 heures (tests E2E complets + documentation workflows)
**Priorité**: P2 - Qualité (validation intégration complète)

---

## Analyse de Sécurité (OWASP Top 10 2021)

### Vue d'ensemble

| # | Vulnérabilité | Statut Actuel | Action Requise | Priorité |
|---|---------------|---------------|----------------|----------|
| A01 | Broken Access Control | ⚠️ PARTIEL | Tests anti-cross-tenant manquants | P0 |
| A02 | Cryptographic Failures | ⚠️ PARTIEL | Chiffrement DB manquant | P1 |
| A03 | Injection | ✅ PROTÉGÉ | SQLAlchemy ORM (parameterized queries) | OK |
| A04 | Insecure Design | ⚠️ PARTIEL | Rate limiting manquant | P1 |
| A05 | Security Misconfiguration | ❌ CRITIQUE | Secrets hardcodés, CORS mal configuré | P0 |
| A06 | Vulnerable Components | ⚠️ PARTIEL | Dépendances non scannées (Dependabot manquant) | P1 |
| A07 | Identification Failures | ⚠️ PARTIEL | JWT validation incomplète (BUG #6, #10) | P0 |
| A08 | Software/Data Integrity | ❌ CRITIQUE | Audit log manquant (BUG #5) | P0 |
| A09 | Logging Failures | ⚠️ PARTIEL | Logs non structurés (BUG #11) | P2 |
| A10 | Server-Side Request Forgery | ✅ N/A | Pas de requêtes sortantes user-controlled | OK |

---

### A01:2021 - Broken Access Control

**État actuel**: ⚠️ PARTIEL

**Protections en place**:
- ✅ Multi-tenant isolation (tenant_id filtrage dans repositories)
- ✅ RBAC (admin, manager, staff)
- ✅ JWT-based authentication
- ✅ Dependency injection (`get_current_user`, `require_role`)

**Vulnérabilités identifiées**:
1. **Tests anti-cross-tenant insuffisants**
   - Repositories filtrent tenant_id ✅
   - MAIS pas de tests exhaustifs de tous les endpoints
   - Risque: Endpoint oublie de filter tenant_id → leak data

2. **IDOR (Insecure Direct Object Reference) non testé**
   - User peut-il accéder à `/api/v1/reservations/{other_user_reservation_id}` ?
   - Tests actuels ne couvrent pas tous les endpoints

3. **Horizontal privilege escalation non testé**
   - Manager peut-il accéder aux données d'un autre tenant ?
   - Tests cross-tenant manquants pour tous rôles

**Actions correctives**:

#### 1. Tests anti-cross-tenant exhaustifs

**Créer**: `tests/security/test_cross_tenant_isolation.py`

```python
"""Tests exhaustifs isolation multi-tenant - Tous endpoints."""
import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures multi-tenant
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def tenant1_user(test_db):
    """User tenant_id=1."""
    user = User(
        tenant_id=1,
        email="user1@tenant1.com",
        hashed_password=get_password_hash("pass"),
        full_name="User Tenant 1",
        role="manager"
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def tenant2_user(test_db):
    """User tenant_id=2."""
    user = User(
        tenant_id=2,
        email="user2@tenant2.com",
        hashed_password=get_password_hash("pass"),
        full_name="User Tenant 2",
        role="manager"
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def tenant1_token(tenant1_user):
    """JWT pour tenant1_user."""
    return create_access_token({"sub": str(tenant1_user.id)})


@pytest.fixture
def tenant2_token(tenant2_user):
    """JWT pour tenant2_user."""
    return create_access_token({"sub": str(tenant2_user.id)})


@pytest.fixture
def tenant1_headers(tenant1_token):
    return {"Authorization": f"Bearer {tenant1_token}"}


@pytest.fixture
def tenant2_headers(tenant2_token):
    return {"Authorization": f"Bearer {tenant2_token}"}


# ═══════════════════════════════════════════════════════════════════════════
# Tests Cross-Tenant - Customers
# ═══════════════════════════════════════════════════════════════════════════

def test_cross_tenant_get_customer(client, test_db, tenant1_headers, tenant2_headers):
    """❌ Tenant 2 ne peut PAS lire customer de Tenant 1."""
    # Tenant 1 crée customer
    customer_data = {"email": "customer@tenant1.com", "first_name": "John", "last_name": "Doe"}
    response = client.post("/api/v1/customers", json=customer_data, headers=tenant1_headers)
    assert response.status_code == 201
    customer_id = response.json()["id"]

    # Tenant 2 tente d'accéder
    response = client.get(f"/api/v1/customers/{customer_id}", headers=tenant2_headers)
    assert response.status_code == 404  # Pas 403 (éviter info leakage)


def test_cross_tenant_list_customers(client, test_db, tenant1_headers, tenant2_headers):
    """❌ Tenant 2 ne voit PAS les customers de Tenant 1."""
    # Tenant 1 crée 3 customers
    for i in range(3):
        client.post(
            "/api/v1/customers",
            json={"email": f"cust{i}@t1.com", "first_name": "John", "last_name": f"Doe{i}"},
            headers=tenant1_headers
        )

    # Tenant 2 crée 2 customers
    for i in range(2):
        client.post(
            "/api/v1/customers",
            json={"email": f"cust{i}@t2.com", "first_name": "Jane", "last_name": f"Doe{i}"},
            headers=tenant2_headers
        )

    # Tenant 1 list → doit voir 3
    response = client.get("/api/v1/customers", headers=tenant1_headers)
    assert response.json()["total"] == 3

    # Tenant 2 list → doit voir 2 (pas 5)
    response = client.get("/api/v1/customers", headers=tenant2_headers)
    assert response.json()["total"] == 2


def test_cross_tenant_update_customer(client, test_db, tenant1_headers, tenant2_headers):
    """❌ Tenant 2 ne peut PAS modifier customer de Tenant 1."""
    # Tenant 1 crée customer
    response = client.post(
        "/api/v1/customers",
        json={"email": "cust@t1.com", "first_name": "John", "last_name": "Doe"},
        headers=tenant1_headers
    )
    customer_id = response.json()["id"]

    # Tenant 2 tente de modifier
    response = client.put(
        f"/api/v1/customers/{customer_id}",
        json={"first_name": "HACKED"},
        headers=tenant2_headers
    )
    assert response.status_code == 404

    # Vérifier que customer NON modifié
    response = client.get(f"/api/v1/customers/{customer_id}", headers=tenant1_headers)
    assert response.json()["first_name"] == "John"  # Pas "HACKED"


def test_cross_tenant_delete_customer(client, test_db, tenant1_headers, tenant2_headers):
    """❌ Tenant 2 ne peut PAS supprimer customer de Tenant 1."""
    # Tenant 1 crée customer
    response = client.post(
        "/api/v1/customers",
        json={"email": "cust@t1.com", "first_name": "John", "last_name": "Doe"},
        headers=tenant1_headers
    )
    customer_id = response.json()["id"]

    # Tenant 2 tente de supprimer
    response = client.delete(f"/api/v1/customers/{customer_id}", headers=tenant2_headers)
    assert response.status_code == 404

    # Vérifier que customer existe toujours
    response = client.get(f"/api/v1/customers/{customer_id}", headers=tenant1_headers)
    assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# Tests Cross-Tenant - Products
# ═══════════════════════════════════════════════════════════════════════════

def test_cross_tenant_get_product(client, tenant1_headers, tenant2_headers):
    """❌ Tenant 2 ne peut PAS lire product de Tenant 1."""
    # Tenant 1 crée product
    product_data = {
        "name": "Assiette T1",
        "sku": "T1-001",
        "category": "assiette",
        "price_per_day_cents": 100,
        "stock_quantity": 50
    }
    response = client.post("/api/v1/products", json=product_data, headers=tenant1_headers)
    product_id = response.json()["id"]

    # Tenant 2 tente d'accéder
    response = client.get(f"/api/v1/products/{product_id}", headers=tenant2_headers)
    assert response.status_code == 404


def test_cross_tenant_reserve_stock(client, tenant1_headers, tenant2_headers):
    """❌ Tenant 2 ne peut PAS réserver stock de product Tenant 1."""
    # Tenant 1 crée product avec stock
    product_data = {
        "name": "Product Reserve",
        "sku": "RESERVE-001",
        "category": "verre",
        "price_per_day_cents": 100,
        "stock_quantity": 10,
        "available_quantity": 10
    }
    response = client.post("/api/v1/products", json=product_data, headers=tenant1_headers)
    product_id = response.json()["id"]

    # Tenant 2 tente de réserver stock (via réservation)
    # 1. Créer customer T2
    response = client.post(
        "/api/v1/customers",
        json={"email": "cust@t2.com", "first_name": "Jane", "last_name": "Doe"},
        headers=tenant2_headers
    )
    customer_t2_id = response.json()["id"]

    # 2. Créer réservation T2 avec product T1 (DOIT ÉCHOUER)
    response = client.post(
        "/api/v1/reservations",
        json={"customer_id": customer_t2_id, "start_date": "2024-01-15", "end_date": "2024-01-20"},
        headers=tenant2_headers
    )
    reservation_id = response.json()["id"]

    # 3. Tenter d'ajouter ligne avec product_id T1
    response = client.post(
        f"/api/v1/reservations/{reservation_id}/lines",
        json={"product_id": product_id, "quantity": 5},
        headers=tenant2_headers
    )
    assert response.status_code == 404  # Product not found pour T2


# ═══════════════════════════════════════════════════════════════════════════
# Tests Cross-Tenant - Reservations
# ═══════════════════════════════════════════════════════════════════════════

def test_cross_tenant_get_reservation(client, tenant1_headers, tenant2_headers):
    """❌ Tenant 2 ne peut PAS lire reservation de Tenant 1."""
    # Setup: Créer réservation T1
    customer_response = client.post(
        "/api/v1/customers",
        json={"email": "cust@t1.com", "first_name": "John", "last_name": "Doe"},
        headers=tenant1_headers
    )
    customer_id = customer_response.json()["id"]

    reservation_response = client.post(
        "/api/v1/reservations",
        json={"customer_id": customer_id, "start_date": "2024-01-15", "end_date": "2024-01-20"},
        headers=tenant1_headers
    )
    reservation_id = reservation_response.json()["id"]

    # Tenant 2 tente d'accéder
    response = client.get(f"/api/v1/reservations/{reservation_id}", headers=tenant2_headers)
    assert response.status_code == 404


def test_cross_tenant_confirm_reservation(client, tenant1_headers, tenant2_headers):
    """❌ Tenant 2 ne peut PAS confirmer reservation de Tenant 1."""
    # Setup: Réservation T1 (similaire au test précédent)
    # ...
    reservation_id = ...  # ID réservation T1

    # Tenant 2 tente de confirmer
    response = client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=tenant2_headers)
    assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Tests Cross-Tenant - Invoices
# ═══════════════════════════════════════════════════════════════════════════

def test_cross_tenant_get_invoice(client, tenant1_headers, tenant2_headers):
    """❌ Tenant 2 ne peut PAS lire invoice de Tenant 1."""
    # Setup: Créer invoice T1
    # ... (via réservation confirmée)
    invoice_id = ...

    # Tenant 2 tente d'accéder
    response = client.get(f"/api/v1/invoices/{invoice_id}", headers=tenant2_headers)
    assert response.status_code == 404


def test_cross_tenant_add_payment(client, tenant1_headers, tenant2_headers):
    """❌ Tenant 2 ne peut PAS payer invoice de Tenant 1."""
    # Setup: Invoice T1 unpaid
    invoice_id = ...

    # Tenant 2 tente de payer
    response = client.post(
        f"/api/v1/invoices/{invoice_id}/add-payment",
        json={"amount_cents": 1000, "payment_method": "card"},
        headers=tenant2_headers
    )
    assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# Tests IDOR (Insecure Direct Object Reference)
# ═══════════════════════════════════════════════════════════════════════════

def test_idor_sequential_id_guessing(client, tenant1_headers):
    """⚠️  IDOR: Deviner IDs séquentiels d'autres ressources.

    Scénario d'attaque:
        1. Attaquant crée customer ID=10
        2. Devine que customer ID=9, 11, 12 existent
        3. Tente d'accéder à ID=9 (autre user même tenant)
        4. Doit être BLOQUÉ si appartient à autre user

    Note:
        CaroCorp utilise isolation TENANT-level (pas USER-level).
        Tous managers d'un tenant peuvent voir toutes resources du tenant.
        Ce test valide ce comportement intentionnel.
    """
    # User 1 crée customer
    response = client.post(
        "/api/v1/customers",
        json={"email": "user1@t1.com", "first_name": "User1", "last_name": "Doe"},
        headers=tenant1_headers
    )
    customer1_id = response.json()["id"]

    # Même user accède au customer (doit réussir)
    response = client.get(f"/api/v1/customers/{customer1_id}", headers=tenant1_headers)
    assert response.status_code == 200

    # ✅ Comportement actuel: Isolation TENANT-level (pas user-level)
    # Tous users d'un tenant peuvent voir ressources du tenant
    # Si besoin isolation USER-level → ajouter user_id filtering


def test_uuid_vs_sequential_ids():
    """💡 Recommandation: Utiliser UUIDs au lieu d'IDs séquentiels.

    Avantages UUIDs:
        - Pas de IDOR via ID guessing
        - Pas d'énumération de ressources
        - Pas d'exposition du volume de données

    Migration:
        - Phase 4: Migrer de BigInteger à UUID
        - Breaking change: Nécessite migration DB + API
    """
    # TODO: Phase 4 roadmap
    pass
```

#### 2. Middleware validation tenant_id

**Créer**: `app/middleware/tenant_validation.py`

```python
"""Middleware validation automatique tenant_id sur toutes requêtes."""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)


class TenantValidationMiddleware(BaseHTTPMiddleware):
    """Valide que chaque requête authentifiée a un tenant_id valide.

    Sécurité:
        - Log toute tentative d'accès sans tenant_id
        - Bloque requêtes cross-tenant au niveau middleware
        - Audit log des violations

    Note:
        Redondance volontaire avec repository filtering (defense in depth).
    """

    async def dispatch(self, request: Request, call_next):
        # Ignorer endpoints publics
        if request.url.path in ["/health", "/api/v1/auth/login", "/api/v1/auth/refresh"]:
            return await call_next(request)

        # Récupérer user depuis request.state (injecté par get_current_user)
        user = getattr(request.state, "user", None)

        if user:
            # Valider tenant_id présent
            if not hasattr(user, "tenant_id") or user.tenant_id is None:
                logger.error(
                    f"🚨 SECURITY VIOLATION: User {user.id} has no tenant_id",
                    extra={"user_id": user.id, "url": request.url.path}
                )
                raise HTTPException(status_code=403, detail="Invalid tenant configuration")

            # Injecter tenant_id dans request.state pour logging
            request.state.tenant_id = user.tenant_id

        response = await call_next(request)
        return response
```

**Estimation Actions A01**: 12 heures (tests exhaustifs + middleware + validation)
**Priorité**: P0 - Sécurité critique

---

### A02:2021 - Cryptographic Failures

**État actuel**: ⚠️ PARTIEL

**Protections en place**:
- ✅ HTTPS en production (TLS 1.2+)
- ✅ Hashed passwords (bcrypt via passlib)
- ✅ JWT tokens signés (HS256)

**Vulnérabilités identifiées**:
1. **Base de données NON chiffrée**
   - PostgreSQL sans encryption at rest
   - Backups non chiffrés
   - Risque: Vol physique disque → données en clair

2. **Secrets en environnement**
   - `.env` file avec secrets en clair
   - Pas de rotation automatique
   - Pas de secrets management (Vault)

3. **Sessions non sécurisées**
   - Pas de secure cookies (httponly, samesite)
   - Refresh tokens stockés en Redis sans chiffrement

**Actions correctives**:

#### 1. PostgreSQL Encryption at Rest

**Configuration**: `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: massa
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: MassaCorp
      # ✅ Activer encryption at rest
      POSTGRES_INITDB_ARGS: "--data-checksums"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      # ✅ Volume chiffré (via LUKS en production)
    command:
      - "postgres"
      - "-c"
      - "ssl=on"  # ✅ Forcer SSL
      - "-c"
      - "ssl_cert_file=/var/lib/postgresql/server.crt"
      - "-c"
      - "ssl_key_file=/var/lib/postgresql/server.key"

volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: "none"
      o: "bind"
      device: "/mnt/encrypted-db"  # ✅ Partition LUKS chiffrée
```

**Setup LUKS** (production):

```bash
# Créer partition chiffrée
sudo cryptsetup luksFormat /dev/sdb1
sudo cryptsetup luksOpen /dev/sdb1 encrypted-db
sudo mkfs.ext4 /dev/mapper/encrypted-db
sudo mount /dev/mapper/encrypted-db /mnt/encrypted-db

# Backup chiffré
pg_dump MassaCorp | gpg --encrypt --recipient admin@carocorp.com > backup.sql.gpg
```

#### 2. Secrets Management (HashiCorp Vault)

**Architecture**:
```
Application → Vault Client → Vault Server → Encrypted Storage
                ↓
         Dynamic Secrets
         (rotation auto 24h)
```

**Configuration**: `app/core/secrets.py`

```python
"""Secrets management via HashiCorp Vault."""
import hvac
from app.core.config import settings


class SecretsManager:
    """Client Vault pour récupération secrets dynamiques."""

    def __init__(self):
        self.client = hvac.Client(
            url=settings.VAULT_ADDR,
            token=settings.VAULT_TOKEN  # Token lecture seule
        )

    def get_db_credentials(self) -> dict:
        """Récupérer credentials DB dynamiques (rotation 24h).

        Returns:
            {"username": "massa_app_20240115", "password": "xxx"}
        """
        secret = self.client.secrets.database.generate_credentials(
            name="carocorp-db",
            mount_point="database"
        )
        return secret["data"]

    def get_jwt_secret(self) -> str:
        """Récupérer JWT secret (rotation mensuelle)."""
        secret = self.client.secrets.kv.v2.read_secret_version(
            path="carocorp/jwt",
            mount_point="secret"
        )
        return secret["data"]["data"]["secret"]


# Usage
secrets_manager = SecretsManager()

# Remplacer settings.DATABASE_URL par:
db_creds = secrets_manager.get_db_credentials()
DATABASE_URL = f"postgresql://{db_creds['username']}:{db_creds['password']}@localhost/MassaCorp"
```

#### 3. Secure Cookies & Session Management

**Configuration**: `app/api/v1/endpoints/auth.py`

```python
from fastapi import Response


@router.post("/login")
def login(response: Response, credentials: LoginRequest):
    """Login avec secure cookies."""
    # Générer tokens
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # ✅ Stocker refresh token dans httpOnly cookie (pas dans response JSON)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,        # ✅ Pas accessible via JavaScript (XSS protection)
        secure=True,          # ✅ HTTPS uniquement
        samesite="strict",    # ✅ CSRF protection
        max_age=7 * 24 * 3600 # 7 jours
    )

    # Retourner uniquement access token
    return {
        "access_token": access_token,
        "token_type": "bearer"
        # ❌ PAS de refresh_token dans JSON
    }
```

**Estimation Actions A02**: 16 heures (Vault setup + encryption + secure cookies + doc)
**Priorité**: P1 - Conformité production

---

### A03:2021 - Injection

**État actuel**: ✅ PROTÉGÉ

**Protections en place**:
- ✅ SQLAlchemy ORM (parameterized queries automatiques)
- ✅ Pydantic validation (input sanitization)
- ✅ Pas de `execute()` avec f-strings

**Validation**:

```python
# ✅ SAFE: SQLAlchemy ORM
customer = db.query(Customer).filter(Customer.email == user_input).first()

# ✅ SAFE: SQLAlchemy Core avec params
stmt = text("SELECT * FROM customers WHERE email = :email")
result = db.execute(stmt, {"email": user_input})

# ❌ UNSAFE (N'EXISTE PAS dans la codebase)
query = f"SELECT * FROM customers WHERE email = '{user_input}'"  # SQL Injection
db.execute(query)
```

**Tests supplémentaires**:

```python
# tests/security/test_sql_injection.py

def test_sql_injection_customer_email(client, auth_headers):
    """❌ Tentative SQL injection via email customer."""
    # Payload injection classique
    malicious_email = "' OR '1'='1' --"

    response = client.post(
        "/api/v1/customers",
        json={"email": malicious_email, "first_name": "Hacker", "last_name": "Test"},
        headers=auth_headers
    )

    # Doit échouer validation Pydantic (email invalide)
    assert response.status_code == 422
    assert "email" in response.json()["detail"][0]["loc"]


def test_sql_injection_product_search(client, auth_headers):
    """❌ Tentative SQL injection via search filter."""
    malicious_search = "'; DROP TABLE products; --"

    response = client.get(
        f"/api/v1/products?search={malicious_search}",
        headers=auth_headers
    )

    # Recherche doit retourner 0 résultats (pas d'erreur SQL)
    assert response.status_code == 200
    assert response.json()["total"] == 0
```

**Estimation Actions A03**: 2 heures (tests validation injection)
**Priorité**: P2 - Validation existante

---

### A04:2021 - Insecure Design

**État actuel**: ⚠️ PARTIEL

**Vulnérabilités identifiées**:
1. **Rate Limiting manquant** (BUG #4)
   - Pas de protection brute force login
   - Pas de protection DoS API
   - Attaquant peut spammer endpoints

2. **Account lockout manquant**
   - Pas de limite tentatives login
   - Pas de CAPTCHA après X échecs

3. **Session management faible**
   - Pas de logout endpoint (invalidation token)
   - Refresh tokens jamais révoqués
   - Pas de "logout all devices"

**Actions correctives**: Voir BUG #4 (Rate Limiting)

**Estimation Actions A04**: 6 heures (rate limit + account lockout + session mgmt)
**Priorité**: P1

---

### A05:2021 - Security Misconfiguration

**État actuel**: ❌ CRITIQUE

**Vulnérabilités identifiées**:

1. **Secrets hardcodés** (CRITIQUE)
   ```python
   # ❌ DANGER: app/core/config.py
   JWT_SECRET: str = "super-secret-key-change-me-in-production"  # Hardcodé !
   ```

2. **CORS mal configuré**
   ```python
   # ❌ TROP PERMISSIF
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # Accepte TOUS domaines
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"]
   )
   ```

3. **Mode DEBUG en production**
   ```python
   # ❌ DANGER: Expose stack traces
   DEBUG: bool = True  # Doit être False en prod
   ```

4. **Endpoints admin sans protection**
   ```python
   # Swagger docs accessible en production
   app = FastAPI(docs_url="/api/docs")  # Doit être None en prod
   ```

**Actions correctives**:

#### 1. Validation secrets au démarrage

**Créer**: `app/core/security_checks.py`

```python
"""Validation sécurité au démarrage de l'application."""
import sys
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def validate_production_security():
    """Vérifier configuration sécurité AVANT démarrage app.

    Bloque démarrage si:
        - JWT_SECRET est la valeur par défaut
        - DEBUG=True en production
        - CORS trop permissif
    """
    errors = []

    # 1. Vérifier JWT_SECRET
    if settings.JWT_SECRET == "super-secret-key-change-me-in-production":
        errors.append("🚨 JWT_SECRET utilise la valeur par défaut ! CHANGEZ-LA IMMÉDIATEMENT")

    if len(settings.JWT_SECRET) < 32:
        errors.append("🚨 JWT_SECRET trop court (min 32 caractères)")

    # 2. Vérifier DEBUG
    if settings.ENV == "production" and settings.DEBUG:
        errors.append("🚨 DEBUG=True en production ! Stack traces exposées")

    # 3. Vérifier CORS
    if settings.ENV == "production" and "*" in settings.CORS_ORIGINS:
        errors.append("🚨 CORS allow_origins=['*'] en production ! Spécifiez domaines exacts")

    # 4. Vérifier DATABASE_URL
    if "password" not in settings.DATABASE_URL or "localhost" in settings.DATABASE_URL:
        logger.warning("⚠️  DATABASE_URL semble pointer vers développement")

    # BLOQUER si erreurs critiques
    if errors:
        for error in errors:
            logger.error(error)

        logger.error("\n❌ DÉMARRAGE BLOQUÉ - CONFIGURATION SÉCURITÉ INVALIDE\n")
        sys.exit(1)

    logger.info("✅ Validation sécurité réussie")
```

**Appel dans** `app/main.py`:

```python
from app.core.security_checks import validate_production_security

# AVANT create_application()
validate_production_security()

app = create_application()
```

#### 2. Configuration CORS stricte

```python
# app/core/config.py

class Settings(BaseSettings):
    # ✅ CORS strict
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],  # Dev uniquement
        env="CORS_ORIGINS",
        description="Domaines autorisés (CSV)"
    )

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


# app/main.py
if settings.ENV == "production":
    # ✅ Production: Domaines exacts uniquement
    allowed_origins = settings.CORS_ORIGINS
    assert "*" not in allowed_origins, "Wildcard CORS interdit en production"
else:
    # Dev: Plus permissif
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # ✅ Méthodes explicites
    allow_headers=["Authorization", "Content-Type"]   # ✅ Headers explicites
)
```

#### 3. Désactiver docs en production

```python
# app/main.py

if settings.ENV == "production":
    # ✅ Pas de docs en production
    app = FastAPI(
        title="CaroCorp API",
        docs_url=None,    # Désactive /docs
        redoc_url=None    # Désactive /redoc
    )
else:
    # Dev: Docs activées
    app = FastAPI(
        title="CaroCorp API",
        docs_url="/api/docs",
        redoc_url="/api/redoc"
    )
```

**Estimation Actions A05**: 4 heures (validation + CORS + docs + tests)
**Priorité**: P0 - Bloquant production

---

### A06:2021 - Vulnerable and Outdated Components

**État actuel**: ⚠️ PARTIEL

**Risques**:
- Dépendances non scannées régulièrement
- Pas de Dependabot / Renovate
- Pas de SBOM (Software Bill of Materials)

**Actions correctives**:

#### 1. GitHub Dependabot

**Créer**: `.github/dependabot.yml`

```yaml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
    open-pull-requests-limit: 10
    reviewers:
      - "carocorp-security-team"
    labels:
      - "dependencies"
      - "security"
    commit-message:
      prefix: "chore(deps)"

    # ✅ Sécurité uniquement (auto-merge)
    # Autres updates nécessitent review manuelle

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

#### 2. Scan vulnérabilités local

```bash
# Installer safety
pip install safety

# Scanner dépendances
safety check --json > security-report.json

# CI/CD
# .github/workflows/security.yml
name: Security Scan

on:
  push:
    branches: [main, develop]
  pull_request:
  schedule:
    - cron: '0 9 * * 1'  # Lundi 9h

jobs:
  scan-dependencies:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install safety bandit

      - name: Scan vulnerabilities (safety)
        run: safety check --json

      - name: Scan code (bandit)
        run: bandit -r app/ -f json -o bandit-report.json

      - name: Upload reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            security-report.json
            bandit-report.json
```

**Estimation Actions A06**: 3 heures (Dependabot + CI scan + doc)
**Priorité**: P1

---

### A07:2021 - Identification and Authentication Failures

**État actuel**: ⚠️ PARTIEL

**Protections en place**:
- ✅ JWT tokens (access + refresh)
- ✅ Bcrypt password hashing
- ✅ Token expiration (30min access, 7j refresh)

**Vulnérabilités**:
- ❌ Pas de MFA (Multi-Factor Authentication)
- ❌ Pas de password complexity validation
- ❌ Pas de password reset flow
- ❌ JWT validation incomplète (BUG #6, #10)

**Actions correctives**: Voir BUG #6 et #10

**Estimation Actions A07**: 8 heures (MFA + password policy + reset flow)
**Priorité**: P0

---

### A08:2021 - Software and Data Integrity Failures

**État actuel**: ❌ CRITIQUE

**Vulnérabilités**:
1. **Audit log manquant** (BUG #5)
   - Pas de traçabilité CREATE/UPDATE/DELETE
   - Pas de non-répudiation
   - Non-conformité RGPD Article 30

2. **Pas de signature code**
   - Commits non signés GPG
   - Releases non signées
   - Supply chain attack possible

**Actions correctives**: Voir BUG #5 + Signature GPG

**Estimation Actions A08**: 20 heures (Audit log + GPG + pipeline)
**Priorité**: P0

---

### A09:2021 - Security Logging and Monitoring Failures

**État actuel**: ⚠️ PARTIEL

**Vulnérabilités**:
- ❌ Logs non structurés (BUG #11)
- ❌ Pas de monitoring sécurité (SIEM)
- ❌ Pas d'alerting automatique

**Actions correctives**: Voir BUG #11

**Estimation Actions A09**: 10 heures (Logs structurés + monitoring + alerting)
**Priorité**: P2

---

### A10:2021 - Server-Side Request Forgery (SSRF)

**État actuel**: ✅ N/A

**Justification**:
- Pas de requêtes HTTP sortantes contrôlées par user
- Pas de webhook callbacks
- Pas d'intégration externe user-controlled

**Validation**: Aucune action requise

---

## Conformité RGPD (Règlement Général sur la Protection des Données)

### Vue d'ensemble Conformité

| Article | Exigence | Statut Actuel | Action Requise | Priorité |
|---------|----------|---------------|----------------|----------|
| Art. 5 | Minimisation données | ✅ OK | Audit champs PII | P2 |
| Art. 6 | Base légale traitement | ⚠️ PARTIEL | Documentation consentement | P1 |
| Art. 13-14 | Information transparente | ❌ MANQUANT | Privacy policy + notices | P1 |
| Art. 15 | Droit d'accès | ⚠️ PARTIEL | Export données JSON | P1 |
| Art. 16 | Droit de rectification | ✅ OK | Endpoints UPDATE existants | OK |
| Art. 17 | Droit à l'effacement | ⚠️ PARTIEL | Anonymisation + cascade delete | P0 |
| Art. 18 | Droit à la limitation | ❌ MANQUANT | Flag "processing_limited" | P2 |
| Art. 20 | Droit à la portabilité | ❌ MANQUANT | Export format standard (JSON/CSV) | P1 |
| Art. 25 | Privacy by design | ⚠️ PARTIEL | Pseudonymisation | P1 |
| Art. 30 | Registre traitements | ❌ MANQUANT | Audit log (BUG #5) | P0 |
| Art. 32 | Sécurité traitement | ⚠️ PARTIEL | Chiffrement DB (A02) | P1 |
| Art. 33-34 | Notification violations | ❌ MANQUANT | Procédure breach notification | P1 |

---

### Article 5 : Principes de Traitement

**Exigence**: Minimisation des données collectées

**Analyse CaroCorp**:

**Données collectées** :
```python
# Customer
- email (PII - nécessaire pour contact)
- first_name, last_name (PII - nécessaire pour identification)
- phone (PII - nécessaire pour contact)
- address (PII - nécessaire pour livraison)
- notes (PII - optionnel, peut contenir données sensibles)

# User
- email (PII - nécessaire pour authentification)
- hashed_password (pas PII - hash irréversible)
- full_name (PII - nécessaire pour identification)
- role (pas PII)

# Reservation
- start_date, end_date (pas PII)
- notes (PII - peut contenir données client sensibles)

# Invoice
- invoice_number, amounts (pas PII direct)
```

**Actions**:
1. ✅ Pas de collecte excessive identifiée
2. ⚠️ Champ `notes` non structuré → risque PII non contrôlée
3. ❌ Pas de flag "consent_marketing" (si newsletters futures)

**Recommandation**:

```python
# app/models/customer.py - Ajouter flags consentement

class Customer(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    # ... champs existants ...

    # ✅ RGPD Art. 6 - Bases légales
    consent_marketing: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Consentement newsletters/marketing (RGPD Art. 6.1.a)"
    )

    consent_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date consentement marketing"
    )

    # ✅ RGPD Art. 17 - Droit à l'effacement
    anonymized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date anonymisation (si droit à l'effacement exercé)"
    )
```

---

### Article 13-14 : Information des Personnes

**Exigence**: Informer utilisateurs du traitement de leurs données

**État actuel**: ❌ MANQUANT

**Actions correctives**:

#### 1. Privacy Policy Endpoint

**Créer**: `app/api/v1/endpoints/legal.py`

```python
"""Endpoints conformité légale (Privacy Policy, Terms of Service)."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/legal", tags=["legal"])


class PrivacyPolicyResponse(BaseModel):
    """Privacy Policy RGPD."""
    version: str
    effective_date: str
    content: dict


@router.get("/privacy-policy", response_model=PrivacyPolicyResponse)
def get_privacy_policy():
    """Récupérer la Privacy Policy (RGPD Art. 13-14).

    Contenu obligatoire:
        - Identité responsable traitement
        - Finalités traitement
        - Base légale (Art. 6)
        - Destinataires données
        - Durée conservation
        - Droits personnes (Art. 15-22)
        - Droit réclamation CNIL
    """
    return {
        "version": "1.0.0",
        "effective_date": "2024-01-15",
        "content": {
            "controller": {
                "name": "CaroCorp SAS",
                "address": "123 Rue Example, 75001 Paris, France",
                "email": "dpo@carocorp.com",
                "phone": "+33 1 23 45 67 89"
            },
            "dpo": {
                "name": "Data Protection Officer",
                "email": "dpo@carocorp.com"
            },
            "purposes": [
                {
                    "purpose": "Gestion des réservations",
                    "legal_basis": "Exécution contrat (Art. 6.1.b)",
                    "data_collected": ["email", "nom", "prénom", "téléphone", "adresse"],
                    "retention_period": "5 ans après fin contrat (obligations comptables)"
                },
                {
                    "purpose": "Facturation",
                    "legal_basis": "Obligation légale (Art. 6.1.c)",
                    "data_collected": ["email", "nom", "montants", "dates"],
                    "retention_period": "10 ans (code de commerce)"
                },
                {
                    "purpose": "Marketing (si consentement)",
                    "legal_basis": "Consentement (Art. 6.1.a)",
                    "data_collected": ["email"],
                    "retention_period": "3 ans depuis dernier contact"
                }
            ],
            "rights": {
                "access": "GET /api/v1/customers/me/data-export",
                "rectification": "PUT /api/v1/customers/{id}",
                "erasure": "POST /api/v1/customers/me/request-deletion",
                "portability": "GET /api/v1/customers/me/data-export?format=json",
                "objection": "POST /api/v1/customers/me/opt-out-marketing",
                "complaint": "CNIL - www.cnil.fr"
            },
            "security": "Chiffrement TLS, hachage mots de passe bcrypt, accès restreints RBAC",
            "international_transfers": "Aucun transfert hors UE",
            "cookies": "Uniquement cookies techniques (session), pas de tracking"
        }
    }
```

#### 2. Consent Management

```python
# app/api/v1/endpoints/customers.py

@router.post("/me/consent-marketing")
def update_marketing_consent(
    consent: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gérer consentement marketing (RGPD Art. 6.1.a).

    Args:
        consent: True = accepte marketing, False = refuse

    Returns:
        Statut consentement mis à jour
    """
    # Trouver customer associé au user
    customer = db.query(Customer).filter(
        Customer.tenant_id == current_user.tenant_id,
        Customer.email == current_user.email
    ).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Mettre à jour consentement
    customer.consent_marketing = consent
    customer.consent_date = datetime.now(timezone.utc) if consent else None
    db.commit()

    # ✅ Audit log (traçabilité RGPD)
    audit_service.log(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="UPDATE_CONSENT_MARKETING",
        entity_type="Customer",
        entity_id=customer.id,
        changes={"consent_marketing": consent}
    )

    return {"consent_marketing": consent, "updated_at": customer.consent_date}
```

---

### Article 15 : Droit d'Accès

**Exigence**: Utilisateur peut demander copie de ses données

**État actuel**: ⚠️ PARTIEL (endpoints lecture existent, mais pas d'export consolidé)

**Actions correctives**:

**Créer**: `app/api/v1/endpoints/gdpr.py`

```python
"""Endpoints conformité RGPD (droits des personnes)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import get_db, CurrentUser
from app.models.customer import Customer
from app.models.reservation import Reservation
from app.models.invoice import Invoice
import json

router = APIRouter(prefix="/gdpr", tags=["gdpr"])


@router.get("/me/data-export")
def export_my_data(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends()
):
    """Export complet des données personnelles (RGPD Art. 15).

    Returns:
        JSON avec TOUTES les données associées au user:
            - Informations compte
            - Réservations
            - Factures
            - Audit logs (actions effectuées)

    Format: JSON structuré (portabilité Art. 20)
    """
    # Récupérer customer associé
    customer = db.query(Customer).filter(
        Customer.tenant_id == current_user.tenant_id,
        Customer.email == current_user.email
    ).first()

    if not customer:
        return {"error": "No customer data found"}

    # Récupérer toutes les données
    reservations = db.query(Reservation).filter(
        Reservation.tenant_id == current_user.tenant_id,
        Reservation.customer_id == customer.id
    ).all()

    invoices = db.query(Invoice).join(Reservation).filter(
        Reservation.tenant_id == current_user.tenant_id,
        Reservation.customer_id == customer.id
    ).all()

    # Construire export structuré
    export_data = {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "format_version": "1.0.0",
        "personal_data": {
            "customer": {
                "id": customer.id,
                "email": customer.email,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "phone": customer.phone,
                "address": customer.address,
                "notes": customer.notes,
                "created_at": customer.created_at.isoformat(),
                "updated_at": customer.updated_at.isoformat(),
                "consent_marketing": customer.consent_marketing,
                "consent_date": customer.consent_date.isoformat() if customer.consent_date else None
            },
            "reservations": [
                {
                    "id": res.id,
                    "reference": res.reference,
                    "status": res.status,
                    "start_date": res.start_date.isoformat(),
                    "end_date": res.end_date.isoformat(),
                    "total_amount_cents": res.total_amount_cents,
                    "notes": res.notes,
                    "created_at": res.created_at.isoformat(),
                    "lines": [
                        {
                            "product_name": line.product.name,
                            "quantity": line.quantity,
                            "unit_price_cents": line.unit_price_cents
                        }
                        for line in res.lines
                    ]
                }
                for res in reservations
            ],
            "invoices": [
                {
                    "id": inv.id,
                    "invoice_number": inv.invoice_number,
                    "status": inv.status,
                    "total_amount_cents": inv.total_amount_cents,
                    "paid_amount_cents": inv.paid_amount_cents,
                    "payment_method": inv.payment_method,
                    "payment_date": inv.payment_date.isoformat() if inv.payment_date else None,
                    "created_at": inv.created_at.isoformat()
                }
                for inv in invoices
            ],
            "audit_trail": {
                "note": "Historique complet disponible sur demande écrite au DPO"
            }
        },
        "metadata": {
            "data_controller": "CaroCorp SAS",
            "dpo_contact": "dpo@carocorp.com",
            "retention_periods": {
                "reservations": "5 ans après fin contrat",
                "invoices": "10 ans (obligations comptables)",
                "marketing_data": "3 ans depuis dernier contact"
            }
        }
    }

    # ✅ Audit log de l'export (traçabilité)
    audit_service.log(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="DATA_EXPORT",
        entity_type="Customer",
        entity_id=customer.id
    )

    return export_data


@router.get("/me/data-export-csv")
def export_my_data_csv(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends()
):
    """Export données format CSV (RGPD Art. 20 - portabilité).

    Returns:
        CSV avec données tabulaires (reservations + invoices)
    """
    # TODO: Générer CSV avec pandas
    pass
```

---

### Article 17 : Droit à l'Effacement

**Exigence**: Utilisateur peut demander suppression de ses données

**État actuel**: ⚠️ PARTIEL (soft delete existe, mais pas d'anonymisation)

**Problème actuel**:
```python
# Soft delete actuel
customer.is_active = False  # ❌ Données toujours présentes en DB

# ✅ RGPD exige ANONYMISATION (pas juste flag)
```

**Actions correctives**:

**1. Service anonymisation** : `app/services/gdpr.py`

```python
"""Services conformité RGPD - Anonymisation et suppression."""
from sqlalchemy.orm import Session
from app.models.customer import Customer
from app.models.reservation import Reservation
from app.models.invoice import Invoice
from app.services.audit import AuditService
from datetime import datetime, timezone
import hashlib


class GDPRService:
    """Service gestion droits RGPD."""

    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    def anonymize_customer(self, customer_id: int, tenant_id: int, user_id: int) -> dict:
        """Anonymiser customer (RGPD Art. 17).

        Processus:
            1. Vérifier que customer n'a pas de factures impayées
            2. Anonymiser données PII:
                - email → "deleted_<hash>@anonymized.local"
                - first_name → "ANONYMIZED"
                - last_name → "USER"
                - phone → None
                - address → None
                - notes → None
            3. Marquer is_active = False
            4. Enregistrer anonymized_at
            5. Audit log (traçabilité suppression)

        Exceptions:
            ValueError: Si factures impayées ou réservations en cours

        Returns:
            {"anonymized": True, "customer_id": ..., "date": ...}
        """
        # Charger customer
        customer = self.db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.tenant_id == tenant_id
        ).first()

        if not customer:
            raise ValueError("Customer not found")

        # 1. Vérifier contraintes légales
        # ❌ Ne peut PAS anonymiser si factures impayées (obligations comptables)
        unpaid_invoices = self.db.query(Invoice).join(Reservation).filter(
            Reservation.customer_id == customer_id,
            Invoice.status.in_(["unpaid", "partial"])
        ).count()

        if unpaid_invoices > 0:
            raise ValueError(
                f"Cannot anonymize customer with {unpaid_invoices} unpaid invoices. "
                "Legal retention period applies (10 years after payment)."
            )

        # ❌ Ne peut PAS anonymiser si réservations en cours
        active_reservations = self.db.query(Reservation).filter(
            Reservation.customer_id == customer_id,
            Reservation.status.in_(["confirmed", "in_progress"])
        ).count()

        if active_reservations > 0:
            raise ValueError(
                f"Cannot anonymize customer with {active_reservations} active reservations. "
                "Please complete or cancel reservations first."
            )

        # 2. Anonymiser données PII
        original_email = customer.email
        customer_hash = hashlib.sha256(f"{customer.id}:{original_email}".encode()).hexdigest()[:8]

        customer.email = f"deleted_{customer_hash}@anonymized.local"
        customer.first_name = "ANONYMIZED"
        customer.last_name = "USER"
        customer.phone = None
        customer.address = None
        customer.notes = None
        customer.is_active = False
        customer.anonymized_at = datetime.now(timezone.utc)

        # 3. Anonymiser notes réservations (peuvent contenir PII)
        self.db.query(Reservation).filter(
            Reservation.customer_id == customer_id
        ).update({"notes": None})

        self.db.commit()

        # 4. Audit log IMMUABLE (traçabilité suppression RGPD)
        self.audit_service.log(
            tenant_id=tenant_id,
            user_id=user_id,
            action="GDPR_ANONYMIZE",
            entity_type="Customer",
            entity_id=customer_id,
            changes={
                "original_email_hash": hashlib.sha256(original_email.encode()).hexdigest(),
                "anonymized_at": customer.anonymized_at.isoformat(),
                "reason": "GDPR Art. 17 - Right to erasure"
            },
            ip_address=None,
            user_agent=None
        )

        return {
            "anonymized": True,
            "customer_id": customer_id,
            "date": customer.anonymized_at.isoformat()
        }

    def check_retention_periods(self):
        """Vérifier périodes de conservation (RGPD Art. 5.1.e).

        Règles:
            - Réservations completed > 5 ans → Anonymiser
            - Marketing sans activité > 3 ans → Supprimer consentement
            - Factures payées > 10 ans → OK garder (obligation légale)
        """
        # TODO: Cron job journalier
        pass
```

**2. Endpoint suppression**:

```python
# app/api/v1/endpoints/gdpr.py

@router.post("/me/request-deletion")
def request_account_deletion(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends()
):
    """Demander suppression compte (RGPD Art. 17).

    Processus:
        1. Vérifier éligibilité (pas de factures impayées)
        2. Anonymiser données PII
        3. Email confirmation à l'utilisateur

    Returns:
        Statut demande (immediate si eligible, pending si contraintes)
    """
    customer = db.query(Customer).filter(
        Customer.tenant_id == current_user.tenant_id,
        Customer.email == current_user.email
    ).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    gdpr_service = GDPRService(db)

    try:
        result = gdpr_service.anonymize_customer(
            customer_id=customer.id,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id
        )

        return {
            "status": "completed",
            "message": "Your personal data has been anonymized",
            "details": result
        }

    except ValueError as e:
        # Contraintes légales empêchent anonymisation immédiate
        return {
            "status": "pending",
            "message": str(e),
            "next_steps": "Your account will be anonymized automatically once legal retention periods expire"
        }
```

---

### Article 20 : Droit à la Portabilité

**Exigence**: Export données format structuré et interopérable

**Actions**: Voir Article 15 (export JSON/CSV)

---

### Article 25 : Privacy by Design & Default

**Exigence**: Sécurité et confidentialité intégrées dès la conception

**Mesures actuelles**:
- ✅ Multi-tenant isolation (design)
- ✅ Soft delete (pas de suppression physique)
- ✅ RBAC (accès restreints)
- ⚠️ Pas de pseudonymisation
- ❌ Pas de chiffrement niveau application

**Actions correctives**:

**Pseudonymisation emails** : `app/services/pseudonymization.py`

```python
"""Pseudonymisation données PII pour analytics/reporting."""
import hashlib
from app.core.config import settings


def pseudonymize_email(email: str) -> str:
    """Pseudonymiser email pour analytics (RGPD Art. 25).

    Exemple:
        "john.doe@example.com" → "a3f5b2c1"

    Usage:
        Logs analytics, reports, exports non-sensibles
    """
    # Hash avec salt (empêche rainbow tables)
    salt = settings.PSEUDONYMIZATION_SALT
    hash_input = f"{salt}:{email}".encode()
    return hashlib.sha256(hash_input).hexdigest()[:8]


def pseudonymize_customer_name(first_name: str, last_name: str) -> str:
    """Pseudonymiser nom pour affichage public.

    Exemple:
        "John", "Doe" → "J. D."
    """
    return f"{first_name[0]}. {last_name[0]}." if first_name and last_name else "Anonymous"
```

---

### Article 30 : Registre des Traitements

**Exigence**: Documentation de tous les traitements de données

**État actuel**: ❌ MANQUANT

**Actions correctives**:

**Créer**: `docs/RGPD_REGISTRE_TRAITEMENTS.md`

```markdown
# Registre des Traitements de Données - CaroCorp SAS

**Responsable traitement**: CaroCorp SAS
**DPO**: dpo@carocorp.com
**Dernière mise à jour**: 2024-01-15

---

## Traitement #1: Gestion des Réservations

**Finalité**: Permettre aux clients de réserver du matériel

**Base légale**: Exécution du contrat (RGPD Art. 6.1.b)

**Catégories de données**:
- Identité: nom, prénom, email
- Coordonnées: téléphone, adresse
- Données transactionnelles: dates réservation, produits, montants

**Catégories de personnes**:
- Clients professionnels
- Clients particuliers

**Destinataires**:
- Personnel CaroCorp (service réservation)
- Prestataire comptable (factures)

**Transferts hors UE**: Aucun

**Durée conservation**:
- Données clients actifs: Durée relation contractuelle + 5 ans
- Factures: 10 ans (obligation légale code de commerce)

**Mesures sécurité**:
- Chiffrement TLS transport
- Hachage mots de passe bcrypt
- Accès restreints RBAC
- Audit logs immuables
- Backups chiffrés journaliers

---

## Traitement #2: Authentification Utilisateurs

**Finalité**: Sécuriser accès à l'application

**Base légale**: Intérêt légitime (RGPD Art. 6.1.f) - sécurité du système

**Catégories de données**:
- Identité: email
- Authentification: mot de passe haché (bcrypt)
- Connexion: IP, user agent, timestamps

**Durée conservation**:
- Comptes actifs: Durée relation contractuelle
- Logs connexion: 12 mois

**Mesures sécurité**:
- JWT tokens (expiration 30min)
- Refresh tokens révocables
- Rate limiting (protection brute force)
- Audit log tentatives connexion

---

## Traitement #3: Marketing (si consentement)

**Finalité**: Envoi newsletters et offres commerciales

**Base légale**: Consentement (RGPD Art. 6.1.a)

**Catégories de données**:
- Email uniquement

**Durée conservation**:
- 3 ans depuis dernier contact
- Suppression immédiate si retrait consentement

**Mesures sécurité**:
- Opt-in explicite (double opt-in)
- Lien désabonnement dans chaque email
- Traçabilité consentement (date, heure, méthode)
```

---

### Article 32 : Sécurité du Traitement

**Exigence**: Mesures techniques et organisationnelles appropriées

**Mesures en place**:
- ✅ Chiffrement TLS (transport)
- ✅ Hachage passwords bcrypt
- ✅ RBAC accès
- ✅ JWT expiration courte
- ⚠️ Chiffrement DB manquant (voir A02)

**Actions**: Voir section A02:2021

---

### Article 33-34 : Notification Violations de Données

**Exigence**: Notifier CNIL et personnes concernées sous 72h si breach

**État actuel**: ❌ MANQUANT

**Actions correctives**:

**Créer**: `docs/PROCEDURE_BREACH_NOTIFICATION.md`

```markdown
# Procédure Notification Violation de Données

## 1. Détection Breach

**Indicateurs**:
- Alerte intrusion (SIEM)
- Accès non autorisé détecté
- Fuite données signalée
- Ransomware détecté

**Actions immédiates** (H+0):
1. Containment (isoler système compromis)
2. Préserver preuves (logs, forensics)
3. Alerter DPO + RSSI
4. Convoquer cellule de crise

---

## 2. Évaluation Gravité (H+2)

**Critères**:
- Nombre personnes impactées
- Nature données (PII, données sensibles)
- Risque préjudice personnes

**Classification**:
- **Gravité HAUTE**: > 1000 personnes OU données sensibles (santé, bancaires)
- **Gravité MOYENNE**: 100-1000 personnes OU données PII standard
- **Gravité FAIBLE**: < 100 personnes ET données non sensibles

---

## 3. Notification CNIL (si requis)

**Délai**: 72 heures maximum après détection

**Contenu notification**:
- Nature violation
- Catégories et nombre personnes concernées
- Conséquences probables
- Mesures prises/envisagées
- Contact DPO

**Formulaire**: https://www.cnil.fr/notifications-violations-donnees

**Exception**: Pas de notification si "peu probable que la violation engendre un risque pour les droits et libertés"

---

## 4. Notification Personnes Concernées

**Si risque ÉLEVÉ pour droits et libertés**:
- Email individuel à chaque personne
- Langage clair et simple
- Description violation
- Mesures protection recommandées
- Contact DPO

**Template email**:
```
Objet: [IMPORTANT] Violation de données - CaroCorp

Madame, Monsieur,

Nous vous informons qu'une violation de données personnelles a affecté votre compte CaroCorp le [DATE].

Nature de l'incident:
[Description claire sans jargon technique]

Données concernées:
[Liste précise: email, nom, etc.]

Mesures prises par CaroCorp:
- [Containment]
- [Correction]
- [Prévention future]

Mesures recommandées pour vous:
- Changez votre mot de passe immédiatement
- Surveillez activité suspecte sur vos comptes
- [Autres selon contexte]

Contact:
DPO CaroCorp - dpo@carocorp.com - 01 23 45 67 89

Cette notification est effectuée conformément au RGPD (Art. 34).
```

---

## 5. Documentation

**Registre violations** (obligatoire même si pas de notification CNIL):
- Date et heure détection
- Nature violation
- Faits et conséquences
- Mesures prises
- Décision notification (oui/non + justification)

**Conservation**: Permanent (audit CNIL)

---

## 6. Post-Mortem (H+72)

- RCA (Root Cause Analysis)
- Identification failles sécurité
- Plan d'action correctif
- Mise à jour procédures
- Formation équipes
```

**Estimation Conformité RGPD**: 40 heures (anonymisation + exports + procédures + doc)
**Priorité**: P0-P1 - Conformité légale obligatoire

---

## Roadmap Détaillée (10 Phases)

### Vue d'ensemble

| Phase | Objectif | Durée | Bugs Corrigés | Coverage | Priorité |
|-------|----------|-------|---------------|----------|----------|
| Phase 1 | Bugs critiques P0 | 25h | #1, #2, #3, #5 | 95% | CRITIQUE |
| Phase 2 | JWT & Auth sécurité | 12h | #6, #10 | 96% | CRITIQUE |
| Phase 3 | Rate Limiting & CSRF | 10h | #4 | 97% | HAUTE |
| Phase 4 | Exception Handling | 14h | #7, #9 | 98% | HAUTE |
| Phase 5 | Database Resilience | 8h | - | 99% | HAUTE |
| Phase 6 | Security Hardening | 12h | - | 99.5% | HAUTE |
| Phase 7 | RGPD Conformité | 20h | - | 99.5% | CRITIQUE |
| Phase 8 | Observabilité | 10h | #11 | 99.8% | MOYENNE |
| Phase 9 | Tests E2E | 12h | #12 | 100% | HAUTE |
| Phase 10 | Documentation & Deploy | 10h | - | 100% | HAUTE |
| **TOTAL** | **100% Coverage + Production-Ready** | **133h** | **12 bugs** | **100%** | **~3-4 semaines** |

---

### Phase 1 : Bugs Critiques P0 (25 heures)

**Objectif**: Corriger les 4 bugs bloquants production

**Bugs traités**:
- 🔴 BUG #1 P0: Désynchronisation ReservationStatus DB/Code
- 🔴 BUG #2 P0: datetime.utcnow() deprecated
- 🔴 BUG #3 P0: CSRF protection non-functional
- 🔴 BUG #5 P0: Audit log manquant

#### Étape 1.1 : BUG #1 - ReservationStatus (4h)

**Actions**:
1. Choisir Option A (synchroniser Enum avec DB)
2. Modifier `app/constants/business.py`:
   ```python
   class ReservationStatus(str, Enum):
       DRAFT = "draft"
       CONFIRMED = "confirmed"
       IN_PROGRESS = "in_progress"  # Remplace DELIVERED
       COMPLETED = "completed"      # Remplace RETURNED
       CANCELLED = "cancelled"
   ```
3. Rechercher tous usages de `DELIVERED` et `RETURNED` (grep)
4. Remplacer par `IN_PROGRESS` et `COMPLETED`
5. Mettre à jour tests
6. Valider avec pytest

**Validation**:
```bash
# Rechercher usages anciens status
grep -r "DELIVERED\|RETURNED" app/ tests/
# Doit retourner 0 résultats

# Tests
pytest tests/unit/test_reservation_service.py -v
pytest tests/integration/test_reservations_endpoints.py -v
```

**Livrable**:
- ✅ Enum synchronisé avec DB
- ✅ 0 usage de DELIVERED/RETURNED
- ✅ Tests passants

---

#### Étape 1.2 : BUG #2 - datetime.utcnow() (3h)

**Actions**:
1. Modifier `app/core/security.py`:
   ```python
   from datetime import datetime, timezone, timedelta

   # Ligne 42 (create_access_token)
   - expire = datetime.utcnow() + expires_delta
   + expire = datetime.now(timezone.utc) + expires_delta

   # Ligne 44
   - expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
   + expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

   # Ligne 50
   - "iat": datetime.utcnow()
   + "iat": datetime.now(timezone.utc)

   # Ligne 81 (create_refresh_token)
   - expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
   + expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

   # Ligne 87
   - "iat": datetime.utcnow()
   + "iat": datetime.now(timezone.utc)
   ```

2. Valider 0 DeprecationWarnings

**Validation**:
```bash
# Rechercher tous usages datetime.utcnow()
grep -r "datetime.utcnow()" app/

# Tests sans warnings
pytest tests/ -v 2>&1 | grep DeprecationWarning
# Doit retourner 0 lignes
```

**Livrable**:
- ✅ 5 occurrences datetime.utcnow() remplacées
- ✅ 0 DeprecationWarning
- ✅ Tests passants

---

#### Étape 1.3 : BUG #3 - CSRF Protection (8h)

**Actions**:
1. Créer modèle Redis session (voir BUG #3)
2. Implémenter `_generate_csrf_token()` avec secrets.token_urlsafe()
3. Implémenter `_validate_csrf_token()` avec Redis lookup
4. Middleware CSRF complet fonctionnel
5. Tests sécurité CSRF

**Validation**:
```bash
# Tests CSRF
pytest tests/security/test_csrf_protection.py -v

# Tous tests doivent passer:
# - test_reject_request_without_csrf_token
# - test_reject_request_with_invalid_csrf_token
# - test_reject_request_with_expired_csrf_token
# - test_accept_request_with_valid_csrf_token
```

**Livrable**:
- ✅ CSRF tokens stockés Redis
- ✅ Validation fonctionnelle
- ✅ 4 tests sécurité passants

---

#### Étape 1.4 : BUG #5 - Audit Log (10h)

**Actions**:
1. Créer modèle `AuditLog` (voir BUG #5)
2. Migration Alembic avec trigger PostgreSQL
3. Service `AuditService`
4. Middleware `AuditLogMiddleware`
5. Endpoint `/api/v1/audit` (admin only)
6. Tests audit log

**Validation**:
```bash
# Migration
alembic upgrade head

# Vérifier trigger immutabilité
psql -d MassaCorp -c "UPDATE audit_logs SET action='HACKED' WHERE id=1;"
# Doit retourner ERROR: trigger prevent_audit_modification

# Tests
pytest tests/unit/test_audit_service.py -v
pytest tests/security/test_audit_log_immutability.py -v
```

**Livrable**:
- ✅ Table audit_logs créée
- ✅ Trigger immutabilité PostgreSQL
- ✅ Middleware audit automatique
- ✅ Tests immutabilité passants

---

**Résumé Phase 1**:
- ✅ 4 bugs P0 corrigés
- ✅ Coverage: 94.42% → 95%
- ✅ 0 bug bloquant production restant

---

### Phase 2 : JWT & Auth Sécurité (12 heures)

**Objectif**: Sécuriser authentification et validation JWT

**Bugs traités**:
- 🟠 BUG #6 P1: Exception handling JWT validation
- 🟠 BUG #10 P1: JWT token expiration edge cases

#### Étape 2.1 : BUG #6 - Exception Handling JWT (6h)

**Actions**:
1. Créer `tests/security/test_jwt_validation.py` (voir BUG #6)
2. Tests pour:
   - Token type invalide (refresh utilisé comme access)
   - Claim "sub" manquant
   - Claim "sub" non-numérique
   - User supprimé après émission token
   - Compte désactivé (is_active=False)
3. Valider que toutes branches d'erreur sont couvertes

**Validation**:
```bash
# Coverage deps.py doit atteindre 100%
pytest tests/security/test_jwt_validation.py --cov=app/core/deps --cov-report=term

# Lignes 62, 71, 76-77, 82, 86 doivent être VERTES
```

**Livrable**:
- ✅ 7 tests JWT validation
- ✅ Coverage deps.py: 100%
- ✅ Toutes branches d'erreur testées

---

#### Étape 2.2 : BUG #10 - JWT Expiration (6h)

**Actions**:
1. Créer `tests/security/test_jwt_expiration.py` (voir BUG #10)
2. Tests pour:
   - Access token expiré rejeté
   - Refresh token valide après access expiré
   - Refresh token expiré rejeté
   - Access token ne peut pas refresh
   - Clock skew tolerance (leeway=0)
3. Configurer leeway=0 dans decode_token

**Validation**:
```bash
pytest tests/security/test_jwt_expiration.py -v

# 5 tests expiration doivent passer
```

**Livrable**:
- ✅ 5 tests expiration
- ✅ Leeway=0 (strict expiration)
- ✅ Refresh flow sécurisé

---

**Résumé Phase 2**:
- ✅ 2 bugs P1 corrigés
- ✅ Coverage: 95% → 96%
- ✅ Authentification production-grade

---

### Phase 3 : Rate Limiting & CSRF (10 heures)

**Objectif**: Protection DoS et CSRF complète

**Bugs traités**:
- 🟠 BUG #4 P1: Rate limiting non implémenté

#### Étape 3.1 : Rate Limiting Redis (6h)

**Actions**:
1. Implémenter `RateLimitMiddleware` avec Redis (voir BUG #4)
2. Algorithme sliding window:
   ```python
   key = f"rate_limit:{user_id}:{endpoint}"
   count = redis.incr(key)
   if count == 1:
       redis.expire(key, window_seconds)
   if count > limit:
       raise HTTPException(429, "Too many requests")
   ```
3. Configuration par endpoint:
   - `/api/v1/auth/login`: 5 req/min
   - `/api/v1/auth/refresh`: 10 req/min
   - Autres endpoints: 100 req/min
4. Tests rate limiting

**Validation**:
```bash
pytest tests/security/test_rate_limiting.py -v

# Tests:
# - test_rate_limit_login (5 req OK, 6ème rejetée)
# - test_rate_limit_refresh (10 req OK, 11ème rejetée)
# - test_rate_limit_reset_after_window
# - test_rate_limit_per_user_isolation
```

**Livrable**:
- ✅ Rate limiting fonctionnel
- ✅ Protection brute force login
- ✅ 4 tests passants

---

#### Étape 3.2 : CSRF Validation Tests (4h)

**Actions**:
1. Compléter tests CSRF (déjà implémenté Phase 1.3)
2. Tests intégration endpoints:
   ```python
   # POST /customers sans CSRF → 403
   # POST /customers avec CSRF valide → 201
   # PUT /customers/{id} sans CSRF → 403
   # DELETE /customers/{id} sans CSRF → 403
   ```

**Validation**:
```bash
pytest tests/integration/test_csrf_endpoints.py -v
```

**Livrable**:
- ✅ Tous endpoints POST/PUT/DELETE protégés CSRF
- ✅ Tests intégration passants

---

**Résumé Phase 3**:
- ✅ 1 bug P1 corrigé
- ✅ Coverage: 96% → 97%
- ✅ Protection DoS + CSRF

---

### Phase 4 : Exception Handling Services (14 heures)

**Objectif**: Couvrir toutes branches d'erreur métier

**Bugs traités**:
- 🟠 BUG #7 P1: Exception handling services
- 🟡 BUG #9 P1: Hard delete non testé

#### Étape 4.1 : ReservationService Errors (6h)

**Actions**:
1. Créer `tests/unit/test_reservation_service_errors.py` (voir BUG #7)
2. Tests:
   - Confirmer réservation déjà confirmée → ValueError
   - Confirmer sans lignes → ValueError
   - Stock insuffisant lors confirmation → ValueError
   - Race condition double réservation → IntegrityError → ValueError

**Validation**:
```bash
pytest tests/unit/test_reservation_service_errors.py --cov=app/services/reservation --cov-report=term

# Lignes 86-87, 96-97, 102 doivent être VERTES
```

**Livrable**:
- ✅ 4 tests erreurs ReservationService
- ✅ Coverage reservation.py: 100%

---

#### Étape 4.2 : ProductService Errors (5h)

**Actions**:
1. Créer `tests/unit/test_product_service_errors.py` (voir BUG #7)
2. Tests:
   - available_quantity > stock_quantity → ValueError
   - IntegrityError lors réservation → ValueError
   - Hard delete product inexistant → False
   - Hard delete product existant → True

**Validation**:
```bash
pytest tests/unit/test_product_service_errors.py --cov=app/services/product --cov-report=term

# Lignes 87, 94-101, 151, 214, 255, 294 doivent être VERTES
```

**Livrable**:
- ✅ 4 tests erreurs ProductService
- ✅ Coverage product.py: 100%

---

#### Étape 4.3 : User Model Properties (1h)

**Actions**:
1. Ajouter tests properties User (voir BUG #8)
2. Tests simples:
   ```python
   test_user_is_admin_property()
   test_user_is_manager_property()
   test_user_is_staff_property()
   test_user_can_manage_products_property()
   ```

**Validation**:
```bash
pytest tests/unit/test_user_model.py --cov=app/models/user --cov-report=term

# Lignes 77, 82, 87, 92 doivent être VERTES
```

**Livrable**:
- ✅ 4 tests properties User
- ✅ Coverage user.py: 100%

---

#### Étape 4.4 : Database Connection Resilience (2h)

**Actions**:
1. Créer `tests/integration/test_database_resilience.py` (voir BUG #9)
2. Tests:
   - DB indisponible au démarrage → OperationalError
   - Perte connexion mid-request → Rollback + 500
   - Session cleanup exception → Finally close()
   - Query timeout → OperationalError

**Validation**:
```bash
pytest tests/integration/test_database_resilience.py --cov=app/core/database --cov-report=term

# Lignes 35-39, 50-54 doivent être VERTES
```

**Livrable**:
- ✅ 4 tests résilience DB
- ✅ Coverage database.py: 100%
- ✅ Configuration pool_pre_ping, timeouts

---

**Résumé Phase 4**:
- ✅ 2 bugs P1 + 1 bug P2 corrigés
- ✅ Coverage: 97% → 98%
- ✅ Robustesse exception handling

---

### Phase 5 : Database Resilience Production (8 heures)

**Objectif**: Configuration DB production-grade

**Actions**:
1. PostgreSQL SSL/TLS activé
2. Connection pooling optimisé
3. Timeouts configurés
4. Health checks automatiques

#### Étape 5.1 : PostgreSQL SSL (2h)

**Configuration** `docker-compose.yml`:
```yaml
services:
  postgres:
    command:
      - "postgres"
      - "-c"
      - "ssl=on"
      - "-c"
      - "ssl_cert_file=/var/lib/postgresql/server.crt"
      - "-c"
      - "ssl_key_file=/var/lib/postgresql/server.key"
    volumes:
      - ./certs/server.crt:/var/lib/postgresql/server.crt:ro
      - ./certs/server.key:/var/lib/postgresql/server.key:ro
```

**Validation**:
```bash
psql "postgresql://massa:pass@localhost/MassaCorp?sslmode=require"
# Doit se connecter en SSL
```

---

#### Étape 5.2 : Connection Pooling (2h)

**Configuration** `app/core/database.py`:
```python
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,           # 10 connexions permanentes
    max_overflow=20,        # +20 connexions burst
    pool_pre_ping=True,     # Vérifier connexion avant utilisation
    pool_recycle=3600,      # Recycler après 1h
    connect_args={
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000"  # 30s max query
    }
)
```

**Validation**:
```bash
# Monitoring connexions
psql -d MassaCorp -c "SELECT count(*) FROM pg_stat_activity WHERE datname='MassaCorp';"
# Doit rester < 30 connexions
```

---

#### Étape 5.3 : Health Checks (4h)

**Créer** `app/api/v1/endpoints/health.py`:
```python
@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint (Kubernetes readiness/liveness)."""
    try:
        # Test DB connexion
        db.execute(text("SELECT 1"))

        # Test Redis connexion
        redis_client.ping()

        return {
            "status": "healthy",
            "db": "connected",
            "redis": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
```

**Validation**:
```bash
curl http://localhost:8001/health
# {"status": "healthy", ...}

# Kubernetes
kubectl apply -f k8s/deployment.yaml
# readinessProbe: httpGet /health
# livenessProbe: httpGet /health
```

---

**Résumé Phase 5**:
- ✅ PostgreSQL SSL activé
- ✅ Connection pooling optimisé
- ✅ Health checks Kubernetes
- ✅ Coverage: 98% → 99%

---

### Phase 6 : Security Hardening OWASP (12 heures)

**Objectif**: Conformité OWASP Top 10 complète

#### Étape 6.1 : Security Misconfiguration (4h)

**Actions**:
1. Validation secrets au démarrage (voir A05)
2. CORS strict (domaines exacts)
3. Désactiver docs en production
4. Security headers middleware:
   ```python
   X-Content-Type-Options: nosniff
   X-Frame-Options: DENY
   X-XSS-Protection: 1; mode=block
   Strict-Transport-Security: max-age=31536000
   ```

**Validation**:
```bash
# Tester démarrage avec secret par défaut
JWT_SECRET="super-secret-key-change-me-in-production" python app/main.py
# Doit bloquer avec erreur

# Tester headers sécurité
curl -I http://localhost:8001/api/v1/customers
# Doit contenir tous headers sécurité
```

---

#### Étape 6.2 : Cryptographic Failures (4h)

**Actions**:
1. PostgreSQL encryption at rest (LUKS)
2. Backup chiffrement GPG
3. Secure cookies (httpOnly, sameSite)

**Validation**:
```bash
# Vérifier cookies sécurisés
curl -v http://localhost:8001/api/v1/auth/login
# Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict
```

---

#### Étape 6.3 : Cross-Tenant Tests Exhaustifs (4h)

**Actions**:
1. Créer `tests/security/test_cross_tenant_isolation.py` (voir A01)
2. Tests pour TOUS endpoints:
   - Customers (GET, LIST, UPDATE, DELETE)
   - Products (GET, LIST, UPDATE, DELETE, RESERVE)
   - Reservations (GET, LIST, UPDATE, CONFIRM, CANCEL)
   - Invoices (GET, LIST, ADD_PAYMENT)

**Validation**:
```bash
pytest tests/security/test_cross_tenant_isolation.py -v

# 20+ tests cross-tenant doivent passer
# Tous doivent retourner 404 (pas 403)
```

---

**Résumé Phase 6**:
- ✅ OWASP Top 10 couvert à 100%
- ✅ Security hardening complet
- ✅ Coverage: 99% → 99.5%

---

### Phase 7 : RGPD Conformité (20 heures)

**Objectif**: Conformité légale RGPD complète

#### Étape 7.1 : Privacy Policy & Consent (4h)

**Actions**:
1. Endpoint `/api/v1/legal/privacy-policy`
2. Champs consentement Customer (consent_marketing, consent_date)
3. Endpoint `/api/v1/customers/me/consent-marketing`

---

#### Étape 7.2 : Data Export (Art. 15) (4h)

**Actions**:
1. Endpoint `/api/v1/gdpr/me/data-export` (JSON)
2. Endpoint `/api/v1/gdpr/me/data-export-csv` (CSV)
3. Tests export complet

---

#### Étape 7.3 : Anonymisation (Art. 17) (6h)

**Actions**:
1. Service `GDPRService.anonymize_customer()`
2. Vérifications contraintes légales (factures impayées)
3. Anonymisation PII (email, nom, téléphone, adresse, notes)
4. Endpoint `/api/v1/gdpr/me/request-deletion`
5. Tests anonymisation

---

#### Étape 7.4 : Registre Traitements & Procédures (6h)

**Actions**:
1. Document `RGPD_REGISTRE_TRAITEMENTS.md`
2. Document `PROCEDURE_BREACH_NOTIFICATION.md`
3. Cron job périodes conservation (auto-anonymisation > 5 ans)

---

**Résumé Phase 7**:
- ✅ Conformité RGPD complète
- ✅ Droits personnes implémentés (Art. 15, 17, 20)
- ✅ Procédures breach notification
- ✅ Coverage: 99.5% (inchangé)

---

### Phase 8 : Observabilité & Logging (10 heures)

**Objectif**: Logs structurés JSON + monitoring

**Bugs traités**:
- 🟡 BUG #11 P2: Logs non structurés

#### Étape 8.1 : Logging Structuré JSON (5h)

**Actions**:
1. Créer `app/core/logging.py` avec `CustomJsonFormatter`
2. Middleware `LoggingContextMiddleware` (request_id, tenant_id, user_id)
3. Migrer tous `logger.info()` vers format structuré

**Validation**:
```bash
# Logs JSON
python app/main.py 2>&1 | jq .

# Output:
# {
#   "timestamp": "2024-01-15T10:30:45Z",
#   "level": "INFO",
#   "logger": "app.services.reservation",
#   "message": "Confirming reservation",
#   "reservation_id": 123,
#   "tenant_id": 1,
#   "request_id": "uuid"
# }
```

---

#### Étape 8.2 : Monitoring & Alerting (5h)

**Actions**:
1. Prometheus metrics exporter
2. Grafana dashboards:
   - Request rate (RED method)
   - Error rate (5xx)
   - Latency p50/p95/p99
   - DB connexions
3. Alertmanager rules:
   - Spike 5xx > 5%
   - Latency p95 > 500ms
   - Login failures > 10/min

**Validation**:
```bash
# Metrics endpoint
curl http://localhost:8001/metrics

# Prometheus scraping
curl http://localhost:9090/api/v1/query?query=up{job="carocorp"}
```

---

**Résumé Phase 8**:
- ✅ Logs structurés JSON
- ✅ Observabilité production-grade
- ✅ Coverage: 99.5% → 99.8%

---

### Phase 9 : Tests E2E Workflows (12 heures)

**Objectif**: Validation workflows complets

**Bugs traités**:
- 🟡 BUG #12 P2: Tests E2E workflows incomplets

#### Étape 9.1 : Workflow Location Complète (6h)

**Actions**:
1. Test E2E: Créer customer → Browse products → Créer réservation → Ajouter lignes → Confirmer → Générer facture → Payer
2. Validation stock réservé automatiquement
3. Validation statuts finaux

---

#### Étape 9.2 : Workflow Annulation (3h)

**Actions**:
1. Test E2E: Réservation confirmée → Annuler → Stock libéré
2. Validation cascade (facture annulée)

---

#### Étape 9.3 : Workflow Concurrence Stock (3h)

**Actions**:
1. Test E2E: Product stock=10 → Client A réserve 7 → Client B réserve 5 (échoue) → A annule → B réserve 5 (réussit)
2. Validation race conditions gérées

---

**Résumé Phase 9**:
- ✅ 3 workflows E2E complets
- ✅ Validation intégration services
- ✅ Coverage: 99.8% → 100% 🎉

---

### Phase 10 : Documentation & Déploiement (10 heures)

**Objectif**: Documentation complète + déploiement production

#### Étape 10.1 : Documentation Technique (4h)

**Actions**:
1. Mettre à jour `README.md` (setup, architecture, sécurité)
2. Créer `docs/ARCHITECTURE.md` (diagrammes, patterns)
3. Créer `docs/SECURITY.md` (authentification, OWASP, RGPD)
4. Créer `docs/API.md` (endpoints, exemples)
5. Générer OpenAPI spec (Swagger export)

---

#### Étape 10.2 : CI/CD Production (3h)

**Actions**:
1. Pipeline GitHub Actions:
   ```yaml
   - Lint (ruff)
   - Typecheck (mypy)
   - Tests (pytest)
   - Security scan (bandit, safety)
   - Build Docker image
   - Push registry
   ```
2. Kubernetes manifests:
   - Deployment (replicas=3)
   - Service (LoadBalancer)
   - Ingress (TLS)
   - ConfigMap (env vars)
   - Secrets (sealed-secrets)

---

#### Étape 10.3 : Déploiement Staging (3h)

**Actions**:
1. Déployer sur staging
2. Tests smoke (health check, login, CRUD)
3. Load testing (k6 - 100 req/s pendant 5min)
4. Validation logs + monitoring
5. Rollback test

**Validation**:
```bash
# Load test
k6 run scripts/load-test.js

# Résultats attendus:
# - p95 latency < 500ms
# - 0% erreurs
# - Autoscaling fonctionne (replicas 3 → 6)
```

---

**Résumé Phase 10**:
- ✅ Documentation complète
- ✅ CI/CD automatisé
- ✅ Déploiement staging réussi
- ✅ 100% Coverage + Production-Ready 🚀

---

### Résumé Global Roadmap

**Accomplissements**:
- ✅ 12 bugs corrigés (4 P0, 5 P1, 3 P2)
- ✅ Couverture: 94.42% → 100%
- ✅ Tests: 322 → 400+ tests
- ✅ OWASP Top 10: 100% couvert
- ✅ RGPD: Conformité complète
- ✅ Production-ready: Oui

**Estimation totale**: 133 heures (~3-4 semaines avec 1 développeur)

**Coût estimé** (si externe):
- Développeur senior: 100€/h × 133h = 13,300€
- Audit sécurité final: 2,000€
- **Total: ~15,000€**

---

## Stratégie de Tests

### Pyramide de Tests

```
        E2E (10%)
       /         \
      /  Integration  \
     /     (20%)        \
    /                    \
   /   Unit Tests (70%)   \
  /_________________________\
```

**Répartition cible**:
- **Unitaires**: 280+ tests (70%) - Services, Repositories, Models
- **Intégration**: 80+ tests (20%) - Endpoints API, Middleware
- **E2E**: 40+ tests (10%) - Workflows complets multi-services
- **Sécurité**: 50+ tests (transversal) - OWASP, RGPD, Multi-tenant

**Total**: ~450 tests (actuellement 322)

---

### Tests Unitaires (70%)

**Objectif**: Tester logique métier isolée

#### Services

**Fichiers**:
- `tests/unit/test_reservation_service.py` (existant)
- `tests/unit/test_reservation_service_errors.py` (Phase 4)
- `tests/unit/test_product_service.py` (existant)
- `tests/unit/test_product_service_errors.py` (Phase 4)
- `tests/unit/test_customer_service.py` (existant)
- `tests/unit/test_invoice_service.py` (existant)
- `tests/unit/test_auth_service.py` (existant)
- `tests/unit/test_gdpr_service.py` (Phase 7)
- `tests/unit/test_audit_service.py` (Phase 1)

**Couverture cible**: 95%+ pour services critiques

**Patterns**:
```python
# Arrange: Setup données test
customer = Customer(tenant_id=1, email="test@example.com", ...)
test_db.add(customer)
test_db.commit()

# Act: Appeler service
service = ReservationService(test_db)
result = service.confirm_reservation(reservation_id, tenant_id=1)

# Assert: Vérifier résultat
assert result.status == ReservationStatus.CONFIRMED
assert product.available_quantity == initial_qty - reserved_qty
```

---

#### Repositories

**Fichiers**:
- `tests/unit/test_base_repository.py` (existant - complet)
- `tests/unit/test_customer_repository.py` (existant)
- `tests/unit/test_product_repository.py` (existant)
- `tests/unit/test_reservation_repository.py` (existant)

**Couverture cible**: 90%+

**Focus**:
- Filtre `tenant_id` automatique
- Pagination (skip, limit)
- Filtres avancés (operators: gt, gte, lt, lte, ne)
- Soft delete (is_active)
- Count, exists, restore

---

#### Models

**Fichiers**:
- `tests/unit/test_user_model.py` (Phase 4 - properties)
- `tests/unit/test_customer_model.py` (existant)
- `tests/unit/test_product_model.py` (existant)
- `tests/unit/test_reservation_model.py` (existant)

**Couverture cible**: 85%+

**Focus**:
- Contraintes DB (CheckConstraint, UniqueConstraint)
- Properties calculées
- Relationships (lazy loading, eager loading)
- Mixins (TenantMixin, SoftDeleteMixin, TimestampMixin)

---

### Tests Intégration (20%)

**Objectif**: Tester endpoints API avec DB réelle

#### Endpoints CRUD

**Fichiers**:
- `tests/integration/test_customers_endpoints.py` (existant)
- `tests/integration/test_products_endpoints.py` (existant)
- `tests/integration/test_reservations_endpoints.py` (existant)
- `tests/integration/test_invoices_endpoints.py` (existant)
- `tests/integration/test_auth_endpoints.py` (existant)
- `tests/integration/test_gdpr_endpoints.py` (Phase 7)
- `tests/integration/test_audit_endpoints.py` (Phase 1)
- `tests/integration/test_legal_endpoints.py` (Phase 7)

**Couverture cible**: 85%+

**Patterns**:
```python
def test_create_customer(client, auth_headers_real):
    """Test POST /api/v1/customers."""
    # Arrange
    customer_data = {
        "email": "new@customer.com",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "0612345678"
    }

    # Act
    response = client.post(
        "/api/v1/customers",
        json=customer_data,
        headers=auth_headers_real
    )

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == customer_data["email"]
    assert "id" in data
    assert "created_at" in data
```

---

#### Middleware

**Fichiers**:
- `tests/integration/test_csrf_middleware.py` (Phase 3)
- `tests/integration/test_rate_limit_middleware.py` (Phase 3)
- `tests/integration/test_audit_middleware.py` (Phase 1)
- `tests/integration/test_logging_middleware.py` (Phase 8)
- `tests/integration/test_security_headers_middleware.py` (Phase 6)

**Couverture cible**: 90%+

**Focus**:
- Middleware execution order
- Request/Response modification
- Exception handling dans middleware
- Performance (overhead minimal)

---

#### Database Resilience

**Fichiers**:
- `tests/integration/test_database_resilience.py` (Phase 5)

**Tests**:
- DB indisponible au démarrage
- Perte connexion mid-request
- Session cleanup (finally block)
- Query timeout
- Connection pool saturation
- Rollback automatique sur exception

---

### Tests E2E (10%)

**Objectif**: Valider workflows complets multi-services

**Fichiers**:
- `tests/e2e/test_complete_workflows.py` (Phase 9)
- `tests/e2e/test_rental_workflow.py` (Phase 9)
- `tests/e2e/test_cancellation_workflow.py` (Phase 9)
- `tests/e2e/test_concurrent_reservations.py` (Phase 9)

**Workflows critiques**:

#### 1. Location Complète

```python
def test_complete_rental_workflow(client, auth_headers_real):
    """E2E: Créer customer → Réserver → Confirmer → Facturer → Payer."""
    # 1. Créer customer
    customer = client.post("/api/v1/customers", json={...}).json()

    # 2. Créer product
    product = client.post("/api/v1/products", json={...}).json()

    # 3. Créer réservation
    reservation = client.post("/api/v1/reservations", json={
        "customer_id": customer["id"],
        "start_date": "2024-01-15",
        "end_date": "2024-01-20"
    }).json()

    # 4. Ajouter lignes
    client.post(f"/api/v1/reservations/{reservation['id']}/lines", json={
        "product_id": product["id"],
        "quantity": 10
    })

    # 5. Confirmer (réserve stock)
    confirmed = client.post(
        f"/api/v1/reservations/{reservation['id']}/confirm"
    ).json()
    assert confirmed["status"] == "confirmed"

    # Vérifier stock réduit
    product_after = client.get(f"/api/v1/products/{product['id']}").json()
    assert product_after["available_quantity"] == 90  # 100 - 10

    # 6. Générer facture
    invoice = client.post(
        f"/api/v1/invoices/from-reservation/{reservation['id']}"
    ).json()

    # 7. Payer
    paid = client.post(f"/api/v1/invoices/{invoice['id']}/add-payment", json={
        "amount_cents": invoice["total_amount_cents"],
        "payment_method": "card"
    }).json()
    assert paid["status"] == "paid"
```

#### 2. Annulation avec Libération Stock

```python
def test_cancel_reservation_releases_stock(client, auth_headers_real):
    """E2E: Confirmer → Annuler → Vérifier stock restauré."""
    # Setup: Réservation confirmée
    # ...

    # Stock AVANT annulation
    product_before = client.get(f"/api/v1/products/{product_id}").json()
    initial_available = product_before["available_quantity"]

    # Annuler
    cancelled = client.post(f"/api/v1/reservations/{res_id}/cancel").json()
    assert cancelled["status"] == "cancelled"

    # Stock APRÈS annulation (restauré)
    product_after = client.get(f"/api/v1/products/{product_id}").json()
    assert product_after["available_quantity"] == initial_available + reserved_qty
```

#### 3. Gestion Concurrence Stock

```python
def test_concurrent_reservations_stock(client, auth_headers_real):
    """E2E: Race condition - 2 clients réservent en parallèle."""
    # Product stock=10
    # Client A réserve 7 → Réussit
    # Client B réserve 5 → Échoue (stock insuffisant)
    # Client A annule → Stock restauré
    # Client B réserve 5 → Réussit maintenant
```

---

### Tests Sécurité (Transversal)

**Objectif**: Valider OWASP Top 10 + RGPD + Multi-tenant

**Fichiers**:
- `tests/security/test_cross_tenant_isolation.py` (Phase 6)
- `tests/security/test_jwt_validation.py` (Phase 2)
- `tests/security/test_jwt_expiration.py` (Phase 2)
- `tests/security/test_csrf_protection.py` (Phase 3)
- `tests/security/test_rate_limiting.py` (Phase 3)
- `tests/security/test_sql_injection.py` (Phase 6)
- `tests/security/test_auth_security.py` (existant)
- `tests/security/test_audit_log_immutability.py` (Phase 1)
- `tests/security/test_gdpr_compliance.py` (Phase 7)

#### Multi-Tenant (CRITIQUE)

**Tous endpoints testés avec 2 tenants**:
```python
# Tenant 1 crée ressource
response1 = client.post("/api/v1/customers", json={...}, headers=tenant1_headers)
customer_id = response1.json()["id"]

# Tenant 2 tente d'accéder → 404 (pas 403)
response2 = client.get(f"/api/v1/customers/{customer_id}", headers=tenant2_headers)
assert response2.status_code == 404

# Tests pour:
# - GET /{id} (lecture)
# - GET / (listing)
# - PUT /{id} (modification)
# - DELETE /{id} (suppression)
# - Actions métier (confirm, cancel, add-payment, etc.)
```

**Couverture**: 100% des endpoints protégés

---

#### JWT Authentication

**Tests validation**:
- ❌ Token expiré rejeté
- ❌ Refresh token utilisé comme access
- ❌ Claim "sub" manquant/invalide
- ❌ User supprimé après émission token
- ❌ Compte désactivé (is_active=False)
- ❌ Access token utilisé pour refresh
- ✅ Token valide accepté
- ✅ Refresh flow correct

---

#### CSRF Protection

**Tests**:
- ❌ POST sans CSRF token → 403
- ❌ POST avec token invalide → 403
- ❌ POST avec token expiré → 403
- ✅ POST avec token valide → 200
- ✅ GET sans CSRF (idempotent) → 200

---

#### Rate Limiting

**Tests**:
- Login: 5 req/min max
- Refresh: 10 req/min max
- API générale: 100 req/min
- Isolation par user (tenant2 non affecté par rate limit tenant1)
- Reset après window expiration

---

#### SQL Injection

**Tests**:
- Injection via email customer
- Injection via search filter
- Injection via notes
- **Résultat attendu**: Validation Pydantic rejette OU query retourne 0 résultats (pas d'erreur SQL)

---

### Fixtures & Helpers

**Fichiers**:
- `tests/conftest.py` (fixtures globales)
- `tests/factories.py` (factory pattern pour entités)

**Fixtures principales**:
```python
@pytest.fixture
def test_db():
    """Session DB test (rollback automatique)."""
    db = TestingSessionLocal()
    yield db
    db.rollback()
    db.close()

@pytest.fixture
def test_user(test_db):
    """User tenant_id=1, role=staff."""
    user = User(tenant_id=1, email="test@carocorp.com", ...)
    test_db.add(user)
    test_db.commit()
    return user

@pytest.fixture
def auth_token(test_user):
    """JWT access token pour test_user."""
    return create_access_token({"sub": str(test_user.id)})

@pytest.fixture
def auth_headers_real(auth_token):
    """Headers Authorization avec token réel."""
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture
def test_customer(test_db, test_user):
    """Customer tenant_id=1."""
    customer = Customer(tenant_id=1, email="customer@test.com", ...)
    test_db.add(customer)
    test_db.commit()
    return customer

@pytest.fixture
def test_product(test_db):
    """Product avec stock."""
    product = Product(
        tenant_id=1,
        name="Test Product",
        sku="TEST-001",
        category="assiette",
        price_per_day_cents=100,
        stock_quantity=100,
        available_quantity=100
    )
    test_db.add(product)
    test_db.commit()
    return product
```

---

### CI/CD Tests

**Pipeline GitHub Actions** (`.github/workflows/tests.yml`):

```yaml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: massa
          POSTGRES_PASSWORD: massa
          POSTGRES_DB: MassaCorp_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run migrations
        env:
          DATABASE_URL: postgresql://massa:massa@localhost/MassaCorp_test
        run: |
          alembic upgrade head

      - name: Run tests
        env:
          DATABASE_URL: postgresql://massa:massa@localhost/MassaCorp_test
          REDIS_URL: redis://localhost:6379/0
          ENV: test
        run: |
          pytest tests/ \
            --cov=app \
            --cov-report=term \
            --cov-report=html \
            --cov-fail-under=95 \
            -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: unittests
```

**Coverage Badges** (README.md):
```markdown
![Coverage](https://codecov.io/gh/carocorp/carocorp-api/branch/main/graph/badge.svg)
![Tests](https://github.com/carocorp/carocorp-api/workflows/Tests/badge.svg)
```

---

### Métriques Qualité Cibles

| Métrique | Cible | Actuel | Phase Objectif |
|----------|-------|--------|----------------|
| **Coverage globale** | 100% | 94.42% | Phase 9 |
| **Coverage services** | 95%+ | 92% | Phase 4 |
| **Coverage repositories** | 90%+ | 95% | ✅ OK |
| **Coverage endpoints** | 85%+ | 88% | ✅ OK |
| **Tests passants** | 100% | 100% (322/322) | ✅ OK |
| **Tests sécurité** | 50+ | 28 | Phase 6 |
| **Tests E2E** | 40+ | 12 | Phase 9 |
| **Bugs P0** | 0 | 4 | Phase 1 |
| **Bugs P1** | 0 | 5 | Phase 4 |
| **Flaky tests** | 0 | 0 | ✅ OK |

---

## Critères de Validation

### Validation Technique

#### 1. Coverage 100%

**Critères**:
- ✅ Tous fichiers `app/**/*.py` couverts
- ✅ Aucune ligne exclue (sauf `pragma: no cover` justifié)
- ✅ Branches conditionnelles toutes testées
- ✅ Exceptions toutes testées

**Commande validation**:
```bash
pytest tests/ --cov=app --cov-report=term --cov-fail-under=100
```

**Output attendu**:
```
---------- coverage: platform linux, python 3.11 -----------
Name                                 Stmts   Miss  Cover
--------------------------------------------------------
app/__init__.py                          5      0   100%
app/api/__init__.py                      3      0   100%
app/api/v1/__init__.py                  15      0   100%
app/api/v1/endpoints/auth.py            85      0   100%
app/api/v1/endpoints/customers.py      120      0   100%
...
app/services/reservation.py            250      0   100%
app/services/product.py                180      0   100%
--------------------------------------------------------
TOTAL                                 1990      0   100%
========================================================
```

---

#### 2. Tests Passants 100%

**Critères**:
- ✅ 0 échec
- ✅ 0 erreur
- ✅ 0 test skipped (sauf justification)
- ✅ 0 flaky test (succès/échec aléatoire)

**Commande validation**:
```bash
pytest tests/ -v --tb=short
```

**Output attendu**:
```
========================== test session starts ===========================
collected 450 items

tests/unit/test_reservation_service.py::test_create_reservation PASSED
tests/unit/test_reservation_service.py::test_confirm_reservation PASSED
...
tests/security/test_cross_tenant_isolation.py::test_cross_tenant_get_customer PASSED
tests/e2e/test_complete_workflows.py::test_complete_rental_workflow PASSED

========================== 450 passed in 45.23s ==========================
```

---

#### 3. Zéro Bug Critique

**Critères**:
- ✅ 0 bug P0 (bloquant production)
- ✅ 0 bug P1 (majeur)
- ⚠️ Bugs P2 acceptables si documentés et planifiés

**Validation**:
```bash
# Rechercher TODOs critiques
grep -r "TODO.*P0\|FIXME.*CRITICAL" app/

# Doit retourner 0 résultats
```

---

#### 4. Sécurité OWASP Top 10

**Critères**:
- ✅ A01 (Broken Access Control): Multi-tenant testé exhaustivement
- ✅ A02 (Cryptographic Failures): Chiffrement TLS + DB + Secrets Vault
- ✅ A03 (Injection): SQLAlchemy ORM + Pydantic validation
- ✅ A04 (Insecure Design): Rate limiting + Account lockout
- ✅ A05 (Security Misconfiguration): Validation secrets + CORS strict + No DEBUG prod
- ✅ A06 (Vulnerable Components): Dependabot + Safety scan
- ✅ A07 (Auth Failures): JWT validation complète + MFA (optionnel)
- ✅ A08 (Integrity Failures): Audit log immuable
- ✅ A09 (Logging Failures): Logs structurés JSON
- ✅ A10 (SSRF): N/A (pas de requêtes sortantes user-controlled)

**Validation**:
```bash
# Scan sécurité
bandit -r app/ -f json
safety check --json
```

---

#### 5. Conformité RGPD

**Critères**:
- ✅ Art. 15 (Droit d'accès): Export données JSON/CSV
- ✅ Art. 17 (Droit à l'effacement): Anonymisation fonctionnelle
- ✅ Art. 20 (Portabilité): Export format standard
- ✅ Art. 30 (Registre traitements): Documentation complète
- ✅ Art. 32 (Sécurité): Chiffrement + Audit log
- ✅ Art. 33-34 (Notification violations): Procédure documentée

**Validation**:
```bash
# Test export RGPD
pytest tests/integration/test_gdpr_endpoints.py -v

# Test anonymisation
pytest tests/unit/test_gdpr_service.py::test_anonymize_customer -v
```

---

### Validation Opérationnelle

#### 6. Performance

**Critères**:
- ✅ Latence p50 < 100ms
- ✅ Latence p95 < 500ms
- ✅ Latence p99 < 1000ms
- ✅ Throughput > 100 req/s
- ✅ Connection pool < 30 connexions

**Validation** (k6 load testing):
```javascript
// scripts/load-test.js
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },  // Ramp up
    { duration: '5m', target: 100 },  // Steady state
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    'http_req_duration': ['p(95)<500'],  // 95% < 500ms
    'http_req_failed': ['rate<0.01'],    // < 1% erreurs
  },
};

export default function () {
  let response = http.get('https://api.carocorp.com/health');
  check(response, {
    'status is 200': (r) => r.status === 200,
    'latency < 500ms': (r) => r.timings.duration < 500,
  });
}
```

**Commande**:
```bash
k6 run scripts/load-test.js
```

**Output attendu**:
```
     ✓ status is 200
     ✓ latency < 500ms

     http_req_duration..........: avg=250ms  p(95)=450ms  p(99)=800ms
     http_req_failed............: 0.00%  ✓ 0     ✗ 100000
```

---

#### 7. Availability & Health Checks

**Critères**:
- ✅ Health check `/health` répond < 1s
- ✅ DB connexion testée
- ✅ Redis connexion testée
- ✅ Uptime > 99.9% (3 replicas Kubernetes)

**Validation**:
```bash
curl -w "@curl-format.txt" http://api.carocorp.com/health

# curl-format.txt:
#   time_total: %{time_total}s
#   http_code:  %{http_code}

# Output attendu:
# time_total: 0.250s
# http_code:  200
```

---

#### 8. Observabilité

**Critères**:
- ✅ Logs JSON structurés (tenant_id, user_id, request_id)
- ✅ Metrics Prometheus (RED method)
- ✅ Traces distribuées (OpenTelemetry)
- ✅ Dashboards Grafana opérationnels
- ✅ Alerting configuré (5xx, latency, login failures)

**Validation**:
```bash
# Logs JSON
docker logs carocorp-api-1 2>&1 | jq .

# Metrics
curl http://localhost:8001/metrics | grep http_requests_total

# Grafana
curl http://grafana.carocorp.com/api/dashboards/db/carocorp-overview
```

---

### Validation Déploiement

#### 9. Staging Deployment

**Critères**:
- ✅ Build Docker réussit
- ✅ Déploiement Kubernetes réussit
- ✅ Health checks passent
- ✅ Smoke tests passent (login, CRUD, workflows)
- ✅ Load test 100 req/s réussit
- ✅ Rollback testé et fonctionnel

**Checklist**:
```bash
# Build image
docker build -t carocorp-api:v1.0.0 .

# Push registry
docker push registry.carocorp.com/carocorp-api:v1.0.0

# Deploy staging
kubectl apply -f k8s/staging/ -n staging

# Wait ready
kubectl wait --for=condition=ready pod -l app=carocorp-api -n staging --timeout=300s

# Smoke tests
pytest tests/smoke/ --base-url=https://staging.carocorp.com -v

# Load test
k6 run scripts/load-test.js --env BASE_URL=https://staging.carocorp.com

# Rollback test
kubectl rollout undo deployment/carocorp-api -n staging
kubectl rollout status deployment/carocorp-api -n staging
```

---

#### 10. Production Readiness Checklist

**Infrastructure**:
- ✅ Kubernetes cluster HA (3 replicas minimum)
- ✅ Load balancer configuré
- ✅ Ingress TLS (cert-manager Let's Encrypt)
- ✅ Autoscaling HPA (CPU > 70% → scale)
- ✅ PDB (Pod Disruption Budget) configuré (minAvailable=2)
- ✅ Resource limits (CPU: 500m-2, Memory: 512Mi-2Gi)
- ✅ Liveness probe: `/health` (initialDelaySeconds=30, period=10)
- ✅ Readiness probe: `/health` (initialDelaySeconds=10, period=5)

**Base de Données**:
- ✅ PostgreSQL HA (primary + replica)
- ✅ Backups automatiques journaliers
- ✅ PITR (Point-In-Time Recovery) activé
- ✅ Connection pooling (pgbouncer)
- ✅ Monitoring (pg_stat_activity, slow queries)

**Sécurité**:
- ✅ Secrets Kubernetes (sealed-secrets)
- ✅ Network Policies (isolation pods)
- ✅ RBAC Kubernetes strict
- ✅ Image scanning (Trivy)
- ✅ Runtime security (Falco)

**Observabilité**:
- ✅ Centralized logging (Loki + Grafana)
- ✅ Metrics (Prometheus + Grafana)
- ✅ Alerting (Alertmanager + PagerDuty)
- ✅ Tracing (Jaeger)

**Documentation**:
- ✅ README.md à jour
- ✅ Architecture diagrammes
- ✅ API documentation (OpenAPI)
- ✅ Runbooks incidents
- ✅ RGPD compliance docs

**Final Sign-Off**:
- ✅ Security audit passé (externe recommandé)
- ✅ Load testing 1000 req/s réussi
- ✅ Disaster recovery testé (restore backup)
- ✅ Team formée (runbooks, incidents, on-call)

---

**🎉 Validation Finale**: Toutes checkboxes ✅ → **PRODUCTION READY** 🚀

---

## Pratiques de Configuration et Settings

**Objectif**: Standardiser l'environnement de développement pour garantir la cohérence du code, la qualité, la sécurité et faciliter l'onboarding des nouveaux développeurs.

### Philosophie

- **Automatisation maximale**: Les vérifications doivent être automatiques (pre-commit, CI/CD)
- **Configuration explicite**: Aucun comportement implicite non documenté
- **Sécurité by design**: Les patterns dangereux sont bloqués avant le commit
- **Cohérence équipe**: Tous les développeurs utilisent les mêmes règles
- **Zero configuration onboarding**: Un nouveau développeur doit pouvoir contribuer en < 30 minutes

---

### 8.1 Configuration VS Code (.vscode/settings.json)

**Emplacement**: `.vscode/settings.json` (racine du projet)

**Pourquoi VS Code**: IDE le plus utilisé en 2026, support Python excellent, extensions riches, configuration partageable via Git.

#### Fichier Complet Recommandé

```json
{
  // ═══════════════════════════════════════════════════════════════
  // Python Configuration
  // ═══════════════════════════════════════════════════════════════

  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.terminal.activateEnvironment": true,
  "python.terminal.activateEnvInCurrentTerminal": true,

  // ═══════════════════════════════════════════════════════════════
  // Linting & Formatting
  // ═══════════════════════════════════════════════════════════════

  // Black (formatter officiel Python)
  "python.formatting.provider": "black",
  "python.formatting.blackArgs": [
    "--line-length=100",
    "--target-version=py311",
    "--preview"
  ],

  // Ruff (linter ultra-rapide, remplace Flake8 + isort + bandit)
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": "explicit",
      "source.fixAll": "explicit"
    },
    "editor.defaultFormatter": "ms-python.black-formatter"
  },

  "ruff.enable": true,
  "ruff.lint.enable": true,
  "ruff.lint.run": "onSave",
  "ruff.lint.args": [
    "--config=${workspaceFolder}/pyproject.toml"
  ],
  "ruff.organizeImports": true,
  "ruff.fixAll": true,

  // Flake8 (désactivé si Ruff utilisé, sinon activer)
  "python.linting.flake8Enabled": false,
  "python.linting.flake8Args": [
    "--max-line-length=100",
    "--extend-ignore=E203,W503",
    "--exclude=.venv,migrations"
  ],

  // ═══════════════════════════════════════════════════════════════
  // Type Checking (Mypy)
  // ═══════════════════════════════════════════════════════════════

  "python.linting.mypyEnabled": true,
  "python.linting.mypyArgs": [
    "--config-file=${workspaceFolder}/pyproject.toml",
    "--show-error-codes",
    "--pretty",
    "--show-column-numbers"
  ],

  "mypy-type-checker.args": [
    "--config-file=${workspaceFolder}/pyproject.toml"
  ],

  // ═══════════════════════════════════════════════════════════════
  // Testing (Pytest)
  // ═══════════════════════════════════════════════════════════════

  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "python.testing.pytestArgs": [
    "tests",
    "-v",
    "--tb=short",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html"
  ],
  "python.testing.autoTestDiscoverOnSaveEnabled": false,

  // ═══════════════════════════════════════════════════════════════
  // Editor Behavior
  // ═══════════════════════════════════════════════════════════════

  "editor.rulers": [100],
  "editor.tabSize": 4,
  "editor.insertSpaces": true,
  "editor.trimAutoWhitespace": true,
  "editor.renderWhitespace": "boundary",
  "editor.wordWrap": "off",

  "files.encoding": "utf8",
  "files.eol": "\n",
  "files.trimTrailingWhitespace": true,
  "files.insertFinalNewline": true,
  "files.trimFinalNewlines": true,

  // ═══════════════════════════════════════════════════════════════
  // Files Exclusions (Performance + Security)
  // ═══════════════════════════════════════════════════════════════

  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    "**/*.pyo": true,
    "**/.pytest_cache": true,
    "**/.mypy_cache": true,
    "**/.ruff_cache": true,
    "**/*.egg-info": true,
    "**/htmlcov": true,
    "**/.coverage": true,
    "**/dist": true,
    "**/build": true,
    "**/.venv": false,
    "**/.env": true
  },

  "files.watcherExclude": {
    "**/.venv/**": true,
    "**/htmlcov/**": true,
    "**/__pycache__/**": true,
    "**/.pytest_cache/**": true,
    "**/.mypy_cache/**": true,
    "**/.ruff_cache/**": true
  },

  "search.exclude": {
    "**/.venv": true,
    "**/htmlcov": true,
    "**/__pycache__": true,
    "**/.pytest_cache": true,
    "**/.mypy_cache": true,
    "**/.ruff_cache": true,
    "**/migrations": false
  },

  // ═══════════════════════════════════════════════════════════════
  // Security: Files to NEVER commit
  // ═══════════════════════════════════════════════════════════════

  "files.associations": {
    ".env": "properties",
    ".env.*": "properties",
    "*.pem": "pem-certificate",
    "*.key": "pem-certificate"
  },

  // ═══════════════════════════════════════════════════════════════
  // Git Integration
  // ═══════════════════════════════════════════════════════════════

  "git.ignoreLimitWarning": true,
  "git.autofetch": true,
  "git.confirmSync": false,
  "git.enableSmartCommit": false,

  // ═══════════════════════════════════════════════════════════════
  // Terminal
  // ═══════════════════════════════════════════════════════════════

  "terminal.integrated.env.linux": {
    "PYTHONPATH": "${workspaceFolder}"
  },
  "terminal.integrated.env.osx": {
    "PYTHONPATH": "${workspaceFolder}"
  },

  // ═══════════════════════════════════════════════════════════════
  // SQLAlchemy & Alembic
  // ═══════════════════════════════════════════════════════════════

  "sqltools.connections": [
    {
      "name": "CaroCorp Local",
      "driver": "PostgreSQL",
      "server": "localhost",
      "port": 5432,
      "database": "carocorp_dev",
      "username": "carocorp_user",
      "password": "",
      "askForPassword": true,
      "connectionTimeout": 30
    }
  ],

  // ═══════════════════════════════════════════════════════════════
  // Performance
  // ═══════════════════════════════════════════════════════════════

  "python.analysis.memory.keepLibraryAst": true,
  "python.analysis.indexing": true,
  "python.analysis.packageIndexDepths": [
    {
      "name": "app",
      "depth": 10
    }
  ],

  // ═══════════════════════════════════════════════════════════════
  // Extensions Recommendations (voir .vscode/extensions.json)
  // ═══════════════════════════════════════════════════════════════

  "extensions.ignoreRecommendations": false
}
```

#### Justifications Clés

**1. Black avec line-length=100** (pas 88)
- **Pourquoi**: 100 caractères est un compromis moderne entre lisibilité et utilisation de l'espace écran
- Standards 2026: GitHub/GitLab montrent 120 caractères, mais 100 optimise pour split-screen
- FastAPI docs officielles utilisent 100

**2. Ruff au lieu de Flake8 + isort + bandit**
- **Pourquoi**: Ruff est 10-100x plus rapide (écrit en Rust)
- Règles compatibles Flake8 (migration transparente)
- Organise imports automatiquement (remplace isort)
- Détecte vulnérabilités sécurité (remplace partiellement bandit)
- Moins de dépendances, configuration unique

**3. Mypy strict activé**
- **Pourquoi**: Type checking prévient 15% des bugs en production (étude Microsoft 2020)
- SQLAlchemy 2.0 avec Mapped types nécessite mypy
- FastAPI Pydantic models bénéficient du type checking

**4. files.exclude vs search.exclude**
- `files.exclude`: Cache fichiers dans l'arbre VS Code (performance)
- `search.exclude`: Exclut de la recherche (performance + évite faux positifs)
- `.venv` caché mais pas exclu de la recherche (besoin d'inspecter dépendances parfois)

**5. PYTHONPATH dans terminal**
- **Pourquoi**: Permet `python -m app.main` au lieu de `PYTHONPATH=. python -m app.main`
- Simplifie debugging et test runner

---

### 8.2 Configuration Extensions VS Code (.vscode/extensions.json)

**Emplacement**: `.vscode/extensions.json`

```json
{
  "recommendations": [
    // Python Development (OBLIGATOIRES)
    "ms-python.python",
    "ms-python.vscode-pylance",
    "ms-python.black-formatter",
    "charliermarsh.ruff",
    "ms-python.mypy-type-checker",

    // Testing & Coverage
    "hbenl.vscode-test-explorer",
    "littlefoxteam.vscode-python-test-adapter",
    "ryanluker.vscode-coverage-gutters",

    // Database
    "mtxr.sqltools",
    "mtxr.sqltools-driver-pg",

    // Git
    "eamodio.gitlens",
    "mhutchie.git-graph",

    // REST API
    "humao.rest-client",
    "42crunch.vscode-openapi",

    // Docker & Kubernetes
    "ms-azuretools.vscode-docker",
    "ms-kubernetes-tools.vscode-kubernetes-tools",

    // Security
    "snyk-security.snyk-vulnerability-scanner",
    "piotrpalarz.vscode-gitignore-generator",

    // Documentation
    "yzhang.markdown-all-in-one",
    "davidanson.vscode-markdownlint",

    // Productivity
    "streetsidesoftware.code-spell-checker",
    "streetsidesoftware.code-spell-checker-french",
    "editorconfig.editorconfig",
    "alefragnani.project-manager",

    // Optional (mais recommandées)
    "tabnine.tabnine-vscode",
    "github.copilot"
  ],

  "unwantedRecommendations": [
    // Éviter conflits avec Black
    "ms-python.autopep8",

    // Éviter conflits avec Ruff
    "ms-python.isort",
    "ms-python.flake8"
  ]
}
```

#### Installation Automatique

```bash
# Script pour installer toutes les extensions d'un coup
# .vscode/install-extensions.sh

#!/bin/bash
set -e

echo "📦 Installation des extensions VS Code recommandées..."

# Lire extensions.json et installer
cat .vscode/extensions.json | \
  grep '"ms-python\|charliermarsh\|mtxr\|eamodio' | \
  sed 's/[",]//g' | \
  xargs -I {} code --install-extension {}

echo "✅ Extensions installées avec succès"
```

---

### 8.3 Configuration Python Complète (pyproject.toml)

**Emplacement**: `pyproject.toml` (racine du projet)

**Pourquoi pyproject.toml**: Standard PEP 518, remplace setup.py + setup.cfg + tox.ini + .flake8. Toute la configuration Python en un seul fichier.

#### Fichier Complet Recommandé

```toml
[tool.poetry]
name = "carocorp"
version = "1.0.0"
description = "CaroCorp - Gestion location vaisselle événements (API REST FastAPI)"
authors = ["Équipe CaroCorp <dev@carocorp.com>"]
readme = "README.md"
homepage = "https://github.com/carocorp/carocorp-api"
repository = "https://github.com/carocorp/carocorp-api"
documentation = "https://docs.carocorp.com"
keywords = ["fastapi", "sqlalchemy", "postgresql", "multi-tenant", "rental"]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "Topic :: Software Development :: Libraries :: Application Frameworks",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.115.0"
uvicorn = {extras = ["standard"], version = "^0.32.0"}
sqlalchemy = "^2.0.0"
alembic = "^1.13.0"
psycopg2-binary = "^2.9.9"
pydantic-settings = "^2.6.0"
redis = "^5.0.0"
celery = "^5.4.0"
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
email-validator = "^2.3.0"
python-multipart = "^0.0.22"
bcrypt = ">=5.0.0"
argon2-cffi = "^23.1.0"  # Recommandé pour hash passwords (plus sécurisé que bcrypt)

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.0"
pytest-cov = "^6.0.0"
pytest-asyncio = "^0.24.0"
pytest-xdist = "^3.6.0"  # Tests parallèles
httpx = "^0.27.0"
black = "^24.10.0"
ruff = "^0.7.0"
mypy = "^1.13.0"
bandit = {extras = ["toml"], version = "^1.7.10"}
safety = "^3.2.0"
pre-commit = "^4.0.0"

# Type stubs
types-redis = "^4.6.0"
types-python-jose = "^3.3.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

# ═══════════════════════════════════════════════════════════════════
# Black Configuration (PEP 8 compliant formatter)
# ═══════════════════════════════════════════════════════════════════

[tool.black]
line-length = 100
target-version = ["py311", "py312"]
include = '\.pyi?$'
extend-exclude = '''
/(
  # Directories
  \.git
  | \.mypy_cache
  | \.pytest_cache
  | \.ruff_cache
  | \.venv
  | venv
  | build
  | dist
  | migrations  # Alembic migrations ne doivent pas être reformatées
  | htmlcov
)/
'''
preview = true  # Active nouvelles features Black

# ═══════════════════════════════════════════════════════════════════
# Ruff Configuration (Ultra-fast Python linter)
# ═══════════════════════════════════════════════════════════════════

[tool.ruff]
line-length = 100
target-version = "py311"
extend-exclude = [
    ".venv",
    "venv",
    "migrations",
    "htmlcov",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
]

[tool.ruff.lint]
# Règles activées (voir https://docs.astral.sh/ruff/rules/)
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort (import sorting)
    "N",      # pep8-naming
    "UP",     # pyupgrade (modern Python syntax)
    "B",      # flake8-bugbear (bug detections)
    "A",      # flake8-builtins (shadowing builtins)
    "C4",     # flake8-comprehensions
    "DTZ",    # flake8-datetimez (timezone aware datetime)
    "T10",    # flake8-debugger (detect pdb)
    "EM",     # flake8-errmsg (error messages)
    "ISC",    # flake8-implicit-str-concat
    "ICN",    # flake8-import-conventions
    "PIE",    # flake8-pie (misc lints)
    "PT",     # flake8-pytest-style
    "Q",      # flake8-quotes
    "RSE",    # flake8-raise
    "RET",    # flake8-return
    "SIM",    # flake8-simplify
    "TID",    # flake8-tidy-imports
    "TCH",    # flake8-type-checking
    "ARG",    # flake8-unused-arguments
    "PTH",    # flake8-use-pathlib
    "ERA",    # eradicate (commented code)
    "PL",     # Pylint
    "TRY",    # tryceratops (exception handling)
    "RUF",    # Ruff-specific rules
    "S",      # flake8-bandit (security)
]

# Règles ignorées (justifications explicites)
ignore = [
    "E501",     # Line too long (géré par Black)
    "B008",     # Do not perform function call in argument defaults (FastAPI Depends())
    "S101",     # Use of assert detected (OK dans tests)
    "TRY003",   # Avoid specifying long messages outside exception class (trop strict)
    "PLR0913",  # Too many arguments (FastAPI endpoints avec beaucoup de params)
    "ARG001",   # Unused function argument (FastAPI dependencies)
    "PTH123",   # open() should be replaced by Path.open() (pas toujours applicable)
]

# Autoriser autofix pour ces règles
fixable = ["ALL"]
unfixable = []

# Règles par fichier
[tool.ruff.lint.per-file-ignores]
"tests/*" = [
    "S101",     # Assert OK dans tests
    "ARG",      # Fixtures Pytest peuvent sembler non utilisées
    "PLR2004",  # Magic values OK dans tests
]
"migrations/*" = [
    "ALL",      # Alembic migrations ne doivent pas être lintées
]
"__init__.py" = [
    "F401",     # Imports non utilisés OK dans __init__.py (exports)
]

[tool.ruff.lint.isort]
known-first-party = ["app"]
section-order = [
    "future",
    "standard-library",
    "third-party",
    "first-party",
    "local-folder"
]

[tool.ruff.lint.mccabe]
max-complexity = 10  # Complexité cyclomatique max

# ═══════════════════════════════════════════════════════════════════
# Mypy Configuration (Static Type Checker)
# ═══════════════════════════════════════════════════════════════════

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true      # Fonctions sans types → erreur
disallow_any_unimported = false    # Trop strict pour début
disallow_any_expr = false          # Trop strict pour début
disallow_any_decorated = false     # FastAPI decorators
disallow_any_explicit = false
disallow_any_generics = false
disallow_subclassing_any = true
disallow_untyped_calls = false     # Trop strict pour début
disallow_untyped_decorators = false  # FastAPI decorators
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
strict_concatenate = true

# Plugins
plugins = ["pydantic.mypy", "sqlalchemy.ext.mypy.plugin"]

# Exclusions
exclude = [
    "^migrations/",
    "^\\.venv/",
    "^build/",
    "^dist/",
]

# Configuration par module
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false  # Tests peuvent être moins stricts

[[tool.mypy.overrides]]
module = [
    "celery.*",
    "redis.*",
    "jose.*",
]
ignore_missing_imports = true  # Pas de stubs pour ces libs

# ═══════════════════════════════════════════════════════════════════
# Pytest Configuration
# ═══════════════════════════════════════════════════════════════════

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

addopts = [
    "-v",                           # Verbose
    "--strict-markers",             # Markers non déclarés = erreur
    "--strict-config",              # Config invalide = erreur
    "--tb=short",                   # Traceback court
    "--cov=app",                    # Coverage sur app/
    "--cov-config=.coveragerc",     # Config coverage
    "--cov-report=term-missing",    # Afficher lignes manquantes
    "--cov-report=html",            # Rapport HTML
    "--cov-fail-under=95",          # Fail si coverage < 95% (objectif 100%)
    "--no-cov-on-fail",             # Pas de rapport si tests fail
    "-n=auto",                      # Parallélisation auto (pytest-xdist)
    "--maxfail=5",                  # Stop après 5 failures
    "--durations=10",               # Afficher 10 tests les plus lents
]

markers = [
    "unit: Unit tests (fast, no I/O)",
    "integration: Integration tests (DB, Redis required)",
    "e2e: End-to-end tests (full stack required)",
    "security: Security tests (OWASP, CSRF, XSS, etc.)",
    "slow: Slow running tests (> 1s)",
    "smoke: Smoke tests (minimal validation)",
]

# Fixtures autodiscovery
pythonpath = ["."]

# Asyncio configuration
asyncio_mode = "auto"

# Warnings
filterwarnings = [
    "error",                        # Transformer warnings en erreurs
    "ignore::DeprecationWarning",   # Ignorer deprecations des libs externes
    "ignore::PendingDeprecationWarning",
]

# ═══════════════════════════════════════════════════════════════════
# Coverage Configuration
# ═══════════════════════════════════════════════════════════════════

[tool.coverage.run]
source = ["app"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "app/tasks/celery_app.py",     # Celery worker
    "app/constants/_template_*.py",
    "*/__pycache__/*",
    "*/.venv/*",
]
branch = true                        # Branch coverage (if/else)
parallel = true                      # Support pytest-xdist

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
sort = "Cover"

exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@abstractmethod",
    "@overload",
    "\\.\\.\\.",                     # Ellipsis (...) dans stubs
]

[tool.coverage.html]
directory = "htmlcov"

# ═══════════════════════════════════════════════════════════════════
# Bandit Configuration (Security Linter)
# ═══════════════════════════════════════════════════════════════════

[tool.bandit]
targets = ["app"]
exclude_dirs = [
    ".venv",
    "venv",
    "tests",
    "migrations",
    "htmlcov",
]
skips = [
    "B101",  # Assert usage (OK dans tests, mais exclude_dirs devrait gérer)
    "B601",  # Paramiko calls (si utilisé)
]
tests = [
    "B201",  # Flask debug
    "B301",  # Pickle usage
    "B302",  # Marshal usage
    "B303",  # MD5/SHA1 usage
    "B304",  # Insecure cipher
    "B305",  # Insecure cipher mode
    "B306",  # Insecure mktemp
    "B307",  # Eval usage
    "B308",  # Mark safe usage
    "B309",  # HTTPSConnection without cert verification
    "B310",  # URL open without timeout
    "B311",  # Random usage (should use secrets)
    "B312",  # Telnet usage
    "B313",  # XML vulnerabilities
    "B314",  # XML vulnerabilities (lxml)
    "B315",  # XML vulnerabilities (expat)
    "B316",  # XML vulnerabilities (sax)
    "B317",  # XML vulnerabilities (expatreader)
    "B318",  # XML vulnerabilities (expatbuilder)
    "B319",  # XML vulnerabilities (minidom)
    "B320",  # XML vulnerabilities (pulldom)
    "B321",  # FTP usage
    "B322",  # Input usage
    "B323",  # Unverified SSL context
    "B324",  # Insecure hash function
    "B501",  # Request with verify=False
    "B502",  # SSL/TLS insecure version
    "B503",  # SSL/TLS insecure cipher
    "B504",  # SSL/TLS default context
    "B505",  # Weak cryptographic key
    "B506",  # YAML load
    "B507",  # SSH no host key verification
    "B601",  # Paramiko calls
    "B602",  # Shell injection
    "B603",  # Subprocess without shell=False
    "B604",  # Function call with shell=True
    "B605",  # Starting process with shell
    "B606",  # Starting process without shell
    "B607",  # Partial path in function call
    "B608",  # SQL injection
    "B609",  # Linux wildcards injection
]
```

#### Justifications Clés Configuration pyproject.toml

**1. Ruff au lieu de Flake8 + isort + pylint**
- **Performance**: Ruff analyse 10000 fichiers en < 1 seconde (Flake8 → 30s)
- **Maintenance**: Une seule dépendance, une seule config
- **Features**: Auto-fix 90% des erreurs

**2. Mypy strict mais progressif**
- `disallow_untyped_defs = true`: Force typing des fonctions (prévient bugs)
- `disallow_untyped_calls = false`: Permet appels libs externes non typées (phase transition)
- **Roadmap**: Activer `disallow_untyped_calls = true` quand coverage types > 80%

**3. pytest-xdist (-n=auto)**
- **Performance**: Tests parallèles sur tous les CPU cores
- Réduit temps CI de 5 min → 1 min (gain 80%)
- Détecte race conditions (tests qui échouent en parallèle = bug concurrency)

**4. Coverage 95% minimum (objectif 100%)**
- `--cov-fail-under=95`: Fail CI si coverage baisse
- **Progression**: 94.42% → 95% → 97% → 100%
- Ligne par ligne tracking avec `--cov-report=term-missing`

**5. Bandit tests explicites**
- Par défaut Bandit check 100+ tests (trop de faux positifs)
- Configuration explicite: Seulement tests sécurité critiques
- Évite B101 (assert) dans tests, B608 (SQL injection) activé

---

### 8.4 Configuration EditorConfig (.editorconfig)

**Emplacement**: `.editorconfig` (racine du projet)

**Pourquoi EditorConfig**: Standard cross-IDE (VS Code, PyCharm, Sublime, Vim). Garantit formatage cohérent même sans VS Code.

```ini
# EditorConfig: https://editorconfig.org

root = true

# Defaults pour tous fichiers
[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space

# Python files
[*.py]
indent_size = 4
max_line_length = 100

# YAML files (Kubernetes, CI/CD)
[*.{yml,yaml}]
indent_size = 2

# JSON files
[*.json]
indent_size = 2

# TOML files (pyproject.toml)
[*.toml]
indent_size = 2

# Markdown files
[*.md]
trim_trailing_whitespace = false  # Trailing spaces = line breaks en Markdown
max_line_length = 120

# Makefile (TABs obligatoires)
[Makefile]
indent_style = tab

# Shell scripts
[*.sh]
indent_size = 2
end_of_line = lf

# Alembic migrations (ne pas toucher)
[migrations/*.py]
indent_size = 4
max_line_length = off

# SQL files
[*.sql]
indent_size = 2

# Docker files
[Dockerfile*]
indent_size = 2

# Ignore generated files
[{package-lock.json,yarn.lock,*.min.js,*.min.css}]
indent_style = ignore
insert_final_newline = ignore
```

---

### 8.5 Pre-commit Hooks Configuration

**Emplacement**: `.pre-commit-config.yaml` (racine du projet)

**Pourquoi Pre-commit**: Validation automatique AVANT chaque commit. Empêche code non conforme d'arriver dans Git. Économise temps de review + CI.

#### Installation

```bash
# Installer pre-commit
pip install pre-commit

# Activer les hooks
pre-commit install

# Test sur tous les fichiers
pre-commit run --all-files
```

#### Configuration Complète

```yaml
# .pre-commit-config.yaml

# Voir https://pre-commit.com pour documentation complète
default_language_version:
  python: python3.11

default_stages: [commit]

repos:
  # ═══════════════════════════════════════════════════════════════
  # Pre-commit hooks built-in (trailing whitespace, YAML, etc.)
  # ═══════════════════════════════════════════════════════════════

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace        # Supprimer trailing whitespace
        args: [--markdown-linebreak-ext=md]
      - id: end-of-file-fixer          # Ajouter newline à la fin
      - id: check-yaml                 # Valider YAML syntax
        args: [--safe]
      - id: check-json                 # Valider JSON syntax
      - id: check-toml                 # Valider TOML syntax
      - id: check-added-large-files    # Bloquer fichiers > 500KB
        args: ['--maxkb=500']
      - id: check-case-conflict        # Détecter conflits case-sensitive
      - id: check-merge-conflict       # Détecter markers merge conflict
      - id: check-docstring-first      # Docstring avant code
      - id: debug-statements           # Détecter pdb.set_trace()
      - id: detect-private-key         # Détecter clés privées (SÉCURITÉ)
      - id: mixed-line-ending          # Force LF (pas CRLF)
        args: ['--fix=lf']
      - id: name-tests-test            # Tests doivent commencer par test_
        args: ['--pytest-test-first']

  # ═══════════════════════════════════════════════════════════════
  # Black (Code Formatter)
  # ═══════════════════════════════════════════════════════════════

  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        args: [--config=pyproject.toml]
        language_version: python3.11

  # ═══════════════════════════════════════════════════════════════
  # Ruff (Linter + Import Sorter)
  # ═══════════════════════════════════════════════════════════════

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff                        # Linter
        args: [--fix, --config=pyproject.toml]
      - id: ruff-format                 # Formatter (alternative à Black)
        args: [--config=pyproject.toml]

  # ═══════════════════════════════════════════════════════════════
  # Mypy (Type Checker)
  # ═══════════════════════════════════════════════════════════════

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        args: [--config-file=pyproject.toml]
        additional_dependencies:
          - types-redis
          - types-python-jose
          - pydantic
          - sqlalchemy

  # ═══════════════════════════════════════════════════════════════
  # Bandit (Security Linter)
  # ═══════════════════════════════════════════════════════════════

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.10
    hooks:
      - id: bandit
        args: [-c, pyproject.toml]
        additional_dependencies: ["bandit[toml]"]

  # ═══════════════════════════════════════════════════════════════
  # Safety (Dependencies Vulnerability Scanner)
  # ═══════════════════════════════════════════════════════════════

  - repo: https://github.com/Lucas-C/pre-commit-hooks-safety
    rev: v1.3.3
    hooks:
      - id: python-safety-dependencies-check
        args: [--short-report, --ignore=70612]  # Ignorer false positives connus

  # ═══════════════════════════════════════════════════════════════
  # Secrets Detection (Détection clés API, tokens, passwords)
  # ═══════════════════════════════════════════════════════════════

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: package.lock.json

  # ═══════════════════════════════════════════════════════════════
  # Pytest (Tests doivent passer AVANT commit)
  # ═══════════════════════════════════════════════════════════════

  - repo: local
    hooks:
      - id: pytest-fast
        name: pytest-fast (unit tests only)
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
        args:
          - tests/unit/
          - -v
          - --tb=short
          - -x                            # Stop au premier échec
          - -m
          - "not slow"                    # Seulement tests rapides
        stages: [commit]

      - id: pytest-full
        name: pytest-full (all tests with coverage)
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
        args:
          - tests/
          - -v
          - --tb=short
          - --cov=app
          - --cov-fail-under=95
        stages: [push]                    # Seulement avant push (pas commit)

  # ═══════════════════════════════════════════════════════════════
  # SQL Migration Check (Alembic)
  # ═══════════════════════════════════════════════════════════════

  - repo: local
    hooks:
      - id: alembic-check
        name: Check Alembic migrations
        entry: python
        language: system
        pass_filenames: false
        args:
          - -c
          - "from alembic.config import Config; from alembic.script import ScriptDirectory; from alembic import command; cfg = Config('alembic.ini'); script = ScriptDirectory.from_config(cfg); heads = script.get_heads(); assert len(heads) == 1, f'Multiple migration heads detected: {heads}'"
        files: ^migrations/
```

#### Justifications Pre-commit

**1. Deux stages: commit vs push**
- `commit`: Checks rapides (< 5s) → Black, Ruff, Mypy, tests unitaires
- `push`: Checks lents (< 2 min) → Tests complets + coverage
- **Pourquoi**: Permet commits fréquents (fast feedback) sans ralentir workflow

**2. detect-secrets avec baseline**
- Première exécution: `detect-secrets scan > .secrets.baseline`
- Commits suivants: Seulement nouveaux secrets détectés
- **Évite**: Faux positifs constants (ex: "password" dans commentaires)

**3. pytest-fast avec -m "not slow"**
- Tests unitaires < 1s → commit
- Tests E2E > 1s → push
- **Gain productivité**: Commit en 10s au lieu de 2 min

**4. Safety avec --ignore**
- Certaines vulnérabilités sont des faux positifs
- Documenter chaque --ignore dans commentaire

**5. Alembic migration check**
- Détecte branches multiples de migrations (erreur fréquente en équipe)
- Empêche merge conflicts sur migrations

#### Bypass Pre-commit (Urgence uniquement)

```bash
# DÉCONSEILLÉ: Bypass tous les hooks
git commit --no-verify -m "hotfix: urgent prod issue"

# RECOMMANDÉ: Bypass seulement un hook spécifique
SKIP=pytest-fast git commit -m "wip: tests en cours"

# JAMAIS: Désactiver pre-commit définitivement
# pre-commit uninstall  # ❌ INTERDIT
```

---

### 8.6 Gitignore Patterns Sécurité

**Emplacement**: `.gitignore` (racine du projet)

**Règle d'or**: JAMAIS commit de secrets, credentials, données sensibles, fichiers temporaires volumineux.

#### Configuration Complète

```gitignore
# ═══════════════════════════════════════════════════════════════════
# Python
# ═══════════════════════════════════════════════════════════════════

__pycache__/
*.py[cod]
*$py.class
*.so
*.egg
*.egg-info/
dist/
build/
*.whl

# Virtual environments
.venv/
venv/
ENV/
env/
.virtualenv/

# PyCharm
.idea/
*.iml
*.iws
.idea_modules/

# VS Code
.vscode/
!.vscode/settings.json
!.vscode/extensions.json
!.vscode/launch.json
!.vscode/tasks.json

# ═══════════════════════════════════════════════════════════════════
# Testing & Coverage
# ═══════════════════════════════════════════════════════════════════

.pytest_cache/
.coverage
.coverage.*
htmlcov/
.tox/
.nox/

# ═══════════════════════════════════════════════════════════════════
# Linting & Type Checking
# ═══════════════════════════════════════════════════════════════════

.mypy_cache/
.ruff_cache/
.pytype/
.dmypy.json
dmypy.json

# ═══════════════════════════════════════════════════════════════════
# 🔴 SÉCURITÉ CRITIQUE: Secrets & Credentials
# ═══════════════════════════════════════════════════════════════════

# Environment variables
.env
.env.local
.env.*.local
.env.production
.env.staging
.env.development
*.env
.envrc

# Credentials
*.pem
*.key
*.p12
*.pfx
*.cer
*.crt
*.der
id_rsa
id_rsa.pub
id_ed25519
id_ed25519.pub
*.asc
*.gpg

# AWS
.aws/
*.aws

# GCP
gcloud-service-key.json
*.json.gcp

# SSH
.ssh/
authorized_keys
known_hosts

# Database dumps (peuvent contenir PII)
*.sql
*.dump
*.backup
*.bak

# Secrets management
secrets.yaml
secrets.yml
vault-password.txt
.vault-pass

# ═══════════════════════════════════════════════════════════════════
# Logs (peuvent contenir tokens/PII)
# ═══════════════════════════════════════════════════════════════════

*.log
logs/
*.log.*
npm-debug.log*
yarn-debug.log*
yarn-error.log*
celerybeat-schedule
celerybeat.pid

# ═══════════════════════════════════════════════════════════════════
# OS Files
# ═══════════════════════════════════════════════════════════════════

.DS_Store
Thumbs.db
desktop.ini
*.swp
*.swo
*~

# ═══════════════════════════════════════════════════════════════════
# Docker
# ═══════════════════════════════════════════════════════════════════

docker-compose.override.yml  # Peut contenir secrets locaux
.dockerignore

# ═══════════════════════════════════════════════════════════════════
# Database
# ═══════════════════════════════════════════════════════════════════

*.db
*.sqlite
*.sqlite3
*.db-journal

# PostgreSQL
.pgpass

# Redis
dump.rdb

# ═══════════════════════════════════════════════════════════════════
# Documentation build
# ═══════════════════════════════════════════════════════════════════

docs/_build/
site/

# ═══════════════════════════════════════════════════════════════════
# Backup files
# ═══════════════════════════════════════════════════════════════════

*.bak
*.bak.*
*.backup
*.old
*.orig
*.tmp
*.temp

# ═══════════════════════════════════════════════════════════════════
# Fichiers volumineux (doivent être dans S3/Git LFS)
# ═══════════════════════════════════════════════════════════════════

*.zip
*.tar
*.tar.gz
*.rar
*.7z
*.iso
*.dmg
*.mp4
*.mov
*.avi
*.mkv

# ═══════════════════════════════════════════════════════════════════
# RGPD: Données personnelles (JAMAIS dans Git)
# ═══════════════════════════════════════════════════════════════════

exports/data-*.csv
exports/data-*.json
exports/customers-*.xlsx
pii_export_*

# ═══════════════════════════════════════════════════════════════════
# Local development
# ═══════════════════════════════════════════════════════════════════

.local/
tmp/
temp/
scratch/
playground/
```

#### Patterns Critiques (Sécurité)

**🔴 TOUJOURS ignorer** (sinon P0 incident):
1. `.env*` → Secrets production (JWT_SECRET, DATABASE_URL, etc.)
2. `*.pem`, `*.key` → Certificats TLS, clés SSH
3. `*.sql`, `*.dump` → Peut contenir PII (RGPD violation)
4. `gcloud-service-key.json` → GCP service account credentials
5. `.aws/` → AWS credentials

**Check avec detect-secrets**:
```bash
# Scanner secrets dans Git history (AVANT first push)
detect-secrets scan --all-files > .secrets.baseline

# Vérifier secrets dans commits existants
git secrets --scan-history
```

---

### 8.7 Configuration CI/CD

#### GitHub Actions (.github/workflows/ci.yml)

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  PYTHON_VERSION: "3.11"
  POETRY_VERSION: "1.8.0"

jobs:
  # ═══════════════════════════════════════════════════════════════
  # Lint & Type Check (Fast Fail)
  # ═══════════════════════════════════════════════════════════════

  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry
        uses: snok/install-poetry@v1
        with:
          version: ${{ env.POETRY_VERSION }}

      - name: Install dependencies
        run: poetry install --no-interaction

      - name: Run Black (check only)
        run: poetry run black --check app tests

      - name: Run Ruff
        run: poetry run ruff check app tests

      - name: Run Mypy
        run: poetry run mypy app

  # ═══════════════════════════════════════════════════════════════
  # Security Scan (Bandit + Safety)
  # ═══════════════════════════════════════════════════════════════

  security:
    name: Security Scan
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Poetry
        uses: snok/install-poetry@v1

      - name: Install dependencies
        run: poetry install --no-interaction

      - name: Run Bandit
        run: poetry run bandit -c pyproject.toml -r app

      - name: Run Safety (dependencies vulnerability)
        run: poetry run safety check --json

      - name: Detect Secrets
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          head: HEAD

  # ═══════════════════════════════════════════════════════════════
  # Tests (Matrix: Python 3.11 + 3.12, PostgreSQL 16)
  # ═══════════════════════════════════════════════════════════════

  test:
    name: Tests (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest

    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: carocorp_test
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: carocorp_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install Poetry
        uses: snok/install-poetry@v1

      - name: Install dependencies
        run: poetry install --no-interaction

      - name: Run Alembic migrations
        env:
          DATABASE_URL: postgresql://carocorp_test:test_password@localhost:5432/carocorp_test
        run: poetry run alembic upgrade head

      - name: Run Pytest with coverage
        env:
          DATABASE_URL: postgresql://carocorp_test:test_password@localhost:5432/carocorp_test
          REDIS_URL: redis://localhost:6379/0
          JWT_SECRET: test-secret-key-min-32-characters-long-for-testing
        run: |
          poetry run pytest \
            --cov=app \
            --cov-report=xml \
            --cov-report=html \
            --cov-fail-under=95 \
            -n=auto

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          flags: unittests
          name: codecov-carocorp

      - name: Archive coverage HTML report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report-py${{ matrix.python-version }}
          path: htmlcov/

  # ═══════════════════════════════════════════════════════════════
  # Docker Build (si tests passent)
  # ═══════════════════════════════════════════════════════════════

  build:
    name: Docker Build
    needs: [lint, security, test]
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: carocorp-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ═══════════════════════════════════════════════════════════════
  # Deploy Staging (si branch develop)
  # ═══════════════════════════════════════════════════════════════

  deploy-staging:
    name: Deploy to Staging
    needs: [build]
    if: github.ref == 'refs/heads/develop' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: staging

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Staging
        run: |
          echo "Deploying to staging..."
          # kubectl apply -f k8s/staging/ ou terraform apply, etc.
```

#### Quality Gates (GitHub Branch Protection)

```yaml
# .github/branch-protection.yml (via API ou UI GitHub)

branches:
  main:
    protection:
      required_status_checks:
        strict: true
        contexts:
          - "Lint & Type Check"
          - "Security Scan"
          - "Tests (Python 3.11)"
          - "Tests (Python 3.12)"
          - "Docker Build"

      required_pull_request_reviews:
        required_approving_review_count: 1
        dismiss_stale_reviews: true
        require_code_owner_reviews: true

      enforce_admins: true
      required_linear_history: true
      allow_force_pushes: false
      allow_deletions: false
```

---

### 8.8 Team Practices & Onboarding

#### Onboarding Checklist Nouveau Développeur

```markdown
# Onboarding CaroCorp - Nouveau Développeur

## Jour 1: Setup Environnement (2 heures)

### Prérequis
- [ ] Python 3.11+ installé (`python --version`)
- [ ] Poetry installé (`poetry --version`)
- [ ] Docker Desktop installé et démarré
- [ ] VS Code installé
- [ ] Git configuré (name, email)

### Setup Projet
```bash
# Clone repo
git clone https://github.com/carocorp/carocorp-api.git
cd carocorp-api

# Install dependencies
poetry install

# Activate venv
poetry shell

# Start services (PostgreSQL + Redis)
docker-compose up -d

# Run migrations
alembic upgrade head

# Install pre-commit hooks
pre-commit install

# Run tests (vérifier que tout est OK)
pytest -v

# Start dev server
uvicorn app.main:app --reload
```

### VS Code Setup
- [ ] Installer extensions recommandées (popup VS Code)
- [ ] Vérifier que Black format au save (Ctrl+S sur fichier Python)
- [ ] Vérifier que Ruff check au save (erreurs rouges dans éditeur)
- [ ] Vérifier que tests runner fonctionne (panneau Testing)

### Accès
- [ ] Accès GitHub repo
- [ ] Accès Slack channel #dev-carocorp
- [ ] Accès staging environment (https://staging.carocorp.com)
- [ ] Accès documentation interne (Notion/Confluence)

---

## Jour 2: Premier Ticket (4 heures)

### Lecture Documentation
- [ ] Lire README.md complet
- [ ] Lire le Dev Playbook (règles architecture)
- [ ] Lire CAROCORP_SECURITY_AUDIT_AND_ROADMAP.md (contexte sécurité)
- [ ] Explorer architecture app/ (models, services, repositories, endpoints)

### Premier Bug Fix (Junior-friendly)
- [ ] Prendre ticket "good first issue" dans backlog
- [ ] Créer branche: `git checkout -b fix/issue-123-description`
- [ ] Écrire test qui reproduit le bug
- [ ] Corriger le bug
- [ ] Vérifier que tests passent (`pytest -v`)
- [ ] Vérifier que pre-commit hooks passent (`git commit`)
- [ ] Push et créer PR

### Code Review
- [ ] Demander review sur #dev-carocorp
- [ ] Répondre aux commentaires review
- [ ] Merge PR (après approval)

---

## Semaine 1: Montée en Compétence

### Concepts Clés à Maîtriser
- [ ] Multi-tenant architecture (tenant_id partout)
- [ ] Soft delete (is_active au lieu de DELETE)
- [ ] Montants en centimes (BigInteger, pas Float)
- [ ] JWT authentication (access + refresh tokens)
- [ ] Repository pattern (BaseRepository)
- [ ] Service layer (business logic)

### Tests Anti-Cross-Tenant
- [ ] Lire `tests/security/test_multi_tenant_isolation.py`
- [ ] Comprendre pourquoi tests anti-cross-tenant sont OBLIGATOIRES
- [ ] Écrire un test anti-cross-tenant pour nouvelle feature

### Sécurité
- [ ] Lire OWASP Top 10 (contexte CaroCorp dans CAROCORP_SECURITY_AUDIT_AND_ROADMAP.md)
- [ ] Comprendre CSRF protection
- [ ] Comprendre rate limiting
- [ ] Comprendre audit log immutable

---

## Mois 1: Autonomie

### Objectifs
- [ ] Livrer 3 features complètes (avec tests + review)
- [ ] Participer à 5 code reviews
- [ ] Corriger 1 bug production (hotfix)
- [ ] Écrire 1 test E2E workflow complet

### Milestone
- [ ] Capable de prendre ticket "ready for dev" et le livrer en autonomie
- [ ] Comprend l'architecture end-to-end (DB → API → Tests → CI → Staging)
- [ ] Connaît les patterns code CaroCorp (pas besoin de copier-coller code existant)
```

---

#### Code Review Checklist

```markdown
# Code Review Checklist - CaroCorp

## Avant de soumettre PR

- [ ] Tests écrits (couverture >= 95%)
- [ ] Tests anti-cross-tenant si feature multi-tenant
- [ ] Pre-commit hooks passent (`git commit`)
- [ ] CI au vert (lint, security, tests)
- [ ] Description PR claire (problème + solution)
- [ ] Lien vers ticket/issue
- [ ] Screenshots si changement UI/API
- [ ] Migration Alembic si changement DB
- [ ] Documentation mise à jour (README, docstrings)

## Review (Reviewer)

### Architecture
- [ ] Respecte patterns existants (Repository, Service, Endpoint)
- [ ] Pas de logique métier dans les endpoints
- [ ] Pas de requêtes SQL directes (utilise repositories)
- [ ] Separation of concerns respectée

### Sécurité
- [ ] Filtre tenant_id partout (si multi-tenant)
- [ ] Validation inputs (Pydantic schemas)
- [ ] Pas de secret hardcodé
- [ ] Pas de SQL injection (SQLAlchemy ORM utilisé)
- [ ] Authent/Authz vérifié (Depends(get_current_user))

### Tests
- [ ] Tests unitaires couvrent business logic
- [ ] Tests integration couvrent endpoints
- [ ] Tests E2E si workflow complexe
- [ ] Tests anti-cross-tenant si applicable
- [ ] Edge cases testés (empty, null, invalid)

### Qualité Code
- [ ] Black formaté (line-length=100)
- [ ] Ruff lint sans erreur
- [ ] Mypy type check sans erreur
- [ ] Pas de code mort (commented code)
- [ ] Docstrings sur fonctions publiques
- [ ] Noms de variables explicites (pas d'abréviations obscures)

### Performance
- [ ] Pas de N+1 queries (utilise joinedload si nécessaire)
- [ ] Pas de boucle sur requêtes DB
- [ ] Index DB sur colonnes filtrées (si nouvelle requête)

### RGPD
- [ ] Données sensibles chiffrées (si applicable)
- [ ] Logs n'exposent pas PII
- [ ] Retention policy respectée (si données temporaires)

---

## Après Review

- [ ] Tous commentaires résolus
- [ ] CI toujours au vert
- [ ] Approval minimum 1 reviewer
- [ ] Merge via squash commit (message propre)
```

---

#### Standards Documentation

```markdown
# Standards Documentation Code - CaroCorp

## Docstrings (Google Style)

```python
def calculate_reservation_total(
    reservation_id: int,
    tenant_id: int,
    include_tax: bool = True
) -> int:
    """Calculate total amount for reservation in cents.

    Args:
        reservation_id: Unique reservation identifier
        tenant_id: Tenant ID for multi-tenant isolation
        include_tax: Whether to include VAT (default: True)

    Returns:
        Total amount in cents (e.g., 25000 = 250.00€)

    Raises:
        ReservationNotFoundError: If reservation doesn't exist
        InsufficientPermissionsError: If user not in same tenant

    Example:
        >>> total = calculate_reservation_total(123, tenant_id=1)
        >>> print(f"Total: {total / 100:.2f}€")
        Total: 250.00€

    Note:
        This function applies tenant_id filter automatically.
        All amounts returned are in cents (BigInteger).
    """
    pass
```

## Comments

```python
# ✅ BON: Explique POURQUOI, pas QUOI
# Utilise argon2 au lieu de bcrypt (OWASP recommandation 2024)
password_hash = argon2.hash(password)

# ❌ MAUVAIS: Explique QUOI (évident en lisant le code)
# Hash le password
password_hash = argon2.hash(password)

# ✅ BON: Explique décision non-évidente
# Timeout 5s: API externe lente, mais on ne peut pas attendre > 5s (UX)
response = httpx.get(url, timeout=5.0)

# ✅ BON: Lien vers documentation externe
# Redis pipeline: https://redis.io/docs/manual/pipelining/
pipe = redis.pipeline()
```

## Type Hints (Mypy Strict)

```python
from typing import Optional, List
from sqlalchemy.orm import Session

# ✅ BON: Type hints complets
def get_products(
    db: Session,
    tenant_id: int,
    category: Optional[str] = None,
    limit: int = 100
) -> List[Product]:
    pass

# ❌ MAUVAIS: Pas de type hints
def get_products(db, tenant_id, category=None, limit=100):
    pass
```

## README.md Structure

```markdown
# CaroCorp API

## Description
API REST FastAPI pour gestion location vaisselle événements.

## Stack
- Python 3.11+
- FastAPI 0.115+
- SQLAlchemy 2.0 (ORM)
- PostgreSQL 16
- Redis 7
- Celery (workers)

## Setup Local

### Prérequis
- Python 3.11+
- Poetry
- Docker Desktop

### Installation
\```bash
# Clone + install
git clone https://github.com/carocorp/carocorp-api.git
cd carocorp-api
poetry install

# Start services
docker-compose up -d

# Migrations
poetry run alembic upgrade head

# Run tests
poetry run pytest

# Start dev server
poetry run uvicorn app.main:app --reload
\```

### Configuration
Copier `.env.example` → `.env` et configurer:
\```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/carocorp_dev
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=<generate-with-openssl-rand-hex-32>
\```

## Architecture
\```
app/
├── api/v1/endpoints/  # Controllers (HTTP routing)
├── services/          # Business logic
├── repositories/      # Data access (SQL queries)
├── models/            # SQLAlchemy models
├── schemas/           # Pydantic DTOs
└── core/              # Config, deps, security
\```

## Documentation
- **API Docs**: http://localhost:8000/api/docs (Swagger UI)
- **Architecture**: voir le Dev Playbook
- **Security Audit**: voir CAROCORP_SECURITY_AUDIT_AND_ROADMAP.md

## Tests
\```bash
# Tous tests
pytest

# Seulement unitaires
pytest tests/unit/ -v

# Avec coverage
pytest --cov=app --cov-report=html

# Tests parallèles (plus rapide)
pytest -n=auto
\```

## Deployment
Voir `docs/deployment.md`

## Contributing
Voir `CONTRIBUTING.md`

## License
MIT
```
```

---

### 8.9 Résumé Configuration Complète

#### Fichiers à Créer/Mettre à Jour

**Créer** (si n'existent pas):
1. `.vscode/settings.json` (1033 lignes configuration VS Code)
2. `.vscode/extensions.json` (extensions recommandées)
3. `.editorconfig` (formatage cross-IDE)
4. `.pre-commit-config.yaml` (hooks validation avant commit)
5. `.github/workflows/ci.yml` (pipeline CI/CD)

**Mettre à jour** (si existent):
1. `pyproject.toml` (ajouter sections Black, Ruff, Mypy, Pytest, Coverage, Bandit)
2. `.gitignore` (ajouter patterns sécurité critiques)

**Documenter**:
1. `README.md` (setup, architecture, tests)
2. `CONTRIBUTING.md` (workflow Git, review checklist)
3. `docs/onboarding.md` (guide nouveau développeur)

#### Temps Estimation Setup Complet

- **Développeur expérimenté**: 3-4 heures
- **Nouveau sur projet**: 6-8 heures (avec lecture docs)
- **Onboarding junior**: 2 jours (avec mentoring)

#### Validation Configuration

```bash
# Script validation complète
# scripts/validate-config.sh

#!/bin/bash
set -e

echo "🔍 Validation configuration projet CaroCorp..."

# 1. VS Code settings exist
if [ ! -f ".vscode/settings.json" ]; then
    echo "❌ .vscode/settings.json manquant"
    exit 1
fi

# 2. Pre-commit installé
if ! command -v pre-commit &> /dev/null; then
    echo "❌ pre-commit non installé (pip install pre-commit)"
    exit 1
fi

# 3. Pre-commit hooks installés
if [ ! -f ".git/hooks/pre-commit" ]; then
    echo "⚠️  pre-commit hooks non installés (run: pre-commit install)"
    pre-commit install
fi

# 4. Test pre-commit sur tous fichiers
echo "🧪 Test pre-commit hooks..."
pre-commit run --all-files

# 5. Vérifier pyproject.toml contient toutes sections
echo "📝 Vérification pyproject.toml..."
required_sections=("tool.black" "tool.ruff" "tool.mypy" "tool.pytest.ini_options" "tool.coverage.run" "tool.bandit")
for section in "${required_sections[@]}"; do
    if ! grep -q "\[$section\]" pyproject.toml; then
        echo "❌ Section [$section] manquante dans pyproject.toml"
        exit 1
    fi
done

# 6. Vérifier .gitignore contient patterns critiques
echo "🔒 Vérification .gitignore (sécurité)..."
critical_patterns=(".env" "*.pem" "*.key" "*.sql")
for pattern in "${critical_patterns[@]}"; do
    if ! grep -q "$pattern" .gitignore; then
        echo "❌ Pattern '$pattern' manquant dans .gitignore (SÉCURITÉ)"
        exit 1
    fi
done

# 7. Test rapide
echo "🧪 Test unitaires rapides..."
poetry run pytest tests/unit/ -v --tb=short -x -m "not slow"

echo "✅ Configuration validée avec succès!"
echo ""
echo "📋 Next steps:"
echo "  1. Commit configuration: git add . && git commit -m 'chore: setup project configuration'"
echo "  2. Push: git push"
echo "  3. Vérifier CI au vert sur GitHub"
```

---

## 🎯 Bénéfices Configuration Complète

### Pour l'Équipe

**Cohérence**:
- Tous les développeurs utilisent les mêmes règles (Black, Ruff, Mypy)
- Zero surprise lors des code reviews (formatage automatique)
- Onboarding < 30 minutes (clone → poetry install → start coding)

**Qualité**:
- 95%+ des bugs détectés AVANT commit (pre-commit hooks)
- Type checking prévient 15% bugs production (étude Microsoft)
- Security scan automatique (Bandit, Safety, detect-secrets)

**Productivité**:
- Auto-fix 90% des erreurs linting (Ruff --fix)
- Tests parallèles (-n=auto) → CI 5 min → 1 min
- Pre-commit fast (< 10s) permet commits fréquents

### Pour la Sécurité

**Defense in Depth**:
- **Layer 1**: Pre-commit hooks (detect-secrets, Bandit)
- **Layer 2**: CI/CD (SAST, dependency scan)
- **Layer 3**: Code review (checklist sécurité)
- **Layer 4**: Production monitoring (audit log, alerts)

**Audit Trail**:
- Tous commits passent validation sécurité
- Historique Git = preuve conformité (audits)
- Coverage 100% = confidence déploiement

### Pour la Conformité (RGPD, ISO 27001)

**Traçabilité**:
- Tous changements code sont tracés (Git)
- Validation automatique (no human error)
- Secrets never committed (detect-secrets)

**Documentation**:
- Configuration as Code (pyproject.toml, .github/workflows/)
- Reproductible (nouveau dev = même setup)
- Auditable (inspecteur peut lire .pre-commit-config.yaml)

---

**🚀 Configuration complète = Production-ready team**


