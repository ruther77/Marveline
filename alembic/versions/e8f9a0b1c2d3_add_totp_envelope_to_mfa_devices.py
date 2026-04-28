"""add totp envelope encryption columns to mfa_devices.

Revision ID: e8f9a0b1c2d3
Revises: a3b4c5d6e7f8, bddb5278ef23, f1a2b3c4d5e6
Create Date: 2026-03-01

NC-07 — Spec §05-MFA-TOTP §5.4 : envelope encryption DEK/KEK.

Stratégie expand/contract :
    Étape 1 (ce plan) : Expand — ajouter 3 colonnes NULLABLE + re-chiffrer données existantes.
    Étape 2 (session future) : Contract — supprimer colonnes si totp_secret_nonce IS NOT NULL pour toutes les rows.

Data migration :
    Les rows v1 ont totp_secret_nonce IS NULL.
    Discriminant : nonce absent → v1 (nonce||ciphertext dans encrypted_secret).
    Re-chiffrement : décrypter v1 → encrypter v2 → mettre à jour les 4 colonnes.
"""
import hashlib
import hmac
import os

import sqlalchemy as sa
from alembic import op
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


revision = "e8f9a0b1c2d3"
down_revision = ("a3b4c5d6e7f8", "bddb5278ef23", "f1a2b3c4d5e6")
branch_labels = None
depends_on = None


# ---- Fonctions cryptographiques inline (pas d'import circulaire en migration) ----

def _v1_derive_key(encryption_key: str) -> bytes:
    """Dérive la clé v1 depuis ENCRYPTION_KEY."""
    return hashlib.sha256(encryption_key.encode("utf-8")).digest()


def _v1_decrypt(blob: bytes, key: bytes) -> str:
    """Déchiffre un blob v1 (nonce_12b || ciphertext || tag)."""
    if len(blob) < 28:
        raise ValueError(f"Blob v1 trop court : {len(blob)} bytes")
    nonce = blob[:12]
    ct = blob[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")


def _v2_get_kek(master_key: str) -> bytes:
    """Dérive le KEK dev depuis TOTP_DEV_MASTER_KEY."""
    return hmac.new(master_key.encode("utf-8"), b"totp-kek-v1", hashlib.sha256).digest()


def _v2_encrypt_dek(dek: bytes, kek: bytes) -> bytes:
    """Chiffre le DEK. Retourne nonce_12b + ct_dek_tag."""
    nonce = os.urandom(12)
    return nonce + AESGCM(kek).encrypt(nonce, dek, None)


def _v2_encrypt(plaintext: str, kek: bytes) -> tuple[bytes, bytes, bytes]:
    """Chiffre un secret en v2. Retourne (ciphertext, nonce, encrypted_dek)."""
    dek = os.urandom(32)
    nonce = os.urandom(12)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext.encode("utf-8"), None)
    encrypted_dek = _v2_encrypt_dek(dek, kek)
    return ciphertext, nonce, encrypted_dek


def _migrate_existing_totp_secrets(bind: sa.engine.Connection) -> int:
    """Re-chiffre les rows v1 (totp_secret_nonce IS NULL) vers v2.

    Returns:
        Nombre de rows migrées.
    """
    # Lecture des clés depuis les variables d'environnement (pas de settings import)
    encryption_key = os.environ.get("ENCRYPTION_KEY", "dev_encryption_key_32bytes_CHANGE")
    totp_master_key = os.environ.get(
        "TOTP_DEV_MASTER_KEY", "dev_totp_master_key_CHANGER_EN_PROD_32ch"
    )

    v1_key = _v1_derive_key(encryption_key)
    kek = _v2_get_kek(totp_master_key)

    rows = bind.execute(
        sa.text(
            "SELECT id, encrypted_secret FROM mfa_devices WHERE totp_secret_nonce IS NULL"
        )
    ).fetchall()

    count = 0
    for row in rows:
        device_id = row[0]
        blob_v1 = bytes(row[1])

        try:
            plaintext = _v1_decrypt(blob_v1, v1_key)
        except Exception as exc:
            raise RuntimeError(
                f"Échec déchiffrement v1 pour mfa_device id={device_id}: {exc}"
            ) from exc

        ct, nonce, enc_dek = _v2_encrypt(plaintext, kek)

        bind.execute(
            sa.text(
                "UPDATE mfa_devices "
                "SET encrypted_secret = :ct, "
                "    totp_secret_nonce = :nonce, "
                "    totp_encrypted_dek = :enc_dek, "
                "    totp_key_version = 'dev-v1' "
                "WHERE id = :device_id"
            ),
            {"ct": ct, "nonce": nonce, "enc_dek": enc_dek, "device_id": device_id},
        )
        count += 1

    return count


def upgrade() -> None:
    # Étape 1 : Expand — ajouter 3 colonnes NULLABLE
    op.add_column(
        "mfa_devices",
        sa.Column(
            "totp_secret_nonce",
            sa.LargeBinary(12),
            nullable=True,
            comment="GCM nonce 12 bytes (envelope encryption v2)",
        ),
    )
    op.add_column(
        "mfa_devices",
        sa.Column(
            "totp_encrypted_dek",
            sa.LargeBinary(),
            nullable=True,
            comment="DEK chiffré par KEK — nonce_12b + ct_dek_tag",
        ),
    )
    op.add_column(
        "mfa_devices",
        sa.Column(
            "totp_key_version",
            sa.String(64),
            nullable=True,
            comment="Version clé KMS ('dev-v1' ou ARN AWS KMS version)",
        ),
    )

    # Étape 2 : Data migration — re-chiffrement v1 → v2
    bind = op.get_bind()
    migrated = _migrate_existing_totp_secrets(bind)
    if migrated > 0:
        print(f"[migration] {migrated} MFA device(s) re-chiffrés v1→v2")


def downgrade() -> None:
    op.drop_column("mfa_devices", "totp_key_version")
    op.drop_column("mfa_devices", "totp_encrypted_dek")
    op.drop_column("mfa_devices", "totp_secret_nonce")
