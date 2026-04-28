"""Generateur de configuration client WireGuard.

Produit le fichier .conf et le QR code pour un peer.
"""

import io
import logging
from dataclasses import dataclass
from typing import Optional

import qrcode
from qrcode.image.pil import PilImage

logger = logging.getLogger(__name__)


@dataclass
class ClientConfig:
    """Configuration client WireGuard complete."""

    peer_name: str
    private_key: str
    address: str
    dns: str
    public_key_server: str
    endpoint: str
    preshared_key: Optional[str] = None
    allowed_ips: str = "0.0.0.0/0"
    persistent_keepalive: int = 25

    def to_conf(self) -> str:
        """Genere le contenu du fichier .conf WireGuard."""
        lines = [
            "[Interface]",
            f"PrivateKey = {self.private_key}",
            f"Address = {self.address}",
        ]

        if self.dns:
            lines.append(f"DNS = {self.dns}")

        lines.append("")
        lines.append("[Peer]")
        lines.append(f"PublicKey = {self.public_key_server}")

        if self.preshared_key:
            lines.append(f"PresharedKey = {self.preshared_key}")

        lines.append(f"AllowedIPs = {self.allowed_ips}")
        lines.append(f"Endpoint = {self.endpoint}")
        lines.append(f"PersistentKeepalive = {self.persistent_keepalive}")

        return "\n".join(lines) + "\n"


class ConfigGeneratorService:
    """Genere les configurations et QR codes pour les peers."""

    def __init__(
        self,
        server_public_key: str,
        server_endpoint: str,
        server_port: int,
    ) -> None:
        self.server_public_key = server_public_key
        self.server_endpoint = server_endpoint
        self.server_port = server_port

    def generate_config(
        self,
        peer_name: str,
        private_key: str,
        address: str,
        dns: str,
        preshared_key: Optional[str] = None,
        allowed_ips: str = "0.0.0.0/0",
        persistent_keepalive: int = 25,
    ) -> ClientConfig:
        """Construit un objet ClientConfig complet."""
        endpoint = f"{self.server_endpoint}:{self.server_port}"

        return ClientConfig(
            peer_name=peer_name,
            private_key=private_key,
            address=address,
            dns=dns,
            public_key_server=self.server_public_key,
            endpoint=endpoint,
            preshared_key=preshared_key,
            allowed_ips=allowed_ips,
            persistent_keepalive=persistent_keepalive,
        )

    def generate_conf_text(
        self,
        peer_name: str,
        private_key: str,
        address: str,
        dns: str,
        preshared_key: Optional[str] = None,
        allowed_ips: str = "0.0.0.0/0",
        persistent_keepalive: int = 25,
    ) -> str:
        """Genere le texte du fichier .conf."""
        config = self.generate_config(
            peer_name=peer_name,
            private_key=private_key,
            address=address,
            dns=dns,
            preshared_key=preshared_key,
            allowed_ips=allowed_ips,
            persistent_keepalive=persistent_keepalive,
        )
        return config.to_conf()

    def generate_qr_code(self, conf_text: str) -> bytes:
        """Genere un QR code PNG a partir du texte de configuration.

        Args:
            conf_text: Contenu du fichier .conf WireGuard.

        Returns:
            Bytes PNG du QR code.
        """
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(conf_text)
        qr.make(fit=True)

        img: PilImage = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer.getvalue()


def get_server_public_key(private_key: str) -> str:
    """Derive la cle publique serveur depuis la cle privee.

    Args:
        private_key: Cle privee WireGuard du serveur (base64).

    Returns:
        Cle publique serveur (base64).
    """
    from app.core.crypto import derive_public_key

    return derive_public_key(private_key)
