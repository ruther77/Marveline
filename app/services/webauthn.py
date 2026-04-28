"""Service WebAuthn/FIDO2 — registration + authentication (M-03).

Utilise py_webauthn pour la verification cryptographique.
Les challenges sont stockes dans Redis-SEC avec TTL 5 min.

S1.T11 (F368/WEBAUTHN-RPID-MULTITENANT-01) : RP_ID/expected_origin per-tenant
via `tenant.rp_id` et `tenant.frontend_url`. Fallback settings.* si NULL.
"""
import base64
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import redis_sec
from app.models.tenant import Tenant
from app.models.webauthn_credential import WebAuthnCredential

logger = logging.getLogger(__name__)

CHALLENGE_TTL_SECONDS = 300  # 5 min


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


class WebAuthnService:
    """Service pour les ceremonies WebAuthn (register + authenticate).

    S1.T11 — Le service est instancie avec le `tenant` courant pour resoudre
    `rp_id` et `expected_origin` per-tenant (F368 WebAuthn multi-tenant).
    Si `tenant` est None (cas legacy/tests), fallback sur les settings globaux.
    """

    def __init__(self, db: AsyncSession, tenant: Optional[Tenant] = None):
        self.db = db
        self.tenant = tenant
        # F368 (S1.T11) — RP_ID + origin + name per-tenant, fallback settings.*
        self.rp_id = (
            tenant.rp_id
            if tenant is not None and tenant.rp_id
            else settings.JWT_ISSUER.replace("www.", "")
        )
        self.rp_name = (
            tenant.name
            if tenant is not None and tenant.name
            else settings.APP_NAME
        )
        self.expected_origin = (
            tenant.frontend_url
            if tenant is not None and tenant.frontend_url
            else settings.FRONTEND_URL
        )

    async def generate_registration_options(
        self, account_id: int, email: str, device_name: str = "Security Key"
    ) -> dict:
        """Genere les options pour le ceremony d'enregistrement.

        Stocke le challenge dans Redis-SEC (TTL 5 min).
        """
        challenge = secrets.token_bytes(32)
        challenge_b64 = _b64url_encode(challenge)

        # Recuperer les credentials existants pour exclure
        existing = await self._list_credentials(account_id)
        exclude = [
            {"type": "public-key", "id": _b64url_encode(c.credential_id)}
            for c in existing
        ]

        # Stocker challenge dans Redis
        key = f"webauthn:register:{account_id}"
        await redis_sec.client.setex(key, CHALLENGE_TTL_SECONDS, challenge_b64)

        return {
            "challenge": challenge_b64,
            "rp": {"id": self.rp_id, "name": self.rp_name},
            "user": {
                "id": _b64url_encode(str(account_id).encode()),
                "name": email,
                "displayName": email.split("@")[0],
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},   # ES256
                {"type": "public-key", "alg": -257},  # RS256
            ],
            "timeout": 60000,
            "attestation": "none",
            "excludeCredentials": exclude,
            "authenticatorSelection": {
                "authenticatorAttachment": "cross-platform",
                "residentKey": "preferred",
                "userVerification": "preferred",
            },
        }

    async def verify_registration(
        self,
        account_id: int,
        credential_id_b64: str,
        client_data_json_b64: str,
        attestation_object_b64: str,
        device_name: str = "Security Key",
    ) -> WebAuthnCredential:
        """Verifie l'attestation et enregistre le credential.

        Raises:
            HTTPException 400: Si verification echoue.
        """
        try:
            from webauthn import verify_registration_response
            from webauthn.helpers.structs import RegistrationCredential
        except ImportError:
            raise HTTPException(500, detail="py_webauthn not installed")

        # Recuperer et consommer le challenge
        key = f"webauthn:register:{account_id}"
        challenge_b64 = await redis_sec.client.getdel(key)
        if not challenge_b64:
            raise HTTPException(400, detail="Challenge expire ou invalide")
        challenge_b64 = challenge_b64.decode() if isinstance(challenge_b64, bytes) else challenge_b64

        credential_id = _b64url_decode(credential_id_b64)

        try:
            verification = verify_registration_response(
                credential=RegistrationCredential(
                    id=credential_id_b64,
                    raw_id=credential_id,
                    response={
                        "client_data_json": _b64url_decode(client_data_json_b64),
                        "attestation_object": _b64url_decode(attestation_object_b64),
                    },
                    type="public-key",
                ),
                expected_challenge=_b64url_decode(challenge_b64),
                expected_rp_id=self.rp_id,
                expected_origin=self.expected_origin,
            )
        except Exception as e:
            logger.warning("WebAuthn registration verification failed: %s", e)
            raise HTTPException(400, detail="Verification du credential echouee")

        # Stocker le credential
        cred = WebAuthnCredential(
            account_id=account_id,
            credential_id=verification.credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            device_name=device_name,
            aaguid=str(verification.aaguid) if verification.aaguid else None,
        )
        self.db.add(cred)
        await self.db.flush()
        await self.db.refresh(cred)

        logger.info("WebAuthn credential registered: account=%d device=%s", account_id, device_name)
        return cred

    async def generate_authentication_options(self, account_id: int) -> dict:
        """Genere les options pour le ceremony d'authentification."""
        credentials = await self._list_credentials(account_id)
        if not credentials:
            raise HTTPException(400, detail="Aucun credential WebAuthn enregistre")

        challenge = secrets.token_bytes(32)
        challenge_b64 = _b64url_encode(challenge)

        key = f"webauthn:auth:{account_id}"
        await redis_sec.client.setex(key, CHALLENGE_TTL_SECONDS, challenge_b64)

        return {
            "challenge": challenge_b64,
            "rpId": self.rp_id,
            "timeout": 60000,
            "userVerification": "preferred",
            "allowCredentials": [
                {
                    "type": "public-key",
                    "id": _b64url_encode(c.credential_id),
                }
                for c in credentials
            ],
        }

    async def verify_authentication(
        self,
        account_id: int,
        credential_id_b64: str,
        client_data_json_b64: str,
        authenticator_data_b64: str,
        signature_b64: str,
    ) -> bool:
        """Verifie l'assertion et met a jour le sign_count.

        Raises:
            HTTPException 400/401: Si verification echoue.
        """
        try:
            from webauthn import verify_authentication_response
            from webauthn.helpers.structs import AuthenticationCredential
        except ImportError:
            raise HTTPException(500, detail="py_webauthn not installed")

        key = f"webauthn:auth:{account_id}"
        challenge_b64 = await redis_sec.client.getdel(key)
        if not challenge_b64:
            raise HTTPException(400, detail="Challenge expire ou invalide")
        challenge_b64 = challenge_b64.decode() if isinstance(challenge_b64, bytes) else challenge_b64

        credential_id = _b64url_decode(credential_id_b64)
        cred = await self._get_credential_by_id(credential_id)
        if not cred or cred.account_id != account_id:
            raise HTTPException(401, detail="Credential inconnu")

        try:
            verification = verify_authentication_response(
                credential=AuthenticationCredential(
                    id=credential_id_b64,
                    raw_id=credential_id,
                    response={
                        "client_data_json": _b64url_decode(client_data_json_b64),
                        "authenticator_data": _b64url_decode(authenticator_data_b64),
                        "signature": _b64url_decode(signature_b64),
                    },
                    type="public-key",
                ),
                expected_challenge=_b64url_decode(challenge_b64),
                expected_rp_id=self.rp_id,
                expected_origin=self.expected_origin,
                credential_public_key=cred.public_key,
                credential_current_sign_count=cred.sign_count,
            )
        except Exception as e:
            logger.warning("WebAuthn auth verification failed: %s", e)
            raise HTTPException(401, detail="Verification WebAuthn echouee")

        # Mettre a jour sign_count (anti-clonage)
        cred.sign_count = verification.new_sign_count
        cred.last_used_at = datetime.now(timezone.utc)
        await self.db.flush()

        return True

    async def list_credentials(self, account_id: int) -> list[dict]:
        """Liste les credentials enregistres pour un compte."""
        creds = await self._list_credentials(account_id)
        return [
            {
                "id": c.id,
                "device_name": c.device_name,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
                "aaguid": c.aaguid,
            }
            for c in creds
        ]

    async def delete_credential(self, account_id: int, credential_db_id: int) -> bool:
        """Supprime un credential WebAuthn."""
        result = await self.db.execute(
            select(WebAuthnCredential).filter(
                WebAuthnCredential.id == credential_db_id,
                WebAuthnCredential.account_id == account_id,
            )
        )
        cred = result.scalar_one_or_none()
        if not cred:
            raise HTTPException(404, detail="Credential introuvable")
        await self.db.delete(cred)
        await self.db.flush()
        logger.info("WebAuthn credential deleted: id=%d account=%d", credential_db_id, account_id)
        return True

    async def _list_credentials(self, account_id: int) -> list[WebAuthnCredential]:
        result = await self.db.execute(
            select(WebAuthnCredential)
            .filter(WebAuthnCredential.account_id == account_id)
            .order_by(WebAuthnCredential.created_at)
        )
        return list(result.scalars().all())

    async def _get_credential_by_id(self, credential_id: bytes) -> WebAuthnCredential | None:
        result = await self.db.execute(
            select(WebAuthnCredential).filter(WebAuthnCredential.credential_id == credential_id)
        )
        return result.scalar_one_or_none()
