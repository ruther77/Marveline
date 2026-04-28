"""WebSocket endpoints KDS restaurant.

WS /ws/kds    — cuisine : reçoit nouvelles commandes, envoie statut "prêt"
WS /ws/salle  — salle : reçoit "commande prête", envoie nouvelles commandes

Auth : ticket éphémère (UUID, TTL 30s, usage unique) via query string (?ticket=xxx).
Le client obtient un ticket via POST /ws/ticket (auth Bearer classique),
puis connecte le WebSocket avec ce ticket au lieu du JWT.
Snapshot initial à la connexion : état actuel de toutes les commandes en cours.
Heartbeat ping/pong : 30s.
"""
import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query

from app.api.ws.manager import (
    Connection,
    kds_manager,
    HEARTBEAT_INTERVAL_SECONDS,
)
from app.core.database import get_async_db
from app.core.deps import get_current_user_async
from app.core.security import decode_access_token
from app.core.exceptions import TokenExpired, TokenInvalid
from app.core.redis import redis_sec
from app.repositories.restaurant.commande import AsyncCommandeRepo

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Ticket éphémère pour auth WebSocket (P1-1) ──────────────────────────


@router.post("/ws/ticket")
async def create_ws_ticket(
    current_user=Depends(get_current_user_async),
) -> dict:
    """Génère un ticket éphémère (UUID, TTL 30s) pour auth WebSocket.

    Le ticket remplace le JWT dans la query string WS, évitant
    l'exposition du token dans les logs Nginx et l'historique navigateur.
    """
    ticket_id = uuid.uuid4().hex
    claims = {
        "account_id": current_user.id,
        "tenant_id": current_user.tenant_id,
        "name": getattr(current_user, "display_name", ""),
    }
    stored = await redis_sec.store_ws_ticket(ticket_id, claims)
    if not stored:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Redis indisponible")
    return {"ticket": ticket_id, "expires_in": redis_sec.WS_TICKET_TTL_SECONDS}


async def _authenticate_ws_ticket(ticket: str) -> dict:
    """Consomme un ticket WS éphémère et retourne les claims.

    Le ticket est supprimé atomiquement (GETDEL) — usage unique.
    Raises:
        ValueError: si ticket invalide, expiré ou déjà consommé.
    """
    claims = await redis_sec.consume_ws_ticket(ticket)
    if claims is None:
        raise ValueError("Ticket invalide, expiré ou déjà utilisé")
    return claims


async def _heartbeat(websocket: WebSocket) -> None:
    """Envoie un ping périodique pour détecter les connexions mortes."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            await websocket.send_json({"event": "ping"})
    except Exception:
        pass  # Connexion fermée


async def _send_initial_state(conn: Connection) -> None:
    """Envoie l'etat actuel des commandes en cours a la connexion.

    Charge les commandes OUVERTE/SERVIE avec leurs lignes depuis la DB.
    Appele juste apres le connect pour que le client ait un snapshot.
    """
    try:
        async for db in get_async_db():
            repo = AsyncCommandeRepo(db)
            commandes = await repo.list_active_for_kds(conn.tenant_id)
            break
    except Exception:
        logger.exception("Failed to load initial KDS state for tenant=%d", conn.tenant_id)
        commandes = []

    await conn.websocket.send_json({
        "event": "initial_state",
        "data": {"commandes": commandes},
    })


@router.websocket("/ws/kds")
async def ws_kds(
    websocket: WebSocket,
    ticket: str = Query(...),
):
    """WebSocket cuisine — reçoit commandes, envoie statut prêt."""
    try:
        claims = await _authenticate_ws_ticket(ticket)
    except ValueError as e:
        await websocket.close(code=4001, reason=str(e))
        return

    conn = Connection(
        websocket=websocket,
        tenant_id=claims["tenant_id"],
        channel="kds",
        account_id=claims["account_id"],
        account_name=claims.get("name", ""),
    )

    await kds_manager.connect(conn)
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))

    try:
        await _send_initial_state(conn)

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                event = msg.get("event")

                if event == "pong":
                    continue

                if event == "ligne_prete":
                    await kds_manager.broadcast_to_channel(
                        conn.tenant_id, "salle", "ligne_prete", msg.get("data", {}),
                    )
                elif event == "commande_prete":
                    await kds_manager.broadcast_to_channel(
                        conn.tenant_id, "salle", "commande_prete", msg.get("data", {}),
                    )

            except json.JSONDecodeError:
                continue

    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        await kds_manager.disconnect(conn)


@router.websocket("/ws/salle")
async def ws_salle(
    websocket: WebSocket,
    ticket: str = Query(...),
):
    """WebSocket salle — reçoit alertes commande prête, envoie nouvelles commandes."""
    try:
        claims = await _authenticate_ws_ticket(ticket)
    except ValueError as e:
        await websocket.close(code=4001, reason=str(e))
        return

    conn = Connection(
        websocket=websocket,
        tenant_id=claims["tenant_id"],
        channel="salle",
        account_id=claims["account_id"],
        account_name=claims.get("name", ""),
    )

    await kds_manager.connect(conn)
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))

    try:
        await _send_initial_state(conn)

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                event = msg.get("event")

                if event == "pong":
                    continue

                if event == "nouvelle_commande":
                    await kds_manager.broadcast_to_channel(
                        conn.tenant_id, "kds", "nouvelle_commande", msg.get("data", {}),
                    )
                elif event == "commande_annulee":
                    await kds_manager.broadcast_to_channel(
                        conn.tenant_id, "kds", "commande_annulee", msg.get("data", {}),
                    )
                elif event == "commande_modifiee":
                    await kds_manager.broadcast_to_channel(
                        conn.tenant_id, "kds", "commande_modifiee", msg.get("data", {}),
                    )

            except json.JSONDecodeError:
                continue

    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        await kds_manager.disconnect(conn)
