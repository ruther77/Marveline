"""WebSocket Connection Manager — rooms par tenant_id.

Gère les connexions WebSocket avec :
    - Rooms par tenant_id (isolation multi-tenant)
    - Channels : 'kds' (cuisine), 'salle' (serveurs)
    - Heartbeat ping/pong (30s interval)
    - Redis pub/sub pour scaling multi-worker Uvicorn
    - Reconnexion auto côté client (backoff exponentiel)

Events publiés :
    - nouvelle_commande : salle → cuisine (commande créée)
    - commande_prete : cuisine → salle (commande prête à servir)
    - ligne_prete : cuisine → salle (plat individuel prêt)
    - commande_annulee : salle → cuisine
    - commande_modifiee : salle → cuisine (ajout/suppression ligne)
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 30


@dataclass
class Connection:
    """Une connexion WebSocket identifiée."""
    websocket: WebSocket
    tenant_id: int
    channel: str       # 'kds' ou 'salle'
    account_id: int
    account_name: str = ""


class ConnectionManager:
    """Gestionnaire de connexions WebSocket par tenant + channel.

    Thread-safe via asyncio (single event loop).
    Pour scaling multi-worker : utiliser Redis pub/sub (publish_event).
    """

    def __init__(self):
        # {tenant_id: {channel: [Connection, ...]}}
        self._rooms: dict[int, dict[str, list[Connection]]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, conn: Connection) -> None:
        """Accepte et enregistre une connexion."""
        await conn.websocket.accept()

        async with self._lock:
            if conn.tenant_id not in self._rooms:
                self._rooms[conn.tenant_id] = {}
            if conn.channel not in self._rooms[conn.tenant_id]:
                self._rooms[conn.tenant_id][conn.channel] = []
            self._rooms[conn.tenant_id][conn.channel].append(conn)

        logger.info(
            "WS connected tenant=%d channel=%s account=%d",
            conn.tenant_id, conn.channel, conn.account_id,
        )

    async def disconnect(self, conn: Connection) -> None:
        """Retire une connexion."""
        async with self._lock:
            room = self._rooms.get(conn.tenant_id, {}).get(conn.channel, [])
            self._rooms.get(conn.tenant_id, {}).get(conn.channel, [])[:] = [
                c for c in room if c.websocket != conn.websocket
            ]

        logger.info(
            "WS disconnected tenant=%d channel=%s account=%d",
            conn.tenant_id, conn.channel, conn.account_id,
        )

    async def broadcast_to_channel(
        self,
        tenant_id: int,
        channel: str,
        event: str,
        data: dict,
    ) -> int:
        """Envoie un event à toutes les connexions d'un channel/tenant.

        Returns:
            Nombre de clients notifiés.
        """
        message = json.dumps({"event": event, "data": data})
        sent = 0
        dead: list[Connection] = []

        async with self._lock:
            connections = list(self._rooms.get(tenant_id, {}).get(channel, []))

        for conn in connections:
            try:
                await conn.websocket.send_text(message)
                sent += 1
            except Exception:
                dead.append(conn)

        # Nettoyage connexions mortes
        for conn in dead:
            await self.disconnect(conn)

        return sent

    async def broadcast_to_tenant(
        self,
        tenant_id: int,
        event: str,
        data: dict,
    ) -> int:
        """Envoie un event à TOUS les channels d'un tenant."""
        sent = 0
        async with self._lock:
            channels = list(self._rooms.get(tenant_id, {}).keys())
        for channel in channels:
            sent += await self.broadcast_to_channel(tenant_id, channel, event, data)
        return sent

    def get_connection_count(self, tenant_id: int, channel: Optional[str] = None) -> int:
        """Nombre de connexions actives."""
        rooms = self._rooms.get(tenant_id, {})
        if channel:
            return len(rooms.get(channel, []))
        return sum(len(conns) for conns in rooms.values())


# Singleton global
kds_manager = ConnectionManager()


# ── Redis pub/sub pour scaling multi-worker ───────────────────────────────────

async def publish_event(tenant_id: int, channel: str, event: str, data: dict) -> None:
    """Publie un event via Redis pub/sub pour distribution cross-worker.

    En production multi-worker (Uvicorn --workers N), les connexions WS
    sont réparties entre workers. Redis pub/sub garantit que tous les
    workers reçoivent l'event et le relaient à leurs connexions locales.
    """
    from app.core.redis import redis_cache

    redis_channel = f"kds:{tenant_id}:{channel}"
    message = json.dumps({"event": event, "data": data})

    try:
        await redis_cache.client.publish(redis_channel, message)
    except Exception as e:
        logger.error("Redis pub/sub publish failed: %s", e)
        # Fallback : broadcast local uniquement
        await kds_manager.broadcast_to_channel(tenant_id, channel, event, data)


async def subscribe_redis_events(tenant_id: int) -> None:
    """S'abonne aux events Redis pour un tenant et les relaie aux WS locaux.

    Lancé une fois par worker au premier WS connect pour ce tenant.
    """
    from app.core.redis import redis_cache

    pubsub = redis_cache.client.pubsub()
    await pubsub.psubscribe(f"kds:{tenant_id}:*")

    try:
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            try:
                payload = json.loads(message["data"])
                channel_parts = message["channel"].decode().split(":")
                channel = channel_parts[2] if len(channel_parts) >= 3 else "kds"
                await kds_manager.broadcast_to_channel(
                    tenant_id, channel, payload["event"], payload["data"],
                )
            except (json.JSONDecodeError, KeyError):
                continue
    except asyncio.CancelledError:
        await pubsub.punsubscribe()
    except Exception as e:
        logger.error("Redis subscriber error tenant=%d: %s", tenant_id, e)
