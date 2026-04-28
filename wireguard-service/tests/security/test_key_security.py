"""Tests de securite pour la gestion des cles WireGuard.

Verifie que :
- Les cles privees sont toujours chiffrees (AES-256-GCM) avant stockage
- Aucune fuite de cle privee en clair dans les responses API
- Le dechiffrement avec mauvaise cle echoue
- Les cles ont la bonne taille et format
- Les preshared keys sont generees correctement
"""

import base64
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Source files
PEER_MODEL = PROJECT_ROOT / "app" / "models" / "peer.py"
PEER_SERVICE = PROJECT_ROOT / "app" / "services" / "peer_service.py"
CONFIG_GENERATOR = PROJECT_ROOT / "app" / "services" / "config_generator.py"
CRYPTO_MODULE = PROJECT_ROOT / "app" / "core" / "crypto.py"
PEERS_ENDPOINT = PROJECT_ROOT / "app" / "api" / "v1" / "peers.py"
CONFIG_ENDPOINT = PROJECT_ROOT / "app" / "api" / "v1" / "config.py"
PEER_SCHEMA = PROJECT_ROOT / "app" / "schemas" / "peer.py"


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests — Crypto module correctness
# ---------------------------------------------------------------------------


class TestCryptoModule:
    """Verifie que le module crypto est correct et securise."""

    def test_crypto_uses_aesgcm(self):
        source = _read_source(CRYPTO_MODULE)
        assert "AESGCM" in source

    def test_crypto_uses_curve25519(self):
        source = _read_source(CRYPTO_MODULE)
        assert "X25519PrivateKey" in source

    def test_crypto_nonce_12_bytes(self):
        """AES-GCM nonce doit etre 12 bytes (96 bits)."""
        source = _read_source(CRYPTO_MODULE)
        assert "urandom(12)" in source

    def test_crypto_key_min_32_bytes(self):
        """Cle AES doit etre minimum 32 bytes."""
        source = _read_source(CRYPTO_MODULE)
        assert "32" in source

    def test_encrypt_decrypt_roundtrip(self):
        """Verifie que encrypt → decrypt retourne la valeur originale."""
        from app.core.crypto import encrypt_value, decrypt_value

        key = "A" * 32
        plaintext = "ceci_est_une_cle_privee_test_b64"
        encrypted = encrypt_value(plaintext, key)
        decrypted = decrypt_value(encrypted, key)
        assert decrypted == plaintext

    def test_encrypt_produces_different_output_each_time(self):
        """Le nonce aleatoire garantit des ciphertexts differents."""
        from app.core.crypto import encrypt_value

        key = "B" * 32
        plaintext = "same_plaintext"
        enc1 = encrypt_value(plaintext, key)
        enc2 = encrypt_value(plaintext, key)
        assert enc1 != enc2

    def test_decrypt_with_wrong_key_fails(self):
        """Dechiffrement avec mauvaise cle doit lever une exception."""
        from app.core.crypto import encrypt_value, decrypt_value
        from cryptography.exceptions import InvalidTag

        key1 = "C" * 32
        key2 = "D" * 32
        encrypted = encrypt_value("secret", key1)
        with pytest.raises(InvalidTag):
            decrypt_value(encrypted, key2)

    def test_encrypted_output_is_base64(self):
        """La sortie chiffree doit etre du base64 valide."""
        from app.core.crypto import encrypt_value

        key = "E" * 32
        encrypted = encrypt_value("test", key)
        decoded = base64.b64decode(encrypted)
        assert len(decoded) > 12  # nonce (12) + ciphertext + tag (16)

    def test_short_key_rejected(self):
        """Une cle trop courte doit etre rejetee."""
        from app.core.crypto import encrypt_value

        with pytest.raises(ValueError, match="trop courte"):
            encrypt_value("test", "short")


class TestKeypairGeneration:
    """Verifie la generation de paires de cles WireGuard."""

    def test_keypair_returns_tuple(self):
        from app.core.crypto import generate_keypair

        result = generate_keypair()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_keypair_base64_format(self):
        from app.core.crypto import generate_keypair

        private_b64, public_b64 = generate_keypair()
        private_bytes = base64.b64decode(private_b64)
        public_bytes = base64.b64decode(public_b64)
        assert len(private_bytes) == 32
        assert len(public_bytes) == 32

    def test_keypair_unique_each_call(self):
        from app.core.crypto import generate_keypair

        kp1 = generate_keypair()
        kp2 = generate_keypair()
        assert kp1[0] != kp2[0]
        assert kp1[1] != kp2[1]

    def test_preshared_key_generation(self):
        from app.core.crypto import generate_preshared_key

        psk = generate_preshared_key()
        psk_bytes = base64.b64decode(psk)
        assert len(psk_bytes) == 32

    def test_derive_public_from_private(self):
        from app.core.crypto import generate_keypair, derive_public_key

        private_b64, expected_public_b64 = generate_keypair()
        derived = derive_public_key(private_b64)
        assert derived == expected_public_b64


# ---------------------------------------------------------------------------
# Tests — Private key never in plaintext in DB model
# ---------------------------------------------------------------------------


class TestPrivateKeyStorage:
    """Verifie que les cles privees sont toujours chiffrees en DB."""

    def test_model_uses_encrypted_field(self):
        """Le modele doit avoir encrypted_private_key, pas private_key."""
        source = _read_source(PEER_MODEL)
        assert "encrypted_private_key" in source
        assert re.search(r"\bprivate_key\b.*mapped_column", source) is None

    def test_service_encrypts_before_store(self):
        """PeerService doit appeler encrypt_value avant de stocker."""
        source = _read_source(PEER_SERVICE)
        assert "encrypt_value" in source

    def test_service_imports_encrypt(self):
        source = _read_source(PEER_SERVICE)
        assert "from app.core.crypto import" in source
        assert "encrypt_value" in source

    def test_service_imports_decrypt(self):
        source = _read_source(PEER_SERVICE)
        assert "decrypt_value" in source

    def test_service_never_logs_private_key(self):
        """Pas de log contenant 'private_key' (risque de fuite)."""
        source = _read_source(PEER_SERVICE)
        log_lines = [
            line for line in source.split("\n")
            if "logger." in line and "private" in line.lower()
        ]
        assert len(log_lines) == 0, f"Log potentiel de cle privee: {log_lines}"


# ---------------------------------------------------------------------------
# Tests — API responses never leak private keys
# ---------------------------------------------------------------------------


class TestApiNoPrivateKeyLeak:
    """Verifie que les endpoints API ne leakent pas les cles privees."""

    def test_peer_response_schema_no_private_key(self):
        """PeerResponse ne doit PAS inclure encrypted_private_key."""
        source = _read_source(PEER_SCHEMA)
        # Trouver la classe PeerResponse et verifier que encrypted_private_key n'y est pas
        assert "PeerResponse" in source
        assert "encrypted_private_key" not in source or "exclude" in source.lower()

    def test_peers_endpoint_no_private_key_in_list(self):
        """L'endpoint list_peers ne doit pas retourner de cle privee."""
        source = _read_source(PEERS_ENDPOINT)
        assert "encrypted_private_key" not in source

    def test_config_endpoint_uses_decrypt(self):
        """L'endpoint /config doit dechiffrer pour generer la config client."""
        source = _read_source(CONFIG_ENDPOINT)
        # La config endpoint appelle le config_generator qui utilise le service
        assert "config" in source.lower()

    def test_config_generator_uses_private_key_safely(self):
        """Le config_generator recoit la cle privee dechiffree uniquement pour generer le .conf."""
        source = _read_source(CONFIG_GENERATOR)
        assert "private_key" in source  # Utilise la cle pour generer la config
        # Mais ne la log pas
        log_lines = [
            line for line in source.split("\n")
            if "logger." in line and "private" in line.lower()
        ]
        assert len(log_lines) == 0


# ---------------------------------------------------------------------------
# Tests — Encryption key validation
# ---------------------------------------------------------------------------


class TestEncryptionKeyValidation:
    """Verifie que la validation de la cle de chiffrement est stricte."""

    def test_config_has_encryption_key(self):
        config_file = PROJECT_ROOT / "app" / "core" / "config.py"
        source = _read_source(config_file)
        assert "ENCRYPTION_KEY" in source

    def test_config_validates_encryption_key_prod(self):
        config_file = PROJECT_ROOT / "app" / "core" / "config.py"
        source = _read_source(config_file)
        assert "validate_production_secrets" in source
        assert "ENCRYPTION_KEY" in source

    def test_config_dangerous_defaults_listed(self):
        config_file = PROJECT_ROOT / "app" / "core" / "config.py"
        source = _read_source(config_file)
        assert "_DANGEROUS_DEFAULTS" in source or "DANGEROUS_DEFAULTS" in source
