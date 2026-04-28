# Patterns — Resilience

## Circuit Breaker

```python
import pybreaker

db_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)

@db_breaker
def call_external_service(payload: dict) -> dict:
    return requests.post("https://external.api/endpoint", json=payload, timeout=5).json()

# Utilisation
try:
    result = call_external_service(data)
except pybreaker.CircuitBreakerError:
    # Fallback : retourner valeur cachée ou erreur gracieuse
    return get_cached_fallback()
```

## Retry avec Jitter (Tenacity)

```python
from tenacity import retry, stop_after_attempt, wait_exponential, wait_random

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
    reraise=True,
)
async def send_with_retry(payload: dict) -> None:
    await external_client.send(payload)
```

## Timeout Strategy

```python
import asyncio
from contextlib import asynccontextmanager

TIMEOUT_SECONDS = 5.0

async def call_with_timeout(coro):
    try:
        return await asyncio.wait_for(coro, timeout=TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("External call timed out after %ss", TIMEOUT_SECONDS)
        raise TimeoutError("External service unavailable")
```

## Bulkhead (Isolation des Ressources)

```python
from asyncio import Semaphore

# Limiter la concurrence vers un service externe
_semaphore = Semaphore(10)  # max 10 appels simultanés

async def isolated_call(data: dict) -> dict:
    async with _semaphore:
        return await external_service.call(data)
```

## Idempotency Keys

```python
import hashlib
import redis

redis_client = redis.Redis()
IDEMPOTENCY_TTL = 86400  # 24h

def idempotent_operation(idempotency_key: str, operation_fn, *args, **kwargs):
    cache_key = f"idempotency:{idempotency_key}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)  # Réponse déjà calculée

    result = operation_fn(*args, **kwargs)
    redis_client.setex(cache_key, IDEMPOTENCY_TTL, json.dumps(result))
    return result

# Endpoint avec idempotency key
@router.post("/payments")
async def create_payment(
    data: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ...
):
    return idempotent_operation(idempotency_key, payment_service.create, tenant_id, data)
```

## Outbox Pattern (Messaging Fiable)

```python
# Table outbox pour garantir la livraison des événements
class OutboxEvent(Base, TimestampMixin):
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

# Dans le service (même transaction que la mutation métier)
def create_reservation(self, ...) -> Reservation:
    reservation = self.repo.create(...)
    outbox_event = OutboxEvent(
        event_type="reservation.created",
        payload={"reservation_id": reservation.id, "tenant_id": reservation.tenant_id}
    )
    self.db.add(outbox_event)
    self.db.commit()  # atomique : réservation + event
    return reservation

# Celery worker lit et publie l'outbox
@celery_app.task
def process_outbox():
    events = db.query(OutboxEvent).filter(OutboxEvent.processed == False).all()
    for event in events:
        publish_to_message_bus(event)
        event.processed = True
    db.commit()
```

## Saga + Compensation

```python
class ReservationSaga:
    """Orchestration de la réservation avec compensation en cas d'échec"""

    def __init__(self, db: Session):
        self.db = db
        self.completed_steps: list[str] = []

    def execute(self, tenant_id: int, reservation_data: dict) -> Reservation:
        try:
            # Step 1: Créer la réservation
            reservation = self._create_reservation(tenant_id, reservation_data)
            self.completed_steps.append("reservation_created")

            # Step 2: Bloquer le stock
            self._reserve_stock(tenant_id, reservation)
            self.completed_steps.append("stock_reserved")

            # Step 3: Créer la facture
            invoice = self._create_invoice(tenant_id, reservation)
            self.completed_steps.append("invoice_created")

            self.db.commit()
            return reservation

        except Exception as e:
            self.db.rollback()
            self._compensate()
            raise

    def _compensate(self) -> None:
        """Annuler les étapes complétées en ordre inverse"""
        for step in reversed(self.completed_steps):
            if step == "stock_reserved":
                self._release_stock()
            elif step == "invoice_created":
                self._cancel_invoice()
```

## Domain Events

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class DomainEvent:
    event_type: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    payload: dict = field(default_factory=dict)

class ReservationConfirmed(DomainEvent):
    event_type: str = "reservation.confirmed"

# Dans le service
def confirm_reservation(self, ...) -> Reservation:
    reservation.status = ReservationStatus.CONFIRMED
    self.event_bus.publish(ReservationConfirmed(
        payload={"reservation_id": reservation.id}
    ))
    self.db.commit()
```

## Matrice Resilience

| Pattern | Quand utiliser | Priorité |
|---|---|---|
| Circuit Breaker | Appels services externes | P1 |
| Retry + Jitter | Opérations idempotentes réseau | P1 |
| Timeout | Tout appel externe | P1 |
| Idempotency Keys | Mutations côté client | P1 |
| Outbox Pattern | Events + mutations atomiques | P1 |
| Bulkhead | Isolation de ressources | P2 |
| Saga | Workflows multi-services | P2 |
| Domain Events | Communication inter-services | P2 |
