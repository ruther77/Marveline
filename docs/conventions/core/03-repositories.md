# Conventions — Repositories

## Principe

- Le repository est la **seule couche** qui accède directement à la DB
- Toujours filtrer par `tenant_id` — jamais de requête globale sans justification écrite
- Pas de logique métier dans les repos — uniquement de l'accès aux données
- `autoflush=False` sur la session de test → `db.flush()` explicite après mutations

## Pattern de Base

```python
from sqlalchemy.orm import Session
from app.models.product import Product
from app.core.exceptions import NotFound

class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, tenant_id: int, product_id: int) -> Product:
        product = (
            self.db.query(Product)
            .filter(Product.tenant_id == tenant_id, Product.id == product_id, Product.is_active == True)
            .first()
        )
        if not product:
            raise NotFound(f"Product {product_id} not found")
        return product

    def list(
        self,
        tenant_id: int,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
    ) -> tuple[list[Product], int]:
        query = (
            self.db.query(Product)
            .filter(Product.tenant_id == tenant_id, Product.is_active == True)
        )
        if search:
            query = query.filter(Product.name.ilike(f"%{search}%"))
        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        return items, total

    def create(self, tenant_id: int, data: dict) -> Product:
        product = Product(tenant_id=tenant_id, **data)
        self.db.add(product)
        self.db.flush()  # obligatoire pour récupérer l'ID généré
        return product

    def soft_delete(self, tenant_id: int, product_id: int) -> None:
        product = self.get_by_id(tenant_id, product_id)
        product.is_active = False
        self.db.flush()
```

## Règle tenant_id

```python
# CORRECT
def get(self, tenant_id: int, id: int) -> Model:
    return db.query(Model).filter(
        Model.tenant_id == tenant_id,
        Model.id == id,
        Model.is_active == True,
    ).first()

# INTERDIT — pas de filtre tenant
def get_global(self, id: int) -> Model:
    return db.query(Model).filter(Model.id == id).first()
```

## Éviter N+1

```python
from sqlalchemy.orm import selectinload, joinedload

# Chargement eager pour relations
def get_invoice_with_lines(self, tenant_id: int, invoice_id: int) -> Invoice:
    return (
        self.db.query(Invoice)
        .options(selectinload(Invoice.lines))
        .filter(Invoice.tenant_id == tenant_id, Invoice.id == invoice_id)
        .first()
    )
```

## Bulk Operations

```python
def bulk_update_status(self, tenant_id: int, ids: list[int], status: str) -> int:
    updated = (
        self.db.query(Model)
        .filter(Model.tenant_id == tenant_id, Model.id.in_(ids))
        .update({"status": status}, synchronize_session="fetch")
    )
    self.db.flush()
    return updated
```

## Cursor Pagination (pour grandes tables)

```python
def list_after_cursor(self, tenant_id: int, cursor_id: int | None, limit: int = 20):
    query = self.db.query(Model).filter(
        Model.tenant_id == tenant_id, Model.is_active == True
    )
    if cursor_id:
        query = query.filter(Model.id > cursor_id)
    items = query.order_by(Model.id).limit(limit + 1).all()
    has_more = len(items) > limit
    return items[:limit], has_more
```

## db.flush() — Règle Importante

```python
# Session test : autoflush=False → TOUJOURS flush explicite
self.db.add(obj)
self.db.flush()  # obligatoire sinon les queries suivantes voient l'état pré-mutation

# Après mutation de status
obj.status = "new_status"
self.db.flush()  # obligatoire pour que sync_cache voie le bon état
```

## Règles

- `tenant_id` dans **chaque** query → violation = P0
- `is_active == True` sur toutes les queries (soft delete)
- `db.flush()` après toute mutation avant query dépendante
- Exception : `NotFound` (pas `NotFoundError`, pas `HTTPException`)
- Pas de logique conditionnelle métier dans les repos
- Pas de `commit()` dans les repos — géré par le service ou la session FastAPI
