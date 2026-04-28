# Conventions — Endpoints FastAPI

## Structure Standard

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user, require_role
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, PaginatedResponse
from app.services.product import ProductService, get_product_service
from app.core.exceptions import NotFound, BusinessError

router = APIRouter(prefix="/products", tags=["products"])

@router.get("/", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    current_user = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    items, total = service.list(current_user.tenant_id, page, limit, search)
    return PaginatedResponse(
        items=items, total=total, page=page, limit=limit,
        pages=(total + limit - 1) // limit,
    )

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    current_user = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    return service.create(current_user.tenant_id, data)

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    current_user = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    return service.get(current_user.tenant_id, product_id)

@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    current_user = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    return service.update(current_user.tenant_id, product_id, data)

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    current_user = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
    service: ProductService = Depends(get_product_service),
):
    service.delete(current_user.tenant_id, product_id)
```

## Gestion des Erreurs

```python
# Les services lèvent NotFound/BusinessError
# Le middleware global les convertit en HTTP 404/400
# Ne pas attraper dans les endpoints sauf cas spécifiques

# Si exception handling local nécessaire :
@router.post("/")
async def create(...):
    try:
        return service.create(...)
    except BusinessError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## RBAC

```python
from app.core.auth import require_role, require_permission

# Rôle
@router.delete("/{id}")
async def delete(_=Depends(require_role("admin"))):
    ...

# Permission fine
@router.post("/export")
async def export(_=Depends(require_permission("billing:read"))):
    ...
```

## Pagination Standard

```python
# Query params standards
page: int = Query(default=1, ge=1)
limit: int = Query(default=20, ge=1, le=100)  # max 100 sauf exception justifiée
search: str | None = Query(default=None, max_length=200)

# Cursor pagination (grandes tables)
cursor: str | None = Query(default=None)
```

## Versioning

```python
# v1 dans le prefix du router
router_v1 = APIRouter(prefix="/v1/products", tags=["products-v1"])
router_v2 = APIRouter(prefix="/v2/products", tags=["products-v2"])

# Header Deprecation sur v1
from app.middleware.deprecation import add_deprecation_header
```

## Rate Limiting

```python
from app.core.rate_limit import rate_limit

@router.post("/upload")
@rate_limit(max_requests=10, window_seconds=60)
async def upload(...):
    ...
```

## Règles

- Aucun endpoint sans `Depends(get_current_user)`
- `tenant_id` toujours depuis `current_user.tenant_id`, jamais depuis le body/path
- Pas de logique métier dans les endpoints — déléguer au service
- `status_code=201` pour POST, `204` pour DELETE
- `response_model` toujours spécifié
- Router enregistré dans `app/api/v1/__init__.py`
- Tests anti-cross-tenant obligatoires sur tout endpoint métier

## Checklist Nouvel Endpoint

- ☐ `Depends(get_current_user)` présent
- ☐ `tenant_id` depuis `current_user` (pas depuis le body)
- ☐ `response_model` spécifié
- ☐ `status_code` correct (201/204)
- ☐ RBAC si action privilégiée
- ☐ Router enregistré dans `__init__.py`
- ☐ Test nominal + test 404 + test cross-tenant
