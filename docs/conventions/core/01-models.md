# Conventions — Modèles SQLAlchemy

## Mixins Obligatoires

```python
from app.models.base import TimestampMixin, SoftDeleteMixin

class MyModel(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "my_table"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    # ... champs métier
```

- `TimestampMixin` : ajoute `created_at`, `updated_at` (auto-update)
- `SoftDeleteMixin` : ajoute `is_active BOOLEAN DEFAULT TRUE`
- `tenant_id NOT NULL` sur **toute** table métier — violation = **P0**

## Index Obligatoires

```python
__table_args__ = (
    Index("ix_my_table_tenant_id_id", "tenant_id", "id"),          # composite obligatoire
    Index("ix_my_table_tenant_id_active", "tenant_id", "is_active"),# filtre fréquent
    # Index sur colonnes filtrées : FK, date, statut
)
```

## Montants Monétaires

```python
# CORRECT — BigInteger centimes
price_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
# 250 = 2.50 EUR

# INTERDIT
price: Mapped[float] = mapped_column(Float)  # jamais de float pour argent
```

## Enums SQLAlchemy

```python
import enum
from sqlalchemy import Enum as SAEnum

class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"

class Reservation(Base, TimestampMixin, SoftDeleteMixin):
    status: Mapped[ReservationStatus] = mapped_column(
        SAEnum(ReservationStatus), nullable=False, default=ReservationStatus.PENDING
    )
```

## Relations

```python
# Lazy loading interdit en production → eager par défaut ou selectinload explicite
from sqlalchemy.orm import relationship, selectinload

class Invoice(Base, TimestampMixin, SoftDeleteMixin):
    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine", back_populates="invoice", lazy="selectin"
    )
```

## Règles Absolues

- `tenant_id NOT NULL` sur toute table métier
- `TimestampMixin` + `SoftDeleteMixin` sur tout modèle persisté
- Index composite `(tenant_id, id)` minimum
- Montants = BigInteger centimes, jamais float
- Pas de `DELETE` physique — soft delete via `is_active = False`
- Pas de magic strings dans les colonnes Enum → utiliser `str, enum.Enum`
- `__init__.py` toujours à jour après ajout de modèle

## Checklist Nouveau Modèle

- ☐ `TimestampMixin` + `SoftDeleteMixin` hérités
- ☐ `tenant_id NOT NULL` présent
- ☐ Index composite `(tenant_id, id)` défini
- ☐ Migration Alembic créée (`expand/contract`)
- ☐ Modèle exporté dans `app/models/__init__.py`
- ☐ Tests d'isolation tenant écrits
