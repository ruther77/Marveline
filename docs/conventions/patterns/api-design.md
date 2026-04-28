# Patterns — API Design

## ETag / Conditional Requests

```python
import hashlib
from fastapi import Request, Response
from fastapi.responses import JSONResponse

def compute_etag(data: dict | list) -> str:
    content = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(content.encode()).hexdigest()

@router.get("/{id}")
async def get_resource(id: int, request: Request, response: Response, ...):
    resource = service.get(tenant_id, id)
    data = resource.model_dump()
    etag = compute_etag(data)

    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304)

    response.headers["ETag"] = etag
    return data
```

## Cursor Pagination (Grandes Tables)

```python
from base64 import b64encode, b64decode

class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None  # base64 encodé
    has_more: bool

def encode_cursor(id: int) -> str:
    return b64encode(str(id).encode()).decode()

def decode_cursor(cursor: str) -> int:
    return int(b64decode(cursor.encode()).decode())

@router.get("/")
async def list_with_cursor(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    ...
):
    cursor_id = decode_cursor(cursor) if cursor else None
    items, has_more = repo.list_after_cursor(tenant_id, cursor_id, limit)
    next_cursor = encode_cursor(items[-1].id) if has_more else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)
```

## Sparse Fieldsets (`?fields=`)

```python
from typing import Any

ALLOWED_FIELDS = {"id", "name", "price_cents", "category_id", "created_at"}

@router.get("/")
async def list_products(
    fields: str | None = Query(default=None, description="Comma-separated fields"),
    ...
):
    items = service.list(tenant_id)

    if fields:
        requested = set(fields.split(",")) & ALLOWED_FIELDS
        return [
            {k: v for k, v in item.model_dump().items() if k in requested}
            for item in items
        ]
    return items
```

## API Versioning v1/v2

```python
# app/api/v1/router.py
from fastapi import APIRouter
router_v1 = APIRouter(prefix="/api/v1")
router_v1.include_router(products_v1.router)

# app/api/v2/router.py
router_v2 = APIRouter(prefix="/api/v2")
router_v2.include_router(products_v2.router)

# Middleware Deprecation sur v1
class DeprecationMiddleware:
    async def __call__(self, scope, receive, send):
        if scope["path"].startswith("/api/v1/"):
            async def send_with_header(message):
                if message["type"] == "http.response.start":
                    headers = dict(message.get("headers", []))
                    headers[b"deprecation"] = b"true"
                    headers[b"sunset"] = b"2026-12-31"
                    message["headers"] = list(headers.items())
                await send(message)
            await self.app(scope, receive, send_with_header)
        else:
            await self.app(scope, receive, send)
```

## Contract-First avec OpenAPI

```yaml
# openapi.yaml
paths:
  /api/v1/products:
    post:
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ProductCreate'
      responses:
        '201':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProductResponse'
```

```bash
# Générer les types TypeScript depuis openapi.yaml
npx openapi-typescript openapi.yaml -o src/types/api.generated.ts
```

## Bulk Operations

```python
class BulkUpdateRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=100)
    status: str

@router.patch("/bulk")
async def bulk_update(
    data: BulkUpdateRequest,
    current_user = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    updated_count = service.bulk_update_status(
        current_user.tenant_id, data.ids, data.status
    )
    return {"updated": updated_count}
```

## Webhooks

```python
class WebhookEvent(BaseModel):
    event_type: str
    timestamp: datetime
    tenant_id: int
    payload: dict

WEBHOOK_SECRET = settings.WEBHOOK_SECRET

def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    expected = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

@router.post("/webhooks/receive")
async def receive_webhook(
    request: Request,
    x_signature: str = Header(..., alias="X-Signature-256"),
):
    body = await request.body()
    if not verify_webhook_signature(body, x_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    event = WebhookEvent(**json.loads(body))
    await process_webhook_event(event)
    return {"received": True}
```

## Health Check

```python
@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    checks = {
        "database": False,
        "redis": False,
    }
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    try:
        redis_client.ping()
        checks["redis"] = True
    except Exception:
        pass

    all_healthy = all(checks.values())
    return JSONResponse(
        content={"status": "healthy" if all_healthy else "degraded", "checks": checks},
        status_code=200 if all_healthy else 503,
    )
```

## Règles

- Toujours préférer cursor pagination pour les listes > 10k lignes
- ETag sur les endpoints GET fréquents (réduction trafic)
- `fields=` whitelist stricte — jamais de reflection automatique
- API Versioning : v1 = stable/deprecatable, v2 = nouvelle version
- Webhooks : HMAC-SHA256, timeout 5s, retry 3x avec backoff
