# Analyse Complète des Constantes - CaroCorp

## 📊 Résumé Exécutif

- **Fichiers analysés** : 67 fichiers Python (app/ + tests/)
- **Constantes déjà extraites** : 6 Enums (252 remplacements)
- **Constantes candidates identifiées** : 8 catégories supplémentaires
- **Impact estimé** : ~150 remplacements additionnels

---

## ✅ Constantes DÉJÀ Extraites (Phase 1 - Terminée)

### 1. ProductCategory (6 valeurs)
```python
ASSIETTE, VERRE, COUVERT, NAPPE, DECO, AUTRE
```
**Utilisations** : 23 fichiers, 252 remplacements

### 2. ProductCondition (4 valeurs)
```python
NEUF, BON, USE, HORS_SERVICE
```

### 3. CustomerType (2 valeurs)
```python
INDIVIDUAL, COMPANY
```

### 4. ReservationStatus (5 valeurs)
```python
DRAFT, CONFIRMED, DELIVERED, RETURNED, CANCELLED
```

### 5. InvoiceStatus (5 valeurs)
```python
DRAFT, SENT, PAID, OVERDUE, CANCELLED
```

### 6. PaymentMethod (4 valeurs)
```python
CASH, CARD, TRANSFER, CHECK
```

---

## 🎯 Constantes À EXTRAIRE (Phase 2 - Recommandées)

### **Catégorie 1 : Messages d'Erreur HTTP**

**Problème** : Messages répétés dans 82 occurrences de `HTTPException`

**Fichiers affectés** :
- `app/api/v1/endpoints/*.py` (tous les endpoints)
- `app/services/*.py` (tous les services)

**Constantes proposées** :
```python
class ErrorMessages(str, Enum):
    """Messages d'erreur standardisés."""

    # Ressources non trouvées
    PRODUCT_NOT_FOUND = "Product not found"            # 6 occurrences
    RESERVATION_NOT_FOUND = "Reservation not found"    # 5 occurrences
    INVOICE_NOT_FOUND = "Invoice not found"            # 4 occurrences
    CUSTOMER_NOT_FOUND = "Customer not found"          # 4 occurrences
    USER_NOT_FOUND = "User not found"                  # 2 occurrences

    # Validation
    INSUFFICIENT_STOCK = "Insufficient stock available"
    SKU_ALREADY_EXISTS = "Product with this SKU already exists"
    EMAIL_ALREADY_EXISTS = "Email already registered"

    # Authentification
    INVALID_CREDENTIALS = "Invalid email or password"
    ACCOUNT_INACTIVE = "Account is inactive"
    INVALID_TOKEN = "Could not validate credentials"
    TOKEN_EXPIRED = "Token has expired"

    # CSRF
    CSRF_TOKEN_MISSING = "CSRF token manquant"
    CSRF_TOKEN_INVALID = "CSRF token invalide"

    # Rate Limiting
    TOO_MANY_REQUESTS = "Too many requests"

    # Business Logic
    INVOICE_ALREADY_PAID = "Invoice is already paid"
    RESERVATION_NOT_DRAFT = "Reservation must be in draft status"
    PAYMENT_EXCEEDS_TOTAL = "Payment amount exceeds invoice total"
```

**Impact** : ~40 remplacements

---

### **Catégorie 2 : HTTP Status Codes**

**Problème** : 82 occurrences de `status.HTTP_*` partout

**Constantes proposées** :
```python
class HTTPStatus:
    """Status codes HTTP standardisés."""

    # Success
    OK = status.HTTP_200_OK
    CREATED = status.HTTP_201_CREATED
    NO_CONTENT = status.HTTP_204_NO_CONTENT

    # Client Errors
    BAD_REQUEST = status.HTTP_400_BAD_REQUEST
    UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED
    FORBIDDEN = status.HTTP_403_FORBIDDEN
    NOT_FOUND = status.HTTP_404_NOT_FOUND

    # Server Errors
    INTERNAL_SERVER_ERROR = status.HTTP_500_INTERNAL_SERVER_ERROR

    # Rate Limiting
    TOO_MANY_REQUESTS = status.HTTP_429_TOO_MANY_REQUESTS
```

**Note** : Alternative - garder `status.HTTP_*` directement (déjà lisible)

**Impact** : ~82 remplacements (optionnel)

---

### **Catégorie 3 : Headers de Sécurité**

**Problème** : Valeurs hardcodées dans `SecurityHeadersMiddleware`

**Fichier** : `app/middleware/security.py:77-92`

**Constantes proposées** :
```python
class SecurityHeaders:
    """Headers de sécurité HTTP standardisés."""

    # Headers names
    X_CONTENT_TYPE_OPTIONS = "X-Content-Type-Options"
    X_FRAME_OPTIONS = "X-Frame-Options"
    X_XSS_PROTECTION = "X-XSS-Protection"
    STRICT_TRANSPORT_SECURITY = "Strict-Transport-Security"
    REFERRER_POLICY = "Referrer-Policy"
    CONTENT_SECURITY_POLICY = "Content-Security-Policy"

    # Values
    NOSNIFF = "nosniff"
    DENY = "DENY"
    XSS_BLOCK = "1; mode=block"
    HSTS_ONE_YEAR = "max-age=31536000; includeSubDomains"
    STRICT_ORIGIN_CROSS_ORIGIN = "strict-origin-when-cross-origin"

    # CSP Policies
    CSP_DEFAULT = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self';"
    )
```

**Impact** : 12 remplacements

---

### **Catégorie 4 : Endpoints Publics**

**Problème** : Liste hardcodée dans `CSRFProtectionMiddleware`

**Fichier** : `app/middleware/security.py:28`

**Constantes proposées** :
```python
class PublicEndpoints:
    """Endpoints publics (pas de CSRF requis)."""

    HEALTH = "/health"
    DOCS = "/api/docs"
    REDOC = "/api/redoc"
    OPENAPI = "/openapi.json"

    @classmethod
    def all(cls) -> set[str]:
        """Retourne tous les endpoints publics."""
        return {cls.HEALTH, cls.DOCS, cls.REDOC, cls.OPENAPI}
```

**Impact** : 4 remplacements

---

### **Catégorie 5 : Méthodes HTTP Sûres**

**Problème** : Hardcodé dans `CSRFProtectionMiddleware`

**Fichier** : `app/middleware/security.py:18`

**Constantes proposées** :
```python
class HTTPMethods:
    """Méthodes HTTP standardisées."""

    # Safe methods (CSRF skip)
    GET = "GET"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

    # Unsafe methods (CSRF required)
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"

    SAFE_METHODS = frozenset([GET, HEAD, OPTIONS])
    UNSAFE_METHODS = frozenset([POST, PUT, PATCH, DELETE])
```

**Impact** : 3 remplacements

---

### **Catégorie 6 : Préfixes Redis Keys**

**Problème** : String literals pour clés Redis dans plusieurs services

**Fichiers** :
- `app/services/auth.py` (refresh tokens)
- `app/services/reservation.py` (compteurs)
- `app/middleware/security.py` (rate limiting, CSRF)

**Constantes proposées** :
```python
class RedisKeys:
    """Préfixes pour les clés Redis."""

    # Auth
    REFRESH_TOKEN = "refresh_token:"
    CSRF_TOKEN = "csrf:"
    SESSION = "session:"

    # Rate Limiting
    RATE_LIMIT = "rate_limit:"

    # Counters
    RESERVATION_COUNTER = "reservation_counter:"
    INVOICE_COUNTER = "invoice_counter:"

    @staticmethod
    def refresh_token(user_id: int) -> str:
        return f"{RedisKeys.REFRESH_TOKEN}{user_id}"

    @staticmethod
    def rate_limit(ip: str) -> str:
        return f"{RedisKeys.RATE_LIMIT}{ip}"

    @staticmethod
    def reservation_counter(year: int) -> str:
        return f"{RedisKeys.RESERVATION_COUNTER}{year}"
```

**Impact** : ~10 remplacements

---

### **Catégorie 7 : Limites & Timeouts**

**Problème** : Valeurs numériques magiques dans le code

**Fichiers** :
- `app/schemas/common.py:41` (limit max 1000)
- `app/middleware/security.py:56` (token min 32 chars)
- `app/middleware/security.py:112` (100 req/min)
- `app/core/config.py` (timeouts)

**Constantes proposées** :
```python
class Limits:
    """Limites et seuils de l'application."""

    # Pagination
    MAX_PAGE_SIZE = 1000
    DEFAULT_PAGE_SIZE = 100

    # Security
    CSRF_TOKEN_MIN_LENGTH = 32
    PASSWORD_MIN_LENGTH = 8

    # Rate Limiting
    REQUESTS_PER_MINUTE = 100
    RATE_LIMIT_WINDOW_SECONDS = 60

    # Session
    SESSION_TIMEOUT_SECONDS = 3600  # 1 heure

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
```

**Impact** : ~15 remplacements

---

### **Catégorie 8 : Rôles Utilisateur**

**Problème** : Strings répétées pour RBAC

**Fichiers** :
- `app/core/deps.py` (require_role)
- `tests/conftest.py` (fixtures)

**Constantes proposées** :
```python
class UserRole(str, Enum):
    """Rôles utilisateur pour RBAC."""

    ADMIN = "admin"
    MANAGER = "manager"
    STAFF = "staff"
```

**Impact** : ~8 remplacements

---

## 📈 Impact Total Phase 2

| Catégorie | Constantes | Remplacements | Priorité |
|-----------|-----------|---------------|----------|
| Messages d'erreur | 20 | ~40 | 🔴 HAUTE |
| Headers sécurité | 13 | 12 | 🟡 MOYENNE |
| Redis keys | 6 | ~10 | 🟡 MOYENNE |
| Endpoints publics | 4 | 4 | 🟢 BASSE |
| HTTP methods | 8 | 3 | 🟢 BASSE |
| Limites/Timeouts | 10 | ~15 | 🟡 MOYENNE |
| Rôles utilisateur | 3 | ~8 | 🟡 MOYENNE |
| **TOTAL** | **64** | **~92** | — |

---

## 🎯 Plan d'Action Recommandé

### Phase 2.1 : Priorité HAUTE (maintenant)
1. **ErrorMessages** : Impact immédiat sur lisibilité et maintenance
2. **UserRole** : Sécurité RBAC critique

### Phase 2.2 : Priorité MOYENNE (cette semaine)
3. **SecurityHeaders** : Renforcer middleware sécurité
4. **RedisKeys** : Éviter typos dans clés cache
5. **Limits** : Documenter les seuils métier

### Phase 2.3 : Priorité BASSE (si temps)
6. **PublicEndpoints** : DRY pour middleware CSRF
7. **HTTPMethods** : Optionnel (déjà lisible)

---

## 🛠️ Implémentation Suggérée

### Option A : Tout dans `app/constants.py` (RECOMMANDÉ)
```python
# app/constants.py (structure complète)

from enum import Enum
from fastapi import status

# === ENUMS MÉTIER (Phase 1 - Fait) ===
class ProductCategory(str, Enum): ...
class ProductCondition(str, Enum): ...
# ... etc

# === MESSAGES D'ERREUR (Phase 2.1) ===
class ErrorMessages(str, Enum): ...

# === RÔLES UTILISATEUR (Phase 2.1) ===
class UserRole(str, Enum): ...

# === SÉCURITÉ (Phase 2.2) ===
class SecurityHeaders: ...
class RedisKeys: ...

# === LIMITES (Phase 2.2) ===
class Limits: ...

# === ENDPOINTS (Phase 2.3) ===
class PublicEndpoints: ...
class HTTPMethods: ...
```

### Option B : Fichiers séparés
```
app/constants/
├── __init__.py           # Exports principaux
├── business.py           # ProductCategory, ReservationStatus, etc.
├── errors.py             # ErrorMessages
├── security.py           # SecurityHeaders, UserRole, RedisKeys
└── http.py               # PublicEndpoints, HTTPMethods
```

**Recommandation** : Option A pour MVP (1 fichier), Option B si > 100 constantes

---

## ✅ Checklist Validation

- [ ] Toutes les strings répétées > 3x sont extraites
- [ ] Tous les magic numbers > 2x sont constants
- [ ] Autocompletion IDE fonctionne (Enums)
- [ ] Tests passent après refactoring
- [ ] Aucune valeur hardcodée dans middleware
- [ ] Documentation à jour

---

## 📝 Prochaines Étapes

1. **Valider** ce rapport avec l'équipe
2. **Créer** script de refactoring Phase 2.1 (ErrorMessages + UserRole)
3. **Exécuter** en dry-run
4. **Tester** (pytest)
5. **Commit** : `refactor: Extract error messages and user roles to constants`
6. **Itérer** sur Phase 2.2 et 2.3

---

**Généré le** : 2026-02-12
**Analyseur** : Claude Code (automated analysis)
