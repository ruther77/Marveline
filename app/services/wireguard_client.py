"""Client HTTP pour le microservice WireGuard.

Proxy les requetes depuis l'API Marveline vers le WG service interne.
Ajoute automatiquement les headers d'authentification inter-service.
"""

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Timeout pour les requetes vers le WG service (secondes)
WG_REQUEST_TIMEOUT = 10.0


class WireGuardClientError(Exception):
    """Erreur de communication avec le WG service."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class WireGuardClient:
    """Client HTTP synchrone vers le microservice WireGuard.

    Usage:
        client = WireGuardClient(tenant_id=1, actor_id="42")
        peers = client.list_peers()
        peer = client.create_peer({"name": "office-paris", "peer_type": "site"})
    """

    def __init__(self, tenant_id: int, actor_id: str) -> None:
        settings = get_settings()
        self._base_url = settings.WG_SERVICE_URL.rstrip("/")
        self._headers = {
            "X-Internal-API-Key": settings.WG_INTERNAL_API_KEY,
            "X-Tenant-ID": str(tenant_id),
            "X-Actor-ID": actor_id,
            "Content-Type": "application/json",
        }
        self._timeout = WG_REQUEST_TIMEOUT

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute une requete HTTP vers le WG service.

        Returns:
            Response JSON parsed.

        Raises:
            WireGuardClientError: Si le WG service est inaccessible ou retourne une erreur.
        """
        url = f"{self._base_url}/wg/v1{path}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    json=json,
                    params=params,
                )
        except httpx.ConnectError:
            logger.error("WG service unreachable at %s", self._base_url)
            raise WireGuardClientError(
                "WireGuard service unavailable",
                status_code=503,
            )
        except httpx.TimeoutException:
            logger.error("WG service timeout for %s %s", method, path)
            raise WireGuardClientError(
                "WireGuard service timeout",
                status_code=504,
            )

        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                logger.debug("Failed to parse WG error response as JSON")
            raise WireGuardClientError(
                message=str(detail),
                status_code=response.status_code,
            )

        if response.status_code == 204:
            return None

        return response.json()

    def _request_raw(self, method: str, path: str) -> httpx.Response:
        """Execute une requete et retourne la Response brute (pour binary content)."""
        url = f"{self._base_url}/wg/v1{path}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                )
        except httpx.ConnectError:
            raise WireGuardClientError("WireGuard service unavailable", 503)
        except httpx.TimeoutException:
            raise WireGuardClientError("WireGuard service timeout", 504)

        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                logger.debug("Failed to parse WG error response as JSON")
            raise WireGuardClientError(str(detail), response.status_code)

        return response

    # ── Peers ──────────────────────────────────────────────────────────

    def list_peers(self) -> dict[str, Any]:
        return self._request("GET", "/peers")

    def get_peer(self, peer_id: str) -> dict[str, Any]:
        return self._request("GET", f"/peers/{peer_id}")

    def create_peer(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/peers", json=data)

    def update_peer(self, peer_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/peers/{peer_id}", json=data)

    def delete_peer(self, peer_id: str) -> None:
        self._request("DELETE", f"/peers/{peer_id}")

    def rotate_peer_keys(self, peer_id: str) -> dict[str, Any]:
        return self._request("POST", f"/peers/{peer_id}/rotate")

    def enable_peer(self, peer_id: str) -> dict[str, Any]:
        return self._request("POST", f"/peers/{peer_id}/enable")

    def disable_peer(self, peer_id: str) -> dict[str, Any]:
        return self._request("POST", f"/peers/{peer_id}/disable")

    # ── Config & QR ───────────────────────────────────────────────────

    def get_peer_config(self, peer_id: str) -> dict[str, Any]:
        return self._request("GET", f"/peers/{peer_id}/config")

    def get_peer_qrcode(self, peer_id: str) -> bytes:
        response = self._request_raw("GET", f"/peers/{peer_id}/qrcode")
        return response.content

    # ── Status ────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        return self._request("GET", "/status")

    # ── IP Pools ──────────────────────────────────────────────────────

    def list_ip_pools(self) -> dict[str, Any]:
        return self._request("GET", "/ip-pools")

    def create_ip_pool(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/ip-pools", json=data)
