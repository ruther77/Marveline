"""Service métier pour la gestion des peers WireGuard."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import (
    decrypt_value,
    derive_public_key,
    encrypt_value,
    generate_keypair,
    generate_preshared_key,
)
from app.models.peer import WgPeer
from app.repositories.audit_log import AuditLogRepository
from app.repositories.base import PaginatedResult
from app.repositories.ip_pool import IpPoolRepository
from app.repositories.peer import PeerRepository
from app.services.ip_allocator import IpAllocatorService, IpExhaustedError
from app.services.wireguard_backend import WireGuardBackend

logger = logging.getLogger(__name__)


class PeerServiceError(Exception):
    """Erreur métier du PeerService."""

    pass


class PeerNotFoundError(PeerServiceError):
    """Peer introuvable."""

    pass


class PeerLimitReachedError(PeerServiceError):
    """Limite de peers par tenant atteinte."""

    pass


class PeerService:
    """Gestion du cycle de vie complet des peers WireGuard.

    Orchestre : keygen → encrypt → allocate IP → WG backend → audit.
    """

    def __init__(
        self,
        session: Session,
        tenant_id: int,
        backend: WireGuardBackend,
        actor_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.backend = backend
        self.actor_id = actor_id
        self.ip_address = ip_address

        self.peer_repo = PeerRepository(session, tenant_id)
        self.ip_pool_repo = IpPoolRepository(session, tenant_id)
        self.audit_repo = AuditLogRepository(session, tenant_id)
        self.ip_allocator = IpAllocatorService(session, tenant_id)

        self._settings = get_settings()

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create_peer(
        self,
        name: str,
        description: Optional[str] = None,
        peer_type: str = "permanent",
        expires_at: Optional[datetime] = None,
        allowed_ips: str = "0.0.0.0/0",
        dns: Optional[str] = None,
        persistent_keepalive: Optional[int] = None,
        pool_id: Optional[int] = None,
    ) -> WgPeer:
        """Crée un nouveau peer WireGuard.

        Flow : keygen → encrypt private key → allocate IP → add to WG → audit.

        Raises:
            PeerLimitReachedError: Si le tenant a atteint la limite.
            IpExhaustedError: Plus d'IP disponibles.
        """
        # Vérifier la limite par tenant
        active_count = self.peer_repo.count_active()
        if active_count >= self._settings.PEER_MAX_PER_TENANT:
            raise PeerLimitReachedError(
                f"Limite de {self._settings.PEER_MAX_PER_TENANT} peers "
                f"atteinte pour le tenant {self.tenant_id}"
            )

        # Générer les clés
        private_key_b64, public_key_b64 = generate_keypair()
        preshared_key = generate_preshared_key()

        # Chiffrer la clé privée pour stockage DB
        encrypted_private_key = encrypt_value(
            private_key_b64, self._settings.ENCRYPTION_KEY
        )

        # Allouer une IP
        if pool_id is None:
            pool_id = self.ip_allocator.find_pool_with_capacity()
            if pool_id is None:
                raise IpExhaustedError(
                    "Aucun pool IP avec de la capacité disponible"
                )

        assigned_ip = self.ip_allocator.allocate_ip(pool_id)

        # Créer l'entité en DB
        peer = self.peer_repo.create(
            {
                "name": name,
                "description": description,
                "public_key": public_key_b64,
                "encrypted_private_key": encrypted_private_key,
                "preshared_key": preshared_key,
                "assigned_ip": assigned_ip,
                "allowed_ips": allowed_ips,
                "persistent_keepalive": persistent_keepalive
                or self._settings.PEER_DEFAULT_KEEPALIVE,
                "dns": dns or self._settings.WG_DNS,
                "peer_type": peer_type,
                "expires_at": expires_at,
                "created_by": self.actor_id,
                "is_enabled": True,
            }
        )

        # Ajouter au backend WireGuard
        self.backend.add_peer(
            interface=self._settings.WG_INTERFACE,
            public_key=public_key_b64,
            allowed_ips=assigned_ip,
            preshared_key=preshared_key,
            persistent_keepalive=peer.persistent_keepalive,
        )

        # Audit
        self.audit_repo.log_action(
            action="peer_created",
            peer_id=peer.id,
            actor_id=self.actor_id,
            details={
                "name": name,
                "peer_type": peer_type,
                "assigned_ip": assigned_ip,
            },
            ip_address=self.ip_address,
        )

        logger.info(
            "Peer created: %s (%s) ip=%s tenant=%d",
            peer.id,
            name,
            assigned_ip,
            self.tenant_id,
        )

        return peer

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_peer(self, peer_id: uuid.UUID) -> WgPeer:
        """Récupère un peer par son ID.

        Raises:
            PeerNotFoundError: Si le peer n'existe pas.
        """
        peer = self.peer_repo.get(peer_id)
        if peer is None:
            raise PeerNotFoundError(f"Peer {peer_id} introuvable")
        return peer

    def list_peers(
        self,
        page: int = 1,
        page_size: int = 20,
        include_inactive: bool = False,
    ) -> PaginatedResult[WgPeer]:
        """Liste les peers du tenant avec pagination."""
        return self.peer_repo.list_all_paginated(
            page=page,
            page_size=page_size,
            include_inactive=include_inactive,
        )

    def search_peers(
        self, search_term: str, page: int = 1, page_size: int = 20
    ) -> PaginatedResult[WgPeer]:
        """Recherche dans les peers du tenant."""
        return self.peer_repo.search(
            search_term=search_term, page=page, page_size=page_size
        )

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update_peer(
        self,
        peer_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        allowed_ips: Optional[str] = None,
        dns: Optional[str] = None,
        persistent_keepalive: Optional[int] = None,
        expires_at: Optional[datetime] = None,
    ) -> WgPeer:
        """Met à jour les métadonnées d'un peer.

        Ne modifie PAS les clés ni l'IP (utiliser rotate_keys pour ça).

        Raises:
            PeerNotFoundError: Si le peer n'existe pas.
        """
        peer = self.get_peer(peer_id)

        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if allowed_ips is not None:
            data["allowed_ips"] = allowed_ips
        if dns is not None:
            data["dns"] = dns
        if persistent_keepalive is not None:
            data["persistent_keepalive"] = persistent_keepalive
        if expires_at is not None:
            data["expires_at"] = expires_at

        if not data:
            return peer

        updated_peer = self.peer_repo.update(peer_id, data)

        # Audit
        self.audit_repo.log_action(
            action="peer_updated",
            peer_id=peer_id,
            actor_id=self.actor_id,
            details={"fields_updated": list(data.keys())},
            ip_address=self.ip_address,
        )

        logger.info(
            "Peer updated: %s fields=%s tenant=%d",
            peer_id,
            list(data.keys()),
            self.tenant_id,
        )

        return updated_peer

    # ------------------------------------------------------------------
    # DELETE (soft delete)
    # ------------------------------------------------------------------

    def delete_peer(self, peer_id: uuid.UUID) -> bool:
        """Supprime un peer (soft delete).

        Flow : revoke from WG backend → soft delete in DB → audit.

        Raises:
            PeerNotFoundError: Si le peer n'existe pas.
        """
        peer = self.get_peer(peer_id)

        # Retirer du backend WireGuard
        self.backend.remove_peer(
            interface=self._settings.WG_INTERFACE,
            public_key=peer.public_key,
        )

        # Soft delete en DB
        self.peer_repo.soft_delete(peer_id)

        # Audit
        self.audit_repo.log_action(
            action="peer_deleted",
            peer_id=peer_id,
            actor_id=self.actor_id,
            details={
                "name": peer.name,
                "assigned_ip": peer.assigned_ip,
            },
            ip_address=self.ip_address,
        )

        logger.info(
            "Peer deleted: %s (%s) tenant=%d",
            peer_id,
            peer.name,
            self.tenant_id,
        )

        return True

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------

    def rotate_keys(self, peer_id: uuid.UUID) -> WgPeer:
        """Rotation des clés d'un peer.

        Génère une nouvelle paire, retire l'ancien peer du backend,
        ajoute le nouveau, met à jour la DB.

        Raises:
            PeerNotFoundError: Si le peer n'existe pas.
        """
        peer = self.get_peer(peer_id)
        old_public_key = peer.public_key

        # Générer nouvelles clés
        new_private_key_b64, new_public_key_b64 = generate_keypair()
        new_preshared_key = generate_preshared_key()

        # Chiffrer la nouvelle clé privée
        encrypted_private_key = encrypt_value(
            new_private_key_b64, self._settings.ENCRYPTION_KEY
        )

        # Retirer l'ancien peer du backend
        self.backend.remove_peer(
            interface=self._settings.WG_INTERFACE,
            public_key=old_public_key,
        )

        # Mettre à jour la DB
        self.peer_repo.update(
            peer_id,
            {
                "public_key": new_public_key_b64,
                "encrypted_private_key": encrypted_private_key,
                "preshared_key": new_preshared_key,
            },
        )

        # Ajouter le nouveau peer au backend
        self.backend.add_peer(
            interface=self._settings.WG_INTERFACE,
            public_key=new_public_key_b64,
            allowed_ips=peer.assigned_ip,
            preshared_key=new_preshared_key,
            persistent_keepalive=peer.persistent_keepalive,
        )

        # Audit
        self.audit_repo.log_action(
            action="peer_keys_rotated",
            peer_id=peer_id,
            actor_id=self.actor_id,
            details={"old_public_key_prefix": old_public_key[:8]},
            ip_address=self.ip_address,
        )

        logger.info(
            "Peer keys rotated: %s tenant=%d", peer_id, self.tenant_id
        )

        # Refresh depuis la DB
        return self.get_peer(peer_id)

    def enable_peer(self, peer_id: uuid.UUID) -> WgPeer:
        """Active un peer (l'ajoute au backend WG).

        Raises:
            PeerNotFoundError: Si le peer n'existe pas.
        """
        peer = self.get_peer(peer_id)

        if peer.is_enabled:
            return peer

        # Mettre à jour la DB
        self.peer_repo.update(peer_id, {"is_enabled": True})

        # Ajouter au backend
        self.backend.add_peer(
            interface=self._settings.WG_INTERFACE,
            public_key=peer.public_key,
            allowed_ips=peer.assigned_ip,
            preshared_key=peer.preshared_key,
            persistent_keepalive=peer.persistent_keepalive,
        )

        # Audit
        self.audit_repo.log_action(
            action="peer_enabled",
            peer_id=peer_id,
            actor_id=self.actor_id,
            ip_address=self.ip_address,
        )

        logger.info(
            "Peer enabled: %s tenant=%d", peer_id, self.tenant_id
        )

        return self.get_peer(peer_id)

    def disable_peer(self, peer_id: uuid.UUID) -> WgPeer:
        """Désactive un peer (le retire du backend WG sans le supprimer).

        Raises:
            PeerNotFoundError: Si le peer n'existe pas.
        """
        peer = self.get_peer(peer_id)

        if not peer.is_enabled:
            return peer

        # Retirer du backend
        self.backend.remove_peer(
            interface=self._settings.WG_INTERFACE,
            public_key=peer.public_key,
        )

        # Mettre à jour la DB
        self.peer_repo.update(peer_id, {"is_enabled": False})

        # Audit
        self.audit_repo.log_action(
            action="peer_disabled",
            peer_id=peer_id,
            actor_id=self.actor_id,
            ip_address=self.ip_address,
        )

        logger.info(
            "Peer disabled: %s tenant=%d", peer_id, self.tenant_id
        )

        return self.get_peer(peer_id)

    def get_peer_private_key(self, peer_id: uuid.UUID) -> str:
        """Déchiffre et retourne la clé privée d'un peer.

        Utilisé uniquement pour la génération de config client.

        Raises:
            PeerNotFoundError: Si le peer n'existe pas.
        """
        peer = self.get_peer(peer_id)
        return decrypt_value(
            peer.encrypted_private_key, self._settings.ENCRYPTION_KEY
        )
