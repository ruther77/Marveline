"""Backend WireGuard — Strategy pattern.

Deux implémentations :
- MockWireGuardBackend : dict en mémoire pour dev/tests (pas de wg installé)
- LiveWireGuardBackend : subprocess wg set/show pour production (NET_ADMIN requis)
"""

import logging
import subprocess
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class PeerStats:
    """Statistiques d'un peer WireGuard."""

    public_key: str
    latest_handshake: int = 0  # Unix timestamp
    transfer_rx: int = 0  # bytes reçus
    transfer_tx: int = 0  # bytes envoyés
    persistent_keepalive: int = 0
    allowed_ips: str = ""
    endpoint: str = ""


@runtime_checkable
class WireGuardBackend(Protocol):
    """Interface pour les opérations WireGuard bas niveau."""

    def add_peer(
        self,
        interface: str,
        public_key: str,
        allowed_ips: str,
        preshared_key: str | None = None,
        persistent_keepalive: int = 25,
    ) -> bool:
        """Ajoute un peer à l'interface WireGuard.

        Returns:
            True si ajouté avec succès.
        """
        ...

    def remove_peer(self, interface: str, public_key: str) -> bool:
        """Retire un peer de l'interface WireGuard.

        Returns:
            True si retiré avec succès.
        """
        ...

    def get_peer_stats(self, interface: str, public_key: str) -> PeerStats | None:
        """Récupère les statistiques d'un peer.

        Returns:
            PeerStats ou None si le peer n'existe pas.
        """
        ...

    def list_peers(self, interface: str) -> list[PeerStats]:
        """Liste tous les peers de l'interface.

        Returns:
            Liste de PeerStats.
        """
        ...

    def is_available(self) -> bool:
        """Vérifie si le backend WireGuard est opérationnel.

        Returns:
            True si disponible.
        """
        ...


class MockWireGuardBackend:
    """Backend WireGuard simulé pour dev/tests.

    Stocke les peers en mémoire (dict). Aucune dépendance système.
    """

    def __init__(self) -> None:
        # {interface: {public_key: PeerStats}}
        self._peers: dict[str, dict[str, PeerStats]] = {}

    def add_peer(
        self,
        interface: str,
        public_key: str,
        allowed_ips: str,
        preshared_key: str | None = None,
        persistent_keepalive: int = 25,
    ) -> bool:
        if interface not in self._peers:
            self._peers[interface] = {}

        self._peers[interface][public_key] = PeerStats(
            public_key=public_key,
            allowed_ips=allowed_ips,
            persistent_keepalive=persistent_keepalive,
        )
        logger.info("MockWG: added peer %s on %s", public_key[:8], interface)
        return True

    def remove_peer(self, interface: str, public_key: str) -> bool:
        if interface in self._peers and public_key in self._peers[interface]:
            del self._peers[interface][public_key]
            logger.info("MockWG: removed peer %s from %s", public_key[:8], interface)
            return True
        logger.warning("MockWG: peer %s not found on %s", public_key[:8], interface)
        return False

    def get_peer_stats(self, interface: str, public_key: str) -> PeerStats | None:
        if interface in self._peers:
            return self._peers[interface].get(public_key)
        return None

    def list_peers(self, interface: str) -> list[PeerStats]:
        if interface not in self._peers:
            return []
        return list(self._peers[interface].values())

    def is_available(self) -> bool:
        return True


class LiveWireGuardBackend:
    """Backend WireGuard réel via subprocess.

    Nécessite :
    - wireguard-tools installé (commande `wg`)
    - Capability NET_ADMIN (Docker cap_add)
    - Interface wg0 déjà créée (via init_wg.sh)
    """

    def _run_wg(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        """Exécute une commande wg."""
        cmd = ["wg", *args]
        logger.debug("LiveWG: executing %s", " ".join(cmd))
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
            timeout=10,
        )

    def add_peer(
        self,
        interface: str,
        public_key: str,
        allowed_ips: str,
        preshared_key: str | None = None,
        persistent_keepalive: int = 25,
    ) -> bool:
        try:
            cmd_args = [
                "set", interface,
                "peer", public_key,
                "allowed-ips", allowed_ips,
                "persistent-keepalive", str(persistent_keepalive),
            ]

            if preshared_key:
                # preshared-key doit être passé via stdin ou fichier temporaire
                # On utilise un pipe via subprocess
                proc = subprocess.run(
                    ["wg", "set", interface,
                     "peer", public_key,
                     "allowed-ips", allowed_ips,
                     "persistent-keepalive", str(persistent_keepalive),
                     "preshared-key", "/dev/stdin"],
                    input=preshared_key,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )
            else:
                self._run_wg(*cmd_args)

            logger.info("LiveWG: added peer %s on %s", public_key[:8], interface)
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("LiveWG: failed to add peer: %s", exc.stderr)
            return False
        except subprocess.TimeoutExpired:
            logger.error("LiveWG: timeout adding peer %s", public_key[:8])
            return False

    def remove_peer(self, interface: str, public_key: str) -> bool:
        try:
            self._run_wg("set", interface, "peer", public_key, "remove")
            logger.info("LiveWG: removed peer %s from %s", public_key[:8], interface)
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("LiveWG: failed to remove peer: %s", exc.stderr)
            return False

    def get_peer_stats(self, interface: str, public_key: str) -> PeerStats | None:
        peers = self.list_peers(interface)
        for peer in peers:
            if peer.public_key == public_key:
                return peer
        return None

    def list_peers(self, interface: str) -> list[PeerStats]:
        """Parse la sortie de `wg show <interface> dump`."""
        try:
            result = self._run_wg("show", interface, "dump")
        except subprocess.CalledProcessError:
            logger.error("LiveWG: failed to list peers on %s", interface)
            return []

        peers = []
        lines = result.stdout.strip().split("\n")

        # Première ligne = interface info, les suivantes = peers
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 8:
                continue

            peers.append(PeerStats(
                public_key=parts[0],
                endpoint=parts[2] if parts[2] != "(none)" else "",
                allowed_ips=parts[3],
                latest_handshake=int(parts[4]) if parts[4] != "0" else 0,
                transfer_rx=int(parts[5]),
                transfer_tx=int(parts[6]),
                persistent_keepalive=int(parts[7]) if parts[7] != "off" else 0,
            ))

        return peers

    def is_available(self) -> bool:
        """Vérifie que la commande wg est disponible."""
        try:
            self._run_wg("--version", check=False)
            return True
        except FileNotFoundError:
            return False


def get_backend(backend_type: str = "mock") -> WireGuardBackend:
    """Factory pour obtenir le backend WireGuard approprié.

    Args:
        backend_type: "mock" ou "live"

    Returns:
        Instance de WireGuardBackend.
    """
    if backend_type == "live":
        backend = LiveWireGuardBackend()
        if not backend.is_available():
            logger.warning(
                "LiveWireGuardBackend demandé mais wg non disponible, "
                "fallback sur MockWireGuardBackend"
            )
            return MockWireGuardBackend()
        return backend
    return MockWireGuardBackend()
