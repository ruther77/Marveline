# Patterns — Event-Driven

## Outbox Pattern

Voir aussi : [`resilience.md`](resilience.md#outbox-pattern-messaging-fiable)

Garantit l'atomicité entre la mutation métier et la publication d'événements :
1. Mutation + OutboxEvent dans la même transaction DB
2. Worker Celery lit l'outbox et publie vers le message bus
3. Marquage `processed = True` une fois publié

```python
# Modèle outbox
class OutboxEvent(Base, TimestampMixin):
    __tablename__ = "outbox_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

## Saga + Compensation

Voir : [`resilience.md`](resilience.md#saga--compensation)

Pour les workflows multi-étapes qui traversent plusieurs services, implémenter des compensations explicites pour chaque étape.

## Domain Events

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class DomainEvent:
    event_type: str
    tenant_id: int
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    payload: dict = field(default_factory=dict)

# Événements du domaine
@dataclass
class ReservationConfirmed(DomainEvent):
    event_type: str = field(default="reservation.confirmed", init=False)

@dataclass
class InvoicePaid(DomainEvent):
    event_type: str = field(default="invoice.paid", init=False)

@dataclass
class StockDepleted(DomainEvent):
    event_type: str = field(default="stock.depleted", init=False)

# Event Bus simple (en mémoire, pour tests)
class InMemoryEventBus:
    def __init__(self):
        self._handlers: dict[str, list] = {}

    def subscribe(self, event_type: str, handler):
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: DomainEvent):
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
```

## Server-Sent Events (SSE)

```python
from fastapi import Request
from fastapi.responses import StreamingResponse
import asyncio

@router.get("/events/stream")
async def event_stream(
    request: Request,
    current_user = Depends(get_current_user),
):
    async def generate():
        channel = f"tenant:{current_user.tenant_id}:events"
        pubsub = redis_client.pubsub()
        pubsub.subscribe(channel)

        try:
            while True:
                if await request.is_disconnected():
                    break

                message = pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    data = json.loads(message["data"])
                    yield f"data: {json.dumps(data)}\n\n"
                else:
                    yield ": keepalive\n\n"  # Eviter timeout
                    await asyncio.sleep(1)
        finally:
            pubsub.unsubscribe(channel)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx : désactiver le buffering
        },
    )

# Publier un événement
def publish_event(tenant_id: int, event_type: str, payload: dict):
    channel = f"tenant:{tenant_id}:events"
    redis_client.publish(channel, json.dumps({"type": event_type, **payload}))
```

## SSE Frontend

```typescript
import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

function useRealtimeUpdates() {
    const queryClient = useQueryClient();
    const eventSourceRef = useRef<EventSource | null>(null);

    useEffect(() => {
        const es = new EventSource('/api/v1/events/stream', { withCredentials: true });

        es.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'reservation.updated') {
                queryClient.invalidateQueries({ queryKey: ['reservations'] });
            }
        };

        es.onerror = () => {
            es.close();
            // Reconnexion avec backoff
            setTimeout(() => eventSourceRef.current = new EventSource(...), 5000);
        };

        eventSourceRef.current = es;
        return () => es.close();
    }, [queryClient]);
}
```

## WebSockets (Collaboration Temps Réel)

```python
from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict

class ConnectionManager:
    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        self.rooms[room].append(websocket)

    def disconnect(self, room: str, websocket: WebSocket):
        self.rooms[room].remove(websocket)

    async def broadcast(self, room: str, message: dict, exclude: WebSocket | None = None):
        data = json.dumps(message)
        for ws in self.rooms[room]:
            if ws != exclude:
                await ws.send_text(data)

manager = ConnectionManager()

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...),
):
    user = await verify_token(token)
    room = f"tenant:{user.tenant_id}:{room_id}"
    await manager.connect(room, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.broadcast(room, {"user": user.name, **data}, exclude=websocket)
    except WebSocketDisconnect:
        manager.disconnect(room, websocket)
```

## Event Sourcing (Pattern Avancé — V2)

```python
# Stocker les événements comme source de vérité
class ReservationEvent(Base, TimestampMixin):
    __tablename__ = "reservation_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reservation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reservations.id"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # confirmed, cancelled, delivered...
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # qui a déclenché l'événement

# Reconstituer l'état depuis les événements (projection)
def rebuild_reservation_state(events: list[ReservationEvent]) -> dict:
    state = {}
    for event in sorted(events, key=lambda e: e.created_at):
        if event.event_type == "created":
            state = event.payload
        elif event.event_type == "confirmed":
            state["status"] = "confirmed"
        elif event.event_type == "cancelled":
            state["status"] = "cancelled"
            state["cancellation_reason"] = event.payload.get("reason")
    return state
```

## LISTEN/NOTIFY PostgreSQL

```python
# Pour les notifications légères intra-service (sans Redis)
import psycopg2
import select

def listen_for_events(channel: str, callback):
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    cursor.execute(f"LISTEN {channel};")

    while True:
        if select.select([conn], [], [], 5) == ([], [], []):
            continue  # timeout, relancer
        conn.poll()
        while conn.notifies:
            notify = conn.notifies.pop(0)
            callback(json.loads(notify.payload))

# Publier une notification
def notify_event(db: Session, channel: str, payload: dict):
    db.execute(text(f"SELECT pg_notify('{channel}', :payload)"),
               {"payload": json.dumps(payload)})
```

## Matrice Event-Driven

| Pattern | Cas d'usage | Priorité |
|---|---|---|
| Outbox | Mutations + events atomiques | P1 |
| Domain Events | Communication loosely-coupled | P1 |
| SSE | Notifications temps réel unidirectionnelles | P1 |
| LISTEN/NOTIFY | Notifications légères intra-DB | P2 |
| WebSockets | Collaboration bidirectionnelle | P2 |
| Saga | Workflows multi-services | P2 |
| Event Sourcing | Audit trail complet + replay | P3 (V2) |
