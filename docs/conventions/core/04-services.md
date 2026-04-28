# Conventions — Services

## Principe

- Les services contiennent la **logique métier**
- Stateless — pas d'état entre les appels
- Pas d'accès direct à la DB — passent par les repositories
- Orchestrent plusieurs repositories si nécessaire
- Lèvent `NotFound` (jamais `HTTPException`)

## Structure Standard

```python
from sqlalchemy.orm import Session
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.core.exceptions import NotFound, BusinessError

class ProductService:
    def __init__(self, db: Session):
        self.repo = ProductRepository(db)
        self.db = db

    def get(self, tenant_id: int, product_id: int) -> ProductResponse:
        product = self.repo.get_by_id(tenant_id, product_id)
        return ProductResponse.model_validate(product)

    def create(self, tenant_id: int, data: ProductCreate) -> ProductResponse:
        # Validation métier
        existing = self.repo.find_by_name(tenant_id, data.name)
        if existing:
            raise BusinessError("Product with this name already exists")

        product = self.repo.create(tenant_id, data.model_dump())
        self.db.commit()
        self.db.refresh(product)
        return ProductResponse.model_validate(product)

    def update(self, tenant_id: int, product_id: int, data: ProductUpdate) -> ProductResponse:
        product = self.repo.get_by_id(tenant_id, product_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
        self.db.commit()
        self.db.refresh(product)
        return ProductResponse.model_validate(product)

    def delete(self, tenant_id: int, product_id: int) -> None:
        self.repo.soft_delete(tenant_id, product_id)
        self.db.commit()
```

## Transactions et Rollback

```python
def transfer_stock(self, tenant_id: int, from_id: int, to_id: int, qty: int) -> None:
    try:
        self.stock_repo.decrement(tenant_id, from_id, qty)
        self.stock_repo.increment(tenant_id, to_id, qty)
        self.db.commit()
    except Exception:
        self.db.rollback()
        raise
```

## Service avec Dépendances Multiples (Unit of Work)

```python
class ReservationService:
    def __init__(self, db: Session):
        self.reservation_repo = ReservationRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.stock_repo = StockRepository(db)
        self.db = db

    def confirm(self, tenant_id: int, reservation_id: int) -> ReservationResponse:
        reservation = self.reservation_repo.get_by_id(tenant_id, reservation_id)
        if reservation.status != ReservationStatus.PENDING:
            raise BusinessError("Only pending reservations can be confirmed")

        # Réserver le stock
        self.stock_repo.reserve(tenant_id, reservation.lines)

        # Changer le statut
        reservation.status = ReservationStatus.CONFIRMED
        self.db.flush()

        # Créer la facture
        invoice = self.invoice_repo.create_from_reservation(tenant_id, reservation)

        self.db.commit()
        return ReservationResponse.model_validate(reservation)
```

## Injection de Dépendances FastAPI

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import get_db

def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    return ProductService(db)
```

## Règles

- Un service = une responsabilité (ex: `ProductService`, pas `ProductAndCategoryService`)
- Toujours `db.commit()` dans le service, jamais dans le repo
- `db.rollback()` en cas d'exception multi-étapes
- Lever `NotFound` (depuis `app.core.exceptions`), jamais `HTTPException`
- Lever `BusinessError` pour violations de règles métier
- `model_validate()` pour convertir ORM → Pydantic (pas `.from_orm()`)
- Pas de catch silencieux — toute erreur loggée ou propagée
- Fonctions < 40 lignes, max 3 niveaux d'imbrication
