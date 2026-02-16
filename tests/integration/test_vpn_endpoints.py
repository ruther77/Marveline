"""Tests d'intégration pour les endpoints VPN proxy (WireGuard).

Les endpoints VPN sont des proxy vers le microservice WireGuard.
On mock le WireGuardClient pour tester la couche API sans dépendance
au service WG externe.
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.endpoints.vpn import _get_wg_client
from app.services.wireguard_client import WireGuardClientError


# ── Sample data ──────────────────────────────────────────────────────

SAMPLE_PEER = {
    "id": "abc-def-123",
    "tenant_id": 1,
    "name": "office-paris",
    "public_key": "WGpubkey12345678901234567890123456789ABC=",
    "assigned_ip": "10.0.0.2",
    "allowed_ips": "0.0.0.0/0",
    "dns": "1.1.1.1",
    "persistent_keepalive": 25,
    "peer_type": "client",
    "is_enabled": True,
    "is_active": True,
    "expires_at": None,
    "created_by": "42",
    "created_at": "2026-02-15T10:00:00",
    "updated_at": "2026-02-15T10:00:00",
}

SAMPLE_CONFIG = {
    "peer_name": "office-paris",
    "config_text": "[Interface]\nPrivateKey = ...\nAddress = 10.0.0.2/24\n",
    "filename": "office-paris.conf",
}

SAMPLE_STATUS = {
    "backend_available": True,
    "interface": "wg0",
    "active_peers_count": 3,
    "peers": [
        {
            "public_key": "WGpubkey12345678901234567890123456789ABC=",
            "latest_handshake": 1700000000,
            "transfer_rx": 1024000,
            "transfer_tx": 512000,
            "endpoint": "1.2.3.4:51820",
            "allowed_ips": "10.0.0.2/32",
        }
    ],
}

SAMPLE_IP_POOL = {
    "id": 1,
    "tenant_id": 1,
    "subnet": "10.0.0.0/24",
    "gateway_ip": "10.0.0.1",
    "next_ip": "10.0.0.3",
    "subnet_mask": 24,
    "description": "Main office pool",
    "created_at": "2026-02-15T10:00:00",
    "updated_at": "2026-02-15T10:00:00",
}


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_wg_client():
    """Override la dependance _get_wg_client pour retourner un mock.

    Autouse car _get_wg_client appelle get_settings().WG_SERVICE_URL
    qui n'est pas forcement configure dans l'environnement de test.
    """
    mock_client = MagicMock()
    app.dependency_overrides[_get_wg_client] = lambda: mock_client
    yield mock_client
    # cleanup: la fixture client() fait app.dependency_overrides.clear()


# ── POST /vpn/peers ──────────────────────────────────────────────────


class TestCreateVpnPeer:
    """Tests POST /api/v1/vpn/peers."""

    def test_create_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Creation d'un peer retourne 201."""
        mock_wg_client.create_peer.return_value = SAMPLE_PEER

        response = client.post(
            "/api/v1/vpn/peers",
            json={"name": "office-paris", "peer_type": "client"},
            headers=auth_headers_admin,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "office-paris"
        assert data["peer_type"] == "client"
        assert data["public_key"] == SAMPLE_PEER["public_key"]
        mock_wg_client.create_peer.assert_called_once()

    def test_create_with_all_fields(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Creation avec tous les champs optionnels."""
        mock_wg_client.create_peer.return_value = {
            **SAMPLE_PEER,
            "name": "warehouse",
            "peer_type": "site",
            "dns": "8.8.8.8",
            "persistent_keepalive": 30,
        }

        response = client.post(
            "/api/v1/vpn/peers",
            json={
                "name": "warehouse",
                "peer_type": "site",
                "allowed_ips": "10.0.1.0/24",
                "dns": "8.8.8.8",
                "persistent_keepalive": 30,
            },
            headers=auth_headers_admin,
        )
        assert response.status_code == 201
        assert response.json()["peer_type"] == "site"

    def test_create_invalid_peer_type_422(self, client: TestClient, auth_headers_admin):
        """peer_type invalide retourne 422."""
        response = client.post(
            "/api/v1/vpn/peers",
            json={"name": "bad", "peer_type": "invalid_type"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 422

    def test_create_empty_name_422(self, client: TestClient, auth_headers_admin):
        """Nom vide retourne 422."""
        response = client.post(
            "/api/v1/vpn/peers",
            json={"name": "", "peer_type": "client"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 422

    def test_create_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:write -> 403."""
        response = client.post(
            "/api/v1/vpn/peers",
            json={"name": "no_perm", "peer_type": "client"},
            headers=auth_headers_real,
        )
        assert response.status_code == 403

    def test_create_unauthenticated_401(self, client: TestClient):
        """Sans auth -> 401."""
        response = client.post(
            "/api/v1/vpn/peers",
            json={"name": "no_auth", "peer_type": "client"},
        )
        assert response.status_code == 401

    def test_create_wg_error_forwarded(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Erreur WG service propagee avec le bon status code."""
        mock_wg_client.create_peer.side_effect = WireGuardClientError("IP pool exhausted", 409)

        response = client.post(
            "/api/v1/vpn/peers",
            json={"name": "office", "peer_type": "client"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 409
        assert "IP pool exhausted" in response.json()["detail"]


# ── GET /vpn/peers ───────────────────────────────────────────────────


class TestListVpnPeers:
    """Tests GET /api/v1/vpn/peers."""

    def test_list_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Liste les peers du tenant."""
        mock_wg_client.list_peers.return_value = {
            "items": [SAMPLE_PEER],
            "total": 1,
        }

        response = client.get("/api/v1/vpn/peers", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "office-paris"

    def test_list_empty(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Liste vide quand aucun peer n'existe."""
        mock_wg_client.list_peers.return_value = {"items": [], "total": 0}

        response = client.get("/api/v1/vpn/peers", headers=auth_headers_admin)
        assert response.status_code == 200
        assert response.json()["total"] == 0
        assert response.json()["items"] == []

    def test_list_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:read -> 403."""
        response = client.get("/api/v1/vpn/peers", headers=auth_headers_real)
        assert response.status_code == 403

    def test_list_wg_unavailable_503(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """WG service indisponible -> 503."""
        mock_wg_client.list_peers.side_effect = WireGuardClientError(
            "WireGuard service unavailable", 503
        )

        response = client.get("/api/v1/vpn/peers", headers=auth_headers_admin)
        assert response.status_code == 503


# ── GET /vpn/peers/{peer_id} ─────────────────────────────────────────


class TestGetVpnPeer:
    """Tests GET /api/v1/vpn/peers/{peer_id}."""

    def test_get_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Recuperation d'un peer par ID."""
        mock_wg_client.get_peer.return_value = SAMPLE_PEER

        response = client.get("/api/v1/vpn/peers/abc-def-123", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "abc-def-123"
        assert data["name"] == "office-paris"
        assert data["assigned_ip"] == "10.0.0.2"

    def test_get_not_found_404(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Peer inexistant -> 404."""
        mock_wg_client.get_peer.side_effect = WireGuardClientError("Peer not found", 404)

        response = client.get("/api/v1/vpn/peers/nonexistent", headers=auth_headers_admin)
        assert response.status_code == 404

    def test_get_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:read -> 403."""
        response = client.get("/api/v1/vpn/peers/abc-def-123", headers=auth_headers_real)
        assert response.status_code == 403


# ── PATCH /vpn/peers/{peer_id} ───────────────────────────────────────


class TestUpdateVpnPeer:
    """Tests PATCH /api/v1/vpn/peers/{peer_id}."""

    def test_update_name(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Mise a jour du nom."""
        mock_wg_client.update_peer.return_value = {**SAMPLE_PEER, "name": "new-name"}

        response = client.patch(
            "/api/v1/vpn/peers/abc-def-123",
            json={"name": "new-name"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "new-name"

    def test_update_multiple_fields(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Mise a jour de plusieurs champs."""
        mock_wg_client.update_peer.return_value = {
            **SAMPLE_PEER,
            "dns": "8.8.4.4",
            "persistent_keepalive": 60,
        }

        response = client.patch(
            "/api/v1/vpn/peers/abc-def-123",
            json={"dns": "8.8.4.4", "persistent_keepalive": 60},
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        assert response.json()["dns"] == "8.8.4.4"

    def test_update_not_found_404(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Update d'un peer inexistant -> 404."""
        mock_wg_client.update_peer.side_effect = WireGuardClientError("Peer not found", 404)

        response = client.patch(
            "/api/v1/vpn/peers/nonexistent",
            json={"name": "nope"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 404

    def test_update_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:write -> 403."""
        response = client.patch(
            "/api/v1/vpn/peers/abc-def-123",
            json={"name": "nope"},
            headers=auth_headers_real,
        )
        assert response.status_code == 403


# ── DELETE /vpn/peers/{peer_id} ──────────────────────────────────────


class TestDeleteVpnPeer:
    """Tests DELETE /api/v1/vpn/peers/{peer_id}."""

    def test_delete_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Suppression retourne 204."""
        mock_wg_client.delete_peer.return_value = None

        response = client.delete("/api/v1/vpn/peers/abc-def-123", headers=auth_headers_admin)
        assert response.status_code == 204
        mock_wg_client.delete_peer.assert_called_once_with("abc-def-123")

    def test_delete_not_found_404(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Suppression d'un peer inexistant -> 404."""
        mock_wg_client.delete_peer.side_effect = WireGuardClientError("Peer not found", 404)

        response = client.delete("/api/v1/vpn/peers/nonexistent", headers=auth_headers_admin)
        assert response.status_code == 404

    def test_delete_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:admin -> 403."""
        response = client.delete("/api/v1/vpn/peers/abc-def-123", headers=auth_headers_real)
        assert response.status_code == 403

    def test_delete_unauthenticated_401(self, client: TestClient):
        """Sans auth -> 401."""
        response = client.delete("/api/v1/vpn/peers/abc-def-123")
        assert response.status_code == 401


# ── POST /vpn/peers/{peer_id}/rotate ─────────────────────────────────


class TestRotateVpnPeerKeys:
    """Tests POST /api/v1/vpn/peers/{peer_id}/rotate."""

    def test_rotate_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Rotation des cles genere une nouvelle public key."""
        rotated_peer = {
            **SAMPLE_PEER,
            "public_key": "NEWpubkey123456789012345678901234567890XY=",
        }
        mock_wg_client.rotate_peer_keys.return_value = rotated_peer

        response = client.post("/api/v1/vpn/peers/abc-def-123/rotate", headers=auth_headers_admin)
        assert response.status_code == 200
        assert response.json()["public_key"] == "NEWpubkey123456789012345678901234567890XY="

    def test_rotate_not_found_404(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Rotation d'un peer inexistant -> 404."""
        mock_wg_client.rotate_peer_keys.side_effect = WireGuardClientError("Peer not found", 404)

        response = client.post("/api/v1/vpn/peers/nonexistent/rotate", headers=auth_headers_admin)
        assert response.status_code == 404

    def test_rotate_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:admin -> 403."""
        response = client.post("/api/v1/vpn/peers/abc-def-123/rotate", headers=auth_headers_real)
        assert response.status_code == 403


# ── POST /vpn/peers/{peer_id}/enable ─────────────────────────────────


class TestEnableVpnPeer:
    """Tests POST /api/v1/vpn/peers/{peer_id}/enable."""

    def test_enable_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Activation d'un peer retourne is_enabled=true."""
        mock_wg_client.enable_peer.return_value = {**SAMPLE_PEER, "is_enabled": True}

        response = client.post("/api/v1/vpn/peers/abc-def-123/enable", headers=auth_headers_admin)
        assert response.status_code == 200
        assert response.json()["is_enabled"] is True

    def test_enable_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:write -> 403."""
        response = client.post("/api/v1/vpn/peers/abc-def-123/enable", headers=auth_headers_real)
        assert response.status_code == 403


# ── POST /vpn/peers/{peer_id}/disable ────────────────────────────────


class TestDisableVpnPeer:
    """Tests POST /api/v1/vpn/peers/{peer_id}/disable."""

    def test_disable_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Desactivation d'un peer retourne is_enabled=false."""
        mock_wg_client.disable_peer.return_value = {**SAMPLE_PEER, "is_enabled": False}

        response = client.post("/api/v1/vpn/peers/abc-def-123/disable", headers=auth_headers_admin)
        assert response.status_code == 200
        assert response.json()["is_enabled"] is False

    def test_disable_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:write -> 403."""
        response = client.post("/api/v1/vpn/peers/abc-def-123/disable", headers=auth_headers_real)
        assert response.status_code == 403


# ── GET /vpn/peers/{peer_id}/config ──────────────────────────────────


class TestGetVpnPeerConfig:
    """Tests GET /api/v1/vpn/peers/{peer_id}/config."""

    def test_config_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Recuperation de la configuration WireGuard."""
        mock_wg_client.get_peer_config.return_value = SAMPLE_CONFIG

        response = client.get("/api/v1/vpn/peers/abc-def-123/config", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["peer_name"] == "office-paris"
        assert "PrivateKey" in data["config_text"]
        assert data["filename"] == "office-paris.conf"

    def test_config_not_found_404(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Config d'un peer inexistant -> 404."""
        mock_wg_client.get_peer_config.side_effect = WireGuardClientError("Peer not found", 404)

        response = client.get("/api/v1/vpn/peers/nonexistent/config", headers=auth_headers_admin)
        assert response.status_code == 404

    def test_config_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:read -> 403."""
        response = client.get("/api/v1/vpn/peers/abc-def-123/config", headers=auth_headers_real)
        assert response.status_code == 403


# ── GET /vpn/peers/{peer_id}/qrcode ──────────────────────────────────


class TestGetVpnPeerQrcode:
    """Tests GET /api/v1/vpn/peers/{peer_id}/qrcode."""

    def test_qrcode_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Recuperation du QR code en PNG."""
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_wg_client.get_peer_qrcode.return_value = fake_png

        response = client.get("/api/v1/vpn/peers/abc-def-123/qrcode", headers=auth_headers_admin)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert len(response.content) > 0

    def test_qrcode_not_found_404(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """QR code d'un peer inexistant -> 404."""
        mock_wg_client.get_peer_qrcode.side_effect = WireGuardClientError("Peer not found", 404)

        response = client.get("/api/v1/vpn/peers/nonexistent/qrcode", headers=auth_headers_admin)
        assert response.status_code == 404

    def test_qrcode_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:read -> 403."""
        response = client.get("/api/v1/vpn/peers/abc-def-123/qrcode", headers=auth_headers_real)
        assert response.status_code == 403


# ── GET /vpn/status ──────────────────────────────────────────────────


class TestGetVpnStatus:
    """Tests GET /api/v1/vpn/status."""

    def test_status_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Statut du serveur WireGuard."""
        mock_wg_client.get_status.return_value = SAMPLE_STATUS

        response = client.get("/api/v1/vpn/status", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["backend_available"] is True
        assert data["interface"] == "wg0"
        assert data["active_peers_count"] == 3
        assert len(data["peers"]) == 1

    def test_status_wg_unavailable_503(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """WG service indisponible -> 503."""
        mock_wg_client.get_status.side_effect = WireGuardClientError(
            "WireGuard service unavailable", 503
        )

        response = client.get("/api/v1/vpn/status", headers=auth_headers_admin)
        assert response.status_code == 503

    def test_status_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:read -> 403."""
        response = client.get("/api/v1/vpn/status", headers=auth_headers_real)
        assert response.status_code == 403

    def test_status_unauthenticated_401(self, client: TestClient):
        """Sans auth -> 401."""
        response = client.get("/api/v1/vpn/status")
        assert response.status_code == 401


# ── GET /vpn/ip-pools ────────────────────────────────────────────────


class TestListVpnIpPools:
    """Tests GET /api/v1/vpn/ip-pools."""

    def test_list_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Liste les pools IP du tenant."""
        mock_wg_client.list_ip_pools.return_value = {
            "items": [SAMPLE_IP_POOL],
            "total": 1,
        }

        response = client.get("/api/v1/vpn/ip-pools", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["subnet"] == "10.0.0.0/24"
        assert data["items"][0]["gateway_ip"] == "10.0.0.1"

    def test_list_empty(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Liste vide quand aucun pool n'existe."""
        mock_wg_client.list_ip_pools.return_value = {"items": [], "total": 0}

        response = client.get("/api/v1/vpn/ip-pools", headers=auth_headers_admin)
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:read -> 403."""
        response = client.get("/api/v1/vpn/ip-pools", headers=auth_headers_real)
        assert response.status_code == 403


# ── POST /vpn/ip-pools ───────────────────────────────────────────────


class TestCreateVpnIpPool:
    """Tests POST /api/v1/vpn/ip-pools."""

    def test_create_success(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Creation d'un pool IP retourne 201."""
        mock_wg_client.create_ip_pool.return_value = SAMPLE_IP_POOL

        response = client.post(
            "/api/v1/vpn/ip-pools",
            json={
                "subnet": "10.0.0.0/24",
                "gateway_ip": "10.0.0.1",
                "description": "Main office pool",
            },
            headers=auth_headers_admin,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subnet"] == "10.0.0.0/24"
        assert data["gateway_ip"] == "10.0.0.1"
        assert data["description"] == "Main office pool"

    def test_create_invalid_subnet_422(self, client: TestClient, auth_headers_admin):
        """Subnet invalide retourne 422."""
        response = client.post(
            "/api/v1/vpn/ip-pools",
            json={"subnet": "not-a-cidr", "gateway_ip": "10.0.0.1"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 422

    def test_create_missing_gateway_422(self, client: TestClient, auth_headers_admin):
        """gateway_ip manquant retourne 422."""
        response = client.post(
            "/api/v1/vpn/ip-pools",
            json={"subnet": "10.0.0.0/24"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 422

    def test_create_staff_forbidden(self, client: TestClient, auth_headers_real):
        """Un staff n'a pas la permission vpn:admin -> 403."""
        response = client.post(
            "/api/v1/vpn/ip-pools",
            json={"subnet": "10.0.0.0/24", "gateway_ip": "10.0.0.1"},
            headers=auth_headers_real,
        )
        assert response.status_code == 403

    def test_create_unauthenticated_401(self, client: TestClient):
        """Sans auth -> 401."""
        response = client.post(
            "/api/v1/vpn/ip-pools",
            json={"subnet": "10.0.0.0/24", "gateway_ip": "10.0.0.1"},
        )
        assert response.status_code == 401

    def test_create_wg_error_forwarded(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """Erreur WG service propagee (ex: subnet duplique)."""
        mock_wg_client.create_ip_pool.side_effect = WireGuardClientError(
            "Duplicate subnet", 409
        )

        response = client.post(
            "/api/v1/vpn/ip-pools",
            json={"subnet": "10.0.0.0/24", "gateway_ip": "10.0.0.1"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 409
        assert "Duplicate subnet" in response.json()["detail"]


# ── Error handling ───────────────────────────────────────────────────


class TestWgErrorHandling:
    """Tests de propagation des erreurs du WG service."""

    def test_timeout_504(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """WG service timeout -> 504."""
        mock_wg_client.list_peers.side_effect = WireGuardClientError(
            "WireGuard service timeout", 504
        )

        response = client.get("/api/v1/vpn/peers", headers=auth_headers_admin)
        assert response.status_code == 504
        assert "timeout" in response.json()["detail"].lower()

    def test_bad_gateway_502(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """WG service bad gateway -> 502."""
        mock_wg_client.get_peer.side_effect = WireGuardClientError("Bad gateway", 502)

        response = client.get("/api/v1/vpn/peers/some-id", headers=auth_headers_admin)
        assert response.status_code == 502

    def test_internal_error_500(self, client: TestClient, auth_headers_admin, mock_wg_client):
        """WG service erreur interne -> 500."""
        mock_wg_client.get_status.side_effect = WireGuardClientError(
            "Internal server error", 500
        )

        response = client.get("/api/v1/vpn/status", headers=auth_headers_admin)
        assert response.status_code == 500
