# Conventions — Schémas Pydantic

## Pattern Base/Create/Update/Response

```python
from pydantic import BaseModel, field_validator, model_validator
from decimal import Decimal

class ProductBase(BaseModel):
    name: str
    price_cents: int  # BigInteger centimes côté DB

class ProductCreate(ProductBase):
    category_id: int

class ProductUpdate(BaseModel):
    name: str | None = None
    price_cents: int | None = None

class ProductResponse(ProductBase):
    id: int
    price_euros: float  # calculé depuis price_cents

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def price_euros(self) -> float:
        return self.price_cents / 100
```

## Montants : Centimes → Euros

- Stockage DB : `BigInteger` centimes
- Réponse API : champ `_euros` calculé (computed_field)
- Validation : toujours vérifier `>= 0`

```python
@field_validator("price_cents")
@classmethod
def price_must_be_positive(cls, v: int) -> int:
    if v < 0:
        raise ValueError("price_cents must be >= 0")
    return v
```

## Validators Utiles

```python
from pydantic import field_validator, model_validator

# Validator de champ
@field_validator("email")
@classmethod
def normalize_email(cls, v: str) -> str:
    return v.lower().strip()

# Validator cross-champ
@model_validator(mode="after")
def check_dates(self) -> "ReservationCreate":
    if self.end_date <= self.start_date:
        raise ValueError("end_date must be after start_date")
    return self
```

## Pagination

```python
class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=1000)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    pages: int
```

## Schémas de Liste (résumé vs détail)

```python
class CustomerList(BaseModel):
    """Utilisé dans les listes — champs minimaux"""
    id: int
    name: str
    email: str

class CustomerResponse(CustomerList):
    """Détail complet — inclut tous les champs"""
    address: str | None
    city: str | None
    phone: str | None
    created_at: datetime
```

## Règles

- `from_attributes=True` (ou `orm_mode=True` en Pydantic v1) sur tous les schémas Response
- Pas de `dict` nu comme type de retour — toujours un schéma typé
- Champs optionnels dans `Update` = `X | None = None`
- Pas d'`id` dans `Create` (auto-généré)
- `tenant_id` jamais exposé dans les réponses API publiques
- Schémas exportés dans `app/schemas/__init__.py`

## Checklist Nouveau Schéma

- ☐ Classes Base/Create/Update/Response distinctes
- ☐ `model_config = ConfigDict(from_attributes=True)` sur Response
- ☐ Montants en centimes avec computed_field `_euros`
- ☐ Validators sur champs critiques
- ☐ Exporté dans `app/schemas/__init__.py`
