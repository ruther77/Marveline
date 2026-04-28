# Patterns — Performance

## Materialized Views (Agrégats Fréquents)

```python
# Migration : créer une materialized view
def upgrade():
    op.execute("""
        CREATE MATERIALIZED VIEW tenant_revenue_summary AS
        SELECT
            tenant_id,
            DATE_TRUNC('month', created_at) AS month,
            COUNT(*) AS invoice_count,
            SUM(total_cents) AS revenue_cents
        FROM invoices
        WHERE is_active = TRUE
        GROUP BY tenant_id, DATE_TRUNC('month', created_at);

        CREATE UNIQUE INDEX ON tenant_revenue_summary (tenant_id, month);
    """)

# Rafraîchir (Celery task quotidienne)
@celery_app.task
def refresh_revenue_summary():
    with get_db_context() as db:
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY tenant_revenue_summary"))
        db.commit()
```

## Partial Indexes

```python
# Index uniquement sur les lignes actives (économise 60-80% d'espace)
op.create_index(
    "ix_products_tenant_active",
    "products",
    ["tenant_id", "name"],
    postgresql_where=sa.text("is_active = TRUE"),
)

# Index sur colonnes fréquemment filtrées
op.create_index(
    "ix_reservations_tenant_status",
    "reservations",
    ["tenant_id", "status"],
    postgresql_where=sa.text("status IN ('pending', 'confirmed')"),
)
```

## Cache Tags (Redis)

```python
import redis
from typing import Callable
import json

redis_client = redis.Redis()

def cache_with_tags(key: str, tags: list[str], ttl: int = 300):
    """Décorateur cache avec invalidation par tags"""
    def decorator(fn: Callable):
        async def wrapper(*args, **kwargs):
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)

            result = await fn(*args, **kwargs)
            redis_client.setex(key, ttl, json.dumps(result, default=str))

            # Enregistrer les tags → clés
            for tag in tags:
                redis_client.sadd(f"tag:{tag}", key)
                redis_client.expire(f"tag:{tag}", ttl + 60)

            return result
        return wrapper
    return decorator

def invalidate_tag(tag: str):
    """Invalider toutes les clés associées à un tag"""
    keys = redis_client.smembers(f"tag:{tag}")
    if keys:
        redis_client.delete(*keys)
    redis_client.delete(f"tag:{tag}")

# Utilisation
@cache_with_tags(f"products:{tenant_id}", tags=[f"tenant:{tenant_id}:products"], ttl=300)
async def get_products_cached(tenant_id: int):
    return await products_service.list(tenant_id)

# Sur mutation
def create_product(tenant_id, data):
    product = repo.create(...)
    invalidate_tag(f"tenant:{tenant_id}:products")
    return product
```

## pgBouncer (Connection Pooling)

```python
# docker-compose.yml
pgbouncer:
  image: edoburu/pgbouncer:1.21.0
  environment:
    DB_HOST: postgres
    DB_USER: ${POSTGRES_USER}
    DB_PASSWORD: ${POSTGRES_PASSWORD}
    DB_NAME: ${POSTGRES_DB}
    POOL_MODE: transaction  # transaction pooling pour FastAPI
    MAX_CLIENT_CONN: 200
    DEFAULT_POOL_SIZE: 20
  ports:
    - "5432:5432"

# SQLAlchemy via pgBouncer
DATABASE_URL = "postgresql://user:pass@pgbouncer:5432/db?prepared_statement_cache_size=0"
# IMPORTANT: désactiver prepared statements avec pgBouncer en mode transaction
```

## Read Replica

```python
# Configuration double engine
write_engine = create_engine(settings.DATABASE_URL)
read_engine = create_engine(settings.DATABASE_URL_READ_REPLICA)

# Session factory
WriteSession = sessionmaker(bind=write_engine)
ReadSession = sessionmaker(bind=read_engine)

# Dependency injection
def get_read_db():
    with ReadSession() as session:
        yield session

# Endpoints lecture seule
@router.get("/reports/summary")
async def get_summary(read_db: Session = Depends(get_read_db)):
    ...
```

## SWR (Stale-While-Revalidate) Frontend

```typescript
// React Query : staleTime = SWR
const { data } = useQuery({
    queryKey: ['dashboard', year],
    queryFn: () => dashboardApi.getStats(year),
    staleTime: 5 * 60 * 1000,  // 5 min : données considérées fraîches
    gcTime: 10 * 60 * 1000,    // 10 min : garder en cache même si stale
});

// Prefetch anticipé au hover
const queryClient = useQueryClient();
const prefetchProduct = (id: number) =>
    queryClient.prefetchQuery({
        queryKey: ['products', id],
        queryFn: () => productsApi.get(id),
        staleTime: 60_000,
    });
```

## Debounced Search Frontend

```typescript
import { useDeferredValue, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

function SearchProducts() {
    const [search, setSearch] = useState('');
    const deferredSearch = useDeferredValue(search);  // React 18 — pas de debounce manuel

    const { data } = useQuery({
        queryKey: ['products', 'search', deferredSearch],
        queryFn: () => productsApi.search(deferredSearch),
        enabled: deferredSearch.length >= 2,
    });
}
```

## Slow Query Detection

```python
from sqlalchemy import event
import logging
import time

logger = logging.getLogger(__name__)
SLOW_QUERY_THRESHOLD_MS = 500

@event.listens_for(Engine, "before_cursor_execute")
def before_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info["query_start_time"] = time.time()

@event.listens_for(Engine, "after_cursor_execute")
def after_execute(conn, cursor, statement, parameters, context, executemany):
    elapsed_ms = (time.time() - conn.info["query_start_time"]) * 1000
    if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
        logger.warning(
            "Slow query detected: %.2fms\n%s",
            elapsed_ms,
            statement[:500],
        )
```

## Règles Performance

| Règle | Seuil | Priorité |
|---|---|---|
| N+1 interdit | 0 N+1 en production | P0 |
| Index composite | (tenant_id, id) obligatoire | P0 |
| Pagination max | 100 items/page (10k export) | P1 |
| Cache TTL | 5 min défaut, 1h agrégats | P1 |
| Slow query log | > 500ms → WARNING | P1 |
| pgBouncer | Pool 20 connections | P2 |
| Materialized view | Agrégats > 100k lignes | P2 |
