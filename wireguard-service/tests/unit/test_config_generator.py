"""Tests pour le generateur de configuration client WireGuard."""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_GEN_FILE = PROJECT_ROOT / "app" / "services" / "config_generator.py"
CONFIG_SCHEMA_FILE = PROJECT_ROOT / "app" / "schemas" / "config.py"
CONFIG_ENDPOINT_FILE = PROJECT_ROOT / "app" / "api" / "v1" / "config.py"
ROUTER_FILE = PROJECT_ROOT / "app" / "api" / "v1" / "router.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests structurels — ConfigGeneratorService (analyse source)
# ---------------------------------------------------------------------------


class TestConfigGeneratorStructure:
    """Verifie la structure du service config_generator."""

    def test_file_exists(self):
        assert CONFIG_GEN_FILE.exists()

    def test_imports_qrcode(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "import qrcode" in source

    def test_imports_io(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "import io" in source

    def test_client_config_dataclass(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "@dataclass" in source
        assert "class ClientConfig:" in source

    def test_client_config_fields(self):
        source = _read_source(CONFIG_GEN_FILE)
        for field in [
            "peer_name",
            "private_key",
            "address",
            "dns",
            "public_key_server",
            "endpoint",
            "preshared_key",
            "allowed_ips",
            "persistent_keepalive",
        ]:
            assert field in source, f"ClientConfig missing field: {field}"

    def test_to_conf_method(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "def to_conf(self)" in source

    def test_to_conf_generates_interface_section(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert '"[Interface]"' in source
        assert '"PrivateKey = "' in source or "PrivateKey" in source
        assert '"Address = "' in source or "Address" in source

    def test_to_conf_generates_peer_section(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert '"[Peer]"' in source
        assert '"PublicKey = "' in source or "PublicKey" in source
        assert '"AllowedIPs = "' in source or "AllowedIPs" in source
        assert '"Endpoint = "' in source or "Endpoint" in source
        assert "PersistentKeepalive" in source

    def test_to_conf_handles_dns(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "DNS" in source

    def test_to_conf_handles_preshared_key(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "PresharedKey" in source


class TestConfigGeneratorServiceStructure:
    """Verifie la structure de la classe ConfigGeneratorService."""

    def test_class_exists(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "class ConfigGeneratorService:" in source

    def test_init_params(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "server_public_key" in source
        assert "server_endpoint" in source
        assert "server_port" in source

    def test_generate_config_method(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "def generate_config(" in source

    def test_generate_conf_text_method(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "def generate_conf_text(" in source

    def test_generate_qr_code_method(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "def generate_qr_code(" in source

    def test_qr_code_returns_bytes(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "-> bytes" in source

    def test_qr_code_uses_png_format(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert 'format="PNG"' in source

    def test_qr_code_uses_bytesio(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "BytesIO" in source

    def test_get_server_public_key_function(self):
        source = _read_source(CONFIG_GEN_FILE)
        assert "def get_server_public_key(" in source
        assert "derive_public_key" in source


# ---------------------------------------------------------------------------
# Tests structurels — Config schema
# ---------------------------------------------------------------------------


class TestConfigSchemaStructure:
    """Verifie la structure du schema config."""

    def test_file_exists(self):
        assert CONFIG_SCHEMA_FILE.exists()

    def test_client_config_response(self):
        source = _read_source(CONFIG_SCHEMA_FILE)
        assert "class ClientConfigResponse(BaseModel):" in source

    def test_schema_fields(self):
        source = _read_source(CONFIG_SCHEMA_FILE)
        assert "peer_name" in source
        assert "config_text" in source
        assert "filename" in source


# ---------------------------------------------------------------------------
# Tests structurels — Config endpoints
# ---------------------------------------------------------------------------


class TestConfigEndpointStructure:
    """Verifie la structure des endpoints config."""

    def test_file_exists(self):
        assert CONFIG_ENDPOINT_FILE.exists()

    def test_router_defined(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert 'router = APIRouter(prefix="/peers"' in source

    def test_router_has_config_tag(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert 'tags=["config"]' in source

    def test_get_config_endpoint(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "/{peer_id}/config" in source
        assert "def get_peer_config(" in source

    def test_get_config_returns_client_config_response(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "response_model=ClientConfigResponse" in source

    def test_get_qrcode_endpoint(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "/{peer_id}/qrcode" in source
        assert "def get_peer_qrcode(" in source

    def test_qrcode_returns_png(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "image/png" in source

    def test_qrcode_uses_response(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "from fastapi.responses import Response" in source
        assert "Response(" in source

    def test_imports_peer_service(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "from app.services.peer_service import" in source
        assert "PeerNotFoundError" in source

    def test_imports_config_generator(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "from app.services.config_generator import" in source
        assert "ConfigGeneratorService" in source
        assert "get_server_public_key" in source

    def test_imports_auth_dependency(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "from app.core.deps import" in source
        assert "get_internal_auth" in source

    def test_get_peer_service_dependency(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "def _get_peer_service(" in source

    def test_get_config_generator_dependency(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "def _get_config_generator(" in source

    def test_handles_404(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "HTTP_404_NOT_FOUND" in source

    def test_decrypts_private_key(self):
        """L'endpoint doit dechiffrer la cle privee pour generer le .conf."""
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "get_peer_private_key" in source

    def test_sanitizes_filename(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "def _sanitize_filename(" in source
        assert ".conf" in source

    def test_qrcode_content_disposition(self):
        source = _read_source(CONFIG_ENDPOINT_FILE)
        assert "Content-Disposition" in source


class TestConfigRouterIntegration:
    """Verifie que le router config est integre."""

    def test_router_includes_config(self):
        source = _read_source(ROUTER_FILE)
        assert "config_router" in source or "config.router" in source

    def test_router_imports_config(self):
        source = _read_source(ROUTER_FILE)
        assert "from app.api.v1.config import" in source


# ---------------------------------------------------------------------------
# Tests fonctionnels — ClientConfig.to_conf()
# ---------------------------------------------------------------------------


class TestClientConfigToConf:
    """Tests fonctionnels pour la generation du fichier .conf."""

    def _make_config(self, **overrides):
        """Helper pour creer un ClientConfig avec des valeurs par defaut."""
        try:
            from app.services.config_generator import ClientConfig
        except ImportError:
            pytest.skip("config_generator not importable locally")

        defaults = {
            "peer_name": "test-peer",
            "private_key": "cHJpdmF0ZS1rZXktYmFzZTY0LWVuY29kZWQ=",
            "address": "10.10.0.2/32",
            "dns": "1.1.1.1,8.8.8.8",
            "public_key_server": "c2VydmVyLXB1YmxpYy1rZXktYmFzZTY0",
            "endpoint": "vpn.example.com:51820",
            "preshared_key": None,
            "allowed_ips": "0.0.0.0/0",
            "persistent_keepalive": 25,
        }
        defaults.update(overrides)
        return ClientConfig(**defaults)

    def test_contains_interface_section(self):
        config = self._make_config()
        text = config.to_conf()
        assert "[Interface]" in text

    def test_contains_peer_section(self):
        config = self._make_config()
        text = config.to_conf()
        assert "[Peer]" in text

    def test_contains_private_key(self):
        config = self._make_config()
        text = config.to_conf()
        assert "PrivateKey = cHJpdmF0ZS1rZXktYmFzZTY0LWVuY29kZWQ=" in text

    def test_contains_address(self):
        config = self._make_config()
        text = config.to_conf()
        assert "Address = 10.10.0.2/32" in text

    def test_contains_dns(self):
        config = self._make_config()
        text = config.to_conf()
        assert "DNS = 1.1.1.1,8.8.8.8" in text

    def test_no_dns_when_empty(self):
        config = self._make_config(dns="")
        text = config.to_conf()
        assert "DNS" not in text

    def test_contains_server_public_key(self):
        config = self._make_config()
        text = config.to_conf()
        assert "PublicKey = c2VydmVyLXB1YmxpYy1rZXktYmFzZTY0" in text

    def test_contains_allowed_ips(self):
        config = self._make_config()
        text = config.to_conf()
        assert "AllowedIPs = 0.0.0.0/0" in text

    def test_contains_endpoint(self):
        config = self._make_config()
        text = config.to_conf()
        assert "Endpoint = vpn.example.com:51820" in text

    def test_contains_persistent_keepalive(self):
        config = self._make_config()
        text = config.to_conf()
        assert "PersistentKeepalive = 25" in text

    def test_contains_preshared_key_when_set(self):
        config = self._make_config(preshared_key="cHJlc2hhcmVkLWtleQ==")
        text = config.to_conf()
        assert "PresharedKey = cHJlc2hhcmVkLWtleQ==" in text

    def test_no_preshared_key_when_none(self):
        config = self._make_config(preshared_key=None)
        text = config.to_conf()
        assert "PresharedKey" not in text

    def test_ends_with_newline(self):
        config = self._make_config()
        text = config.to_conf()
        assert text.endswith("\n")

    def test_interface_before_peer(self):
        config = self._make_config()
        text = config.to_conf()
        assert text.index("[Interface]") < text.index("[Peer]")


class TestConfigGeneratorServiceFunctional:
    """Tests fonctionnels pour ConfigGeneratorService."""

    def _make_service(self):
        try:
            from app.services.config_generator import ConfigGeneratorService
        except ImportError:
            pytest.skip("config_generator not importable locally")

        return ConfigGeneratorService(
            server_public_key="c2VydmVyLXB1YmxpYy1rZXk=",
            server_endpoint="vpn.example.com",
            server_port=51820,
        )

    def test_generate_config_returns_client_config(self):
        svc = self._make_service()
        from app.services.config_generator import ClientConfig

        config = svc.generate_config(
            peer_name="test",
            private_key="cHJpdmF0ZQ==",
            address="10.10.0.2/32",
            dns="1.1.1.1",
        )
        assert isinstance(config, ClientConfig)

    def test_generate_config_sets_endpoint(self):
        svc = self._make_service()
        config = svc.generate_config(
            peer_name="test",
            private_key="cHJpdmF0ZQ==",
            address="10.10.0.2/32",
            dns="1.1.1.1",
        )
        assert config.endpoint == "vpn.example.com:51820"

    def test_generate_conf_text_returns_string(self):
        svc = self._make_service()
        text = svc.generate_conf_text(
            peer_name="test",
            private_key="cHJpdmF0ZQ==",
            address="10.10.0.2/32",
            dns="1.1.1.1",
        )
        assert isinstance(text, str)
        assert "[Interface]" in text
        assert "[Peer]" in text


class TestQrCodeGeneration:
    """Tests fonctionnels pour la generation QR code."""

    def _make_service(self):
        try:
            from app.services.config_generator import ConfigGeneratorService
        except ImportError:
            pytest.skip("config_generator not importable locally")

        return ConfigGeneratorService(
            server_public_key="c2VydmVyLXB1YmxpYy1rZXk=",
            server_endpoint="vpn.example.com",
            server_port=51820,
        )

    def test_generate_qr_code_returns_bytes(self):
        try:
            import qrcode  # noqa: F401
        except ImportError:
            pytest.skip("qrcode not installed locally")

        svc = self._make_service()
        qr_bytes = svc.generate_qr_code("[Interface]\nPrivateKey = test\n")
        assert isinstance(qr_bytes, bytes)

    def test_generate_qr_code_is_png(self):
        try:
            import qrcode  # noqa: F401
        except ImportError:
            pytest.skip("qrcode not installed locally")

        svc = self._make_service()
        qr_bytes = svc.generate_qr_code("[Interface]\nPrivateKey = test\n")
        # PNG magic bytes
        assert qr_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_generate_qr_code_non_empty(self):
        try:
            import qrcode  # noqa: F401
        except ImportError:
            pytest.skip("qrcode not installed locally")

        svc = self._make_service()
        qr_bytes = svc.generate_qr_code("[Interface]\nPrivateKey = test\n")
        assert len(qr_bytes) > 100
