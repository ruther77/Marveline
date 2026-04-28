# Conventions — Constantes et Enums

## Structure

```
app/constants/
├── __init__.py       ← exports
├── business.py       ← constantes métier
├── errors.py         ← messages d'erreur
├── security.py       ← constantes sécurité
├── http.py           ← codes HTTP personnalisés
└── limits.py         ← limites système (pagination, tailles)
```

## business.py

```python
# app/constants/business.py

class ReservationStatus:
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DELIVERED = "delivered"
    RETURNED = "returned"
    CANCELLED = "cancelled"

class InvoiceStatus:
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class PaymentMethod:
    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    CHECK = "check"

class DepositStatus:
    HELD = "held"
    RELEASED = "released"
    RETAINED = "retained"

# Taux TVA
VAT_RATE_STANDARD = 20  # %
VAT_RATE_REDUCED = 10   # %

# Délais
DEFAULT_PAYMENT_DAYS = 30
DEPOSIT_RELEASE_DAYS = 7
```

## limits.py

```python
# app/constants/limits.py

PAGINATION_DEFAULT = 20
PAGINATION_MAX = 100
PAGINATION_MAX_EXPORT = 10_000

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

MAX_PRODUCT_NAME_LENGTH = 200
MAX_NOTES_LENGTH = 5000

# Rate limiting
RATE_LIMIT_LOGIN = 5      # req/min
RATE_LIMIT_API_DEFAULT = 100  # req/min
RATE_LIMIT_UPLOAD = 10    # req/min
```

## errors.py

```python
# app/constants/errors.py

class ErrorMessages:
    NOT_FOUND = "{entity} not found"
    ALREADY_EXISTS = "{entity} already exists"
    INVALID_STATUS = "Cannot transition from {from_status} to {to_status}"
    INSUFFICIENT_STOCK = "Insufficient stock for product {product_id}"
    CROSS_TENANT_ACCESS = "Access denied"
```

## Enums SQLAlchemy

```python
import enum

class ReservationStatusEnum(str, enum.Enum):
    """Utilisé dans les modèles SQLAlchemy"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DELIVERED = "delivered"
    RETURNED = "returned"
    CANCELLED = "cancelled"
```

## Règles

- **Jamais de magic strings** pour les concepts métier → toujours depuis `app/constants/`
- Constantes dans le bon fichier (`business.py` pour le métier, `limits.py` pour les limites)
- Enums Python `str, enum.Enum` pour les colonnes SQLAlchemy
- Exportées depuis `app/constants/__init__.py`
- Pas de nombres magiques dans le code

## Anti-patterns

```python
# INTERDIT
if reservation.status == "confirmed":  # magic string
if limit > 1000:                       # magic number

# CORRECT
from app.constants.business import ReservationStatus
from app.constants.limits import PAGINATION_MAX

if reservation.status == ReservationStatus.CONFIRMED:
if limit > PAGINATION_MAX:
```
