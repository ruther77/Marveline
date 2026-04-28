"""Service Wallet — generation et mise a jour des passes Apple/Google Wallet.

Responsabilites :
- Generation PKPass (Apple Wallet) signe
- Generation Google Wallet JWT (save URL)
- Mise a jour silencieuse des passes (APNs push / Google Wallet API)
- Enregistrement/desenregistrement des devices (callbacks Apple)
- Generation et verification des barcodes HMAC

Architecture :
- Apple : PKPass (ZIP signe) + APNs push → wallet fetch le pass mis a jour
- Google : JWT signe → URL save. Update via Google Wallet REST API directement.
"""

import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import time
import zipfile
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import settings
from app.models.loyalty import LoyaltyMember, WalletPass
from app.services.loyalty import generate_barcode

logger = logging.getLogger(__name__)

# ── Barcode ───────────────────────────────────────────────────────────────────
# generate_barcode() et verify_barcode() sont dans services/loyalty.py
# (importe ici pour usage dans la generation de pass)


# ── PKPass (Apple Wallet) ─────────────────────────────────────────────────────


class PKPassBuilder:
    """Construit un fichier .pkpass signe pour Apple Wallet.

    Structure du .pkpass (ZIP) :
        pass.json       — donnees du pass
        manifest.json   — checksums SHA1 de chaque fichier
        signature       — PKCS#7 signature du manifest
        icon.png, icon@2x.png, logo.png, strip.png — images
    """

    def __init__(
        self,
        pass_type_id: str,
        team_id: str,
        cert_path: str,
        key_path: str,
        wwdr_cert_path: str,
    ):
        self.pass_type_id = pass_type_id
        self.team_id = team_id
        self.cert_path = cert_path
        self.key_path = key_path
        self.wwdr_cert_path = wwdr_cert_path

    def build(
        self,
        member: LoyaltyMember,
        serial_number: str,
        auth_token: str,
        web_service_url: str,
        program_name: str,
        points_balance: int = 0,
        tier: str = "standard",
        next_reward_text: str = "",
        offer_text: str = "",
        referral_code: str = "",
        cumulative_ca_cents: int = 0,
        discount_percent: int = 0,
    ) -> bytes:
        """Genere le fichier .pkpass complet en bytes."""
        pass_json = self._build_pass_json(
            member=member,
            serial_number=serial_number,
            auth_token=auth_token,
            web_service_url=web_service_url,
            program_name=program_name,
            points_balance=points_balance,
            tier=tier,
            next_reward_text=next_reward_text,
            offer_text=offer_text,
            referral_code=referral_code,
            cumulative_ca_cents=cumulative_ca_cents,
            discount_percent=discount_percent,
        )

        pass_json_bytes = json.dumps(pass_json, ensure_ascii=False).encode("utf-8")

        # Construire le manifest (checksums SHA1)
        files = {"pass.json": pass_json_bytes}
        # Ajouter les images si elles existent
        for img_name in ["icon.png", "icon@2x.png", "logo.png", "strip.png"]:
            img_path = os.path.join(os.path.dirname(__file__), "..", "templates", "wallet", img_name)
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    files[img_name] = f.read()

        manifest = {}
        for name, data in files.items():
            manifest[name] = hashlib.sha1(data).hexdigest()

        manifest_bytes = json.dumps(manifest).encode("utf-8")
        files["manifest.json"] = manifest_bytes

        # Signer le manifest
        signature = self._sign_manifest(manifest_bytes)
        if signature:
            files["signature"] = signature

        # Construire le ZIP
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in files.items():
                zf.writestr(name, data)

        return buffer.getvalue()

    def _build_pass_json(
        self,
        member: LoyaltyMember,
        serial_number: str,
        auth_token: str,
        web_service_url: str,
        program_name: str,
        points_balance: int,
        tier: str,
        next_reward_text: str,
        offer_text: str,
        referral_code: str,
        cumulative_ca_cents: int,
        discount_percent: int,
    ) -> dict:
        """Construit le pass.json selon la spec Apple."""
        barcode_value = generate_barcode(member.id)

        # L'Incontournable (programme points)
        if points_balance > 0 or tier in ("standard", "vip"):
            return self._build_points_pass_json(
                member, serial_number, auth_token, web_service_url,
                program_name, points_balance, tier, next_reward_text,
                offer_text, referral_code, barcode_value,
            )
        # Marveline (programme CA)
        return self._build_revenue_pass_json(
            member, serial_number, auth_token, web_service_url,
            program_name, cumulative_ca_cents, discount_percent,
            tier, barcode_value,
        )

    def _build_points_pass_json(
        self, member, serial_number, auth_token, web_service_url,
        program_name, points_balance, tier, next_reward_text,
        offer_text, referral_code, barcode_value,
    ) -> dict:
        tier_display = "VIP" if tier == "vip" else "Membre"
        phone_masked = f"{member.phone[:3]} ** ** ** {member.phone[-2:]}" if len(member.phone) > 5 else member.phone

        return {
            "formatVersion": 1,
            "passTypeIdentifier": self.pass_type_id,
            "serialNumber": serial_number,
            "teamIdentifier": self.team_id,
            "webServiceURL": web_service_url,
            "authenticationToken": auth_token,
            "organizationName": program_name,
            "description": f"Carte de fidelite {program_name}",
            "backgroundColor": "rgb(30, 30, 30)",
            "foregroundColor": "rgb(255, 255, 255)",
            "labelColor": "rgb(212, 175, 55)",
            "storeCard": {
                "primaryFields": [{
                    "key": "points",
                    "label": "MES POINTS",
                    "value": str(points_balance),
                    "changeMessage": "+%@ points ajoutes !",
                }],
                "secondaryFields": [
                    {"key": "tier", "label": "STATUT", "value": tier_display},
                    {"key": "next_reward", "label": "PROCHAIN REWARD", "value": next_reward_text or "500 pts"},
                ],
                "auxiliaryFields": [
                    {"key": "offer", "label": "OFFRE DU MOMENT", "value": offer_text or ""},
                ],
                "backFields": [
                    {"key": "referral_code", "label": "Code parrain", "value": f"{referral_code} — Partagez et gagnez 200 pts"},
                    {"key": "member_since", "label": "Membre depuis", "value": member.created_at.strftime("%B %Y") if member.created_at else ""},
                    {"key": "phone", "label": "Telephone", "value": phone_masked},
                    {"key": "terms", "label": "Conditions", "value": "Points valables 12 mois. Bonus valables 6 mois."},
                ],
            },
            "barcode": {
                "message": barcode_value,
                "format": "PKBarcodeFormatCode128",
                "messageEncoding": "iso-8859-1",
                "altText": f"ID: {member.id}",
            },
            "barcodes": [{
                "message": barcode_value,
                "format": "PKBarcodeFormatCode128",
                "messageEncoding": "iso-8859-1",
                "altText": f"ID: {member.id}",
            }],
        }

    def _build_revenue_pass_json(
        self, member, serial_number, auth_token, web_service_url,
        program_name, cumulative_ca_cents, discount_percent,
        tier, barcode_value,
    ) -> dict:
        tier_labels = {"nouveau": "NOUVEAU", "habitue": "HABITUE", "privilegie": "PRIVILEGIE"}
        tier_display = tier_labels.get(tier, tier.upper())
        discount_display = f"-{discount_percent}%" if discount_percent > 0 else "Standard"
        ca_eur = cumulative_ca_cents / 100

        return {
            "formatVersion": 1,
            "passTypeIdentifier": self.pass_type_id,
            "serialNumber": serial_number,
            "teamIdentifier": self.team_id,
            "webServiceURL": web_service_url,
            "authenticationToken": auth_token,
            "organizationName": program_name,
            "description": f"Carte de fidelite {program_name}",
            "backgroundColor": "rgb(25, 25, 35)",
            "foregroundColor": "rgb(255, 255, 255)",
            "labelColor": "rgb(180, 140, 100)",
            "storeCard": {
                "primaryFields": [{
                    "key": "discount",
                    "label": "REMISE",
                    "value": discount_display,
                }],
                "secondaryFields": [
                    {"key": "tier", "label": "STATUT", "value": tier_display},
                    {"key": "cumulative_ca", "label": "CA CUMULE", "value": f"{ca_eur:.0f} EUR"},
                ],
                "auxiliaryFields": [
                    {"key": "next_tier", "label": "PROCHAIN PALIER", "value": self._next_tier_text(cumulative_ca_cents)},
                ],
                "backFields": [
                    {"key": "progress", "label": "Progression", "value": f"{ca_eur:.0f} EUR / 2 000 EUR"},
                    {"key": "member_since", "label": "Membre depuis", "value": member.created_at.strftime("%B %Y") if member.created_at else ""},
                    {"key": "terms", "label": "Conditions", "value": "CA cumule sur 24 mois glissants."},
                ],
            },
            "barcode": {
                "message": barcode_value,
                "format": "PKBarcodeFormatCode128",
                "messageEncoding": "iso-8859-1",
                "altText": f"ID: {member.id}",
            },
            "barcodes": [{
                "message": barcode_value,
                "format": "PKBarcodeFormatCode128",
                "messageEncoding": "iso-8859-1",
                "altText": f"ID: {member.id}",
            }],
        }

    def _next_tier_text(self, ca_cents: int) -> str:
        from app.constants.loyalty import TIER_HABITUE_THRESHOLD_CENTS, TIER_PRIVILEGIE_THRESHOLD_CENTS
        if ca_cents >= TIER_PRIVILEGIE_THRESHOLD_CENTS:
            return "Palier maximum atteint"
        if ca_cents >= TIER_HABITUE_THRESHOLD_CENTS:
            remaining = (TIER_PRIVILEGIE_THRESHOLD_CENTS - ca_cents) / 100
            return f"Encore {remaining:.0f} EUR pour -10%"
        remaining = (TIER_HABITUE_THRESHOLD_CENTS - ca_cents) / 100
        return f"Encore {remaining:.0f} EUR pour -5%"

    def _sign_manifest(self, manifest_bytes: bytes) -> Optional[bytes]:
        """Signe le manifest avec le certificat Apple (PKCS#7 detached).

        Necessite les fichiers de certificat configures.
        Retourne None si les certificats ne sont pas configures.
        """
        if not self.cert_path or not os.path.exists(self.cert_path):
            logger.warning("Apple Pass certificate not configured — pass will not be signed")
            return None

        try:
            from cryptography.hazmat.primitives.serialization import pkcs7, Encoding
            from cryptography.hazmat.primitives import hashes
            from cryptography.x509 import load_pem_x509_certificate
            from cryptography.hazmat.primitives.serialization import load_pem_private_key

            with open(self.cert_path, "rb") as f:
                cert = load_pem_x509_certificate(f.read())
            with open(self.key_path, "rb") as f:
                key = load_pem_private_key(f.read(), password=None)
            with open(self.wwdr_cert_path, "rb") as f:
                wwdr = load_pem_x509_certificate(f.read())

            signature = (
                pkcs7.PKCS7SignatureBuilder()
                .set_data(manifest_bytes)
                .add_signer(cert, key, hashes.SHA256())
                .add_certificate(wwdr)
                .sign(Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])
            )
            return signature

        except ImportError:
            logger.warning("cryptography PKCS7 not available — pass will not be signed")
            return None
        except Exception:
            logger.exception("Failed to sign PKPass manifest")
            return None


# ── Google Wallet ─────────────────────────────────────────────────────────────


class GoogleWalletBuilder:
    """Genere les objets Google Wallet via l'API REST.

    Flow :
    1. Creer un LoyaltyClass (une fois, au setup du programme)
    2. Creer un LoyaltyObject par membre
    3. Generer un JWT save URL pour l'ajout au wallet
    4. Update l'objet directement via API pour les mises a jour
    """

    def __init__(self, issuer_id: str, service_account_json_path: str, class_suffix: str):
        self.issuer_id = issuer_id
        self.service_account_path = service_account_json_path
        self.class_suffix = class_suffix
        self._credentials = None

    def _get_class_id(self, program_name: str) -> str:
        clean = program_name.lower().replace(" ", "_").replace("'", "")
        return f"{self.issuer_id}.{clean}_{self.class_suffix}"

    def _get_object_id(self, member_id: int) -> str:
        return f"{self.issuer_id}.loyalty_member_{member_id}"

    def build_save_url(
        self,
        member: LoyaltyMember,
        program_name: str,
        points_balance: int = 0,
        tier: str = "standard",
        cumulative_ca_cents: int = 0,
        discount_percent: int = 0,
    ) -> Optional[str]:
        """Genere l'URL save pour Google Wallet.

        Retourne None si Google Wallet n'est pas configure.
        """
        if not self.issuer_id or not self.service_account_path:
            logger.warning("Google Wallet not configured")
            return None

        try:
            import jwt as pyjwt

            # Charger le service account
            if not os.path.exists(self.service_account_path):
                logger.warning("Google Wallet service account file not found: %s", self.service_account_path)
                return None

            with open(self.service_account_path) as f:
                sa = json.load(f)

            barcode_value = generate_barcode(member.id)

            loyalty_object = {
                "id": self._get_object_id(member.id),
                "classId": self._get_class_id(program_name),
                "state": "ACTIVE",
                "accountId": str(member.id),
                "accountName": f"{member.first_name} {member.last_name}",
                "barcode": {
                    "type": "CODE_128",
                    "value": barcode_value,
                    "alternateText": f"ID: {member.id}",
                },
                "loyaltyPoints": {
                    "balance": {
                        "int": points_balance,
                    },
                    "label": "Points",
                },
            }

            # Pour Marveline (location) on utilise les secondary fields
            if discount_percent > 0:
                loyalty_object["loyaltyPoints"] = {
                    "balance": {"string": f"-{discount_percent}%"},
                    "label": "Remise",
                }

            # Construire le JWT
            claims = {
                "iss": sa["client_email"],
                "aud": "google",
                "origins": [],
                "typ": "savetowallet",
                "payload": {
                    "loyaltyObjects": [loyalty_object],
                },
            }

            token = pyjwt.encode(
                claims,
                sa["private_key"],
                algorithm="RS256",
            )

            return f"https://pay.google.com/gp/v/save/{token}"

        except Exception:
            logger.exception("Failed to build Google Wallet save URL")
            return None

    async def update_object(
        self,
        member: LoyaltyMember,
        program_name: str,
        points_balance: int = 0,
        tier: str = "standard",
        cumulative_ca_cents: int = 0,
        discount_percent: int = 0,
    ) -> bool:
        """Met a jour l'objet loyalty dans Google Wallet via l'API REST.

        Retourne True si la mise a jour a reussi.
        """
        if not self.issuer_id or not self.service_account_path:
            return False

        try:
            access_token = await self._get_access_token()
            if not access_token:
                return False

            object_id = self._get_object_id(member.id)
            barcode_value = generate_barcode(member.id)

            patch_body = {
                "loyaltyPoints": {
                    "balance": {"int": points_balance},
                    "label": "Points",
                },
                "barcode": {
                    "type": "CODE_128",
                    "value": barcode_value,
                },
            }

            if discount_percent > 0:
                patch_body["loyaltyPoints"] = {
                    "balance": {"string": f"-{discount_percent}%"},
                    "label": "Remise",
                }

            async with httpx.AsyncClient() as client:
                resp = await client.patch(
                    f"https://walletobjects.googleapis.com/walletobjects/v1/loyaltyObject/{object_id}",
                    json=patch_body,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )

            if resp.status_code in (200, 204):
                return True

            logger.warning("Google Wallet update failed: %d %s", resp.status_code, resp.text[:200])
            return False

        except Exception:
            logger.exception("Failed to update Google Wallet object")
            return False

    async def _get_access_token(self) -> Optional[str]:
        """Obtient un access token Google via le service account."""
        try:
            import jwt as pyjwt

            if not os.path.exists(self.service_account_path):
                return None

            with open(self.service_account_path) as f:
                sa = json.load(f)

            now = int(time.time())
            claims = {
                "iss": sa["client_email"],
                "scope": "https://www.googleapis.com/auth/wallet_object.issuer",
                "aud": "https://oauth2.googleapis.com/token",
                "iat": now,
                "exp": now + 3600,
            }
            assertion = pyjwt.encode(claims, sa["private_key"], algorithm="RS256")

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": assertion,
                    },
                    timeout=10,
                )

            if resp.status_code == 200:
                return resp.json()["access_token"]

            logger.warning("Failed to get Google access token: %d", resp.status_code)
            return None

        except Exception:
            logger.exception("Failed to get Google access token")
            return None


# ── APNs Push (Apple) ─────────────────────────────────────────────────────────


class APNsPushService:
    """Envoie des push silencieux via APNs pour mettre a jour les passes Apple Wallet.

    Flow :
    1. Push vide vers le device token du pass
    2. Apple Wallet re-fetch le pass via webServiceURL
    3. Le serveur repond avec le pass mis a jour
    """

    def __init__(self, key_path: str, key_id: str, team_id: str, use_sandbox: bool = True):
        self.key_path = key_path
        self.key_id = key_id
        self.team_id = team_id
        self.host = "api.sandbox.push.apple.com" if use_sandbox else "api.push.apple.com"

    async def send_update(self, push_token: str, pass_type_id: str) -> bool:
        """Envoie une notification push silencieuse pour declencher le re-fetch du pass."""
        if not self.key_path or not os.path.exists(self.key_path):
            logger.warning("APNs key not configured")
            return False

        try:
            import jwt as pyjwt

            with open(self.key_path, "rb") as f:
                key_data = f.read()

            now = int(time.time())
            token = pyjwt.encode(
                {"iss": self.team_id, "iat": now},
                key_data,
                algorithm="ES256",
                headers={"kid": self.key_id},
            )

            async with httpx.AsyncClient(http2=True) as client:
                resp = await client.post(
                    f"https://{self.host}/3/device/{push_token}",
                    json={},
                    headers={
                        "Authorization": f"bearer {token}",
                        "apns-topic": pass_type_id,
                        "apns-push-type": "background",
                        "apns-priority": "5",
                    },
                    timeout=10,
                )

            if resp.status_code == 200:
                return True

            logger.warning("APNs push failed: %d %s", resp.status_code, resp.text[:200])
            return False

        except Exception:
            logger.exception("Failed to send APNs push")
            return False


# ── WalletService (facade) ────────────────────────────────────────────────────


class WalletService:
    """Facade qui coordonne PKPass, Google Wallet et APNs.

    Usage :
        wallet_svc = WalletService()
        pkpass_bytes = wallet_svc.generate_apple_pass(member, program_name, ...)
        save_url = wallet_svc.generate_google_save_url(member, program_name, ...)
        await wallet_svc.notify_pass_update(member_id, db)
    """

    def __init__(self):
        self.pkpass_builder = PKPassBuilder(
            pass_type_id=settings.APPLE_PASS_TYPE_ID,
            team_id=settings.APPLE_TEAM_ID,
            cert_path=settings.APPLE_PASS_CERT_PATH,
            key_path=settings.APPLE_PASS_KEY_PATH,
            wwdr_cert_path=settings.APPLE_WWDR_CERT_PATH,
        )
        self.google_builder = GoogleWalletBuilder(
            issuer_id=settings.GOOGLE_WALLET_ISSUER_ID,
            service_account_json_path=settings.GOOGLE_WALLET_SERVICE_ACCOUNT_JSON,
            class_suffix=settings.GOOGLE_WALLET_CLASS_SUFFIX,
        )
        self.apns = APNsPushService(
            key_path=settings.APNS_KEY_PATH,
            key_id=settings.APNS_KEY_ID,
            team_id=settings.APPLE_TEAM_ID,
            use_sandbox=settings.APNS_USE_SANDBOX,
        )

    def generate_serial_number(self, member_id: int) -> str:
        """Genere un serial number unique pour un pass."""
        return f"loyalty-{member_id}-{secrets.token_hex(8)}"

    def generate_auth_token(self) -> str:
        """Genere un token d'authentification pour les callbacks wallet."""
        return secrets.token_urlsafe(32)

    def generate_apple_pass(
        self,
        member: LoyaltyMember,
        serial_number: str,
        auth_token: str,
        web_service_url: str,
        program_name: str,
        points_balance: int = 0,
        tier: str = "standard",
        next_reward_text: str = "",
        offer_text: str = "",
        referral_code: str = "",
        cumulative_ca_cents: int = 0,
        discount_percent: int = 0,
    ) -> bytes:
        """Genere un PKPass signe."""
        return self.pkpass_builder.build(
            member=member,
            serial_number=serial_number,
            auth_token=auth_token,
            web_service_url=web_service_url,
            program_name=program_name,
            points_balance=points_balance,
            tier=tier,
            next_reward_text=next_reward_text,
            offer_text=offer_text,
            referral_code=referral_code,
            cumulative_ca_cents=cumulative_ca_cents,
            discount_percent=discount_percent,
        )

    def generate_google_save_url(
        self,
        member: LoyaltyMember,
        program_name: str,
        points_balance: int = 0,
        tier: str = "standard",
        cumulative_ca_cents: int = 0,
        discount_percent: int = 0,
    ) -> Optional[str]:
        """Genere l'URL save pour Google Wallet."""
        return self.google_builder.build_save_url(
            member=member,
            program_name=program_name,
            points_balance=points_balance,
            tier=tier,
            cumulative_ca_cents=cumulative_ca_cents,
            discount_percent=discount_percent,
        )

    async def notify_pass_update(
        self,
        wallet_passes: list[WalletPass],
        program_name: str,
        member: LoyaltyMember,
        points_balance: int = 0,
        tier: str = "standard",
        cumulative_ca_cents: int = 0,
        discount_percent: int = 0,
    ) -> int:
        """Notifie tous les devices d'un membre que le pass a ete mis a jour.

        Apple : push silencieux → le wallet re-fetch le pass
        Google : update direct via API REST

        Retourne le nombre de devices notifies avec succes.
        """
        success = 0

        for wp in wallet_passes:
            if wp.platform == "apple" and wp.push_token:
                ok = await self.apns.send_update(wp.push_token, settings.APPLE_PASS_TYPE_ID)
                if ok:
                    success += 1
                    wp.last_updated_at = datetime.now(timezone.utc)

            elif wp.platform == "google":
                ok = await self.google_builder.update_object(
                    member=member,
                    program_name=program_name,
                    points_balance=points_balance,
                    tier=tier,
                    cumulative_ca_cents=cumulative_ca_cents,
                    discount_percent=discount_percent,
                )
                if ok:
                    success += 1
                    wp.last_updated_at = datetime.now(timezone.utc)

        return success
